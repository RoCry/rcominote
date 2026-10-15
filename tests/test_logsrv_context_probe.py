"""Offline fixed-address/context gates; all live transport calls are replaced."""

import asyncio
import copy
import gzip
import json
import shutil
import struct
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from test_sd_nor_probe import attach_actions, info, receipt, save

from rcominote.experiments import logsrv_context_probe as probe


@pytest.fixture
def guarded(tmp_path):
    image = gzip.decompress(
        Path("docs/evidence/minimal-image-2026-10-13/original-system.bin.gz").read_bytes()
    )
    image_path = tmp_path / "image.bin"
    image_path.write_bytes(image)
    directories = []
    for i, (address, size) in enumerate(probe.GUARDS.items()):
        report = attach_actions(receipt(f"rc{i:010x}", address, size))
        data = image[address - 0x10000000 : address - 0x10000000 + size]
        report["expected_sha256"] = probe.sha(data)
        directories.append(save(tmp_path / f"guard{i}", report, data))
    return image_path, directories


def snapshot(name, phase, *, address=probe.GLOBAL):
    report = receipt(name, address, 4 if phase == probe.Phase.pointer else 32, phase=phase)
    report.update(ok=False, sd_write_attempted=False)
    return report


@pytest.mark.parametrize(
    "value", [0, probe.RAM_START - 4, probe.RAM_START + 1, probe.RAM_END - 76, 0x40000000]
)
def test_pointer_rejects_null_unaligned_and_whole_object_outside_ram(value):
    with pytest.raises(ValueError, match="RAM/object80"):
        probe.pointer(value.to_bytes(4, "little"))


def test_pointer_accepts_only_complete_aligned_object_at_bounds():
    for value in (probe.RAM_START, probe.RAM_END - 80):
        assert probe.pointer(value.to_bytes(4, "little")) == value
    with pytest.raises(ValueError, match="exactly4"):
        probe.pointer(b"\0" * 3)


def test_context_decodes_counters_without_treating_them_as_three_bit_indices():
    data = bytearray(32)
    data[:9] = struct.pack("<I5B", 0x18008000, 3, 0, 0, 254, 255)
    struct.pack_into("<8H", data, 10, 0, 504, 1, 2, 3, 4, 5, 6)
    struct.pack_into("<I", data, 28, 17)
    fields = probe.context_fields(bytes(data))
    assert (fields["rd"], fields["wr"], fields["drop_count"]) == (254, 255, 17)
    assert fields["slot_lengths"] == [0, 504, 1, 2, 3, 4, 5, 6]
    struct.pack_into("<H", data, 10, 505)
    with pytest.raises(ValueError, match="504"):
        probe.context_fields(bytes(data))
    with pytest.raises(ValueError, match="exactly32"):
        probe.context_fields(bytes(31))


@pytest.mark.parametrize(
    "mutation", ["fake-actions", "wrong-byte", "duplicate", "wrong-range", "failed", "producer"]
)
def test_required_guards_reject_substituted_or_incomplete_proof(guarded, mutation):
    image, directories = guarded
    assert len(probe.validate_guards(directories, image.read_bytes(), None)) == 5
    path = directories[-1] / "report.json"
    report = json.loads(path.read_bytes())
    if mutation == "fake-actions":
        report["att_packets"] = []
    elif mutation == "wrong-byte":
        raw = b"x" * report["source_bytes"]
        (directories[-1] / "download.bin").write_bytes(raw)
        report["download_sha256"] = probe.sha(raw)
    elif mutation == "duplicate":
        directories[-1] = directories[0]
    elif mutation == "wrong-range":
        report["source_address"] = "0x1000bf80"
    elif mutation == "failed":
        report["ok"] = False
    else:
        report["producer"] = "dbg fread spi_flash 0"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        probe.validate_guards(directories, image.read_bytes(), None)


def test_handler_readonly_requires_bound_full_actions_parent(guarded, tmp_path):
    image, directories = guarded
    index = list(probe.GUARDS).index(0x10024A20)
    parent = directories[index]
    raw = (parent / "report.json").read_bytes()
    child = json.loads(raw)
    for key in (
        "att_packets",
        "writes",
        "frames",
        "notifications",
        "log_characteristics",
        "ack_count",
        "expected_ack_count",
        "end_received",
        "pending_hex",
        "log_session_complete",
    ):
        child.pop(key)
    child.update(download_only=True, sd_write_attempted=False, parent_report_sha256=probe.sha(raw))
    directories[index] = save(tmp_path / "handler-read", child, (parent / "download.bin").read_bytes())
    with pytest.raises(ValueError, match="explicit write parent"):
        probe.validate_guards(directories, image.read_bytes(), None)
    assert len(probe.validate_guards(directories, image.read_bytes(), parent)) == 5
    original = json.loads(raw)
    original["att_packets"] = []
    (parent / "report.json").write_text(json.dumps(original))
    with pytest.raises(ValueError, match="parent hash"):
        probe.validate_guards(directories, image.read_bytes(), parent)


@pytest.mark.parametrize("mutation", ["short", "failed", "pointer", "guard", "summary", "producer"])
def test_context_cannot_follow_invalid_pointer_parent(guarded, tmp_path, mutation):
    image, directories = guarded
    verified = probe.validate_guards(directories, image.read_bytes(), None)
    report = attach_actions(snapshot("rc0000000100", probe.Phase.pointer))
    report.update(
        ok=True,
        sd_write_attempted=True,
        guards=verified,
        verification={"pointer": hex(probe.RAM_START), "allocation_bound_bytes": 80},
    )
    parent = save(tmp_path / "pointer", report, probe.RAM_START.to_bytes(4, "little"))
    if mutation == "short":
        (parent / "download.bin").write_bytes(b"abc")
    elif mutation == "failed":
        report["ok"] = False
    elif mutation == "pointer":
        data = (probe.RAM_END - 76).to_bytes(4, "little")
        (parent / "download.bin").write_bytes(data)
        report["download_sha256"] = probe.sha(data)
    elif mutation == "guard":
        report["guards"][0]["report_sha256"] = "0" * 64
    elif mutation == "summary":
        report["verification"]["pointer"] = hex(probe.RAM_START + 4)
    else:
        report["producer"] = "dbg fread spi_flash 0"
    (parent / "report.json").write_text(json.dumps(report))
    with patch.object(probe, "capture", AsyncMock()) as capture:
        with pytest.raises(ValueError):
            probe.main(
                image,
                tmp_path / "rejected",
                directories,
                create_sd_file=True,
                phase=probe.Phase.context,
                previous_path=parent,
            )
        capture.assert_not_awaited()
    rejected = json.loads((tmp_path / "rejected" / "report.json").read_bytes())
    assert rejected["ok"] is False and rejected["sd_write_attempted"] is False


def test_two_independent_successes_bind_exact_pointer_parent(guarded, tmp_path):
    image, directories = guarded
    write_calls, download_calls = [], []

    async def write(report):
        write_calls.append(report["dump_command"])
        report.update(attach_actions(copy.deepcopy(report)), sd_write_attempted=True)

    async def download(report, out, size):
        download_calls.append(size)
        data = probe.RAM_START.to_bytes(4, "little") if size == 4 else bytes(32)
        (out / "download.bin").write_bytes(data)
        report.update(download_bytes=size, received_bytes=size, download_sha256=probe.sha(data))
        return data

    with (
        patch.object(probe.sd_bootstrap, "identity", AsyncMock(return_value=(info(), []))) as identity,
        patch.object(probe.sd_bootstrap, "write_file", write),
        patch.object(probe.sd_bootstrap, "download_file", download),
    ):
        parent = tmp_path / "pointer"
        probe.main(image, parent, directories, create_sd_file=True)
        original = (parent / "report.json").read_bytes()
        out = tmp_path / "context"
        probe.main(
            image, out, directories, create_sd_file=True, phase=probe.Phase.context, previous_path=parent
        )
    result = json.loads((out / "report.json").read_bytes())
    assert result["ok"] is True and result["source_address"] == hex(probe.RAM_START)
    assert result["previous"]["report_sha256"] == probe.sha(original)
    assert (parent / "report.json").read_bytes() == original
    assert len(write_calls) == 2 and download_calls == [4, 32] and identity.await_count == 4
    assert result["verification"]["slot_lengths"] == [0] * 8


@pytest.mark.parametrize("mutation", ["producer", "mmio", "size", "mode"])
def test_invalid_request_fails_before_identity(tmp_path, mutation):
    report = snapshot("rc0000000100", probe.Phase.pointer)
    if mutation == "producer":
        report["producer"] = "dbg fread spi_flash 0"
    elif mutation == "mmio":
        report["source_address"] = "0x40000000"
    elif mutation == "size":
        report["source_bytes"] = 512
    else:
        report["phase"] = "slot"
    with patch.object(probe.sd_bootstrap, "identity", AsyncMock()) as identity:
        with pytest.raises(ValueError):
            asyncio.run(probe.capture(report, tmp_path))
        identity.assert_not_awaited()


def test_actions_failure_blocks_download_and_retains_primary_poststate_failure(tmp_path):
    report = snapshot("rc0000000100", probe.Phase.pointer)

    async def fake_write(target):
        target.update(attach_actions(copy.deepcopy(target)), sd_write_attempted=True)
        target["att_packets"] = []

    with (
        patch.object(
            probe.sd_bootstrap, "identity", AsyncMock(side_effect=[(info(), []), OSError("postinfo failed")])
        ),
        patch.object(probe.sd_bootstrap, "write_file", fake_write),
        patch.object(probe.sd_bootstrap, "download_file", AsyncMock()) as download,
    ):
        with pytest.raises(ValueError, match="ATT Actions writes"):
            asyncio.run(probe.capture(report, tmp_path))
        download.assert_not_awaited()
    assert report["after_error"] == "OSError: postinfo failed"


def test_collision_never_writes_or_downloads_but_checks_poststate(tmp_path):
    report = snapshot("rc0000000100", probe.Phase.pointer)
    with (
        patch.object(
            probe.sd_bootstrap, "identity", AsyncMock(return_value=(info(), [{"name": report["name"]}]))
        ) as identity,
        patch.object(probe.sd_bootstrap, "write_file", AsyncMock()) as write,
        patch.object(probe.sd_bootstrap, "download_file", AsyncMock()) as download,
    ):
        with pytest.raises(FileExistsError, match="already listed"):
            asyncio.run(probe.capture(report, tmp_path))
        write.assert_not_awaited()
        download.assert_not_awaited()
    assert identity.await_count == 2 and report["state_verification"]["free_capacity_decrease"] == 0


def test_wrong_image_or_missing_guards_fail_without_capture(guarded, tmp_path):
    image, directories = guarded
    with patch.object(probe, "capture", AsyncMock()) as capture:
        with pytest.raises(ValueError, match="five distinct"):
            probe.main(image, tmp_path / "missing-guard", directories[:-1], create_sd_file=True)
        image.write_bytes(b"wrong image")
        with pytest.raises(ValueError, match="verified FW"):
            probe.main(image, tmp_path / "wrong-image", directories, create_sd_file=True)
        capture.assert_not_awaited()


def test_published_historical_bundle_replays_without_private_reports_or_device(tmp_path):
    relative = Path("docs/evidence/logsrv-context-live-2026-10-14.json")
    source = json.loads(relative.read_bytes())
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    shutil.copyfile(relative, destination)
    inputs = [source["image"]["file"]] + [row["raw"]["file"] for row in source["guards"]]
    inputs += [source[phase]["raw"]["file"] for phase in ("pointer", "context")]
    for name in inputs:
        target = destination.parent / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(relative.parent / name, target)
    with (
        patch.object(probe.sd_bootstrap, "identity", AsyncMock()) as identity,
        patch.object(probe.sd_bootstrap, "write_file", AsyncMock()) as write,
        patch.object(probe.sd_bootstrap, "download_file", AsyncMock()) as download,
    ):
        result = probe.replay_public(destination)
        identity.assert_not_awaited()
        write.assert_not_awaited()
        download.assert_not_awaited()
    assert result["pointer"] == "0x180111fc" and result["historical_context_only"] is True
    assert result["context_fields"]["rd"] == result["context_fields"]["wr"] == 204
    assert result["context_fields"]["slot_lengths"] == [0, 0, 0, 0, 139, 0, 0, 0]
    assert result["private_packet_audit_rerun"] is False
    raw = destination.parent / source["context"]["raw"]["file"]
    original = raw.read_bytes()
    raw.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    with pytest.raises(ValueError, match="sample hash"):
        probe.replay_public(destination)
    raw.write_bytes(original)
    destination.write_bytes(destination.read_bytes() + b" ")
    with pytest.raises(ValueError, match="compact receipt changed"):
        probe.replay_public(destination)
