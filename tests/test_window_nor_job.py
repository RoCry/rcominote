"""Synthetic byte/provenance and fail-stop control tests; never live evidence.

Mocked parent/pair replay only isolates job-level linkage, not HCI validity.
Real parent-chain replay is a separate explicit local preflight.
"""

import json
from unittest.mock import patch

import pytest
from test_dual_probe import info
from test_window_nor_contract import fixture as pair_fixture

from rcominote.experiments import window_nor_job as W


def plan_fixture():
    base = pair_fixture()
    return {
        "profile": W.PROFILE,
        "serial": W.OWNED_SERIAL,
        "planned_at": "2026-10-14T10:01:00+00:00",
        "source_image_sha256": W.U.probe.IMAGE_SHA,
        "coverage_basis": W.coverage_basis(),
        "prefix_evidence": W.prefix_source.verify()[1],
        "new_range": [0x2600, 0x3000],
        "max_connections": 5,
        "max_producer_executions": 10,
        "max_sd_test_files": 10,
        "parent": base["parent"],
        "window_parent": base["window_parent"],
        "progress_parent": {
            "directory": "/unit-test/progress",
            "report_sha256": W.PROGRESS_SHA,
            "hci_sha256": W.PROGRESS_HCI_SHA,
            "verification": {"sha256": W.S.audit.sha(bytes([0xB4]) * 512)},
        },
        "slots": [
            {
                "nor_offset": offset,
                "directory": f"{offset:04x}",
                "names": [f"rc{i * 2 + n:010x}" for n in (0, 1)],
            }
            for i, offset in enumerate(W.OFFSETS)
        ],
    }


def original_fixture(plan, index):
    slot = plan["slots"][index]
    report = pair_fixture(slot["nor_offset"])
    report.update(
        parent=plan["parent"],
        window_parent=plan["window_parent"],
        ok=True,
        pair_verified=True,
        final_audit_complete=True,
        before=info(),
        after=info(),
        expected_before=info(),
        predecessor_state_verification=W.verify_state(info(), info(), sd_write=False),
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


def test_join_preserves_actual_distinct_bytes_not_ff_assumptions():
    sectors = [(offset, bytes([i]) * 512) for i, offset in enumerate(W.OFFSETS, 1)]
    head = [bytes([b]) * 512 for b in (0xA0, 0xA2, 0xA4)]
    tail, full = W.join_sectors(sectors, *head)
    assert len(tail) == 2560 and len(full) == 4096
    assert full == b"".join(head) + b"".join(data for _, data in sectors)


@pytest.mark.parametrize("fault", ["gap", "duplicate", "order", "short", "prefix", "2200", "2400"])
def test_join_never_fills_gaps_or_substitutes_prior_blocks(fault):
    sectors = [(offset, bytes([i]) * 512) for i, offset in enumerate(W.OFFSETS)]
    head = [bytes(512)] * 3
    if fault == "gap":
        sectors.pop()
    elif fault == "duplicate":
        sectors[-1] = sectors[-2]
    elif fault == "order":
        sectors.reverse()
    elif fault == "short":
        sectors[-1] = (sectors[-1][0], bytes(511))
    else:
        head[{"prefix": 0, "2200": 1, "2400": 2}[fault]] = bytes(511)
    with pytest.raises(ValueError, match="requires"):
        W.join_sectors(sectors, *head)


@pytest.mark.parametrize(
    "fault",
    [
        "count",
        "offset",
        "type",
        "path",
        "nonce",
        "syntax",
        "budget",
        "basis",
        "profile",
        "progress",
        "prefix",
    ],
)
def test_immutable_plan_cannot_expand_change_basis_or_alias_nonces(fault):
    plan = plan_fixture()
    W.validate_plan(plan)
    if fault == "count":
        plan["slots"].pop()
    elif fault == "offset":
        plan["slots"][0]["nor_offset"] = 0x2400
    elif fault == "type":
        plan["slots"][0]["nor_offset"] = float(W.OFFSETS[0])
    elif fault == "path":
        plan["slots"][0]["directory"] = "../2600"
    elif fault == "nonce":
        plan["slots"][1]["names"][0] = plan["slots"][0]["names"][0]
    elif fault == "syntax":
        plan["slots"][0]["names"][0] = "rcxxx"
    elif fault == "budget":
        plan["max_connections"] = 6
    elif fault == "basis":
        plan["coverage_basis"]["verified_prefix"][1] = 0x3000
    elif fault == "profile":
        plan["profile"] = "bulk"
    elif fault == "prefix":
        plan["prefix_evidence"]["sha256"] = "0" * 64
    else:
        plan["progress_parent"]["report_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        W.validate_plan(plan)


@pytest.mark.parametrize("fault", ["report", "capture"])
def test_progress_hash_failure_does_not_call_complete_replay(tmp_path, fault):
    (tmp_path / "report.json").write_bytes(b"{}")
    (tmp_path / "session.btsnoop").write_bytes(b"invalid")
    hashes = ["0" * 64, W.PROGRESS_HCI_SHA] if fault == "report" else [W.PROGRESS_SHA, "0" * 64]
    with (
        patch.object(W.S.audit, "sha", side_effect=hashes),
        patch.object(W.N, "replay") as replay,
        pytest.raises(ValueError, match="exact successful"),
    ):
        W.progress_gate(tmp_path, tmp_path)
    replay.assert_not_called()


@pytest.mark.parametrize("successes", [1, 2])
def test_first_failure_after_one_or_two_pairs_stops_without_assembly(tmp_path, successes):
    plan = plan_fixture()
    out, parent = tmp_path / "out", tmp_path / "progress"
    parent.mkdir()
    (parent / "report.json").write_text(json.dumps({"after": info()}))
    reports = [original_fixture(plan, i) | {"ok": False} for i in range(5)]
    calls = []

    def run(report, directory, image):
        calls.append(report["nor_offset"])
        if len(calls) > successes:
            report.update(ok=False, error="intentional fail-stop")
            W.S.save(directory / "report.json", report)
            raise ValueError("intentional fail-stop")
        report["ok"] = True
        W.S.save(directory / "report.json", report)

    with (
        patch.object(W, "prepare", return_value=(plan, reports)),
        patch.object(W, "authorize"),
        patch.object(W, "run_pair", side_effect=run),
        patch.object(W.N, "replay", return_value={"synthetic_control_flow_only": True}) as replay,
        patch.object(W, "audit_job") as assemble,
        pytest.raises(ValueError, match="intentional"),
    ):
        W.main(tmp_path / "unused", parent, out)
    assert calls == list(W.OFFSETS[: successes + 1]) and replay.call_count == successes
    assemble.assert_not_called()
    report = json.loads((out / "report.json").read_bytes())
    assert report["ok"] is False and len(report["completed"]) == successes
    assert (out / f"checkpoint-{W.OFFSETS[successes - 1]:04x}.json").is_file()
    assert not (out / "tail.bin").exists() and not (out / "fw1_boot.bin").exists()
    with patch.object(W, "audit_job") as audit, pytest.raises(ValueError, match="Original window job"):
        W.replay(out, tmp_path)
    audit.assert_not_called()


def synthetic_job(tmp_path):
    """Only job linkage is real here: original HCI replay must be mocked explicitly."""
    plan = plan_fixture()
    parent = tmp_path / "early"
    progress_dir = tmp_path / "progress"
    for p in (parent, progress_dir):
        (p / "first").mkdir(parents=True)
    block2200, block2400 = bytes([0xA2]) * 512, bytes([0xA4]) * 512
    (parent / "first/sector.bin").write_bytes(block2200)
    (progress_dir / "first/sector.bin").write_bytes(block2400)
    plan["parent"]["directory"] = str(parent)
    plan["parent"]["verification"]["sha256"] = W.S.audit.sha(block2200)
    plan["progress_parent"]["directory"] = str(progress_dir)
    plan["progress_parent"]["verification"]["sha256"] = W.S.audit.sha(block2400)
    progress = {
        "parent": plan["parent"],
        "window_parent": plan["window_parent"],
        "after": info(),
        "ended_at": "2026-10-14T10:00:00+00:00",
    }
    W.S.save(tmp_path / "job-plan.json", plan)
    job = {
        "profile": W.PROFILE,
        "plan": W.J.reference(tmp_path, tmp_path / "job-plan.json"),
        "started_at": "2026-10-14T10:02:00+00:00",
        "ended_at": "2026-10-14T10:13:00+00:00",
        "completed": [],
        "ok": False,
    }
    results = {}
    for i, slot in enumerate(plan["slots"]):
        directory = tmp_path / slot["directory"]
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
            {"report": W.J.reference(tmp_path, directory / "report.json"), "verification": result}
        )
    return plan, progress, job, results


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing",
        "failed",
        "prestate",
        "summary",
        "parent",
        "nonce",
        "path",
        "offset",
        "pair-time",
        "job-time",
        "reference",
        "prefix-summary",
    ],
)
def test_job_rechecks_each_original_and_full_provenance_before_assembly(tmp_path, fault):
    plan, progress, job, results = synthetic_job(tmp_path)
    report_path = tmp_path / "2600/report.json"
    original = json.loads(report_path.read_bytes())
    if fault == "missing":
        job["completed"].pop()
    elif fault == "failed":
        original["ok"] = False
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
        original["nor_offset"] = 0x2400
    elif fault == "pair-time":
        original["started_at"] = "2026-10-14T09:00:00+00:00"
    elif fault == "job-time":
        job["ended_at"] = "2026-10-14T10:05:00+00:00"
    elif fault == "prefix-summary":
        plan["prefix_evidence"]["input_windows"] = 21
        (tmp_path / "job-plan.json").write_text(json.dumps(plan))
        job["plan"] = W.J.reference(tmp_path, tmp_path / "job-plan.json")
    report_path.write_text(json.dumps(original))
    if fault != "reference":
        job["completed"][0]["report"] = (
            W.J.reference(tmp_path, report_path) if fault != "path" else job["completed"][0]["report"]
        )
    with (
        patch.object(W, "progress_gate", return_value=(plan["progress_parent"], progress)),
        patch.object(W, "parent_names", return_value=set()),
        patch.object(W.N, "replay", side_effect=lambda path, image: results[path.name]),
    ):
        if fault:
            with pytest.raises(ValueError):
                W.audit_job(job, tmp_path, tmp_path)
        else:
            tail, full, proof = W.audit_job(job, tmp_path, tmp_path)
            assert tail == b"".join(bytes([i]) * 512 for i in range(1, 6))
            assert (
                full == W.prefix_source.PREFIX.read_bytes() + bytes([0xA2]) * 512 + bytes([0xA4]) * 512 + tail
            )
            assert proof["partition_bytes"] == 4096


def test_archived_job_requires_original_end_time_before_audit(tmp_path):
    raw = json.dumps({"ok": True, "started_at": "2026-10-14T10:00:00+00:00"}).encode()
    (tmp_path / "report.json").write_bytes(raw)
    with patch.object(W, "audit_job") as audit, pytest.raises(ValueError, match="original end"):
        W.replay(tmp_path, tmp_path)
    audit.assert_not_called()
    assert (tmp_path / "report.json").read_bytes() == raw


def test_failed_capture_keeps_actual_partial_and_does_not_compare_pair(tmp_path):
    report = pair_fixture(0x2600) | {"started_at": W.S.now(), "ok": False, "pair_verified": False}
    (tmp_path / "first").mkdir()

    async def fail(actual, directory, image):
        (directory / "first/download.bin").write_bytes(b"actual partial fixture")
        raise ValueError("capture did not complete")

    with (
        patch.object(W.N, "capture", side_effect=fail),
        patch.object(W.U, "compare_pair") as compare,
        pytest.raises(ValueError, match="capture did not complete"),
    ):
        W.run_pair(report, tmp_path, tmp_path)
    compare.assert_not_called()
    saved = json.loads((tmp_path / "report.json").read_bytes())
    assert saved["ok"] is False and saved["final_audit_complete"] is False
    assert "capture did not complete" in saved["error"] and saved["ended_at"]
    assert (tmp_path / "first/download.bin").read_bytes() == b"actual partial fixture"
