"""No hardware: fixed ring profile, immutable HCI replay and failure retention."""

import asyncio
import copy
from unittest.mock import AsyncMock, patch

import pytest
from test_hci_interval import HANDLE, LOCAL, packets, parsed, record
from test_sd_nor_probe import attach_actions, info, receipt

from rcominote.experiments import hci_interval as H
from rcominote.experiments import sd_nor_interval as interval
from rcominote.experiments import sd_nor_probe as probe


def evidence(tmp_path):
    raw = H.HEADER + b"".join(record(p, op, stamp=100 + i) for i, (op, p) in enumerate(packets()))
    raw += record(b"\x10\x01\x00", stamp=107)  # Unrelated event proves capture spans transfer end.
    (tmp_path / "session.btsnoop").write_bytes(raw)
    events = parsed()
    return {
        "profile": interval.PROFILE,
        "condition": "verified-through-download",
        "sd_write_attempted": False,
        "update_attempted": True,
        "transfer_complete": True,
        "monitor_exit": 124,
        "hci_capture": {"bytes": len(raw), "sha256": interval.sha(raw), "records": 6},
        "link": {"peer": H.PEER, "controller": "hci0", "handle": HANDLE, "local": LOCAL},
        "update_requested_us": 102,
        "download_start_us": 105,
        "download_end_us": 106,
        "baseline": events[1],
        "applied": events[4],
        "actual_hci_request": events[2],
        "before": info(),
        "after": info(),
        "state_verification": interval.verify_state(info(), info(), sd_write=False),
    }


def test_private_capture_replay_does_not_trust_success_summaries(tmp_path):
    original = evidence(tmp_path)
    interval.replay(original, tmp_path)
    for key, value in (
        ("applied", original["applied"] | {"interval": 12}),
        ("baseline", original["baseline"] | {"timeout": 400}),
        ("download_start_us", 103),
        ("download_end_us", 101),
        ("transfer_complete", False),
        ("after_error", "failed"),
        ("actual_hci_request", original["actual_hci_request"] | {"min_length": 0}),
        ("state_verification", {}),
    ):
        with pytest.raises(ValueError):
            interval.replay(original | {key: value}, tmp_path)
    raw = (tmp_path / "session.btsnoop").read_bytes()
    (tmp_path / "session.btsnoop").write_bytes(raw[:-1])
    with pytest.raises(ValueError):
        interval.replay(original, tmp_path)


def test_forged_capture_hash_is_rejected(tmp_path):
    report = evidence(tmp_path)
    report["hci_capture"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash"):
        interval.replay(report, tmp_path)


def test_exit130_needs_owned_stop_and_still_complete_hci(tmp_path):
    report = evidence(tmp_path) | {"monitor_exit": 130}
    with pytest.raises(ValueError, match="Exit130"):
        interval.replay(report, tmp_path)
    report["monitor_stop"] = {"signal": "SIGINT", "requested": True, "delivery": "sent"}
    interval.replay(report, tmp_path)
    report["applied"] = report["applied"] | {"interval": 12}
    with pytest.raises(ValueError, match="applied condition"):
        interval.replay(report, tmp_path)


@pytest.mark.parametrize("complete", [True, False])
def test_fixed_ring_callback_one_download_retains_partial(tmp_path, complete):
    report = attach_actions(receipt("rc0123456789", probe.BUFFER, 4096, phase=probe.Phase.baseline))
    data = b"x" * (4096 if complete else 3852)
    calls = []

    class Connection:
        async def download(self, name, sink, *, offset):
            calls.append((name, offset))
            sink(data)
            if not complete:
                raise RuntimeError("short fixed ring")
            return len(data)

    async def capture(transport, oracle, out, *, operation):
        assert oracle == b"" and out == tmp_path
        await operation(Connection(), out, transport)

    with patch.object(interval.session, "capture", capture), patch.object(interval, "replay") as replay:
        if complete:
            asyncio.run(interval.download(report, tmp_path))
            replay.assert_called_once_with(report["transport"], tmp_path)
        else:
            with pytest.raises(RuntimeError, match="short"):
                asyncio.run(interval.download(report, tmp_path))
            replay.assert_not_called()
    assert calls == [(report["name"], 0)]
    assert (tmp_path / "download.bin").read_bytes() == data
    assert report["received_bytes"] == len(data)
    assert report["before"] == info()  # Nested transport never replaces stage identity.


@pytest.mark.parametrize("fault", ["context", "address", "size", "command", "actions"])
def test_wrong_source_or_incomplete_actions_never_opens_transport(tmp_path, fault):
    report = attach_actions(receipt("rc0123456789", probe.BUFFER, 4096, phase=probe.Phase.baseline))
    key, value = {
        "context": ("phase", "context"),
        "address": ("source_address", "0x18000000"),
        "size": ("source_bytes", 512),
        "command": ("dump_command", "dbg fread spi_flash 512"),
        "actions": ("att_packets", []),
    }[fault]
    report[key] = value
    with patch.object(interval.session, "capture", AsyncMock()) as capture:
        with pytest.raises(ValueError):
            asyncio.run(interval.download(report, tmp_path))
        capture.assert_not_called()


def test_interval_requires_complete_unique_marker_including_wrapped_echo():
    report = receipt("rc0123456789", probe.BUFFER, 4096, phase=probe.Phase.baseline)
    report["transport_profile"] = interval.PROFILE
    echo = b"logsrv: cmd(7) " + report["dump_command"].encode() + b"\n\r\n"
    payload = echo.ljust(4096, b"x")
    assert probe.validate_payload(report, payload[20:] + payload[:20])["no_nor_rows"]
    for value in (echo[:-1], echo + echo, report["dump_command"].encode()):
        with pytest.raises(ValueError, match="complete current dump marker"):
            probe.validate_payload(report, value.ljust(4096, b"x"))


def test_interval_boot_existing_public_ring_and_complete_marker():
    from pathlib import Path

    data = Path("docs/evidence/sd-bridge-2026-10-13/boot-ring-download.bin").read_bytes()
    report = {
        "phase": "boot",
        "transport_profile": interval.PROFILE,
        "dump_command": "dbg dumpbuf 402910729 4096 /SD:/RECORDER/Call-rcb61b078de5.mp3",
    }
    assert probe.validate_payload(report, data)["sector_sha256"] == probe.BOOT_SHA


def test_interval_capture_requires_actions_before_transport(tmp_path):
    report = receipt("rc0123456789", probe.BUFFER, 4096, phase=probe.Phase.baseline)
    report["transport_profile"] = interval.PROFILE

    async def fake_write(target):
        target.update(attach_actions(copy.deepcopy(target)))
        target["att_packets"] = []

    with (
        patch.object(probe.sd_bootstrap, "identity", AsyncMock(return_value=(info(), []))),
        patch.object(probe.sd_bootstrap, "write_file", fake_write),
        patch.object(interval, "download", AsyncMock()) as download,
    ):
        with pytest.raises(ValueError, match="ATT Actions"):
            asyncio.run(probe.capture(report, tmp_path))
        download.assert_not_called()
    assert report["after"] == info()


def test_cli_rejects_context_interval_before_io(tmp_path):
    with pytest.raises(Exception, match="baseline/boot only"):
        probe.main(
            tmp_path,
            tmp_path / "out",
            [],
            create_sd_file=True,
            phase=probe.Phase.context,
            transport=probe.Transport.interval,
        )
    assert not (tmp_path / "out").exists()
    assert probe.app.pretty_exceptions_show_locals is False


def test_previous_interval_baseline_replays_private_capture(tmp_path):
    import json
    import struct

    # Real previous() walks baseline -> context; isolate only the already-tested
    # guard verifier, leaving Actions, bytes, nonce, state and HCI gates intact.
    refs = [{"source": "test-verified-guard-reference"}]
    ctx = tmp_path / "context"
    ctx.mkdir()
    context = attach_actions(receipt("rc0000000100", probe.CONTEXT, 28, phase=probe.Phase.context))
    context.update(guards=refs)
    raw = struct.pack("<5I", 0, 20, 20, 4096, probe.BUFFER) + b"\x01\0" + bytes(6)
    (ctx / "download.bin").write_bytes(raw)
    context.update(download_bytes=len(raw), received_bytes=len(raw), download_sha256=interval.sha(raw))
    (ctx / "report.json").write_text(json.dumps(context))
    parent = probe.previous(ctx, probe.Phase.context, refs, b"", None)
    base = tmp_path / "baseline"
    base.mkdir()
    report = attach_actions(receipt("rc0000000101", probe.BUFFER, 4096, phase=probe.Phase.baseline))
    body = (b"logsrv: cmd(7) " + report["dump_command"].encode() + b"\n\r\n").ljust(4096, b"x")
    report.update(
        guards=refs,
        previous=parent,
        transport_profile=interval.PROFILE,
        transport=evidence(base),
        received_bytes=4096,
        download_bytes=4096,
        download_sha256=interval.sha(body),
    )
    (base / "download.bin").write_bytes(body)
    (base / "report.json").write_text(json.dumps(report))
    assert probe.previous(base, probe.Phase.baseline, refs, b"", None)["download_sha256"] == interval.sha(
        body
    )
    capture = base / "session.btsnoop"
    capture.write_bytes(capture.read_bytes()[:-1])
    with pytest.raises(ValueError, match="Incomplete final"):
        probe.previous(base, probe.Phase.baseline, refs, b"", None)
