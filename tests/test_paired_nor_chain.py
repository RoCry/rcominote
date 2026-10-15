"""Real-file iterative source walk; wire body tested separately with full2 pages."""

import copy
import json
import struct
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from test_paired_nor_plan import fixture

from rcominote import protocol as Boyi
from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C


def chain(root, count):
    template, _baseline = fixture(root / "fixture")
    state = copy.deepcopy(template["expected_before"])
    raw_info = bytearray.fromhex(state["device"]["raw"])
    struct.pack_into(">I", raw_info, 4, 59589)
    state["device"] = Boyi.parse_device_info(bytes(raw_info))
    baseline = b"." * 4096
    anchor = root / "legacy"
    (anchor / "second").mkdir(parents=True)
    original = {
        "ok": True,
        "profile": C.legacy.PROFILE,
        "after": state,
        "ended_at": "2026-10-14T09:00:00+00:00",
    }
    oldplan, oldproof = {"names": [C.F.NAME]}, {"verified": True}
    C.S.save(anchor / "report.json", original)
    C.S.save(anchor / "plan.json", oldplan)
    (anchor / "session.btsnoop").write_bytes(b"synthetic anchor body admitted by stub")
    (anchor / "second/download.bin").write_bytes(baseline)
    pins = {name: A.A.sha((anchor / name).read_bytes()) for name in C.LEGACY_PINS}
    refs = {name: C.pins.pinned(anchor / name, sha)[1] for name, sha in pins.items()}
    source = C.source_summary(anchor, original, oldplan, oldproof, baseline, state, refs)
    directories = []
    for index in range(count):
        directory = root / f"node{index}"
        slotdir = directory / template["pages"][0]["directory"]
        (slotdir / "second").mkdir(parents=True)
        plan = copy.deepcopy(template)
        plan.update(parent=source, expected_before=state, planned_at=source["ended_at"])
        for n, op in enumerate(plan["pages"][0]["operations"]):
            nonce = f"rc{2 * index + n:010x}"
            op.update(nonce=nonce, uptime_command=f"kernel uptime {nonce}")
        C.validate_plan(plan)
        C.S.save(directory / "plan.json", plan)
        ended = (datetime.fromisoformat(source["ended_at"]) + timedelta(seconds=1)).isoformat()
        C.S.save(slotdir / "report.json", {"after": state, "ended_at": ended})
        (slotdir / "second/download.bin").write_bytes(baseline)
        original = {
            "profile": C.PROFILE,
            "ok": True,
            "ended_at": ended,
            "plan": C.J.reference(directory, directory / "plan.json"),
            "completed": [{"report": C.J.reference(directory, slotdir / "report.json")}],
            "verification": {"node": index},
        }
        C.S.save(directory / "report.json", original)
        refs = {
            "report": C.J.reference(directory, directory / "report.json"),
            "plan": original["plan"],
            "baseline": C.J.reference(directory, slotdir / "second/download.bin"),
        }
        source = C.source_summary(directory, original, plan, original["verification"], baseline, state, refs)
        directories.append(directory)
    return directories, pins, baseline, source, oldproof


def test_450_parent_nodes_walk_real_files_without_recursion_and_audit_oldest_first(tmp_path):
    directories, pins, baseline, expected, oldproof = chain(tmp_path, 450)
    seen = []

    def admitted(job, plan, directory, previous):
        assert previous == baseline and plan["expected_before"] == expected["latest_info"]
        seen.append(directory)
        return job["verification"]

    with (
        patch.object(C, "LEGACY_PINS", pins),
        patch.object(C.old, "replay", return_value=oldproof) as anchor,
        patch.object(A, "_replay_admitted", side_effect=admitted),
    ):
        ring, state, source = C.parent_gate(directories[-1], None)
    anchor.assert_called_once()
    assert seen == directories
    assert ring == baseline and state == expected["latest_info"] and source == expected
    assert len(source["prior_names"]) == 901


def test_resolved_parent_cycle_rejects_before_anchor_or_body(tmp_path):
    plan, _baseline = fixture(tmp_path / "fixture")
    directory = tmp_path / "cycle"
    directory.mkdir()
    plan["parent"].update(directory=str(directory), profile=C.PROFILE)
    C.S.save(directory / "plan.json", plan)
    C.S.save(
        directory / "report.json",
        {"ok": True, "profile": C.PROFILE, "plan": C.J.reference(directory, directory / "plan.json")},
    )
    with (
        patch.object(C.old, "replay") as anchor,
        patch.object(A, "_replay_admitted") as body,
        pytest.raises(ValueError, match="Cycle"),
    ):
        C.parent_gate(directory, None)
    anchor.assert_not_called()
    body.assert_not_called()


@pytest.mark.parametrize("fault", ["failed", "summary", "plan-ref"])
def test_intermediate_failure_or_untrusted_parent_summary_cannot_be_skipped(tmp_path, fault):
    directories, pins, _baseline, _source, oldproof = chain(tmp_path, 3)
    middle = directories[1]
    job = json.loads((middle / "report.json").read_bytes())
    if fault == "failed":
        job["ok"] = False
    elif fault == "plan-ref":
        job["plan"]["sha256"] = "0" * 64
    else:
        plan = json.loads((middle / "plan.json").read_bytes())
        plan["parent"]["verification"] = {"untrusted": True}
        (middle / "plan.json").write_text(json.dumps(plan))
        job["plan"] = C.J.reference(middle, middle / "plan.json")
    (middle / "report.json").write_text(json.dumps(job))
    with (
        patch.object(C, "LEGACY_PINS", pins),
        patch.object(C.old, "replay", return_value=oldproof),
        patch.object(A, "_replay_admitted", side_effect=lambda job, *_: job["verification"]),
        pytest.raises(ValueError),
    ):
        C.parent_gate(directories[-1], None)
