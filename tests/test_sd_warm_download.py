"""Offline tests for one connection and independently accepted tail/full reads."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from test_sd_nor_probe import attach_actions, info, receipt

from rcominote.experiments import sd_warm_download as W


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    image = bytes(range(256)) * 3623 + bytes(range(144))
    assert len(image) == 927632
    monkeypatch.setattr(W, "IMAGE_SHA", W.sha(image))
    monkeypatch.setattr(W, "ORACLE_SHA", W.sha(image[0xDD500:0xDE500]))
    path = tmp_path / "image.bin"
    path.write_bytes(image)
    parent = tmp_path / "parent"
    parent.mkdir()
    report = attach_actions(receipt(W.NAME, 0x18000000, W.SIZE))
    report.update(source_image_sha256=W.IMAGE_SHA, expected_sha256=W.ORACLE_SHA, ok=False)
    raw = json.dumps(report).encode()
    (parent / "report.json").write_bytes(raw)
    monkeypatch.setattr(W, "PARENT_SHA", W.sha(raw))
    return path, parent, image[0xDD500:0xDE500]


def test_failed_full_parent_with_complete_actions_is_accepted(inputs):
    image, parent, oracle = inputs
    actual, evidence = W.validate_inputs(image, parent)
    assert actual == oracle
    assert evidence["actions_verified"] is True


@pytest.mark.parametrize("change", ["name", "command", "image", "actions", "identity", "parent_sha"])
def test_input_gates_prevent_connection(inputs, tmp_path, monkeypatch, change):
    image, parent, _ = inputs
    path = parent / "report.json"
    report = json.loads(path.read_bytes())
    if change == "name":
        report["name"] = "rc0123456789"
    elif change == "command":
        report["dump_command"] = W.COMMAND.replace("402653184", "402653185")
    elif change == "image":
        image.write_bytes(b"wrong")
    elif change == "actions":
        report["att_packets"] = report["att_packets"][:-1]
    elif change == "identity":
        report["after"]["serial"] = "wrong"
    path.write_text(json.dumps(report) + "\n")
    if change != "parent_sha":
        monkeypatch.setattr(W, "PARENT_SHA", W.sha(path.read_bytes()))
    with patch.object(W, "find_device", AsyncMock()) as find:
        with pytest.raises((ValueError, RuntimeError)):
            W.main(image, parent, tmp_path / "out")
        find.assert_not_awaited()
    assert not (tmp_path / "out").exists()


def test_existing_output_prevents_device_access(inputs, tmp_path):
    image, parent, _ = inputs
    out = tmp_path / "out"
    out.mkdir()
    with patch.object(W, "find_device", AsyncMock()) as find:
        with pytest.raises(FileExistsError):
            W.main(image, parent, out)
        find.assert_not_awaited()


@pytest.mark.parametrize(
    "fault", [None, "tail_short", "tail_corrupt", "barrier", "full_short", "full_corrupt", "overrun", "after"]
)
def test_unique_connection_order_oracles_and_failure_stop(tmp_path, fault):
    oracle = bytes(range(256)) * 16
    conn = AsyncMock()
    conn.__aenter__.return_value = conn
    events = []
    reads = 0

    async def identity(connection, serial):
        nonlocal reads
        assert connection is conn and serial == W.OWNED_SERIAL
        reads += 1
        events.append("info")
        if fault == "barrier" and reads == 2:
            return info(1)
        if fault in ("after", "full_short") and reads == 3:
            raise OSError("postcheck unavailable")
        return info()

    async def download(name, sink, *, offset):
        assert name == W.NAME
        events.append(offset)
        data = oracle[offset:]
        if fault == "tail_short" and offset:
            sink(data[:64])
            raise RuntimeError("Short tail")
        if fault == "full_short" and not offset:
            sink(data[:-244])
            raise RuntimeError("Short full")
        if (fault == "tail_corrupt" and offset) or (fault == "full_corrupt" and not offset):
            data = bytes([data[0] ^ 1]) + data[1:]
        sink(data)
        if fault == "overrun" and not offset:
            sink(b"extra")
        return len(data)

    conn.download.side_effect = download
    report = {}
    with (
        patch.object(W, "find_device", AsyncMock(return_value=object())) as find,
        patch.object(W, "Connection", return_value=conn) as factory,
        patch.object(W, "read_info", side_effect=identity),
    ):
        if fault:
            with pytest.raises((ValueError, RuntimeError, OSError)) as raised:
                asyncio.run(W.capture(report, oracle, tmp_path))
            if fault == "full_short":
                assert str(raised.value) == "Short full"
                assert report["after_error"] == "OSError: postcheck unavailable"
        else:
            asyncio.run(W.capture(report, oracle, tmp_path))
        find.assert_awaited_once()
        factory.assert_called_once()
        conn.__aenter__.assert_awaited_once()
        conn.__aexit__.assert_awaited_once()
    if fault in ("tail_short", "tail_corrupt"):
        assert events == ["info", 3968, "info"]
        assert not (tmp_path / "full.bin").exists()
    elif fault == "barrier":
        assert events == ["info", 3968, "info", "info"]
        assert not (tmp_path / "full.bin").exists()
    else:
        assert events == ["info", 3968, "info", 0, "info"]
        saved = (tmp_path / "full.bin").read_bytes()
        assert len(saved) == (3852 if fault == "full_short" else 4096)
        if fault not in ("full_short", "full_corrupt", "overrun"):
            assert report["full"]["exact_match"] is True
        else:
            assert not report["full"].get("exact_match")
    if fault is None:
        assert report["tail"]["exact_match"] is True
        assert report["state_verification"]["allowed_decrease"] == 0


def test_main_persists_failure_receipt_and_never_claims_success(inputs, tmp_path):
    image, parent, _ = inputs
    out = tmp_path / "out"
    with (
        patch.object(W, "capture", AsyncMock(side_effect=RuntimeError("deliberate failure"))),
        pytest.raises(RuntimeError, match="deliberate failure"),
    ):
        W.main(image, parent, out)
    report = json.loads((out / "report.json").read_text())
    assert report["ok"] is False
    assert report["sd_write_attempted"] is False
    assert report["error"] == "RuntimeError: deliberate failure"
