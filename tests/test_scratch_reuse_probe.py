"""Offline fixed runtime/failure tests; mocked transport never claims HCI proof."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_dual_probe import fake_actions
from test_scratch_reuse_audit import plan_fixture

from rcominote.experiments import hci_interval_io as IO
from rcominote.experiments import scratch_reuse_probe as R
from rcominote.log_capture import START, STOP


def test_three_body_exact_six_acks_marks_only_dump_as_sd_attempt():
    async def run():
        actions, conn = fake_actions()
        op = plan_fixture()["operations"][0]
        expected = R.C.recipe(op)
        original = conn.client.action_write.side_effect
        states = []

        async def send(packet):
            states.append(op["sd_write_attempted"])
            await original(packet)

        conn.client.action_write.side_effect = send
        await actions.run_commands(op, expected[2:-1], sd_write_command_index=2)
        assert [c.args[0] for c in conn.client.action_write.await_args_list] == expected
        assert states == [False, False, False, False, True, True]
        assert op["ack_count"] == 6 and op["log_session_complete"] and op["pending_hex"] == ""

    asyncio.run(run())


def test_more_than_three_body_packets_rejected_before_write():
    async def run():
        actions, conn = fake_actions()
        with pytest.raises(ValueError, match="at most three"):
            await actions.run_commands({}, [b"a"] * 4, sd_write_command_index=3)
        conn.client.action_write.assert_not_called()

    asyncio.run(run())


def test_cancelled_three_body_cleanup_is_two_seconds_without_sd_attempt():
    original_timeout = asyncio.timeout

    async def run():
        actions, conn = fake_actions()
        original = conn.client.action_write.side_effect

        async def broken(packet):
            if packet == START:
                raise asyncio.CancelledError("stage cancelled")
            if packet == STOP:
                await asyncio.sleep(1)
            await original(packet)

        conn.client.action_write.side_effect = broken
        op = {}
        with pytest.raises(asyncio.CancelledError, match="stage cancelled"):
            await actions.run_commands(op, [b"a", b"b", b"c"], sd_write_command_index=2)
        assert op["cleanup_error"] == "TimeoutError: " and not op["sd_write_attempted"]
        assert conn.client.action_write.await_count == 3

    with patch.object(
        R.asyncio, "timeout", side_effect=lambda n: original_timeout(0.001 if n == 2 else n)
    ) as timeout:
        asyncio.run(run())
    assert any(c.args == (2,) for c in timeout.call_args_list)


@pytest.mark.parametrize("seconds", [55, 70])
def test_monitor_fixed_command_deadline_and_owned_capture(tmp_path, seconds):
    monitor = IO.Monitor(tmp_path, seconds=seconds)
    process = SimpleNamespace(returncode=0)
    with (
        patch.object(IO.asyncio, "create_subprocess_exec", new=AsyncMock(return_value=process)) as spawn,
        patch.object(monitor, "poll", return_value=[{"kind": "controller"}]),
    ):
        asyncio.run(monitor.start())
    assert spawn.await_args.args[5] == f"{seconds}s"
    assert spawn.await_args.args[:5] == ("sudo", "-n", "timeout", "--signal=INT", "--kill-after=2s")
    assert monitor.path.read_bytes() == b""
    monitor.error_file.close()


@pytest.mark.parametrize("seconds", [True, 0, 54, 56, 71, 70.0])
def test_unsupported_monitor_deadline_fails_before_file_creation_or_spawn(tmp_path, seconds):
    with (
        patch.object(IO.asyncio, "create_subprocess_exec", new=AsyncMock()) as spawn,
        pytest.raises(ValueError, match="fixed55 or70"),
    ):
        IO.Monitor(tmp_path, seconds=seconds)
    spawn.assert_not_called()
    assert not list(tmp_path.iterdir())


def runtime_fixture(tmp_path):
    plan = plan_fixture()
    report = R.C.report(plan)
    report.update(att_packets=[], transport={"link": {}})
    for label in R.C.STAGES:
        (tmp_path / label).mkdir()
    conn = SimpleNamespace(file_list=AsyncMock(return_value=[]))
    return plan, report, conn, SimpleNamespace(run_commands=AsyncMock())


async def identity(_conn, owner, key, before, *, writing=False):
    owner[key] = before
    owner[f"{key}_span"] = [0, 1]


def test_default_startup_stops_before_baseline_download_or_actions(tmp_path):
    plan, report, conn, actions = runtime_fixture(tmp_path)
    error = ValueError("Startup tuple is outside FAST policy")
    with (
        patch.object(R, "plan_gate"),
        patch.object(R, "identity", new=AsyncMock(side_effect=identity)),
        patch.object(R.startup, "wait_startup", new=AsyncMock(side_effect=error)),
        patch.object(R, "download", new=AsyncMock()) as download,
        patch.object(R.R, "observe"),
        pytest.raises(ValueError) as raised,
    ):
        asyncio.run(R.connected(conn, actions, None, report, plan, b"." * 4096, tmp_path))
    assert raised.value is error
    actions.run_commands.assert_not_called()
    download.assert_not_called()
    assert not list((tmp_path / "first").iterdir())


@pytest.mark.parametrize("stage", ["baseline", "first", "second"])
def test_first_failure_stops_later_stages_and_preserves_prior_success(tmp_path, stage):
    plan, report, conn, actions = runtime_fixture(tmp_path)
    baseline = b"." * 4096
    failure = ValueError("current stage failed")
    tx = {"update": {"record": 1}}
    observed = {"transactions": [tx] * 3, "pending": []}
    state = {"cursor": 3}

    async def normalize(_m, _c, _r, op, cursor):
        op["normalization"] = tx

    async def download(_c, _r, op, directory):
        data = baseline if op["operation_id"] == "baseline" else bytes(4096)
        (directory / "download.bin").write_bytes(data)
        if op["operation_id"] == stage:
            raise failure
        return data

    async def finish(_c, _m, _r, op, cursor, before, *, writing):
        op.update(after=before, slow_settlement=tx)

    async def run_commands(op, body, *, sd_write_command_index):
        assert len(body) == 3 and sd_write_command_index == 2
        op.update(writes=[{}] * 6, sd_write_attempted=True)

    def observe(*_args):
        return {"transactions": [tx] * state["cursor"], "pending": []}

    async def wire(*_args):
        # before host normalization cursor+1, then complete cursor+3
        cursor = state["cursor"]
        if not observed.get("fast_phase"):
            observed.update(transactions=[tx] * (cursor + 1), fast_phase=True)
        elif cursor == 3 and report["operations"][0].get("after"):
            state["cursor"] = 6
            observed.update(transactions=[tx] * 6, fast_phase=False)
        elif cursor == 6 and report["operations"][1].get("after"):
            state["cursor"] = 9
            observed.update(transactions=[tx] * 9, fast_phase=False)
        return report, observed, []

    # Baseline has its separate complete three-transaction prefix.
    async def live_wire(*args):
        if not report["baseline"].get("live_complete"):
            return report, {"transactions": [tx] * 3, "pending": []}, []
        return await wire(*args)

    actions.run_commands.side_effect = run_commands
    with (
        patch.object(R, "plan_gate"),
        patch.object(R, "identity", new=AsyncMock(side_effect=identity)),
        patch.object(R.startup, "wait_startup", new=AsyncMock(return_value=(tx, {}))),
        patch.object(R.R, "normalize", new=AsyncMock(side_effect=normalize)),
        patch.object(R, "download", new=AsyncMock(side_effect=download)),
        patch.object(R, "finish_stage", new=AsyncMock(side_effect=finish)),
        patch.object(R.startup, "live_wire", new=AsyncMock(side_effect=live_wire)),
        patch.object(R.R, "observe", side_effect=observe),
        patch.object(R.N, "pre_download_fast", new=AsyncMock(return_value=[tx])),
        patch.object(R.evidence, "baseline_window"),
        patch.object(R.evidence, "barrier"),
        patch.object(R.evidence, "actions", return_value={}),
        patch.object(R.W, "default_activity_fast", return_value={}),
        patch.object(R.W, "download_window"),
        patch.object(R.C, "payload", return_value={"sector_hex": "00" * 512}),
        pytest.raises(ValueError) as raised,
    ):
        asyncio.run(R.connected(conn, actions, None, report, plan, baseline, tmp_path))
    assert raised.value is failure
    index = R.C.STAGES.index(stage)
    assert actions.run_commands.await_count == index
    assert (tmp_path / stage / "download.bin").exists()
    for label in R.C.STAGES[index + 1 :]:
        assert not list((tmp_path / label).iterdir())
    for op in [report["baseline"], *report["operations"]][:index]:
        assert op["live_complete"] is True and op["ok"] is True
    assert not report["ok"]


def test_actual_partial_download_saved_when_transport_fails(tmp_path):
    async def transfer(_name, sink, **kwargs):
        sink(b"actual partial")
        raise OSError("link lost")

    conn = SimpleNamespace(download=AsyncMock(side_effect=transfer), offline_allowed=False)
    op = {"operation_id": "first"}
    with pytest.raises(OSError, match="link lost"):
        asyncio.run(R.download(conn, {"att_packets": [], "setup_end": 0}, op, tmp_path))
    assert (tmp_path / "download.bin").read_bytes() == b"actual partial"
    assert op["received_bytes"] == 14 and not conn.offline_allowed


def test_immutable_plan_mutation_rejected_before_authorization_or_capture(tmp_path):
    plan = plan_fixture()
    report = {"plan": {"file": "plan.json"}}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    report["plan"] = R.J.reference(tmp_path, path)
    plan["operations"][0]["name"] = "rc1111111111"
    with pytest.raises(ValueError, match="immutable original"):
        R.plan_gate(report, plan, tmp_path)


def test_failed_second_stage_original_top_flag_and_first_success_preserved(tmp_path):
    plan = plan_fixture()
    baseline = b"." * 4096
    target = tmp_path / "new-job"

    async def failed_capture(report, *_args):
        report["baseline"].update(ok=True, live_complete=True)
        report["operations"][0].update(ok=True, live_complete=True, verification={"actual": "first"})
        report["operations"][1].update(received_bytes=11)
        (target / "second" / "download.bin").write_bytes(b"actual tail")
        raise ValueError("second fresh nonce not retained")

    with (
        patch.object(R.C, "prepare", return_value=(plan, baseline)),
        patch.object(R.C, "source_gate", return_value=baseline),
        patch.object(R, "authorize") as auth,
        patch.object(R, "capture", new=AsyncMock(side_effect=failed_capture)),
        patch.object(R.evidence, "validate") as audit,
        pytest.raises(ValueError, match="second fresh nonce"),
    ):
        R.main(tmp_path / "image", tmp_path / "known", tmp_path / "state", target)
    auth.assert_called_once()
    audit.assert_not_called()
    saved = json.loads((target / "report.json").read_bytes())
    assert saved["ok"] is False and saved["operations"][0]["ok"] is True
    assert saved["operations"][1]["ok"] is False and saved["ended_at"]
    assert (target / "second" / "download.bin").read_bytes() == b"actual tail"
    with pytest.raises(ValueError, match="Original failed"):
        R.replay(target, tmp_path / "image")


@pytest.mark.parametrize("fault", ["missing", "nonce", "policy"])
def test_actual_report_bindings_rejected_before_capture(tmp_path, fault):
    plan = plan_fixture()
    report = R.C.report(plan)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    report["plan"] = R.J.reference(tmp_path, path)
    if fault == "missing":
        report["operations"].pop()
    elif fault == "nonce":
        report["operations"][0]["nonce"] = "rcffffffff00"
    else:
        report["startup_policy"] = R.startup.POLICY
    with (
        patch.object(R, "capture", new=AsyncMock()) as capture,
        pytest.raises(ValueError, match="before I/O"),
    ):
        R.plan_gate(report, plan, tmp_path)
    capture.assert_not_called()
