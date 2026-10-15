"""Offline zero-write runtime, final-identity-before-content and failed replay."""

import asyncio
import copy
import json
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_scratch_postmortem_contract import fixture, plan_fixture

from rcominote.experiments import scratch_postmortem_probe as R


def test_actions_notifications_always_fail_without_consume_or_write():
    with pytest.raises(ValueError, match="Actions notification forbidden"):
        R.no_actions(b"\x1b\x18\0actual")
    with pytest.raises(ValueError, match="Actions notification forbidden"):
        R.forbidden_notification(None, b"actual")
    R.no_actions(b"\x13")


async def identity(_conn, owner, key, before):
    owner[key] = before


@pytest.mark.parametrize(
    "exception", [ValueError("DEFAULT"), TimeoutError("deadline"), asyncio.CancelledError("cancelled")]
)
def test_startup_failure_never_normalizes_or_downloads(exception, tmp_path):
    plan = plan_fixture()
    report = R.C.report(plan) | {"att_packets": [], "transport": {"link": {}}}
    conn = SimpleNamespace(file_list=AsyncMock(return_value=[]))
    with (
        patch.object(R.shared, "identity", new=AsyncMock(side_effect=identity)) as read,
        patch.object(R.C.startup, "wait_startup", new=AsyncMock(side_effect=exception)),
        patch.object(R.R, "normalize", new=AsyncMock()) as normalize,
        patch.object(R.shared, "download", new=AsyncMock()) as download,
        patch.object(R.R, "observe"),
        pytest.raises(type(exception)) as raised,
    ):
        asyncio.run(R.connected(conn, None, report, plan, tmp_path))
    assert raised.value is exception
    normalize.assert_not_called()
    download.assert_not_called()
    assert read.await_count == (2 if isinstance(exception, ValueError) else 1)
    assert not report["operation"]["live_complete"]


def test_complete_transfer_gets_slow_and_final_identity_before_return(tmp_path):
    plan = plan_fixture()
    report = R.C.report(plan) | {"att_packets": [], "transport": {"link": {}}}
    conn = SimpleNamespace(file_list=AsyncMock(return_value=[]))
    sequence = []

    async def read(_conn, owner, key, before):
        sequence.append(key)
        owner[key] = before

    async def download(*_args):
        sequence.append("download")

    async def slow(*_args, **_kwargs):
        sequence.append("slow-identity")

    with (
        patch.object(R.shared, "identity", new=AsyncMock(side_effect=read)),
        patch.object(R.C.startup, "wait_startup", new=AsyncMock(return_value=({}, {}))),
        patch.object(R.R, "normalize", new=AsyncMock()),
        patch.object(R.shared, "download", new=AsyncMock(side_effect=download)),
        patch.object(R.shared, "finish_stage", new=AsyncMock(side_effect=slow)),
        patch.object(R.R, "observe"),
        patch.object(R, "plan_gate"),
        patch.object(R.C, "content") as parser,
    ):
        asyncio.run(R.connected(conn, None, report, plan, tmp_path))
    assert sequence == ["before", "download", "slow-identity", "after"]
    assert report["operation"]["live_complete"] and report["operation"]["ended_at"]
    parser.assert_not_called()


def test_content_failure_retains_complete_original_wire_final_identity_and_readonly_proof(tmp_path):
    captured, plan, previous = fixture(tmp_path / "synthetic")
    target = tmp_path / "new"
    sequence = []
    original_audit = R.C.readonly

    async def capture(report, _plan, out):
        report.update(copy.deepcopy(captured))
        shutil.copyfile(tmp_path / "synthetic/session.btsnoop", out / "session.btsnoop")
        shutil.copyfile(tmp_path / "synthetic/retained/download.bin", out / "retained/download.bin")
        sequence.append("captured-close-and-final-identity")

    def readonly(report, out, plan):
        sequence.append("full-readonly-audit")
        return original_audit(report, out, plan)

    def parser(*_args):
        sequence.append("content-parser")
        assert (target / "readonly-checkpoint.json").exists()
        raise ValueError("fresh nonce not retained")

    with (
        patch.object(R.S, "now", return_value="2026-10-14T10:01:30+00:00"),
        patch.object(R.C, "prepare", return_value=(plan, previous)),
        patch.object(R.C, "source_gate", return_value=previous),
        patch.object(R, "authorize"),
        patch.object(R, "capture", new=AsyncMock(side_effect=capture)),
        patch.object(R.C, "readonly", side_effect=readonly),
        patch.object(R.C, "content", side_effect=parser),
        pytest.raises(ValueError, match="fresh nonce"),
    ):
        R.main(tmp_path / "image", tmp_path / "failed", target)
    saved = json.loads((target / "report.json").read_bytes())
    assert sequence == ["captured-close-and-final-identity", "full-readonly-audit", "content-parser"]
    assert not saved["ok"] and saved["operation"]["ok"] and saved["readonly_proof"]["verified"]
    assert saved["after"] == saved["before"] and saved["disconnect_observation"]["observed"]
    assert saved["content_error"] and "error" not in saved
    assert (target / "retained/download.bin").stat().st_size == 4096
    assert not (target / "retained/sector.bin").exists()
    assert R.C.readonly(saved, target, plan) == saved["readonly_proof"]
    with pytest.raises(ValueError, match="Original failed"):
        R.replay(target, tmp_path / "image")


def test_fixed_report_or_plan_mutation_fails_before_authorization(tmp_path):
    plan = plan_fixture()
    report = R.C.report(plan)
    R.S.save(tmp_path / "plan.json", plan)
    report["plan"] = R.J.reference(tmp_path, tmp_path / "plan.json")
    report["operation"]["name"] = "rc0000000000"
    with (
        patch.object(R, "capture", new=AsyncMock()) as capture,
        pytest.raises(ValueError, match="before I/O"),
    ):
        R.plan_gate(report, plan, tmp_path)
    capture.assert_not_called()
