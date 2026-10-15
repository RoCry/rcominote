"""Offline job-linkage tests; mocked checkpoint/pair replay is never HCI proof."""

import copy
import json
from unittest.mock import patch

import pytest
from test_dual_probe import info
from test_window_nor_contract import fixture as pair_fixture

from rcominote.experiments import status_window_job as W
from rcominote.experiments.sd_bootstrap import verify_state


def plan_fixture():
    base = pair_fixture()
    prefix = b"".join(bytes([value]) * 512 for value in (0xA0, 0xA2, 0xA4, 0xA6))
    summary = {
        "directory": "/unit-test/failed-job",
        "parent": base["parent"],
        "window_parent": base["window_parent"],
        "ended_at": "2026-10-14T10:00:00+00:00",
        "prior_names": [f"rc{100 + i:010x}" for i in range(12)],
        "verified_prefix": [0x2000, 0x2800],
        "bytes": 2048,
        "sha256": W.S.audit.sha(prefix),
        "latest_info": info(),
        "pins": {"synthetic_only": True},
    }
    return {
        "profile": W.PROFILE,
        "serial": W.OWNED_SERIAL,
        "planned_at": "2026-10-14T10:01:00+00:00",
        "source_image_sha256": W.U.probe.IMAGE_SHA,
        "checkpoint_directory": summary["directory"],
        "checkpoint": summary,
        "parent": summary["parent"],
        "window_parent": summary["window_parent"],
        "coverage_basis": W.coverage_basis(),
        "status_event_policy": W.E.POLICY,
        "new_range": [0x2800, 0x3000],
        "max_connections": 4,
        "max_producer_executions": 8,
        "max_sd_test_files": 8,
        "policy": W.POLICY,
        "slots": [
            {
                "nor_offset": offset,
                "directory": f"{offset:04x}",
                "names": [f"rc{i * 2 + n:010x}" for n in (0, 1)],
            }
            for i, offset in enumerate(W.OFFSETS)
        ],
    }, prefix


def original_fixture(plan, index):
    slot = plan["slots"][index]
    report = pair_fixture(slot["nor_offset"])
    report.update(
        parent=plan["parent"],
        window_parent=plan["window_parent"],
        status_event_policy=W.E.POLICY,
        ok=True,
        pair_verified=True,
        final_audit_complete=True,
        before=info(),
        after=info(),
        expected_before=info(),
        predecessor_state_verification=verify_state(info(), info(), sd_write=False),
        started_at=f"2026-10-14T10:{3 + index * 2:02d}:00+00:00",
        ended_at=f"2026-10-14T10:{4 + index * 2:02d}:00+00:00",
    )
    for op, name in zip(report["operations"], slot["names"], strict=True):
        path = f"/SD:/RECORDER/Call-{name}.mp3"
        op.update(
            name=name,
            device_path=path,
            dump_command=f"dbg dumpbuf {W.U.probe.BUFFER} 4096 {path}",
            ok=True,
            live_complete=True,
        )
    return report


def synthetic_job(root):
    plan, prefix = plan_fixture()
    W.S.save(root / "job-plan.json", plan)
    job = {
        "profile": W.PROFILE,
        "plan": W.J.reference(root, root / "job-plan.json"),
        "started_at": "2026-10-14T10:02:00+00:00",
        "ended_at": "2026-10-14T10:12:00+00:00",
        "completed": [],
        "ok": False,
    }
    results = {}
    for i, slot in enumerate(plan["slots"]):
        directory = root / slot["directory"]
        (directory / "first").mkdir(parents=True)
        raw = bytes([i + 1]) * 512
        (directory / "first/sector.bin").write_bytes(raw)
        W.S.save(directory / "report.json", original_fixture(plan, i))
        result = {
            "nor_range": [slot["nor_offset"], slot["nor_offset"] + 512],
            "bytes": 512,
            "sha256": W.S.audit.sha(raw),
        }
        results[slot["directory"]] = result
        job["completed"].append(
            {"report": W.J.reference(root, directory / "report.json"), "verification": result}
        )
    return plan, prefix, job, results


def test_join_preserves_distinct_actual_bytes():
    sectors = [(offset, bytes([i]) * 512) for i, offset in enumerate(W.OFFSETS, 1)]
    prefix = bytes(range(256)) * 8
    tail, full = W.join_sectors(sectors, prefix)
    assert tail == b"".join(data for _, data in sectors)
    assert full == prefix + tail and len(tail) == 2048 and len(full) == 4096


@pytest.mark.parametrize("fault", ["missing", "duplicate", "order", "short", "prefix"])
def test_join_rejects_missing_reordered_or_short_bytes(fault):
    sectors = [(offset, bytes(512)) for offset in W.OFFSETS]
    prefix = bytes(2048)
    if fault == "missing":
        sectors.pop()
    elif fault == "duplicate":
        sectors[-1] = sectors[-2]
    elif fault == "order":
        sectors.reverse()
    elif fault == "short":
        sectors[-1] = (sectors[-1][0], bytes(511))
    else:
        prefix = bytes(2047)
    with pytest.raises(ValueError, match="requires"):
        W.join_sectors(sectors, prefix)


@pytest.mark.parametrize(
    "fault",
    [
        "count",
        "offset",
        "type",
        "path",
        "nonce",
        "prior-nonce",
        "syntax",
        "budget",
        "budget-type",
        "basis",
        "profile",
        "policy",
        "checkpoint-path",
        "checkpoint-prefix",
        "checkpoint-hash",
        "parent",
        "time",
    ],
)
def test_fixed_plan_cannot_expand_or_change_coverage_policy_or_nonces(fault):
    plan, _ = plan_fixture()
    W.validate_plan(plan)
    if fault == "count":
        plan["slots"].pop()
    elif fault == "offset":
        plan["slots"][0]["nor_offset"] = 0x2600
    elif fault == "type":
        plan["slots"][0]["nor_offset"] = float(W.OFFSETS[0])
    elif fault == "path":
        plan["slots"][0]["directory"] = "../2800"
    elif fault == "nonce":
        plan["slots"][1]["names"][0] = plan["slots"][0]["names"][0]
    elif fault == "prior-nonce":
        plan["slots"][0]["names"][0] = plan["checkpoint"]["prior_names"][0]
    elif fault == "syntax":
        plan["slots"][0]["names"][0] = "rcxxx"
    elif fault == "budget":
        plan["max_connections"] = 5
    elif fault == "budget-type":
        plan["max_connections"] = 4.0
    elif fault == "basis":
        plan["coverage_basis"]["verified_prefix"][1] = 0x3000
    elif fault == "profile":
        plan["profile"] = "bulk"
    elif fault == "policy":
        plan["status_event_policy"] = "ignore-status"
    elif fault == "checkpoint-path":
        plan["checkpoint_directory"] = "/other"
    elif fault == "checkpoint-prefix":
        plan["checkpoint"]["verified_prefix"][1] = 0x2A00
    elif fault == "checkpoint-hash":
        plan["checkpoint"]["sha256"] = "invalid"
    elif fault == "parent":
        plan["parent"]["report_sha256"] = "0" * 64
    else:
        plan["planned_at"] = "2026-10-14T09:59:00+00:00"
    with pytest.raises(ValueError):
        W.validate_plan(plan)


def test_prepare_checks_checkpoint_before_parent_preparation_or_authorization(tmp_path):
    with (
        patch.object(W.checkpoint, "verify", side_effect=ValueError("checkpoint rejected")),
        patch.object(W.C, "prepare") as constructor,
        patch.object(W, "authorize") as auth,
        pytest.raises(ValueError, match="checkpoint rejected"),
    ):
        W.main(tmp_path, tmp_path / "old", tmp_path / "new")
    constructor.assert_not_called()
    auth.assert_not_called()
    assert not (tmp_path / "new").exists()


def test_prepare_sets_one_shared_profile_and_pins_actual_checkpoint_state(tmp_path):
    plan, prefix = plan_fixture()
    plan["checkpoint"]["directory"] = str(tmp_path.resolve())
    reports = [original_fixture(plan, i) for i in range(4)]
    with (
        patch.object(W.checkpoint, "verify", return_value=(prefix, info(), plan["checkpoint"])),
        patch.object(W.C, "prepare", side_effect=reports) as constructor,
        patch.object(W.S, "now", return_value=plan["planned_at"]),
    ):
        actual, prepared = W.prepare(tmp_path, tmp_path)
    assert [call.args[3] for call in constructor.call_args_list] == list(W.OFFSETS)
    assert actual["checkpoint"] == plan["checkpoint"]
    assert all(r["status_event_policy"] == W.E.POLICY and r["profile"] == W.C.PROFILE for r in prepared)


@pytest.mark.parametrize("successes", [1, 2])
def test_first_failure_stops_later_slots_and_never_assembles(tmp_path, successes):
    plan, bytes_placeholder = plan_fixture()
    out = tmp_path / "out"
    reports = [original_fixture(plan, i) for i in range(4)]
    calls = []

    def run(report, directory, image):
        assert report["expected_before"] == info()
        calls.append(report["nor_offset"])
        if len(calls) > successes:
            report.update(ok=False, error="intentional fail-stop")
            W.S.save(directory / "report.json", report)
            raise ValueError("intentional fail-stop")
        W.S.save(directory / "report.json", report)

    with (
        patch.object(W, "prepare", return_value=(plan, reports)),
        patch.object(W.checkpoint, "verify", return_value=(bytes_placeholder, info(), plan["checkpoint"])),
        patch.object(W, "authorize"),
        patch.object(W, "run_pair", side_effect=run),
        patch.object(W.N, "replay", return_value={"synthetic": True}) as replay,
        patch.object(W, "audit_job") as assemble,
        pytest.raises(ValueError, match="intentional"),
    ):
        W.main(tmp_path, tmp_path, out)
    assert calls == list(W.OFFSETS[: successes + 1]) and replay.call_count == successes
    assemble.assert_not_called()
    saved = json.loads((out / "report.json").read_bytes())
    assert saved["ok"] is False and len(saved["completed"]) == successes
    assert (out / f"checkpoint-{W.OFFSETS[successes - 1]:04x}.json").is_file()
    assert not (out / "tail.bin").exists() and not (out / "fw1_boot.bin").exists()
    for offset in W.OFFSETS[successes + 1 :]:
        assert list((out / f"{offset:04x}/first").iterdir()) == []
        assert list((out / f"{offset:04x}/second").iterdir()) == []
    with patch.object(W, "audit_job") as audit, pytest.raises(ValueError, match="Original status job"):
        W.replay(out, tmp_path)
    audit.assert_not_called()


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing",
        "failed",
        "pair-flag",
        "audit-flag",
        "op-flag",
        "prestate",
        "summary",
        "parent",
        "nonce",
        "path",
        "offset",
        "pair-time",
        "overlap",
        "job-time",
        "end-omitted",
        "reference",
        "policy",
        "producer",
        "source",
        "basis",
        "profile",
        "oracle",
        "short",
        "sha",
        "result",
        "checkpoint",
        "prefix",
        "latest-state",
    ],
)
def test_audit_rechecks_actual_pairs_and_checkpoint_before_assembly(tmp_path, fault):
    plan, prefix, job, results = synthetic_job(tmp_path)
    report_path = tmp_path / "2800/report.json"
    original = json.loads(report_path.read_bytes())
    summary, state = copy.deepcopy(plan["checkpoint"]), info()
    if fault == "missing":
        job["completed"].pop()
    elif fault in ("failed", "pair-flag", "audit-flag"):
        original[
            {"failed": "ok", "pair-flag": "pair_verified", "audit-flag": "final_audit_complete"}[fault]
        ] = False
    elif fault == "op-flag":
        original["operations"][1]["ok"] = False
    elif fault == "prestate":
        original["expected_before"]["serial"] = "changed"
    elif fault == "summary":
        original["predecessor_state_verification"] = {}
    elif fault == "parent":
        original["parent"]["report_sha256"] = "0" * 64
    elif fault == "nonce":
        original["operations"][0]["name"] = "rcffffffffff"
    elif fault == "path":
        job["completed"][0]["report"]["file"] = "../report.json"
    elif fault == "offset":
        original["nor_offset"] = 0x2600
    elif fault == "pair-time":
        original["started_at"] = "2026-10-14T09:00:00+00:00"
    elif fault == "overlap":
        original["ended_at"] = "2026-10-14T10:06:00+00:00"
    elif fault == "job-time":
        job["ended_at"] = "2026-10-14T10:05:00+00:00"
    elif fault == "end-omitted":
        del job["ended_at"]
    elif fault == "policy":
        original["status_event_policy"] = "ignore-status"
    elif fault == "producer":
        original["operations"][1]["producer"] = "dbg fread spi_flash 0x2600"
    elif fault == "source":
        original["source_image_sha256"] = "0" * 64
    elif fault == "basis":
        original["coverage_basis"]["previously_covered"] = [0x2000, 0x2800]
    elif fault == "profile":
        original["profile"] = "per-address-2800"
    elif fault == "oracle":
        original["operations"][0]["oracle"] = {"all_ff": True}
    elif fault == "short":
        (tmp_path / "2800/first/sector.bin").write_bytes(bytes(511))
    elif fault == "sha":
        (tmp_path / "2800/first/sector.bin").write_bytes(bytes([255]) * 512)
    elif fault == "result":
        results["2800"] = results["2800"] | {"nor_range": [0x2600, 0x2800]}
    elif fault == "checkpoint":
        summary["pins"] = {"different_source": True}
    elif fault == "prefix":
        prefix = bytes([255]) * 2048
    elif fault == "latest-state":
        state["serial"] = "changed"
    report_path.write_text(json.dumps(original))
    if fault not in ("reference", "path"):
        job["completed"][0]["report"] = W.J.reference(tmp_path, report_path)
    with (
        patch.object(W.checkpoint, "verify", return_value=(prefix, state, summary)),
        patch.object(W.N, "replay", side_effect=lambda path, image: results[path.name]),
    ):
        if fault:
            with pytest.raises((ValueError, KeyError)):
                W.audit_job(job, tmp_path, tmp_path)
        else:
            tail, full, proof = W.audit_job(job, tmp_path, tmp_path)
            assert tail == b"".join(bytes([i]) * 512 for i in range(1, 5)) and full == prefix + tail
            assert proof["partition_bytes"] == 4096 and proof["new_verified_bytes"] == 2048
            assert proof["connections"] == 4 and proof["independent_producer_executions"] == 8
            assert proof["independent_oracle"] is False


@pytest.mark.parametrize("fault", [None, "output", "summary", "end"])
def test_archived_replay_checks_original_end_and_output_references(tmp_path, fault):
    plan, prefix, job, results = synthetic_job(tmp_path)
    with (
        patch.object(W.checkpoint, "verify", return_value=(prefix, info(), plan["checkpoint"])),
        patch.object(W.N, "replay", side_effect=lambda path, image: results[path.name]),
    ):
        tail, full, result = W.audit_job(job, tmp_path, tmp_path)
        job.update(ok=True, verification=result, outputs={})
        for name, data in (("tail.bin", tail), ("fw1_boot.bin", full)):
            (tmp_path / name).write_bytes(data)
            job["outputs"][name] = W.J.reference(tmp_path, tmp_path / name)
        if fault == "output":
            (tmp_path / "tail.bin").write_bytes(bytes(2048))
        elif fault == "summary":
            job["verification"]["partition_sha256"] = "0" * 64
        elif fault == "end":
            del job["ended_at"]
        W.S.save(tmp_path / "report.json", job)
        if fault:
            with pytest.raises(ValueError):
                W.replay(tmp_path, tmp_path)
        else:
            assert W.replay(tmp_path, tmp_path) == result


@pytest.mark.parametrize("fault", ["exception", "incomplete"])
def test_failed_capture_preserves_actual_partial_without_pair_promotion(tmp_path, fault):
    plan, _ = plan_fixture()
    report = original_fixture(plan, 0)
    (tmp_path / "first").mkdir()

    async def fail(actual, directory, image):
        (directory / "first/download.bin").write_bytes(b"actual partial fixture")
        if fault == "exception":
            raise ValueError("capture did not complete")

    with (
        patch.object(W.N, "capture", side_effect=fail),
        patch.object(W.U, "compare_pair") as compare,
        pytest.raises(ValueError),
    ):
        W.run_pair(report, tmp_path, tmp_path)
    compare.assert_not_called()
    saved = json.loads((tmp_path / "report.json").read_bytes())
    assert saved["ok"] is saved["pair_verified"] is saved["final_audit_complete"] is False
    assert saved["error"] and saved["ended_at"]
    assert (tmp_path / "first/download.bin").read_bytes() == b"actual partial fixture"


def test_failed_pair_replay_stops_before_next_connection_or_checkpoint(tmp_path):
    plan, bytes_placeholder = plan_fixture()
    reports = [original_fixture(plan, i) for i in range(4)]
    out = tmp_path / "out"

    def run(report, directory, image):
        W.S.save(directory / "report.json", report)

    with (
        patch.object(W, "prepare", return_value=(plan, reports)),
        patch.object(W.checkpoint, "verify", return_value=(bytes_placeholder, info(), plan["checkpoint"])),
        patch.object(W, "authorize"),
        patch.object(W, "run_pair", side_effect=run) as capture,
        patch.object(W.N, "replay", side_effect=ValueError("complete replay rejected")),
        patch.object(W, "audit_job") as audit,
        pytest.raises(ValueError, match="complete replay rejected"),
    ):
        W.main(tmp_path, tmp_path, out)
    assert capture.call_count == 1
    audit.assert_not_called()
    saved = json.loads((out / "report.json").read_bytes())
    assert saved["completed"] == [] and saved["ok"] is False
    assert not (out / "checkpoint-2800.json").exists()
    assert not (out / "tail.bin").exists()
    assert list((out / "2a00/first").iterdir()) == []


def test_existing_output_path_never_authorizes_or_connects(tmp_path):
    plan, _ = plan_fixture()
    with (
        patch.object(W, "prepare", return_value=(plan, [])),
        patch.object(W, "authorize") as auth,
        patch.object(W, "run_pair") as capture,
        pytest.raises(FileExistsError),
    ):
        W.main(tmp_path, tmp_path, tmp_path)
    auth.assert_not_called()
    capture.assert_not_called()


def test_equal_ff_data_from_another_address_never_counts_as_fixed_target(tmp_path):
    plan, prefix, job, results = synthetic_job(tmp_path)
    path = tmp_path / "2800/report.json"
    original = json.loads(path.read_bytes())
    original["operations"][1]["producer"] = "dbg fread spi_flash 0x2600"
    path.write_text(json.dumps(original))
    job["completed"][0]["report"] = W.J.reference(tmp_path, path)
    raw = bytes([255]) * 512
    (tmp_path / "2800/first/sector.bin").write_bytes(raw)
    results["2800"]["sha256"] = W.S.audit.sha(raw)
    with (
        patch.object(W.checkpoint, "verify", return_value=(prefix, info(), plan["checkpoint"])),
        patch.object(W.N, "replay") as replay,
        pytest.raises(ValueError, match="producer"),
    ):
        W.audit_job(job, tmp_path, tmp_path)
    replay.assert_not_called()
