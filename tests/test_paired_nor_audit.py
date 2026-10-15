"""Real synthetic ATT/HCI through v2 pure audit, without content oracle."""

import copy
import json
import struct
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import test_scratch_system_pair_contract as legacy
from test_hci_interval import record
from test_nor_freshness import place
from test_param_window import fragment
from test_scratch_reuse_parser import NONCE, OTHER

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C


def fixture(
    directory,
    *,
    offset=0x24400,
    different=False,
    with_f0=False,
    nonces=(NONCE, OTHER),
    placements=(100, 2400),
):
    def recipe(op):
        op["producer"] = f"dbg fread spi_flash {'0' if offset == 0 else hex(offset)}"
        return C.recipe(op)

    with (
        patch.object(legacy.C, "OFFSET", offset),
        patch.object(legacy.C, "recipe", side_effect=recipe),
        patch.object(legacy.C, "payload", side_effect=C.payload),
        patch.object(legacy, "NONCE", nonces[0]),
        patch.object(legacy, "OTHER", nonces[1]),
        patch.object(
            legacy,
            "place",
            side_effect=lambda data, at, **kw: place(
                data, placements[0] if at == 100 else placements[1], **kw
            ),
        ),
    ):
        report, oldplan, baseline = legacy.fixture(directory, different=different, with_f0=with_f0)
    for op in oldplan["operations"]:
        op["producer"] = f"dbg fread spi_flash {'0' if offset == 0 else hex(offset)}"
    source = oldplan["parent"] | {"profile": C.legacy.PROFILE}
    plan = {
        "profile": C.PROFILE,
        "name": C.F.NAME,
        "address_space": "physical-4MiB-NOR",
        "offsets": [offset],
        "pages": [
            {
                "page_index": 0,
                "nor_offset": offset,
                "directory": f"page0-{offset:06x}",
                "operations": oldplan["operations"],
            }
        ],
        "planned_at": oldplan["planned_at"],
        "parent": source,
        "expected_before": report["before"],
        "budget": C.budgets(1),
        "page_budget": C.BUDGET.copy(),
        "startup_policy": C.startup.LEGACY_POLICY,
        "status_event_policy": C.E.POLICY,
        "actions_policy": C.ACTIONS_POLICY,
        "independent_oracle": False,
    }
    page = C.page_plan(plan, 0, report["before"], source["ended_at"])
    report.update({key: page[key] for key in C.FIELDS})
    delta = (
        A.P.H.EPOCH_US
        + int(datetime.fromisoformat(report["started_at"]).timestamp() * 1_000_000)
        + 1_000_000
        - 1000
    )
    relocate_wire(report, directory, delta)
    return report, plan, page, baseline


def relocate_wire(report, directory, delta):
    """Synthetic captured wall clocks must agree with original declared epoch."""

    def shift(value, key=""):
        if isinstance(value, dict):
            return {k: shift(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [shift(v, key) for v in value]
        return value + delta if key.endswith("_us") and type(value) is int else value

    report.update(shift(report))
    raw = (directory / "session.btsnoop").read_bytes()
    raw = A.P.H.HEADER + b"".join(
        record(packet, opcode, stamp=stamp + delta)
        for _n, opcode, stamp, packet in A.P.records(raw, report["hci_capture"]["records"])
    )
    (directory / "session.btsnoop").write_bytes(raw)
    report["hci_capture"]["sha256"] = A.A.sha(raw)
    report["att_hci_binding"] = A.dual_hci.bind(report, raw)


def replace_download(report, directory, label, baseline):
    """Rewrite both actual synthetic ATT notifications and original HCI bytes."""
    warm = (
        report["baseline"]
        if label == "baseline"
        else next(op for op in report["operations"] if op["operation_id"] == label)
    )
    at = 0
    for row in report["att_packets"][warm["download_start"] : warm["download_end"]]:
        packet = bytes.fromhex(row["hex"])
        if packet[:3] == b"\x1b\x2a\0":
            size = len(packet) - 3
            row["hex"] = (packet[:3] + baseline[at : at + size]).hex()
            at += size
    assert at == 4096
    raw, records, index = (directory / "session.btsnoop").read_bytes(), [], 0
    for _n, opcode, stamp, packet in A.P.records(raw, report["hci_capture"]["records"]):
        if opcode in (4, 5) and int.from_bytes(packet[6:8], "little") == 4:
            row = report["att_packets"][index]
            index += 1
            pdu = bytes.fromhex(row["hex"])
            opcode, packet = fragment(struct.pack("<HH", len(pdu), 4) + pdu, direction=row["direction"])
        records.append(record(packet, opcode, stamp=stamp))
    raw = A.P.H.HEADER + b"".join(records)
    (directory / "session.btsnoop").write_bytes(raw)
    (directory / label / "download.bin").write_bytes(baseline)
    report["hci_capture"]["sha256"] = A.A.sha(raw)
    report["att_hci_binding"] = A.dual_hci.bind(report, raw)
    warm["download_sha256"] = A.A.sha(baseline)
    warm["download_verification"] = A.A.download(report, warm, baseline, minimum_start=report["setup_end"])


def replace_baseline(report, directory, baseline):
    replace_download(report, directory, "baseline", baseline)
    first = report["operations"][0]
    first["verification"] = C.payload(first, (directory / "first/download.bin").read_bytes(), baseline)


def test_future_nonce_in_current_first_ring_rejects_before_second_acceptance(tmp_path):
    report, _plan, page, baseline = fixture(tmp_path)
    token = "rc1234567890"
    page["future_nonces"].extend([token, "rcabcdef0123"])
    report["future_nonces"] = page["future_nonces"]
    first = report["operations"][0]
    data = bytearray((tmp_path / "first/download.bin").read_bytes())
    data[:12] = token.encode()  # Before current nonce, outside its strict acquisition scope.
    replace_download(report, tmp_path, "first", bytes(data))
    first["verification"] = C.payload(first, bytes(data), baseline)
    with pytest.raises(ValueError, match="nonce absent"):
        A.validate_page(report, tmp_path, page, baseline)


def shift_clock(value, seconds):
    if isinstance(value, dict):
        return {k: shift_clock(v, seconds) for k, v in value.items()}
    if isinstance(value, list):
        return [shift_clock(v, seconds) for v in value]
    if isinstance(value, str) and value.startswith("2026-10-14T"):
        return (datetime.fromisoformat(value) + timedelta(seconds=seconds)).isoformat()
    return value


def two_page_archive(root):
    first_dir, second_dir = root / "page0-024400", root / "page1-024600"
    first, plan, _page, baseline = fixture(first_dir)
    second, second_plan, _page, _baseline = fixture(
        second_dir, offset=0x24600, nonces=("rc1234567890", "rcabcdef0123"), placements=(500, 2800)
    )
    previous = (first_dir / "second/download.bin").read_bytes()
    replace_baseline(second, second_dir, previous)
    second = shift_clock(second, 90)
    relocate_wire(second, second_dir, 90_000_000)
    slot = second_plan["pages"][0] | {"page_index": 1, "directory": second_dir.name}
    plan["pages"].append(slot)
    plan["offsets"].append(0x24600)
    plan["budget"] = C.budgets(2)
    C.S.save(root / "plan.json", plan)
    ref = A.J.reference(root, root / "plan.json")
    receipts, proofs = [], []
    state, ended = plan["expected_before"], plan["parent"]["ended_at"]
    for index, (page, directory, base) in enumerate(
        ((first, first_dir, baseline), (second, second_dir, previous))
    ):
        page_plan = C.page_plan(plan, index, state, ended)
        page.update({key: page_plan[key] for key in C.FIELDS})
        for stage in [page["baseline"], *page["operations"]]:
            stage["ok"] = True
        proof = A.validate_page(page, directory, page_plan, base)
        page.update(ok=True, plan=ref, verification=proof)
        C.S.save(directory / "report.json", page)
        receipts.append(A.ledger_entry(root, plan["pages"][index], page, proof))
        proofs.append(proof)
        state, ended = page["after"], page["ended_at"]
    job = {
        "profile": C.PROFILE,
        "budget": plan["budget"],
        "plan": ref,
        "ok": True,
        "started_at": first["started_at"],
        "ended_at": second["ended_at"],
        "completed": receipts,
        "verification": A.job_proof(plan, proofs),
    }
    C.S.save(root / "report.json", job)
    return job, plan, baseline


def test_full_two_page_wire_ledger_uses_previous_second_download_and_normal_close(tmp_path):
    job, plan, baseline = two_page_archive(tmp_path)
    proofs, current, state = A.completed_prefix(job, plan, tmp_path, baseline)
    assert [p["raw_range"] for p in proofs] == [[0x24400, 0x24600], [0x24600, 0x24800]]
    assert current == (tmp_path / "page1-024600/second/download.bin").read_bytes()
    assert state == job["completed"][-1]["after"]


@pytest.mark.parametrize("fault", ["initial-baseline", "predecessor-state", "time", "order"])
def test_two_page_chain_cannot_substitute_original_parent_or_predecessor(tmp_path, fault):
    job, plan, baseline = two_page_archive(tmp_path)
    path = tmp_path / "page1-024600"
    page = json.loads((path / "report.json").read_bytes())
    if fault == "initial-baseline":
        replace_baseline(page, path, baseline)
    elif fault == "predecessor-state":
        page["expected_before"] = {}
    elif fault == "time":
        page["predecessor_ended_at"] = plan["parent"]["ended_at"]
    else:
        job["completed"].reverse()
    (path / "report.json").write_text(json.dumps(page))
    if fault != "order":
        job["completed"][1]["report"] = A.J.reference(tmp_path, path / "report.json")
    with pytest.raises(ValueError):
        A.completed_prefix(job, plan, tmp_path, baseline)


@pytest.mark.parametrize("with_f0", [False, True])
def test_complete24400_three_downloads_nine_transactions_and_no_oracle(tmp_path, with_f0):
    report, plan, page, baseline = fixture(tmp_path, with_f0=with_f0)
    proof = A.validate_page(report, tmp_path, page, baseline)
    assert proof["raw_range"] == [0x24400, 0x24600]
    assert proof["paired_bytes"] == 512 and proof["parameter_transactions"] == 9
    aggregate = A.job_proof(plan, [proof])
    assert aggregate["unique_global_coverage_not_evaluated"]
    assert "new_raw_nor_coverage_bytes" not in proof


def test_explicit_v3_full_wire_keeps_nine_transactions_and_requires_saved_new_policy_receipts(tmp_path):
    report, plan, _page, baseline = fixture(tmp_path)
    plan.update(profile=C.PROFILE_V3, prefix_policy=C.F.PADDING_POLICY)
    for slot in plan["pages"]:
        for op in slot["operations"]:
            op["prefix_policy"] = C.F.PADDING_POLICY
    page = C.page_plan(plan, 0, report["before"], plan["parent"]["ended_at"])
    report.update({key: page[key] for key in C.fields(page)})
    previous = baseline
    for op in report["operations"]:
        op["prefix_policy"] = C.F.PADDING_POLICY
        data = (tmp_path / op["operation_id"] / "download.bin").read_bytes()
        op["verification"] = C.payload(op, data, previous)
        assert "critical_chain_inside_written_prefix" not in op["verification"]["freshness"]
        previous = data
    assert A.validate_page(report, tmp_path, page, baseline)["pair_verified"]
    report["prefix_policy"] = C.F.STRICT_POLICY
    with pytest.raises(ValueError, match="explicit v3"):
        A.validate_page(report, tmp_path, page, baseline)


def test_old24200_wire_equivalence_without_promoting_or_relabeling_archive(tmp_path):
    original, oldplan, baseline = legacy.fixture(tmp_path)
    oldproof = legacy.C.validate(original, tmp_path, oldplan, baseline)
    original_capture = (tmp_path / "session.btsnoop").read_bytes()
    # Deep-copy projection tests a pure audit implementation; original stays unchanged.
    report = copy.deepcopy(original)
    page = {key: oldplan[key] for key in legacy.C.FIELDS} | {
        "profile": C.PAGE_PROFILE,
        "budget": C.BUDGET.copy(),
        "nor_offset": 0x24200,
        "page_index": 0,
        "future_nonces": [NONCE, OTHER],
        "predecessor_ended_at": oldplan["parent"]["ended_at"],
        "planned_at": oldplan["planned_at"],
        "operations": oldplan["operations"],
    }
    report.update({key: page[key] for key in C.FIELDS})
    previous = baseline
    for op in report["operations"]:
        data = (tmp_path / op["operation_id"] / "download.bin").read_bytes()
        op["verification"] = C.payload(op, data, previous)
        previous = data
    delta = (
        A.P.H.EPOCH_US
        + int(datetime.fromisoformat(report["started_at"]).timestamp() * 1_000_000)
        + 1_000_000
        - 1000
    )
    relocate_wire(report, tmp_path, delta)
    proof = A.validate_page(report, tmp_path, page, baseline)
    assert proof["observations"] == oldproof["observations"]
    assert proof["sha256"] == oldproof["sha256"]
    assert original["profile"] == legacy.C.PROFILE and not original.get("ok")
    (tmp_path / "session.btsnoop").write_bytes(original_capture)
    assert legacy.C.validate(original, tmp_path, oldplan, baseline) == oldproof


def test_declared_iso_epoch_cannot_move_away_from_original_owned_wire(tmp_path):
    report, _plan, page, baseline = fixture(tmp_path)
    shifted = shift_clock(report, 60)
    shifted.update({key: page[key] for key in C.fields(page)})
    with pytest.raises(ValueError, match="outside declared page epoch"):
        A.validate_page(shifted, tmp_path, page, baseline)


@pytest.mark.parametrize(
    "fault",
    [
        "second-reuses-first",
        "previous",
        "nonce",
        "state",
        "final",
        "fast",
        "incomplete",
        "missing-file",
        "different",
        "future-nonce",
    ],
)
def test_candidate_equality_never_bypasses_full_wire_state_or_freshness(tmp_path, fault):
    report, _plan, page, baseline = fixture(tmp_path, different=fault == "different")
    first, second = report["operations"]
    if fault == "second-reuses-first":
        (tmp_path / "second/download.bin").write_bytes((tmp_path / "first/download.bin").read_bytes())
    elif fault == "previous":
        second["verification"]["freshness"]["previous_ring_sha256"] = C.legacy.A.sha(baseline)
    elif fault == "nonce":
        second["nonce"] = first["nonce"]
    elif fault == "state":
        second["before"] = {}
    elif fault == "final":
        report["state_verification"] = {}
    elif fault == "fast":
        second["pre_download_fast"] = []
    elif fault == "incomplete":
        second["live_complete"] = False
    elif fault == "missing-file":
        (tmp_path / "second/download.bin").unlink()
    elif fault == "future-nonce":
        # Existing previous-page token cannot be reserved for a future producer.
        page["future_nonces"].append(C.F.NAME)
        report["future_nonces"] = page["future_nonces"]
    with pytest.raises((ValueError, FileNotFoundError, KeyError)):
        A.validate_page(report, tmp_path, page, baseline)


def archive(root):
    directory = root / "page0-024400"
    report, plan, page, baseline = fixture(directory)
    C.S.save(root / "plan.json", plan)
    ref = A.J.reference(root, root / "plan.json")
    for stage in [report["baseline"], *report["operations"]]:
        stage["ok"] = True
    report.update(ok=True, plan=ref, verification=A.validate_page(report, directory, page, baseline))
    C.S.save(directory / "report.json", report)
    receipt = A.ledger_entry(root, plan["pages"][0], report, report["verification"])
    job = {
        "profile": C.PROFILE,
        "budget": plan["budget"],
        "plan": ref,
        "ok": True,
        "started_at": report["started_at"],
        "ended_at": report["ended_at"],
        "completed": [receipt],
        "verification": A.job_proof(plan, [report["verification"]]),
    }
    C.S.save(root / "report.json", job)
    return job, plan, baseline


def test_whole_success_replays_exact_ledger_and_failed_whole_keeps_page_without_admission(tmp_path):
    job, plan, baseline = archive(tmp_path)
    assert A._replay_admitted(job, plan, tmp_path, baseline) == job["verification"]
    job["ok"] = False
    (tmp_path / "report.json").write_text(json.dumps(job))
    assert len(A.completed_prefix(job, plan, tmp_path, baseline)[0]) == 1
    with patch.object(C, "source_gate") as source, pytest.raises(ValueError, match="failed whole"):
        A.replay(tmp_path, None)
    source.assert_not_called()


@pytest.mark.parametrize(
    "fault", ["report-ref", "ring", "sector", "state", "chronology", "pageflag", "topproof"]
)
def test_archived_source_order_flags_and_bytes_are_immutable(tmp_path, fault):
    job, plan, baseline = archive(tmp_path)
    receipt = job["completed"][0]
    if fault == "report-ref":
        receipt["report"]["file"] = "other/report.json"
    elif fault in ("ring", "sector"):
        path = tmp_path / "page0-024400/second" / ("download.bin" if fault == "ring" else "sector.bin")
        path.write_bytes(bytes(4096 if fault == "ring" else 512))
    elif fault == "state":
        receipt["after"] = {}
    elif fault == "chronology":
        job["ended_at"] = plan["planned_at"]
    elif fault == "pageflag":
        directory = tmp_path / "page0-024400"
        report = json.loads((directory / "report.json").read_bytes())
        report["ok"] = False
        (directory / "report.json").write_text(json.dumps(report))
        receipt["report"] = A.J.reference(tmp_path, directory / "report.json")
    else:
        job["verification"]["paired_bytes"] = 1024
    (tmp_path / "report.json").write_text(json.dumps(job))
    with pytest.raises((ValueError, FileNotFoundError)):
        A._replay_admitted(job, plan, tmp_path, baseline)
