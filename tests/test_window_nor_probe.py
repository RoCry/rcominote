"""Bounded NOR-window runtime: no competing updates, retries or failure promotion."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from test_sd_nor_probe import info
from test_status_event import row as status_row
from test_window_ram_probe import transaction

from rcominote.experiments import window_nor_probe as N
from rcominote.experiments.dual_client import DualClient


def snapshot(*values, pending=None):
    return {"transactions": list(values), "pending": pending or []}


def fast_pending(parameters=N.R.FAST):
    value = transaction("remote", parameters)
    value["request"] = None
    return value | {"stage": "awaiting-command"}


def run_fast(snapshots, *, required=False):
    with (
        patch.object(N.R, "observe", side_effect=snapshots),
        patch.object(N.asyncio, "sleep", new=AsyncMock()),
    ):
        return asyncio.run(N.pre_download_fast(None, None, {}, cursor=1, required=required, seconds=1))


def test_first_stage_can_reuse_startup_without_inventing_remote_fast():
    startup = transaction("remote", N.R.FAST)
    assert run_fast([snapshot(startup)]) == []


@pytest.mark.parametrize("required", [False, True])
def test_pre_download_pending_fast_must_complete_before_return(required):
    startup = transaction("remote", N.R.FAST)
    fast = transaction("remote", N.R.FAST)
    assert run_fast(
        [snapshot(startup, pending=[fast_pending()]), snapshot(startup, fast)], required=required
    ) == [fast]


def test_second_stage_cannot_use_quiet_wire_as_proof_of_fast_settlement():
    startup = transaction("remote", N.R.FAST)
    with (
        patch.object(N.R, "observe", return_value=snapshot(startup)),
        pytest.raises(TimeoutError),
    ):
        asyncio.run(N.pre_download_fast(None, None, {}, cursor=1, required=True, seconds=0.001))


@pytest.mark.parametrize("fault", ["extra", "overlap", "slow", "host", "unknown", "missing_cursor"])
def test_unexpected_pre_download_traffic_fails_without_new_host_update(fault):
    startup = transaction("remote", N.R.FAST)
    fast = transaction("remote", N.R.FAST)
    value = snapshot(startup, fast)
    if fault == "extra":
        value["transactions"].append(fast)
    elif fault == "overlap":
        value["pending"] = [fast_pending()]
    elif fault == "slow":
        value = snapshot(startup, pending=[fast_pending(N.R.SLOW)])
    elif fault == "host":
        value = snapshot(startup, transaction())
    elif fault == "unknown":
        value = snapshot(startup, pending=[{"origin": "other-connection"}])
    else:
        value = snapshot()
    with patch.object(N.R, "request_once") as request, pytest.raises(ValueError):
        run_fast([value])
    request.assert_not_called()


def test_structural_capture_tail_is_waited_for_even_after_fast_completes():
    startup = transaction("remote", N.R.FAST)
    fast = transaction("remote", N.R.FAST)
    assert run_fast(
        [snapshot(startup, fast, pending=[{"kind": "capture-tail"}]), snapshot(startup, fast)], required=True
    ) == [fast]


def test_failed_ring_download_retains_exact_partial_and_never_parses_old_rows(tmp_path):
    received = b"only actual bytes"
    report = {"att_packets": []}
    operation = {"name": "rc0123456789"}
    conn = SimpleNamespace(offline_allowed=False)

    async def fail(name, sink, *, offset, timeout):
        assert name == operation["name"] and offset == 0 and timeout == 8
        sink(received)
        raise ValueError("new download incomplete")

    conn.download = fail
    with patch.object(N.C, "payload") as parse, pytest.raises(ValueError, match="incomplete"):
        asyncio.run(N.download(conn, report, operation, tmp_path))
    parse.assert_not_called()
    assert not conn.offline_allowed
    assert (tmp_path / "download.bin").read_bytes() == received
    assert not (tmp_path / "sector.bin").exists()
    assert operation["received_bytes"] == len(received)


def test_second_freshness_failure_keeps_first_checkpoint_and_cannot_pair(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "checkpoint.json").write_bytes(b"preserved actual first checkpoint")
    (first / "sector.bin").write_bytes(b"preserved first sector")
    report = {"att_packets": []}
    op = {"operation_id": "second", "name": "rc0123456789", "barrier_complete": True}

    async def complete(name, sink, *, offset, timeout):
        sink(bytes(4096))
        return 4096

    conn = SimpleNamespace(offline_allowed=False, download=complete)
    with (
        patch.object(N.A, "download", return_value={"complete": True}),
        patch.object(N.C, "payload", side_effect=ValueError("previous dump anchor missing")),
        pytest.raises(ValueError, match="anchor"),
    ):
        asyncio.run(N.download(conn, report, op, second))
        N.decode(report, op, second)
    assert (first / "checkpoint.json").read_bytes() == b"preserved actual first checkpoint"
    assert (first / "sector.bin").read_bytes() == b"preserved first sector"
    assert (second / "download.bin").stat().st_size == 4096
    assert not (second / "sector.bin").exists()
    assert not op.get("live_complete") and not op.get("ok")


def test_first_freshness_failure_occurs_after_settlement_and_barrier_but_stops_second(tmp_path):
    report = {
        "att_packets": [],
        "transport": {},
        "operations": [
            {"operation_id": label, "name": f"nonce-{label}", "sd_write_attempted": False}
            for label in ("first", "second")
        ],
    }
    conn = SimpleNamespace(
        client=SimpleNamespace(start_notify=AsyncMock()), file_list=AsyncMock(return_value=[])
    )
    seen = []

    async def identity(_conn, owner, key):
        seen.append(("identity", key))
        owner[key] = {"state": "unchanged"}

    async def run(operation):
        seen.append(("actions", operation["operation_id"]))
        operation["sd_write_attempted"] = True

    async def settlement(*args, **kwargs):
        seen.append(("settlement", kwargs["parameters"]))
        return {}

    def fail_decode(*args):
        seen.append(("decode", "first"))
        raise ValueError("first fresh-chain rejected")

    action = SimpleNamespace(receive=Mock(), run=AsyncMock(side_effect=run))
    with (
        patch.object(N, "Actions", return_value=action),
        patch.object(N, "active_link", return_value={}),
        patch.object(N.A, "setup", return_value={}),
        patch.object(N.A, "actions", return_value={}),
        patch.object(N.S, "read_identity", side_effect=identity),
        patch.object(N, "verify_state", return_value={}),
        patch.object(N.R, "observe", return_value={}),
        patch.object(N.R, "wait_transaction", side_effect=settlement),
        patch.object(N.R, "normalize", new=AsyncMock()),
        patch.object(N, "pre_download_fast", new=AsyncMock(return_value=[])),
        patch.object(N, "download", new=AsyncMock()),
        patch.object(N, "decode", side_effect=fail_decode),
        pytest.raises(ValueError, match="fresh-chain"),
    ):
        asyncio.run(N.connected(conn, None, report, tmp_path))
    assert seen == [
        ("identity", "before"),
        ("settlement", N.R.FAST),
        ("actions", "first"),
        ("settlement", N.R.SLOW),
        ("identity", "after"),
        ("decode", "first"),
        ("identity", "after"),
    ]
    assert action.run.await_count == 1
    assert report["operations"][0]["barrier_complete"] is True
    assert not report["operations"][0].get("live_complete")
    assert report["operations"][1]["sd_write_attempted"] is False


@pytest.mark.parametrize("capacity_change", [0, 1, -1])
def test_predecessor_state_checked_before_file_list_or_any_producer(tmp_path, capacity_change):
    report = {
        "att_packets": [],
        "transport": {},
        "expected_before": info(),
        "operations": [{"operation_id": label, "sd_write_attempted": False} for label in ("first", "second")],
    }
    actual = info(capacity_change)
    conn = SimpleNamespace(
        client=SimpleNamespace(start_notify=AsyncMock()),
        file_list=AsyncMock(side_effect=RuntimeError("test stops after predecessor gate")),
    )
    actions = SimpleNamespace(receive=Mock(), run=AsyncMock())

    async def identity(_conn, owner, key):
        owner[key] = actual

    expected_error = RuntimeError if capacity_change == 0 else ValueError
    with (
        patch.object(N, "Actions", return_value=actions),
        patch.object(N, "active_link", return_value={}),
        patch.object(N.A, "setup", return_value={}),
        patch.object(N.S, "read_identity", side_effect=identity),
        patch.object(N.R, "observe", return_value={}),
        pytest.raises(expected_error),
    ):
        asyncio.run(N.connected(conn, None, report, tmp_path))
    actions.run.assert_not_awaited()
    assert not any(op["sd_write_attempted"] for op in report["operations"])
    if capacity_change:
        conn.file_list.assert_not_awaited()
        assert "predecessor_state_verification" not in report
    else:
        conn.file_list.assert_awaited_once()
        assert report["predecessor_state_verification"] == N.verify_state(info(), actual, sd_write=False)


@pytest.mark.parametrize("fault", ["session", "pair", "audit", "first", "second"])
def test_replay_cannot_promote_original_failure(tmp_path, fault):
    report = {
        "ok": True,
        "pair_verified": True,
        "final_audit_complete": True,
        "operations": [{"ok": True}, {"ok": True}],
    }
    if fault in ("first", "second"):
        report["operations"][fault == "second"]["ok"] = False
    else:
        report[{"session": "ok", "pair": "pair_verified", "audit": "final_audit_complete"}[fault]] = False
    original = json.dumps(report).encode()
    (tmp_path / "report.json").write_bytes(original)
    with patch.object(N.evidence, "validate") as audit, pytest.raises(ValueError, match="Original"):
        N.replay(tmp_path, tmp_path)
    audit.assert_not_called()
    assert (tmp_path / "report.json").read_bytes() == original


def test_invalid_parent_fails_before_output_or_authorization(tmp_path):
    with (
        patch.object(N.C, "prepare", side_effect=ValueError("changed window parent")),
        patch.object(N, "authorize") as authorize,
        pytest.raises(ValueError, match="parent"),
    ):
        N.main(tmp_path, tmp_path, tmp_path, tmp_path / "never-created")
    authorize.assert_not_called()
    assert not (tmp_path / "never-created").exists()


def test_cli_fixes_one_offset_and_stops_after_capture_failure(tmp_path):
    report = {"operations": [{"operation_id": "first"}, {"operation_id": "second"}], "ok": False}
    with (
        patch.object(N.C, "prepare", return_value=report) as prepare,
        patch.object(N, "authorize"),
        patch.object(N, "capture", new=AsyncMock(side_effect=TimeoutError("first failure"))) as capture,
        patch.object(N.U, "compare_pair") as compare,
        pytest.raises(TimeoutError),
    ):
        N.main(tmp_path, tmp_path, tmp_path, tmp_path / "single")
    assert prepare.call_args.args[-1] == 0x2400
    assert capture.await_count == 1
    compare.assert_not_called()
    retained = json.loads((tmp_path / "single" / "report.json").read_bytes())
    assert retained["ok"] is False and retained["final_audit_complete"] is False
    assert retained["error"] == "TimeoutError: first failure"


def test_runtime_status_observer_records_original_index_without_consuming_dispatch_queue():
    report = {"att_packets": [], "expected_before": info(), "status_event_policy": N.events.POLICY}
    conn = SimpleNamespace(client=SimpleNamespace(receive_observer=None))
    N.attach_status_observer(conn, report)
    value = status_row()
    report["att_packets"].append(value)
    conn.client.receive_observer(0, value)
    assert N.events.verify(report)[0] == {0}
    assert report["att_packets"] == [value]


@pytest.mark.parametrize("fault", ["changed-state", "unsupported-event", "crc"])
def test_socket_observer_fails_before_actions_dispatch_on_changed_or_unknown_event(fault):
    report = {"att_packets": [], "expected_before": info(), "status_event_policy": N.events.POLICY}
    client = DualClient.__new__(DualClient)
    client.report = report
    client.receive_observer = None
    client.receive_guard = Mock()
    conn = SimpleNamespace(client=client)
    N.attach_status_observer(conn, report)
    value = status_row()
    if fault == "changed-state":
        value = status_row(bytes.fromhex("026301010009ffff030001000000000000000000"))
    elif fault == "unsupported-event":
        value = status_row(command=N.Boyi.VOICE_CONTROL_CHANGE)
    else:
        value["hex"] = value["hex"][:-2] + "ff"
    with pytest.raises(ValueError):
        client.record("rx", bytes.fromhex(value["hex"]))
    client.receive_guard.assert_not_called()
    assert len(report["att_packets"]) == 1
    assert report["status_events"] == []


def test_ninth_status_stays_in_raw_trace_but_fails_before_later_work():
    report = {"att_packets": [], "expected_before": info(), "status_event_policy": N.events.POLICY}
    conn = SimpleNamespace(client=SimpleNamespace(receive_observer=None))
    N.attach_status_observer(conn, report)
    for index in range(9):
        value = status_row()
        report["att_packets"].append(value)
        if index < 8:
            conn.client.receive_observer(index, value)
        else:
            with pytest.raises(ValueError, match="bound"):
                conn.client.receive_observer(index, value)
    assert len(report["att_packets"]) == 9 and len(report["status_events"]) == 8
