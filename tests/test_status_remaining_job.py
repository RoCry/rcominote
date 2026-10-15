"""Synthetic fixed-final-sector job linkage; checkpoint/NOR replay explicitly mocked."""

import copy
import json
from unittest.mock import patch

import pytest
from test_controlled_tail_checkpoint import historical_plan as old_plan_fixture
from test_dual_probe import info
from test_status_window_job import original_fixture as pair_original_fixture

from rcominote.experiments import status_remaining_job as K


def plan_fixture():
    old, prefix = old_plan_fixture()
    prefix += bytes([0xAA]) * 512 + bytes([0xAC]) * 512
    summary = old["checkpoint"] | {
        "directory": "/unit-test/partial-controlled-job",
        "verified_prefix": [0x2000, 0x2E00],
        "bytes": 3584,
        "sha256": K.W.S.audit.sha(prefix),
        "ended_at": "2026-10-14T10:00:45+00:00",
        "control_state_parent": old["checkpoint"],
        "control_parent": old["control_parent"],
        "original_job_ok": False,
        "original_failed_pair_verified": False,
        "prior_names": old["checkpoint"]["prior_names"] + [n for slot in old["slots"] for n in slot["names"]],
    }
    plan = old | {
        "profile": K.PROFILE,
        "policy": K.POLICY,
        "checkpoint_directory": summary["directory"],
        "checkpoint": summary,
        "verified_prefix": [0x2000, 0x2E00],
        "new_range": [0x2E00, 0x3000],
        "max_connections": 1,
        "max_producer_executions": 2,
        "max_sd_test_files": 2,
        "slots": [
            {"nor_offset": 0x2E00, "directory": "2e00", "names": [f"rc{2000 + n:010x}" for n in (0, 1)]}
        ],
    }
    return plan, prefix


def original_fixture(plan, index):
    report = pair_original_fixture(plan, index)
    report.update(startup_policy=plan["startup_policy"], control_parent=plan["control_parent"])
    return report


def synthetic_job(root):
    plan, prefix = plan_fixture()
    K.W.S.save(root / "job-plan.json", plan)
    job = {
        "profile": K.PROFILE,
        "plan": K.W.J.reference(root, root / "job-plan.json"),
        "started_at": "2026-10-14T10:02:00+00:00",
        "ended_at": "2026-10-14T10:10:00+00:00",
        "completed": [],
        "ok": False,
    }
    results = {}
    for index, slot in enumerate(plan["slots"]):
        directory = root / slot["directory"]
        (directory / "first").mkdir(parents=True)
        raw = bytes([index + 1]) * 512
        (directory / "first/sector.bin").write_bytes(raw)
        K.W.S.save(directory / "report.json", original_fixture(plan, index))
        result = {
            "nor_range": [slot["nor_offset"], slot["nor_offset"] + 512],
            "bytes": 512,
            "sha256": K.W.S.audit.sha(raw),
        }
        results[slot["directory"]] = result
        job["completed"].append(
            {"report": K.W.J.reference(root, directory / "report.json"), "verification": result}
        )
    return plan, prefix, job, results


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "count",
        "offset",
        "type",
        "path",
        "nonce",
        "old-nonce",
        "budget",
        "status",
        "range",
        "prefix",
        "promoted",
        "chronology",
        "startup-policy",
        "control-state",
    ],
)
def test_plan_fixes_final_sector_two_fresh_names_and_source(fault):
    plan, _ = plan_fixture()
    if fault == "count":
        plan["slots"].pop()
    elif fault == "offset":
        plan["slots"][0]["nor_offset"] = 0x2800
    elif fault == "type":
        plan["slots"][0]["nor_offset"] = float(K.OFFSETS[0])
    elif fault == "path":
        plan["slots"][0]["directory"] = "../2a00"
    elif fault == "nonce":
        plan["slots"][0]["names"][1] = plan["slots"][0]["names"][0]
    elif fault == "old-nonce":
        plan["slots"][0]["names"][0] = plan["checkpoint"]["prior_names"][0]
    elif fault == "budget":
        plan["max_connections"] = 4
    elif fault == "status":
        plan["status_event_policy"] = "skip"
    elif fault == "range":
        plan["new_range"][0] = 0x2800
    elif fault == "prefix":
        plan["checkpoint"]["bytes"] = 2048
    elif fault == "promoted":
        plan["checkpoint"]["original_job_ok"] = True
    elif fault == "chronology":
        plan["planned_at"] = "2026-10-14T09:59:00+00:00"
    elif fault == "startup-policy":
        plan["startup_policy"] = "allow-any-startup"
    elif fault == "control-state":
        plan["control_parent"]["latest_info"] = info(1)
    if fault:
        with pytest.raises(ValueError):
            K.validate_plan(plan)
    else:
        K.validate_plan(plan)


@pytest.mark.parametrize("fault", ["wrong-target", "missing", "short", "prefix"])
def test_assembly_rejects_missing_or_wrong_order_without_filling(fault):
    sectors = [(offset, bytes([i]) * 512) for i, offset in enumerate(K.OFFSETS)]
    prefix = bytes(3584)
    if fault == "wrong-target":
        sectors[0] = (0x2C00, sectors[0][1])
    elif fault == "missing":
        sectors.pop()
    elif fault == "short":
        sectors[-1] = (sectors[-1][0], bytes(511))
    else:
        prefix = bytes(2048)
    with pytest.raises(ValueError):
        K.join_sectors(sectors, prefix)


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing",
        "failed",
        "prestate",
        "state-proof",
        "nonce",
        "source",
        "producer",
        "time",
        "pair-time",
        "policy",
        "parent",
        "short",
        "checkpoint",
        "prefix",
    ],
)
def test_full_assembly_requires_all_actual_pair_and_prefix_proofs(tmp_path, fault):
    plan, prefix, job, results = synthetic_job(tmp_path)
    path = tmp_path / "2e00/report.json"
    original = json.loads(path.read_bytes())
    summary = copy.deepcopy(plan["checkpoint"])
    if fault == "missing":
        job["completed"].pop()
    elif fault == "failed":
        original["final_audit_complete"] = False
    elif fault == "prestate":
        original["expected_before"] = info(1)
    elif fault == "state-proof":
        original["predecessor_state_verification"] = {}
    elif fault == "nonce":
        original["operations"][0]["name"] = "rcffffffffff"
    elif fault == "source":
        original["source_image_sha256"] = "0" * 64
    elif fault == "producer":
        original["operations"][1]["producer"] = "dbg fread spi_flash 0x2800"
    elif fault == "time":
        job["ended_at"] = "2026-10-14T10:03:00+00:00"
    elif fault == "pair-time":
        original["ended_at"] = "2026-10-14T10:11:00+00:00"
    elif fault == "policy":
        original["status_event_policy"] = "skip"
    elif fault == "parent":
        original["window_parent"]["directory"] = "/other"
    elif fault == "short":
        (tmp_path / "2e00/first/sector.bin").write_bytes(bytes(511))
    elif fault == "checkpoint":
        summary["sha256"] = "0" * 64
    elif fault == "prefix":
        prefix = bytes(3584)
    path.write_text(json.dumps(original))
    if job["completed"]:
        job["completed"][0]["report"] = K.W.J.reference(tmp_path, path)
    with (
        patch.object(K.checkpoint, "verify", return_value=(prefix, info(), summary)),
        patch.object(K.control_source, "verify", return_value=plan["control_parent"]),
        patch.object(K.W.N, "replay", side_effect=lambda p, image: results[p.name]),
    ):
        if fault:
            with pytest.raises(ValueError):
                K.audit_job(job, tmp_path, tmp_path)
        else:
            tail, full, result = K.audit_job(job, tmp_path, tmp_path)
            assert tail == bytes([1]) * 512 and full == prefix + tail
            assert len(full) == 4096 and result["new_verified_bytes"] == 512
            assert result["connections"] == 1 and result["independent_producer_executions"] == 2
            assert result["independent_oracle"] is False


def test_first_failure_stops_without_retry_or_assembly(tmp_path):
    plan, prefix = plan_fixture()
    reports = [original_fixture(plan, 0)]
    out = tmp_path / "new"

    def fail(report, directory, image):
        assert report["expected_before"] == info()
        report.update(ok=False, error="first failure")
        K.W.S.save(directory / "report.json", report)
        raise ValueError("first failure")

    with (
        patch.object(K, "prepare", return_value=(plan, reports)),
        patch.object(K.checkpoint, "verify", return_value=(prefix, info(), plan["checkpoint"])),
        patch.object(K.control_source, "verify", return_value=plan["control_parent"]) as control,
        patch.object(K.W, "authorize"),
        patch.object(K.W, "run_pair", side_effect=fail) as capture,
        patch.object(K.W.N, "replay") as replay,
        patch.object(K, "audit_job") as audit,
        pytest.raises(ValueError, match="first failure"),
    ):
        K.main(tmp_path, tmp_path, tmp_path, out)
    capture.assert_called_once()
    replay.assert_not_called()
    audit.assert_not_called()
    assert control.call_count == 2
    assert all(call.args[2] == plan["checkpoint"]["control_state_parent"] for call in control.call_args_list)
    saved = json.loads((out / "report.json").read_bytes())
    assert saved["ok"] is False and saved["completed"] == []
    assert not (out / "fw1_boot.bin").exists() and not (out / "tail.bin").exists()
    with patch.object(K, "audit_job") as replay_audit, pytest.raises(ValueError, match="original success"):
        K.replay(out, tmp_path)
    replay_audit.assert_not_called()


@pytest.mark.parametrize("fault", [None, "output", "summary", "end"])
def test_archived_outputs_require_original_end_and_replayed_bytes(tmp_path, fault):
    plan, prefix, job, results = synthetic_job(tmp_path)
    with (
        patch.object(K.checkpoint, "verify", return_value=(prefix, info(), plan["checkpoint"])),
        patch.object(K.control_source, "verify", return_value=plan["control_parent"]),
        patch.object(K.W.N, "replay", side_effect=lambda p, image: results[p.name]),
    ):
        tail, full, result = K.audit_job(job, tmp_path, tmp_path)
        job.update(ok=True, outputs={}, verification=result)
        for name, raw in (("tail.bin", tail), ("fw1_boot.bin", full)):
            (tmp_path / name).write_bytes(raw)
            job["outputs"][name] = K.W.J.reference(tmp_path, tmp_path / name)
        if fault == "output":
            (tmp_path / "fw1_boot.bin").write_bytes(bytes(4096))
        elif fault == "summary":
            job["verification"]["partition_sha256"] = "0" * 64
        elif fault == "end":
            del job["ended_at"]
        K.W.S.save(tmp_path / "report.json", job)
        if fault:
            with pytest.raises(ValueError):
                K.replay(tmp_path, tmp_path)
        else:
            assert K.replay(tmp_path, tmp_path) == result


def test_checkpoint_failure_precedes_output_creation_or_authorization(tmp_path):
    with (
        patch.object(K.checkpoint, "verify", side_effect=ValueError("checkpoint rejected")),
        patch.object(K.W.C, "prepare") as prepare,
        patch.object(K.W, "authorize") as auth,
        pytest.raises(ValueError, match="checkpoint rejected"),
    ):
        K.main(tmp_path, tmp_path, tmp_path, tmp_path / "new")
    assert not (tmp_path / "new").exists()
    prepare.assert_not_called()
    auth.assert_not_called()


def test_changed_control_after_prepare_stops_before_authorization_or_pair(tmp_path):
    plan, prefix = plan_fixture()
    reports = [original_fixture(plan, index) for index in range(len(plan["slots"]))]
    changed = copy.deepcopy(plan["control_parent"]) | {"references": {"changed": True}}
    with (
        patch.object(K, "prepare", return_value=(plan, reports)),
        patch.object(K.checkpoint, "verify", return_value=(prefix, info(), plan["checkpoint"])),
        patch.object(K.control_source, "verify", return_value=changed),
        patch.object(K.W, "authorize") as authorize,
        patch.object(K.W, "run_pair") as capture,
        pytest.raises(ValueError, match="control admission"),
    ):
        K.main(tmp_path, tmp_path, tmp_path, tmp_path / "out")
    authorize.assert_not_called()
    capture.assert_not_called()
