"""Fail-stop/linkage runtime mocks, with aggregate original-failure gates."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_scratch_system_pair_contract import fixture

from rcominote.experiments import scratch_system_pair_probe as R


@pytest.mark.parametrize("stage", ["baseline", "first", "second"])
def test_first_failure_preserves_prior_results_and_never_executes_later_producer(tmp_path, stage):
    _original, plan, baseline = fixture(tmp_path / "synthetic")
    report = R.C.report(plan) | {"att_packets": [], "transport": {"link": {}}}
    out = tmp_path / "new"
    for label in R.C.STAGES:
        (out / label).mkdir(parents=True)
    conn = SimpleNamespace(file_list=AsyncMock(return_value=[]))
    actions = SimpleNamespace(run_commands=AsyncMock())
    tx = {"update": {"record": 1}}
    error = ValueError("current fresh candidate failed")

    async def identity(_conn, owner, key, state, **_kwargs):
        owner[key] = state

    async def download(_conn, _report, op, target):
        data = baseline if op["operation_id"] == "baseline" else bytes(4096)
        (target / "download.bin").write_bytes(b"actual partial" if op["operation_id"] == stage else data)
        if op["operation_id"] == stage:
            raise error
        return data

    async def normalize(_m, _c, _r, op, _cursor):
        op["normalization"] = tx

    async def finish(_c, _m, _r, op, _cursor, before, **_kwargs):
        op.update(after=before, slow_settlement=tx)

    async def commands(op, body, *, sd_write_command_index):
        assert body == R.C.recipe(op)[2:-1] and sd_write_command_index == 2
        op.update(writes=[{}] * 6, sd_write_attempted=True)

    def observe(*_args):
        return {
            "transactions": [tx] * (6 if report["operations"][0].get("live_complete") else 3),
            "pending": [],
        }

    actions.run_commands.side_effect = commands
    snapshots = [(report, {"transactions": [tx] * n, "pending": []}, []) for n in (3, 4, 6, 7, 9)]
    with (
        patch.object(R.shared, "identity", new=AsyncMock(side_effect=identity)),
        patch.object(R.C.startup, "wait_startup", new=AsyncMock(return_value=(tx, {}))),
        patch.object(R, "plan_gate"),
        patch.object(R.R, "normalize", new=AsyncMock(side_effect=normalize)),
        patch.object(R.shared, "download", new=AsyncMock(side_effect=download)),
        patch.object(R.shared, "finish_stage", new=AsyncMock(side_effect=finish)),
        patch.object(R.C.startup, "live_wire", new=AsyncMock(side_effect=snapshots)),
        patch.object(R.R, "observe", side_effect=observe),
        patch.object(R.C.shared, "baseline_window"),
        patch.object(R.C.shared, "barrier"),
        patch.object(R.C, "actions", return_value={}),
        patch.object(R.N, "pre_download_fast", new=AsyncMock(return_value=[tx])),
        patch.object(R.W, "default_activity_fast", return_value={}),
        patch.object(R.W, "download_window"),
        patch.object(R.C, "payload", return_value={"sector_hex": "00" * 512}),
        pytest.raises(ValueError) as raised,
    ):
        asyncio.run(R.connected(conn, actions, None, report, plan, baseline, out))
    assert raised.value is error
    index = R.C.STAGES.index(stage)
    assert actions.run_commands.await_count == index
    assert (out / stage / "download.bin").read_bytes() == b"actual partial"
    for label in R.C.STAGES[index + 1 :]:
        assert not list((out / label).iterdir())
    for op in [report["baseline"], *report["operations"]][:index]:
        assert op["ok"] and op["live_complete"]
    assert not report["ok"] and not (out / R.C.OUTPUT).exists()


@pytest.mark.parametrize("fault", ["count", "nonce", "path", "plan-file"])
def test_immutable_plan_and_exact_two_slot_report_gate_before_capture(tmp_path, fault):
    _original, plan, _baseline = fixture(tmp_path)
    report = R.C.report(plan)
    R.S.save(tmp_path / "plan.json", plan)
    report["plan"] = R.J.reference(tmp_path, tmp_path / "plan.json")
    if fault == "count":
        report["operations"].pop()
    elif fault == "nonce":
        report["operations"][1]["nonce"] = report["operations"][0]["nonce"]
    elif fault == "path":
        report["operations"][0]["name"] = "rc0000000000"
    else:
        plan["budget"]["producers"] = 3
    with patch.object(R, "capture", new=AsyncMock()) as capture, pytest.raises(ValueError):
        R.plan_gate(report, plan, tmp_path)
    capture.assert_not_called()


def archive(directory):
    report, plan, baseline = fixture(directory)
    for op in (report["baseline"], *report["operations"]):
        op["ok"] = True
    report["verification"] = R.C.validate(report, directory, plan, baseline)
    report["ok"] = True
    R.S.save(directory / "plan.json", plan)
    report["plan"] = R.J.reference(directory, directory / "plan.json")
    (directory / R.C.OUTPUT).write_bytes((directory / "first/sector.bin").read_bytes())
    report["outputs"] = {R.C.OUTPUT: R.J.reference(directory, directory / R.C.OUTPUT)}
    R.S.save(directory / "report.json", report)
    return report, plan, baseline


def test_full_original_success_replays_only_with_exact_output_and_source(tmp_path):
    report, _plan, baseline = archive(tmp_path)
    with patch.object(R.C, "source_gate", return_value=baseline):
        assert R.replay(tmp_path, tmp_path / "unused-image") == report["verification"]
    (tmp_path / R.C.OUTPUT).write_bytes(bytes(512))
    with patch.object(R.C, "source_gate", return_value=baseline), pytest.raises(ValueError):
        R.replay(tmp_path, tmp_path / "unused-image")


@pytest.mark.parametrize("flag", ["top", "first", "second"])
def test_original_failure_rejected_before_source_or_pair_recomputation(tmp_path, flag):
    report, _plan, _baseline = archive(tmp_path)
    if flag == "top":
        report["ok"] = False
    else:
        report["operations"][0 if flag == "first" else 1]["ok"] = False
    (tmp_path / "report.json").write_text(json.dumps(report))
    with patch.object(R.C, "source_gate") as source, pytest.raises(ValueError, match="Original failed"):
        R.replay(tmp_path, tmp_path / "unused-image")
    source.assert_not_called()


def test_failed_second_keeps_first_without_aggregate_output(tmp_path):
    _original, plan, baseline = fixture(tmp_path / "synthetic")
    out = tmp_path / "new"

    async def failure(report, *_args):
        report["baseline"].update(ok=True, live_complete=True)
        report["operations"][0].update(ok=True, live_complete=True)
        report["operations"][1].update(producer_attempted=True, sd_write_attempted=True)
        (out / "second/download.bin").write_bytes(b"actual second partial")
        raise ValueError("second failed")

    with (
        patch.object(R.C, "prepare", return_value=(plan, baseline)),
        patch.object(R.C, "source_gate", return_value=baseline),
        patch.object(R, "authorize"),
        patch.object(R, "capture", new=AsyncMock(side_effect=failure)),
        patch.object(R.C, "validate") as audit,
        pytest.raises(ValueError, match="second failed"),
    ):
        R.main(tmp_path / "image", tmp_path / "parent", out)
    audit.assert_not_called()
    saved = json.loads((out / "report.json").read_bytes())
    assert not saved["ok"] and saved["operations"][0]["ok"] and not saved["operations"][1]["ok"]
    assert not (out / R.C.OUTPUT).exists() and "outputs" not in saved


def test_final_predecessor_uses_last_actual_barrier_even_when_content_failed(tmp_path):
    report, _plan, _baseline = fixture(tmp_path)
    first, second = report["operations"]
    first["barrier_complete"] = True
    second.update(barrier_complete=True, live_complete=False, error="content failed")
    assert R.final_state(report) == second["after"]
    second["after"] = {}
    with pytest.raises(ValueError, match="Identity summary"):
        R.final_state(report)
    second["barrier_complete"] = False
    assert R.final_state(report) == first["after"]
