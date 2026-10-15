"""Read-only runtime boundaries: stale capture, pending negotiation and immutable partials."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rcominote.experiments import window_ram_probe as R


def transaction(origin="host", parameters=(6, 6, 0, 500)):
    fields = dict(zip(("min", "max", "latency", "timeout"), parameters, strict=True))
    return {
        "origin": origin,
        "request": fields,
        "remote_request": fields if origin == "remote" else None,
        "remote_accept": {"result": 0} if origin == "remote" else None,
    }


@pytest.mark.parametrize("exit_code", [0, 124, 137, 1])
def test_stopped_capture_cannot_reuse_stale_settlement(exit_code):
    monitor = SimpleNamespace(process=SimpleNamespace(returncode=exit_code), poll=Mock())
    conn = SimpleNamespace(_check_failure=Mock())
    with patch.object(R.P, "inspect") as inspect, pytest.raises(RuntimeError, match="stale observations"):
        R.observe(monitor, conn, {})
    inspect.assert_not_called()
    monitor.poll.assert_not_called()


def test_link_change_rejected_before_capture_poll():
    monitor = SimpleNamespace(process=SimpleNamespace(returncode=None), poll=Mock())
    conn = SimpleNamespace(_check_failure=Mock())
    with (
        patch.object(R, "active_link", return_value={"changed": True}),
        pytest.raises(ValueError, match="changed"),
    ):
        R.observe(monitor, conn, {"original": True})
    monitor.poll.assert_not_called()


def test_partial_capture_tail_waits_and_is_never_confused_with_parameter_pending():
    actual = transaction()
    snapshots = [
        {"transactions": [actual], "pending": [{"kind": "capture-tail"}]},
        {"transactions": [actual], "pending": []},
    ]
    with patch.object(R, "observe", side_effect=snapshots), patch.object(R.asyncio, "sleep", new=AsyncMock()):
        result = asyncio.run(
            R.wait_transaction(None, None, {}, index=0, origin="host", parameters=(6, 6, 0, 500), seconds=1)
        )
    assert result == actual


@pytest.mark.parametrize("fault", ["extra", "pending", "wrong_parameters", "wrong_origin"])
def test_stage_cannot_accept_unexpected_parameter_traffic(fault):
    actual = transaction()
    snapshot = {"transactions": [actual], "pending": []}
    if fault == "extra":
        snapshot["transactions"].append(actual)
    elif fault == "pending":
        snapshot["pending"] = [{"stage": "awaiting-update", "origin": "remote"}]
    elif fault == "wrong_parameters":
        actual["request"]["timeout"] = 600
    else:
        actual["origin"] = "remote"
    with patch.object(R, "observe", return_value=snapshot), pytest.raises(ValueError):
        asyncio.run(
            R.wait_transaction(None, None, {}, index=0, origin="host", parameters=(6, 6, 0, 500), seconds=1)
        )


def test_pending_update_never_sends_another_host_command():
    snapshot = {"transactions": [], "pending": [{"stage": "awaiting-update"}]}
    operation = {}
    with (
        patch.object(R, "observe", return_value=snapshot),
        patch.object(R, "request_once", new=AsyncMock()) as request,
        pytest.raises(ValueError, match="no host update attempted"),
    ):
        asyncio.run(R.normalize(None, None, {"transport": {"link": {}}}, operation, 0))
    request.assert_not_called()
    assert "normalization_attempted" not in operation


def test_missing_expected_settlement_is_bounded_without_filler_or_retry():
    with (
        patch.object(R, "observe", return_value={"transactions": [], "pending": []}),
        pytest.raises(TimeoutError),
    ):
        asyncio.run(
            R.wait_transaction(
                None, None, {}, index=0, origin="host", parameters=(6, 6, 0, 500), seconds=0.001
            )
        )


def test_failed_download_keeps_only_actual_received_bytes_and_closes_offline_gate(tmp_path):
    received = b"explicit partial fixture"
    report = {"att_packets": [], "setup_end": 0}
    operation = {"operation_id": "first", "name": R.W.NAME}
    conn = SimpleNamespace(offline_allowed=False)

    async def fail(name, sink, *, offset, timeout):
        assert name == R.W.NAME and offset == 0 and timeout == 8
        sink(received)
        raise ValueError("download failed")

    conn.download = fail
    with patch.object(R.A, "download") as audit, pytest.raises(ValueError, match="download failed"):
        asyncio.run(R.download(conn, report, operation, tmp_path, bytes(4096)))
    audit.assert_not_called()
    assert not conn.offline_allowed
    assert (tmp_path / "download.bin").read_bytes() == received
    assert operation["received_bytes"] == len(received)
    assert "download_bytes" not in operation


@pytest.mark.parametrize("fault", ["session", "first", "second"])
def test_replay_cannot_promote_original_failed_or_incomplete_trial(tmp_path, fault):
    report = {"ok": True, "operations": [{"ok": True}, {"ok": True}]}
    if fault == "session":
        report["ok"] = False
    else:
        report["operations"][0 if fault == "first" else 1]["ok"] = False
    original = json.dumps(report).encode()
    (tmp_path / "report.json").write_bytes(original)
    with patch.object(R.evidence, "validate") as validate, pytest.raises(ValueError, match="Original"):
        R.replay(tmp_path, tmp_path)
    validate.assert_not_called()
    assert (tmp_path / "report.json").read_bytes() == original


def test_invalid_preflight_never_creates_output_or_authorizes(tmp_path):
    with (
        patch.object(R.W, "validate_inputs", side_effect=ValueError("original parent changed")),
        patch.object(R, "authorize") as authorize,
        pytest.raises(ValueError, match="parent changed"),
    ):
        R.main(tmp_path, tmp_path, tmp_path / "never-created")
    authorize.assert_not_called()
    assert not (tmp_path / "never-created").exists()
