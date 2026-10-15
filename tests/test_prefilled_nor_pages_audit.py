"""Full synthetic paired-page evidence and cross-page ownership; no devices."""

import json
import shutil
from unittest.mock import patch

import pytest
from test_nor_freshness import place
from test_paired_nor_audit import relocate_wire, replace_download, shift_clock
from test_prefilled_nor_control import RAM
from test_prefilled_nor_pages import fixture, validate
from test_scratch_reuse_parser import SECTOR, chain

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_nor_pages as N


@patch.object(P, "RAM_SHA", A.A.sha(RAM))
def archive(root, *, two=False, parent=None):
    first, plan, _page, baseline = fixture(root)
    delta = 90 if parent else 0
    if parent:
        source, baseline = parent
        plan.update(parent=source, expected_before=source["latest_info"], planned_at=source["ended_at"])
        directory = root / plan["pages"][0]["directory"]
        replace_download(first, directory, "baseline", baseline)
        first = shift_clock(first, delta)
        relocate_wire(first, directory, delta * 1_000_000)
    pages = [first]
    if two:
        temporary = root / "temporary"
        second, extra, _page, _baseline = fixture(temporary, 0x1EC400)
        old = temporary / extra["pages"][0]["directory"]
        slot = extra["pages"][0] | {"page_index": 1, "directory": "page1-1ec400"}
        directory = root / slot["directory"]
        shutil.move(old, directory)
        shutil.rmtree(temporary)
        previous = (root / plan["pages"][0]["directory"] / "second/download.bin").read_bytes()
        replace_download(second, directory, "baseline", previous)
        second = shift_clock(second, 90 + delta)
        relocate_wire(second, directory, (90 + delta) * 1_000_000)
        plan["pages"].append(slot)
        plan["offsets"].append(slot["nor_offset"])
        plan["budget"] = N.budgets(2)
        pages.append(second)
    (root / "plan.json").write_text(json.dumps(plan))
    reference = C.J.reference(root, root / "plan.json")
    state, ended, previous = plan["expected_before"], plan["parent"]["ended_at"], baseline
    receipts, proofs = [], []
    with patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])):
        for index, (slot, actual) in enumerate(zip(plan["pages"], pages, strict=True)):
            directory = root / slot["directory"]
            page = C.page_plan(plan, index, state, ended)
            actual.update({k: page[k] for k in C.fields(page)})
            actual["plan"] = reference
            history, predecessor = previous, previous
            for op in actual["operations"]:
                if op["kind"] == "prefill":
                    data = RAM
                else:
                    at = (
                        (500 if op["operation_id"] == "first" else 2800)
                        if index
                        else (300 if op["operation_id"] == "first" else 2600)
                    )
                    data = place(chain(op["nonce"], page["nor_offset"], SECTOR), at, initial=history)
                    replace_download(actual, directory, op["operation_id"], data)
                op["verification"] = N.content(op, data, predecessor, RAM, page, history)
                if op["kind"] == "nor":
                    history = data
                predecessor = data
            proof = N.validate(actual, directory, page, previous)
            actual.update(ok=True, verification=proof)
            C.S.save(directory / "report.json", actual)
            receipts.append(A.ledger_entry(root, slot, actual, proof))
            proofs.append(proof)
            previous, state, ended = predecessor, actual["after"], actual["ended_at"]
    job = {
        "profile": N.PROFILE,
        "budget": plan["budget"],
        "plan": reference,
        "ok": True,
        "started_at": pages[0]["started_at"],
        "ended_at": ended,
        "completed": receipts,
        "verification": A.job_proof(plan, proofs),
    }
    C.S.save(root / "report.json", job)
    return job, plan, baseline


def test_two_complete_pages_replay_all_wire_and_carry_previous_actual_second(tmp_path):
    job, plan, baseline = archive(tmp_path, two=True)
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
    ):
        proofs, current, state = A.completed_prefix(job, plan, tmp_path, baseline)
        assert A._replay_admitted(job, plan, tmp_path, baseline) == job["verification"]
    assert [p["raw_range"] for p in proofs] == [[0x1EC200, 0x1EC400], [0x1EC400, 0x1EC600]]
    assert current == (tmp_path / "page1-1ec400/second/download.bin").read_bytes()
    assert state == job["completed"][-1]["after"]
    assert len(job["completed"][0]["rings"]) == 5
    assert job["verification"]["paired_bytes"] == 1024
    assert job["verification"]["unique_global_coverage_not_evaluated"] is True


@pytest.mark.parametrize(
    "fault",
    [
        "different",
        "wrong-history",
        "ram",
        "missing-fast",
        "pending",
        "final-state",
        "close",
        "original-flag",
        "error",
        "future-nonce",
    ],
)
def test_equal_candidates_cannot_bypass_full_source_transfer_and_final_gates(tmp_path, fault):
    actual, plan, page, baseline = fixture(tmp_path)
    path = tmp_path / plan["pages"][0]["directory"]
    first, second = actual["operations"][1], actual["operations"][3]
    if fault == "different":
        data = place(
            chain(second["nonce"], page["nor_offset"], bytes(reversed(SECTOR))),
            2600,
            initial=(path / "first/download.bin").read_bytes(),
        )
        replace_download(actual, path, "second", data)
        with patch.object(P, "RAM_SHA", A.A.sha(RAM)):
            second["verification"] = N.content(
                second, data, RAM, RAM, page, (path / "first/download.bin").read_bytes()
            )
        (path / "second/sector.bin").write_bytes(bytes(reversed(SECTOR)))
    elif fault == "wrong-history":
        second["verification"]["freshness"]["marker_previous_ring_sha256"] = A.A.sha(RAM)
    elif fault == "ram":
        replace_download(actual, path, "prefill-first", b"X" * 4095 + b"H")
    elif fault == "missing-fast":
        first["pre_download_fast"] = []
    elif fault == "pending":
        rows = actual["att_packets"][first["actions_start"] : first["actions_end"]]
        last = [row for row in rows if row["hex"].startswith("1b1800")][-1]
        last["hex"] = last["hex"][:-2]  # Actual captured F1 is incomplete, not a summary edit.
        replace_download(actual, path, "first", (path / "first/download.bin").read_bytes())
        actual["hci_capture"]["bytes"] = len((path / "session.btsnoop").read_bytes())
    elif fault == "final-state":
        actual["after"] = actual["before"] | {"changed": True}
    elif fault == "close":
        actual["disconnect_observation"]["event"]["reason"] = 8
    elif fault == "original-flag":
        second["ok"] = False
    elif fault == "error":
        actual["capture_error"] = "transport failed"
    else:
        data = bytearray((path / "first/download.bin").read_bytes())
        data[100:112] = second["nonce"].encode()
        replace_download(actual, path, "first", bytes(data))
    with pytest.raises((ValueError, IndexError, KeyError)):
        validate(tmp_path, actual, page, baseline)


@pytest.mark.parametrize("fault", ["initial-baseline", "state", "time", "order"])
def test_cross_page_substitutions_rejected_even_with_resealed_references(tmp_path, fault):
    job, plan, baseline = archive(tmp_path, two=True)
    path = tmp_path / "page1-1ec400"
    actual = json.loads((path / "report.json").read_bytes())
    if fault == "initial-baseline":
        replace_download(actual, path, "baseline", baseline)
    elif fault == "state":
        actual["expected_before"] = {}
    elif fault == "time":
        actual["predecessor_ended_at"] = plan["parent"]["ended_at"]
    else:
        job["completed"].reverse()
    (path / "report.json").write_text(json.dumps(actual))
    if fault != "order":
        job["completed"][1]["report"] = C.J.reference(tmp_path, path / "report.json")
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
        pytest.raises(ValueError),
    ):
        A.completed_prefix(job, plan, tmp_path, baseline)


def test_failed_job_keeps_complete_prefix_but_is_never_successful_parent(tmp_path):
    job, plan, baseline = archive(tmp_path, two=True)
    job.update(ok=False, error="later failure")
    job["completed"] = job["completed"][:1]
    (tmp_path / "report.json").write_text(json.dumps(job))
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
    ):
        assert len(A.completed_prefix(job, plan, tmp_path, baseline)[0]) == 1
    with pytest.raises(ValueError, match="failed"):
        C.parent_gate(tmp_path, None)


def test_successful_prefilled_job_is_full_iterative_parent_without_old_control_relabel(tmp_path):
    import test_scratch_reuse_audit as historical
    from test_prefilled_nor_control import fixture as known_fixture
    from test_prefilled_nor_v2 import upgrade
    from test_sd_nor_probe import info

    anchor, known_root, root = tmp_path / "anchor", tmp_path / "known-v2", tmp_path / "unknown"
    with patch.object(historical, "info", return_value=info(9)):
        known, known_plan, baseline, oracles = known_fixture(known_root)
    (anchor / "second").mkdir(parents=True)
    original = {
        "profile": C.legacy.PROFILE,
        "ok": True,
        "after": known_plan["expected_before"],
        "ended_at": known_plan["parent"]["ended_at"],
    }
    old_plan, old_proof = {"names": known_plan["parent"]["prior_names"]}, {"verified": True}
    C.S.save(anchor / "report.json", original)
    C.S.save(anchor / "plan.json", old_plan)
    (anchor / "second/download.bin").write_bytes(baseline)
    (anchor / "session.btsnoop").write_bytes(b"outer legacy fixture; body separately tested")
    pins = {name: A.A.sha((anchor / name).read_bytes()) for name in C.LEGACY_PINS}
    refs = {name: C.pins.pinned(anchor / name, digest)[1] for name, digest in pins.items()}
    known_plan["parent"] = C.source_summary(
        anchor, original, old_plan, old_proof, baseline, original["after"], refs
    )
    with (
        patch.object(C.pins, "oracles", return_value=oracles),
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, known_plan["ram_oracle"])),
    ):
        upgrade(known_root, known, known_plan, baseline)
        known["verification"] = P.validate(known, known_root, known_plan, baseline, RAM)
        known["ok"] = True
        C.S.save(known_root / "report.json", known)
        current = (known_root / "second/download.bin").read_bytes()
        references = {
            "report": C.J.reference(known_root, known_root / "report.json"),
            "plan": known["plan"],
            "baseline": C.J.reference(known_root, known_root / "second/download.bin"),
        }
        source = C.source_summary(
            known_root, known, known_plan, known["verification"], current, known["after"], references
        )
        with patch.object(historical, "info", return_value=info(9)):
            job, plan, _baseline = archive(root, parent=(source, current))
        with patch.object(C, "LEGACY_PINS", pins), patch.object(C.old, "replay", return_value=old_proof):
            actual, state, parent = C.parent_gate(root, None)
            assert actual == (root / plan["pages"][0]["directory"] / "second/download.bin").read_bytes()
            assert state == job["completed"][-1]["after"] and parent["profile"] == N.PROFILE
            assert parent["verification"] == job["verification"]
            following, _previous = N.prepare(None, root, [0x1EC400, 0x1EC600])
            assert C.source_gate(following, None) == actual
            assert set(C.nonces(following)).isdisjoint(parent["prior_names"])
