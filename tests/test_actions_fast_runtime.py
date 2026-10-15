"""Fixed experimental lifecycle only; no device, auth or production API changes."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_actions_fast_control import ORACLE, content, f0, fixture

from rcominote.experiments import actions_fast_control as C
from rcominote.experiments import actions_fast_runtime as R
from rcominote.log_capture import START, STOP
from rcominote.log_probe import ACK


@pytest.mark.parametrize("mode,finish_at", [("fast", 0), ("default", 2), ("fast", 8), ("fast", "stop")])
def test_fixed_session_measures_condition_before_target_and_flushes_only_as_bounded(
    mode, finish_at, tmp_path
):
    original, plan = fixture(tmp_path, mode=mode)
    session = C.report(plan) | {
        "transport": original["transport"],
        "startup_classification": original["startup_classification"],
        "att_packets": [],
    }
    conn = SimpleNamespace(
        queue=asyncio.Queue(), _transaction=asyncio.Lock(), offline_allowed=False, _check_failure=lambda: None
    )
    conn._fail = lambda error: setattr(conn, "failure", error)
    conn.client = SimpleNamespace(_link=SimpleNamespace(notifications=[]))
    actions = R.FixedActions(conn, session)
    normalized, fillers = [False], [0]
    ledger = [1]

    async def send(packet):
        session["att_packets"].append(
            {
                "direction": "tx",
                "hex": (b"\x12\x16\0" + packet).hex(),
                "monotonic_ns": len(session["att_packets"]),
            }
        )
        if packet not in C.recipe(plan, 8):
            raise AssertionError("arbitrary command")
        if packet in (C.packet(plan["marker_command"]), C.packet(C.MDB), C.packet(C.VERSION)):
            assert normalized[0]
        actions.receive(None, ACK)
        if packet == C.packet(C.VERSION):
            fillers[0] += 1
        if (packet == C.packet(C.MDB) and finish_at == 0) or (
            packet == C.packet(C.VERSION) and fillers[0] == finish_at
        ):
            actions.receive(None, f0(content(plan)))
        if packet == STOP:
            if finish_at == "stop":
                actions.receive(None, f0(content(plan)))
            actions.receive(None, b"\x1d\xf1\x81\0\0")

    conn.client.action_write = AsyncMock(side_effect=send)

    async def settle(*_args, **_kwargs):
        ledger[0] = 2
        return original["operation"]["activity_fast"][0]

    async def normalize(*_args):
        assert conn.client.action_write.await_args_list[-1].args[0] == START
        normalized[0] = True
        ledger[0] += 1

    with (
        patch.object(R.R, "normalize", new=AsyncMock(side_effect=normalize)),
        patch.object(R.R, "wait_transaction", new=AsyncMock(side_effect=settle)),
        patch.object(
            R.R, "observe", side_effect=lambda *_: {"transactions": [{}] * ledger[0], "pending": []}
        ),
    ):
        asyncio.run(actions.run_control(session["operation"], plan, None, ORACLE))
    op = session["operation"]
    expected_fillers = 8 if finish_at == "stop" else finish_at
    assert [call.args[0] for call in conn.client.action_write.await_args_list] == C.recipe(
        plan, expected_fillers
    )
    assert op["fillers"] == expected_fillers and op["ack_count"] == 5 + expected_fillers
    assert op["log_session_complete"] and op["live_complete"] and op["pending_hex"] == ""
    assert not op["sd_write_attempted"] and not hasattr(conn, "failure")


@pytest.mark.parametrize("fault", ["missing-fast", "normalize", "framing", "exhausted", "late-parameter"])
def test_failure_stops_target_or_fillers_and_sends_one_bounded_stop(tmp_path, fault):
    original, plan = fixture(tmp_path, mode="default" if fault == "missing-fast" else "fast")
    session = C.report(plan) | {
        "transport": original["transport"],
        "startup_classification": original["startup_classification"],
        "att_packets": [],
    }
    conn = SimpleNamespace(
        queue=asyncio.Queue(), _transaction=asyncio.Lock(), offline_allowed=False, _check_failure=lambda: None
    )
    conn._fail = lambda error: setattr(conn, "failure", error)
    conn.client = SimpleNamespace(_link=SimpleNamespace(notifications=[]))
    actions = R.FixedActions(conn, session)
    ledger = [1]

    async def send(packet):
        actions.receive(None, ACK)
        if packet == C.packet(C.MDB) and fault == "framing":
            actions.receive(None, b"bad-header")
        if packet == C.packet(C.MDB) and fault == "late-parameter":
            ledger[0] += 1
        if packet == STOP:
            actions.receive(None, b"\x1d\xf1\x81\0\0")

    conn.client.action_write = AsyncMock(side_effect=send)

    async def normalize(*_args):
        if fault == "normalize":
            raise ValueError("condition not applied")
        ledger[0] = 2

    with (
        patch.object(R.R, "normalize", new=AsyncMock(side_effect=normalize)),
        patch.object(
            R.R, "wait_transaction", new=AsyncMock(side_effect=TimeoutError("condition not applied"))
        ),
        patch.object(
            R.R, "observe", side_effect=lambda *_: {"transactions": [{}] * ledger[0], "pending": []}
        ),
        pytest.raises((ValueError, TimeoutError)),
    ):
        asyncio.run(actions.run_control(session["operation"], plan, None, ORACLE))
    writes = [call.args[0] for call in conn.client.action_write.await_args_list]
    assert writes.count(STOP) == 1 and writes.count(C.packet(C.MDB)) == (
        0 if fault in ("missing-fast", "normalize") else 1
    )
    assert writes.count(C.packet(C.VERSION)) == (8 if fault == "exhausted" else 0)
    assert hasattr(conn, "failure") and not session["operation"]["sd_write_attempted"]
    assert actions.operation is None


def test_invalid_plan_rejected_before_any_runtime_command(tmp_path):
    _original, plan = fixture(tmp_path)
    plan["mdb_command"] = "dbg mdb 40000000 100"
    conn = SimpleNamespace(
        queue=asyncio.Queue(),
        _transaction=asyncio.Lock(),
        client=SimpleNamespace(_link=SimpleNamespace(notifications=[])),
    )
    conn.client.action_write = AsyncMock()
    actions = R.FixedActions(conn, {"att_packets": []})
    with pytest.raises(ValueError):
        asyncio.run(actions.run_control({}, plan, None, ORACLE))
    conn.client.action_write.assert_not_called()


@pytest.mark.parametrize("tail", [ACK, f0(b"post-end")])
def test_coalesced_terminal_notification_sets_sticky_failure_without_callback_throw(tail):
    conn = SimpleNamespace(client=SimpleNamespace())
    actions = R.FixedActions(conn, {})
    actions.operation = {"notifications": []}
    actions.stream = R.Stream()
    actions.expected = actions.total_expected = 1
    actions.receive(None, ACK + b"\x1d\xf1\x81\0\0" + tail)
    assert isinstance(actions.failure, ValueError) and actions.changed.is_set()
    assert actions.operation["notifications"]  # Raw evidence retained.


def test_mutated_saved_plan_is_rejected_before_scan(tmp_path):
    actual, plan = fixture(tmp_path)
    plan["marker"] = "afc1111111111111111"
    plan["marker_command"] = "kernel uptime " + plan["marker"]
    with patch.object(R, "find_device", new=AsyncMock()) as scan, pytest.raises(ValueError):
        asyncio.run(R.capture(actual, plan, ORACLE, tmp_path))
    scan.assert_not_called()


@pytest.mark.parametrize("mode", ["fast", "default"])
def test_initial_settlement_rejects_extra_activity_or_accepts_already_settled_default_fast(tmp_path, mode):
    actual, plan = fixture(tmp_path, mode=mode)
    transactions = [actual["startup_settlement"], actual["operation"]["normalization"]]
    if mode == "default":
        transactions[1] = actual["operation"]["activity_fast"][0]
    with patch.object(R.R, "observe", return_value={"transactions": transactions, "pending": []}):
        if mode == "fast":
            with pytest.raises(ValueError):
                asyncio.run(R.initial(None, None, actual, plan))
        else:
            first, classification = asyncio.run(R.initial(None, None, actual, plan))
            assert first == actual["startup_settlement"] and classification["mode"] == "default"


def test_timeout_does_not_issue_final_identity(tmp_path):
    actual, plan = fixture(tmp_path)
    actions = SimpleNamespace(run_control=AsyncMock(side_effect=TimeoutError("active bound")))
    with (
        patch.object(R.identity, "identity", new=AsyncMock()) as identify,
        patch.object(
            R,
            "initial",
            new=AsyncMock(return_value=(actual["startup_settlement"], actual["startup_classification"])),
        ),
        pytest.raises(TimeoutError),
    ):
        asyncio.run(R.connected(None, actions, None, actual, plan, ORACLE))
    assert identify.await_count == 1 and identify.await_args.args[2] == "before"
    assert "omitted" in actual["after_error"]
