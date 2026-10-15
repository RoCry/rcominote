"""Offline runtime control/fail-stop and shared Actions compatibility tests."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from test_dual_probe import fake_actions, info, operation

from rcominote.experiments import startup_ram_probe as R
from rcominote.experiments import window_ram_audit as common
from rcominote.log_capture import START, STOP
from rcominote.log_probe import ACK, PREPARE


def runtime_fixture():
    report = {
        "expected_before": info(),
        "att_packets": [],
        "transport": {"link": {}},
        "operations": [
            {"operation_id": label, "name": R.C.RAM.NAME, "sd_write_attempted": False}
            for label in ("first", "second")
        ],
    }
    return (
        report,
        SimpleNamespace(file_list=AsyncMock(return_value=[])),
        SimpleNamespace(run_commands=AsyncMock()),
    )


async def identity(_conn, owner, key, expected):
    owner[key] = expected


def test_empty_body_pulse_has_three_exact_writes_and_preserves_f0_without_sd_flag():
    async def run():
        actions, conn = fake_actions()
        original = conn.client.action_write.side_effect
        text = b"background"
        payload = b"\0" + len(text).to_bytes(2, "little") + text
        frame = b"\x1d\xf0\x81" + len(payload).to_bytes(2, "little") + payload

        async def send(packet):
            if packet == START:
                actions.receive(None, frame[:7])
                actions.receive(None, frame[7:])
            await original(packet)

        conn.client.action_write.side_effect = send
        op = {}
        await actions.run_commands(op, [], sd_write_command_index=None)
        assert [call.args[0] for call in conn.client.action_write.await_args_list] == [PREPARE, START, STOP]
        assert op["ack_count"] == 3 and op["log_session_complete"] and not op["sd_write_attempted"]
        assert any(row.get("text") == "background" for row in op["frames"])
        assert op["pending_hex"] == "" and op["end_received"]

    asyncio.run(run())


def test_legacy_actions_run_still_has_five_acks_and_sd_write_attempt():
    async def run():
        actions, conn = fake_actions()
        op = operation()
        await actions.run(op)
        assert len(conn.client.action_write.await_args_list) == op["ack_count"] == 5
        assert op["sd_write_attempted"] is True and op["log_session_complete"] is True

    asyncio.run(run())


@pytest.mark.parametrize("index", [0, True, -1])
def test_empty_body_invalid_sd_index_fails_before_any_write(index):
    async def run():
        actions, conn = fake_actions()
        with pytest.raises(ValueError, match="explicit valid SD-write index"):
            await actions.run_commands({}, [], sd_write_command_index=index)
        conn.client.action_write.assert_not_called()

    asyncio.run(run())


def test_early_f1_after_prepare_retires_pulse_without_start_or_console_body():
    async def run():
        actions, conn = fake_actions()

        async def early(_packet):
            actions.receive(None, ACK)
            actions.receive(None, b"\x1d\xf1\x81\0\0")

        conn.client.action_write.side_effect = early
        op = {}
        with pytest.raises(ValueError, match="exact request"):
            await actions.run_commands(op, [], sd_write_command_index=None)
        assert [call.args[0] for call in conn.client.action_write.await_args_list] == [PREPARE]
        assert not op["sd_write_attempted"] and not op["log_session_complete"]
        assert isinstance(conn.failure, RuntimeError)

    asyncio.run(run())


def test_failed_empty_pulse_cleanup_stop_is_bounded_and_original_failure_retained():
    original_timeout = asyncio.timeout

    async def run():
        actions, conn = fake_actions()
        original = conn.client.action_write.side_effect

        async def broken(packet):
            if packet == START:
                actions.receive(None, b"bad-frame")
            elif packet == STOP:
                await asyncio.sleep(1)
            else:
                await original(packet)

        conn.client.action_write.side_effect = broken
        op = {}
        with pytest.raises(ValueError):
            await actions.run_commands(op, [], sd_write_command_index=None)
        assert op["cleanup_error"] == "TimeoutError: " and not op["sd_write_attempted"]
        assert [call.args[0] for call in conn.client.action_write.await_args_list].count(STOP) == 1

    with patch.object(
        R.asyncio, "timeout", side_effect=lambda seconds: original_timeout(0.001 if seconds == 2 else seconds)
    ) as bounded:
        asyncio.run(run())
    assert any(call.args == (2,) for call in bounded.call_args_list)


@pytest.mark.parametrize("phase", ["seed", "data"])
@pytest.mark.parametrize("exception_type", [asyncio.CancelledError, TimeoutError])
def test_timeout_or_cancellation_preserves_original_failure_and_sends_no_final_identity(
    phase, exception_type
):
    report, conn, actions = runtime_fixture()
    error = exception_type("bounded failure")
    with (
        patch.object(R, "readonly_identity", new=AsyncMock(side_effect=identity)) as read,
        patch.object(R.C.startup, "wait_startup", new=AsyncMock(side_effect=error)),
        patch.object(R.R, "observe") as observe,
        pytest.raises(exception_type) as raised,
    ):
        asyncio.run(
            R.seed_connected(conn, None, report)
            if phase == "seed"
            else R.data_connected(conn, actions, None, report, None, bytes(4096))
        )
    assert raised.value is error and read.await_count == 1 and read.await_args.args[2] == "before"
    assert "omitted after timeout/cancellation" in report["after_error"]
    observe.assert_not_called()
    actions.run_commands.assert_not_called()


@pytest.mark.parametrize("fault", ["startup-fast", "pending", "missing-fast", "stale-fast"])
def test_default_and_causal_fast_gates_fail_before_host_normalization_or_download(tmp_path, fault):
    report, conn, actions = runtime_fixture()
    snapshot = {"transactions": [None], "pending": [{}] if fault == "pending" else []}
    with (
        patch.object(R, "readonly_identity", new=AsyncMock(side_effect=identity)),
        patch.object(
            R.C.startup,
            "wait_startup",
            new=AsyncMock(
                return_value=({"startup": True}, {"mode": "fast" if fault == "startup-fast" else "default"})
            ),
        ),
        patch.object(R.R, "observe", return_value=snapshot),
        patch.object(R.evidence, "pulse", return_value={"acks": 3}),
        patch.object(
            R.R,
            "wait_transaction",
            new=AsyncMock(
                side_effect=TimeoutError("FAST absent") if fault == "missing-fast" else None,
                return_value={"actual_fast": True},
            ),
        ),
        patch.object(R, "live_fast_proof", new=AsyncMock(side_effect=ValueError("FAST before pulse"))),
        patch.object(R.R, "normalize", new=AsyncMock()) as normalize,
        patch.object(R.R, "download", new=AsyncMock()) as download,
        pytest.raises((ValueError, TimeoutError)),
    ):
        asyncio.run(R.data_connected(conn, actions, None, report, tmp_path, bytes(4096)))
    normalize.assert_not_called()
    download.assert_not_called()
    assert actions.run_commands.await_count == int(fault in ("missing-fast", "stale-fast"))
    if actions.run_commands.await_count:
        assert actions.run_commands.await_args.args[1] == []
        assert actions.run_commands.await_args.kwargs == {"sd_write_command_index": None}


def test_actual_initial_state_mismatch_fails_before_file_list_or_pulse():
    report, conn, actions = runtime_fixture()

    async def different(_conn, owner, key):
        owner[key] = info(1)

    with (
        patch.object(R.S, "read_identity", new=AsyncMock(side_effect=different)),
        patch.object(R.C.startup, "wait_startup", new=AsyncMock()) as startup,
        pytest.raises(ValueError, match="bounded SD capacity"),
    ):
        asyncio.run(R.data_connected(conn, actions, None, report, None, bytes(4096)))
    conn.file_list.assert_not_called()
    startup.assert_not_called()
    actions.run_commands.assert_not_called()


def test_successful_runtime_uses_two_pulses_and_exact_seven_transaction_indices(tmp_path):
    report, conn, actions = runtime_fixture()
    for op in report["operations"]:
        (tmp_path / op["operation_id"]).mkdir()
    count = 1
    events = []

    async def stage(_monitor, _conn, _link, *, index, origin, parameters, seconds):
        nonlocal count
        assert count == index
        events.append(("fast" if parameters == R.R.FAST else "slow", index))
        count += 1
        return {"stage": index}

    async def normalize(_monitor, _conn, _report, _op, index):
        nonlocal count
        assert count == index
        events.append(("host", index))
        count += 1

    async def pulse(op, commands, *, sd_write_command_index):
        assert commands == [] and sd_write_command_index is None
        events.append(("pulse", op["operation_id"]))

    async def download(_conn, _report, op, _directory, _oracle):
        events.append(("download", op["operation_id"]))

    actions.run_commands.side_effect = pulse
    with (
        patch.object(R, "readonly_identity", new=AsyncMock(side_effect=identity)),
        patch.object(R.C.startup, "wait_startup", new=AsyncMock(return_value=({}, {"mode": "default"}))),
        patch.object(R.R, "observe", side_effect=lambda *_: {"transactions": [None] * count, "pending": []}),
        patch.object(R.evidence, "pulse", return_value={"acks": 3}),
        patch.object(R.R, "wait_transaction", new=AsyncMock(side_effect=stage)),
        patch.object(R, "live_fast_proof", new=AsyncMock(return_value={"causal": True})),
        patch.object(R.R, "normalize", new=AsyncMock(side_effect=normalize)),
        patch.object(R.R, "download", new=AsyncMock(side_effect=download)),
    ):
        asyncio.run(R.data_connected(conn, actions, None, report, tmp_path, bytes(4096)))
    assert events == [
        ("pulse", "first"),
        ("fast", 1),
        ("host", 2),
        ("download", "first"),
        ("slow", 3),
        ("pulse", "second"),
        ("fast", 4),
        ("host", 5),
        ("download", "second"),
        ("slow", 6),
    ]
    assert count == 7 and all(op["live_complete"] for op in report["operations"])
    assert all(op["sd_write_attempted"] is False for op in report["operations"])


@pytest.mark.parametrize("error_type", [ValueError, asyncio.CancelledError])
def test_failed_phase_keeps_original_partial_bytes_and_failed_flags(tmp_path, error_type):
    report, _, _ = runtime_fixture()
    report.update(ok=False, profile="explicit synthetic phase")
    partial = tmp_path / "first"
    partial.mkdir()

    async def fail(_report, out, _kind, _oracle):
        (out / "first/download.bin").write_bytes(b"actual synthetic partial")
        raise error_type("original capture failure")

    with (
        patch.object(R.C, "phase", return_value=report),
        patch.object(R, "capture_phase", new=AsyncMock(side_effect=fail)),
        patch.object(R.evidence, "data") as audit,
        pytest.raises(error_type),
    ):
        asyncio.run(R.run_phase({}, "data", tmp_path, bytes(4096)))
    audit.assert_not_called()
    saved = json.loads((tmp_path / "report.json").read_bytes())
    assert saved["ok"] is False and saved["error"] == f"{error_type.__name__}: original capture failure"
    assert (partial / "download.bin").read_bytes() == b"actual synthetic partial"
    assert "verification" not in saved


def test_monitor_exit_cannot_reuse_cached_disconnect():
    monitor = SimpleNamespace(
        process=SimpleNamespace(returncode=0), poll=Mock(), snoop=SimpleNamespace(events=[])
    )
    with pytest.raises(RuntimeError, match="Monitor stopped"):
        asyncio.run(R.observe_disconnect(monitor, {"transport": {"link": {"handle": 1}}}))
    monitor.poll.assert_not_called()


@pytest.mark.parametrize("changed", [False, True])
def test_live_causal_proof_waits_only_for_capture_tail_and_matching_host_prefix(changed):
    report = {"transport": {"link": {"handle": 1}}, "att_packets": [{"direction": "tx", "hex": "aa"}]}
    monitor = SimpleNamespace(path=SimpleNamespace(read_bytes=Mock(return_value=b"synthetic")))
    snapshots = [
        {"pending": [{"kind": "capture-tail"}], "records": 1},
        {"pending": [], "records": 2},
    ]
    with (
        patch.object(R.R, "observe"),
        patch.object(R.C.startup.parameters, "inspect", side_effect=snapshots),
        patch.object(
            R.dual_hci, "att_packets", return_value=[{"direction": "tx", "hex": "bb" if changed else "aa"}]
        ),
        patch.object(common, "wire_positions", return_value=[(2, 2, 100)]),
        patch.object(R.evidence, "activity_fast", return_value={"causal": True}) as proof,
        patch.object(R.asyncio, "sleep", new=AsyncMock()),
    ):
        if changed:
            with pytest.raises(ValueError, match="Changed/extra"):
                asyncio.run(R.live_fast_proof(monitor, None, report, {"activity_fast": {}}, {}))
            proof.assert_not_called()
        else:
            assert asyncio.run(R.live_fast_proof(monitor, None, report, {"activity_fast": {}}, {})) == {
                "causal": True
            }
            proof.assert_called_once()


def test_seed_failure_stops_before_data_connection(tmp_path):
    for kind in R.C.PHASES:
        (tmp_path / kind).mkdir()
    (tmp_path / "plan.json").write_text("{}")
    job = {"plan": R.J.reference(tmp_path, tmp_path / "plan.json"), "phases": {}}

    async def failed(_plan, kind, out, _oracle):
        assert kind == "seed"
        R.S.save(out / "report.json", {"ok": False, "error": "seed failed"})
        raise ValueError("seed failed")

    with (
        patch.object(R, "plan_gate"),
        patch.object(R.C, "source_gate", return_value=bytes(4096)),
        patch.object(R, "run_phase", new=AsyncMock(side_effect=failed)) as run,
        pytest.raises(ValueError, match="seed failed"),
    ):
        asyncio.run(R.run_control(job, {}, tmp_path, tmp_path, bytes(4096)))
    assert run.await_count == 1 and set(job["phases"]) == {"seed"}
    assert not (tmp_path / "data/report.json").exists()


def test_bad_preflight_never_creates_output_or_authorizes(tmp_path):
    with (
        patch.object(R.C, "prepare", side_effect=ValueError("state/source changed")),
        patch.object(R, "authorize") as authorize,
        pytest.raises(ValueError, match="state/source changed"),
    ):
        R.main(tmp_path, tmp_path, tmp_path, tmp_path / "never")
    authorize.assert_not_called()
    assert not (tmp_path / "never").exists()


def test_source_recheck_failure_after_plan_save_never_authorizes(tmp_path):
    out = tmp_path / "new"
    with (
        patch.object(R.C, "prepare", return_value=({}, bytes(4096))),
        patch.object(R, "plan_gate"),
        patch.object(R.C, "source_gate", side_effect=ValueError("source changed after prepare")),
        patch.object(R, "authorize") as authorize,
        pytest.raises(ValueError, match="source changed after prepare"),
    ):
        R.main(tmp_path, tmp_path, tmp_path, out)
    authorize.assert_not_called()
    assert json.loads((out / "report.json").read_bytes())["ok"] is False


def test_in_memory_plan_change_rejected_before_source_gate(tmp_path):
    (tmp_path / "plan.json").write_text('{"phases": ["seed", "data"]}')
    job = {"plan": R.J.reference(tmp_path, tmp_path / "plan.json")}
    with pytest.raises(ValueError, match="In-memory control plan"):
        R.plan_gate(job, {"phases": ["data"]}, tmp_path)


def test_replay_does_not_promote_original_control_failure(tmp_path):
    original = b'{"ok": false}'
    (tmp_path / "report.json").write_bytes(original)
    with patch.object(R.evidence, "validate") as audit, pytest.raises(ValueError, match="Original"):
        R.replay(tmp_path, tmp_path)
    audit.assert_not_called()
    assert (tmp_path / "report.json").read_bytes() == original
