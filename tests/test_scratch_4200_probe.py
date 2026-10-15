"""Mocked runtime fail-stop linkage only; no synthetic test claims device proof."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_scratch_4200_contract import fixture

from rcominote.experiments import scratch_4200_probe as R


def runtime(tmp_path):
    _captured, plan, baseline = fixture(tmp_path / "synthetic")
    out = tmp_path / "new"
    out.mkdir()
    for label in ("baseline", "overwrite"):
        (out / label).mkdir()
    report = R.C.report(plan) | {"att_packets": [], "transport": {"link": {}}}
    return report, plan, baseline, out


@pytest.mark.parametrize("fault", ["baseline-mismatch", "missing-fast", "partial", "content"])
def test_failure_never_retries_or_performs_additional_producer(tmp_path, fault):
    report, plan, baseline, out = runtime(tmp_path)
    conn = SimpleNamespace(file_list=AsyncMock(return_value=[]))
    actions = SimpleNamespace(run_commands=AsyncMock())
    tx = {"update": {"record": 1}}
    original = ValueError("current candidate rejected")

    async def identity(_conn, owner, key, before, **_kwargs):
        owner[key] = before

    async def download(_conn, _report, op, target):
        if op["operation_id"] == "baseline":
            return baseline if fault != "baseline-mismatch" else bytes(4096)
        (target / "download.bin").write_bytes(b"actual partial" if fault == "partial" else bytes(4096))
        if fault == "partial":
            raise original
        return bytes(4096)

    async def finish(_conn, _monitor, _report, op, _cursor, state, **_kwargs):
        op.update(after=state, slow_settlement=tx)

    async def commands(op, body, *, sd_write_command_index):
        assert body == R.C.recipe(op)[2:-1] and sd_write_command_index == 2
        op.update(writes=[{}] * 6, sd_write_attempted=True)

    async def normalize(_monitor, _conn, _report, op, _cursor):
        op["normalization"] = tx

    actions.run_commands.side_effect = commands
    snapshots = [(report, {"transactions": [tx] * count, "pending": []}, []) for count in (3, 4, 6)]
    with (
        patch.object(R.shared, "identity", new=AsyncMock(side_effect=identity)) as read,
        patch.object(R.C.startup, "wait_startup", new=AsyncMock(return_value=(tx, {}))),
        patch.object(R, "plan_gate"),
        patch.object(R.R, "normalize", new=AsyncMock(side_effect=normalize)) as normalize_mock,
        patch.object(R.shared, "download", new=AsyncMock(side_effect=download)) as transfer,
        patch.object(R.shared, "finish_stage", new=AsyncMock(side_effect=finish)),
        patch.object(R.C.startup, "live_wire", new=AsyncMock(side_effect=snapshots)),
        patch.object(R.R, "observe", return_value={"transactions": [tx] * 3, "pending": []}),
        patch.object(R.C.shared, "baseline_window"),
        patch.object(R.C.shared, "barrier"),
        patch.object(R.C, "actions", return_value={"acks": 6, "f0_frames": 0}),
        patch.object(
            R.N,
            "pre_download_fast",
            new=AsyncMock(side_effect=original if fault == "missing-fast" else None, return_value=[tx]),
        ),
        patch.object(R.W, "default_activity_fast", return_value={}),
        patch.object(R.W, "download_window"),
        patch.object(R.C, "payload", side_effect=original),
        pytest.raises(ValueError),
    ):
        asyncio.run(R.connected(conn, actions, None, report, plan, baseline, out))
    assert not report["ok"] and not report["operation"]["ok"]
    assert actions.run_commands.await_count == int(fault != "baseline-mismatch")
    assert normalize_mock.await_count == (2 if fault in ("partial", "content") else 1)
    assert transfer.await_count == (2 if fault in ("partial", "content") else 1)
    assert read.await_count == 2  # Initial and final actual identity, even content failure.
    assert report["operation"].get("producer_attempted") is (None if fault == "baseline-mismatch" else True)
    assert not (out / "overwrite/sector.bin").exists()
    if fault == "partial":
        assert (out / "overwrite/download.bin").read_bytes() == b"actual partial"
    if fault != "baseline-mismatch":
        assert report["baseline"]["ok"] and report["operation"]["ended_at"]


@pytest.mark.parametrize("fault", ["path", "nonce", "extra-operation", "plan-file"])
def test_pre_io_binding_rejects_mutated_report_or_immutable_plan(tmp_path, fault):
    report, plan, _baseline, out = runtime(tmp_path)
    R.S.save(out / "plan.json", plan)
    report["plan"] = R.J.reference(out, out / "plan.json")
    if fault == "path":
        report["operation"]["name"] = "rc0000000000"
    elif fault == "nonce":
        report["operation"]["nonce"] = "rc0000000000"
    elif fault == "extra-operation":
        report["operations"] = []
    else:
        plan["budget"]["sd_writes"] = 2
    with patch.object(R, "capture", new=AsyncMock()) as capture, pytest.raises(ValueError):
        R.plan_gate(report, plan, out)
    capture.assert_not_called()


def test_failed_top_report_preserves_baseline_and_original_attempts(tmp_path):
    _report, plan, baseline, _out = runtime(tmp_path)
    target = tmp_path / "new-job"

    async def failure(actual, *_args):
        actual["baseline"].update(ok=True, live_complete=True)
        actual["operation"].update(producer_attempted=True, sd_write_attempted=True)
        (target / "overwrite/download.bin").write_bytes(b"real retained partial")
        raise ValueError("candidate failed")

    with (
        patch.object(R.C, "prepare", return_value=(plan, baseline)),
        patch.object(R.C, "source_gate", return_value=baseline),
        patch.object(R, "authorize"),
        patch.object(R, "capture", new=AsyncMock(side_effect=failure)),
        patch.object(R.C, "validate") as audit,
        pytest.raises(ValueError, match="candidate failed"),
    ):
        R.main(tmp_path / "image", tmp_path / "parent", target)
    audit.assert_not_called()
    saved = json.loads((target / "report.json").read_bytes())
    assert not saved["ok"] and saved["baseline"]["ok"] and not saved["operation"]["ok"]
    assert saved["operation"]["producer_attempted"] and saved["operation"]["sd_write_attempted"]
    assert (target / "overwrite/download.bin").read_bytes() == b"real retained partial"
    with pytest.raises(ValueError, match="Original failed"):
        R.replay(target, tmp_path / "image")


def test_content_failure_uses_complete_actual_after_barrier_with_allowed_capacity_drop(tmp_path):
    from test_scratch_4200_contract import refresh_wire

    report, _plan, _baseline = fixture(tmp_path)
    op = report["operation"]
    raw = bytes.fromhex(op["before"]["device"]["raw"])
    free = op["before"]["device"]["free_capacity"] - 1
    raw = raw[:4] + free.to_bytes(4, "big") + raw[8:]
    after = op["before"] | {"device": R.C.Boyi.parse_device_info(raw)}
    for owner in (op, report):
        owner["after"] = after
        last = owner["after_span"][1] - 1
        report["att_packets"][last]["hex"] = (
            b"\x1b\x24\0" + R.C.Boyi.frame(R.C.Boyi.GET_DEVICE_INFO, raw)
        ).hex()
    op.update(barrier_complete=True, live_complete=False, ok=False, error="content parser rejected")
    op["state_verification"] = R.C.verify_state(op["before"], after, sd_write=True)
    report["state_verification"] = R.C.verify_state(after, after, sd_write=False)
    refresh_wire(report, tmp_path)
    assert R.final_state(report) == after
    with patch.object(R.shared.S, "read_identity", new=AsyncMock()):
        asyncio.run(R.shared.identity(None, report, "after", R.final_state(report)))
    assert report["state_verification"]["free_capacity_before"] == free
    assert report["state_verification"]["free_capacity_decrease"] == 0
    assert not op["ok"] and not report["ok"] and "after_error" not in report


@pytest.mark.parametrize("complete", [False, True])
def test_bare_or_inconsistent_after_never_becomes_final_predecessor(tmp_path, complete):
    report, _plan, _baseline = fixture(tmp_path)
    op = report["operation"]
    op["after"] = {}
    op["barrier_complete"] = complete
    report["baseline"]["barrier_complete"] = True
    if complete:
        with pytest.raises(ValueError, match="Identity summary"):
            R.final_state(report)
    else:
        assert R.final_state(report) == report["baseline"]["after"]
