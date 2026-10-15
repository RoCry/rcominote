"""Full synthetic accepted-prefix/N2 failure; only outer ancestor proof is supplied.

No private fixture, parser exception injection or fabricated success report.
Capture/policy pins are replaced with synthetic fixture pins, never bypassed.
"""

import copy
import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from test_hci_interval import record
from test_nor_freshness import place
from test_paired_nor_audit import replace_download
from test_prefilled_nor_control import RAM
from test_prefilled_nor_pages_audit import archive
from test_scratch_reuse_parser import SECTOR, chain

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_nor_pages as N
from rcominote.experiments import prefilled_notice_checkpoint as K

PAGE = "page1-1ec400"
OFFSETS = [0x1EC200, 0x1EC400, 0x1EC600]


def save(path, value):
    path.write_text(json.dumps(value))


def fixture(root):
    job, plan, baseline = archive(root, two=True)
    source = plan["parent"]
    source["profile"] = N.PROFILE  # Heavy ancestor admission is outside this fixture.
    names = set(source["prior_names"])
    for i in range(64 - len(names)):
        names.add(f"rc{i:010x}")
    source["prior_names"] = sorted(names)
    assert len(names) == 64
    third = copy.deepcopy(plan["pages"][1])
    third.update(page_index=2, directory="page2-1ec600", nor_offset=OFFSETS[2])
    for i, op in enumerate(third["operations"]):
        if op["kind"] == "nor":
            nonce = f"rcffffffff0{i}"
            op.update(
                nor_offset=OFFSETS[2],
                producer="dbg fread spi_flash 0x1ec600",
                nonce=nonce,
                uptime_command="kernel uptime " + nonce,
            )
    plan["pages"].append(third)
    plan["offsets"] = OFFSETS.copy()
    plan["budget"] = N.budgets(3)
    save(root / "plan.json", plan)
    reference = C.J.reference(root, root / "plan.json")
    first_path = root / plan["pages"][0]["directory"]
    first = json.loads((first_path / "report.json").read_bytes())
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
    ):
        page = C.page_plan(plan, 0, plan["expected_before"], source["ended_at"])
        first.update({k: page[k] for k in C.fields(page)})
        first["plan"] = reference
        first["verification"] = N.validate(first, first_path, page, baseline)
        save(first_path / "report.json", first)
        job.update(
            plan=reference,
            budget=plan["budget"],
            completed=[A.ledger_entry(root, plan["pages"][0], first, first["verification"])],
        )
        path = root / PAGE
        report = json.loads((path / "report.json").read_bytes())
        page = C.page_plan(plan, 1, first["after"], first["ended_at"])
        report.update({k: page[k] for k in C.fields(page)})
        report["plan"] = reference
    previous = (first_path / "second/download.bin").read_bytes()
    op = report["operations"][1]
    text = K.C.F.WAKE_GAP.join(chain(op["nonce"], OFFSETS[1], SECTOR).rsplit(b"\n" + C.F.F.LOG_PREFIX, 1))
    current = place(text, 500, initial=previous)
    replace_download(report, path, "first", current)
    end = op["verified_end"]
    raw = (path / "session.btsnoop").read_bytes()
    wire = A.common.wire_positions(report, raw)
    final = {n for i in range(*report["after_span"]) for n in range(wire[i][0], wire[i][1] + 1)}
    records = list(A.P.records(raw, report["hci_capture"]["records"]))
    selected = [r for r in records if r[0] <= wire[end - 1][1] or r[0] in final or r == records[-1]]
    raw = A.P.H.HEADER + b"".join(record(p, code, stamp=t) for _, code, t, p in selected)
    (path / "session.btsnoop").write_bytes(raw)
    report["att_packets"] = report["att_packets"][:end] + report["att_packets"][slice(*report["after_span"])]
    for i, row in enumerate(report["att_packets"]):
        row["monotonic_ns"] = i
    report["after_span"] = [end, len(report["att_packets"])]
    report["after_verification"] = A.A.identity(report, report, "after")
    observed = A.P.inspect(raw, link=report["transport"]["link"], final=True)
    assert len(observed["transactions"]) == 9 and not observed["pending"]
    report["hci_capture"] = {"bytes": len(raw), "sha256": A.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = A.dual_hci.bind(report, raw)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    op.update(ok=False, live_complete=False, barrier_complete=True, error=K.ERROR)
    op.pop("verification")
    (path / "first/sector.bin").unlink()
    for i in (2, 3):
        report["operations"][i] = page["operations"][i] | {"ok": False, "live_complete": False}
        for p in (path / page["operations"][i]["operation_id"]).rglob("*"):
            if p.is_file():
                p.unlink()
    report.update(ok=False, error=K.ERROR, capture_error=K.ERROR)
    report.pop("verification")
    job.update(ok=False, error=K.ERROR)
    job.pop("verification")
    save(path / "report.json", report)
    save(root / "report.json", job)
    frozen, code, entries = root / "source-snapshot", {}, []
    for name in K.CODE:
        p = frozen / "src/rcominote/experiments" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f"synthetic captured original {name}".encode())
        code[name] = A.A.sha(p.read_bytes())
        entries.append({"path": str(p.relative_to(frozen)), "bytes": p.stat().st_size, "sha256": code[name]})
    save(
        frozen / "manifest.json",
        {"created_at": source["ended_at"], "source_files": entries, "test_files": []},
    )
    pins = {
        "code": code,
        "manifest": A.A.sha((frozen / "manifest.json").read_bytes()),
        "counts": (len(entries), 0),
    }
    return job, plan, baseline, current, report, pins


@contextmanager
def gates(root, plan, pins):
    bound = {
        name: A.A.sha((root / name).read_bytes())
        for name in ("report.json", "plan.json", f"{PAGE}/report.json", f"{PAGE}/session.btsnoop")
    }
    with (
        patch.object(K, "PAGE", PAGE),
        patch.object(K, "OFFSETS", OFFSETS),
        patch.object(K, "PINS", bound),
        patch.object(K, "CODE", pins["code"]),
        patch.object(K, "MANIFEST_SHA", pins["manifest"]),
        patch.object(K, "SOURCE_COUNTS", pins["counts"]),
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
    ):
        yield


def test_full_synthetic_prefix_and_original_rejected_gap_adopt_sd_only_no_sector(tmp_path):
    _job, plan, baseline, current, report, pins = fixture(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with gates(tmp_path, plan, pins):
        data, state, result = K.failed_prefix(tmp_path, plan["parent"], baseline)
    assert data == current and state == report["after"] and len(result["prior_names"]) == 70
    assert result["communication"]["content_error_reproduced"] == K.ERROR
    assert result["communication"]["failed_content_accepted"] is False
    assert len(result["original_completed_prefix"]) == 1
    assert result["latest_identity_response_at"] <= result["observed_ended_at"] <= result["failed_ended_at"]
    assert before == {p: p.read_bytes() for p in before}
    with pytest.raises(ValueError, match="failed"):
        C.parent_gate(tmp_path, None)


@pytest.mark.parametrize(
    "fault",
    [
        "jobflag",
        "flag",
        "error",
        "barrier",
        "partial",
        "state",
        "nonce",
        "later-file",
        "later-stage",
        "proof",
        "snapshot",
        "history",
        "source",
        "policy",
        "epoch",
        "plan-order",
    ],
)
def test_resealed_labels_do_not_bypass_wire_source_policy_or_empty_later_slots(tmp_path, fault):
    job, plan, baseline, _current, report, pins = fixture(tmp_path)
    op = report["operations"][1]
    if fault == "jobflag":
        job["ok"] = True
    elif fault == "flag":
        op["ok"] = True
    elif fault == "error":
        report["after_error"] = "unrelated transport failure"
    elif fault == "barrier":
        op["barrier_complete"] = False
    elif fault == "partial":
        (tmp_path / PAGE / "first/download.bin").write_bytes(b"partial")
    elif fault == "state":
        report["after"] = {}
    elif fault == "nonce":
        op["nonce"] = "rc0000000000"
    elif fault == "later-file":
        (tmp_path / PAGE / "second/unexpected.bin").write_bytes(b"write")
    elif fault == "later-stage":
        report["operations"][2]["sd_write_attempted"] = True
    elif fault == "proof":
        op["verification"] = {"accepted": True}
    elif fault == "snapshot":
        (tmp_path / "source-snapshot/src/rcominote/experiments/scratch_reuse_parser.py").write_bytes(
            b"substitution"
        )
    elif fault == "history":
        plan["parent"]["prior_names"].pop()
    elif fault == "source":
        plan["parent"]["profile"] = P.PROFILE_V2
    elif fault == "policy":
        plan["gap_policy"] = C.F.PREFILL_WAKE_GAP_POLICY
    elif fault == "epoch":
        report["started_at"] = report["ended_at"]
    else:
        plan["offsets"].reverse()
    save(tmp_path / "plan.json", plan)
    reference = C.J.reference(tmp_path, tmp_path / "plan.json")
    report["plan"] = job["plan"] = reference
    save(tmp_path / PAGE / "report.json", report)
    save(tmp_path / "report.json", job)
    with gates(tmp_path, plan, pins), pytest.raises((ValueError, KeyError, IndexError)):
        K.failed_prefix(tmp_path, plan["parent"], baseline)


def test_create_replay_header_and_seed_scope_remain_distinct_from_success(tmp_path):
    root, out = tmp_path / "failed", tmp_path / "checkpoint"
    _job, plan, baseline, current, report, pins = fixture(root)
    from rcominote.experiments import paired_nor_runtime as runtime

    with (
        gates(root, plan, pins),
        patch.object(runtime, "private_output"),
        patch.object(C, "parent_gate", return_value=(baseline, report["after"], plan["parent"])),
    ):
        data, state, summary = K.create(None, root, out)
        checkpoint = json.loads((out / "checkpoint.json").read_bytes())
        assert K.verify_admitted(checkpoint, out, plan["parent"], baseline)[2] == summary
        assert data == current and summary["verification"]["new_raw_nor_coverage_bytes"] == 0
        assert summary["verification"]["device_io"] == 0 and "ok" not in checkpoint
        assert C.sources.checkpoint_module(K.PROFILE) is K
        with patch.object(C, "parent_gate", return_value=(current, state, summary)):
            fresh, _ = N.prepare(None, out, [0x1ECC00], gap_policy=C.F.PREFILL_WAKE_GAP_POLICY)
            assert set(C.nonces(fresh)).isdisjoint(summary["prior_names"])
            with pytest.raises(ValueError, match="only prefilled unknown"):
                C.prepare(None, out, [0x1ECC00])
            with pytest.raises(ValueError, match="restricted to prefilled unknown"):
                P.prepare_v2(None, out)
        checkpoint["failed"]["prior_names"].pop()
        with pytest.raises(ValueError):
            K.verify_admitted(checkpoint, out, plan["parent"], baseline)


def test_original_capture_hash_mixing_rejects_before_any_communication_adoption(tmp_path):
    _job, plan, baseline, _current, _report, pins = fixture(tmp_path)
    with gates(tmp_path, plan, pins), patch.object(N, "communication") as audit:
        raw = (tmp_path / PAGE / "session.btsnoop").read_bytes()
        (tmp_path / PAGE / "session.btsnoop").write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with pytest.raises(ValueError):
            K.failed_prefix(tmp_path, plan["parent"], baseline)
    audit.assert_not_called()


@pytest.mark.parametrize("fault", ["originalflag", "current", "cycle", "timestamp"])
def test_checkpoint_cannot_relabel_failed_job_or_replace_current_file_or_observed_epoch(tmp_path, fault):
    root, out = tmp_path / "failed", tmp_path / "checkpoint"
    _job, plan, baseline, _current, report, pins = fixture(root)
    from rcominote.experiments import paired_nor_runtime as runtime

    with (
        gates(root, plan, pins),
        patch.object(runtime, "private_output"),
        patch.object(C, "parent_gate", return_value=(baseline, report["after"], plan["parent"])),
    ):
        K.create(None, root, out)
        checkpoint = json.loads((out / "checkpoint.json").read_bytes())
        if fault == "originalflag":
            checkpoint["original_failed_content_ok"] = True
        elif fault == "current":
            (out / "baseline.bin").write_bytes(b"x" * 4096)
            checkpoint["baseline"] = C.J.reference(out, out / "baseline.bin")
        elif fault == "cycle":
            checkpoint["failed"]["directory"] = str(out)
        else:
            checkpoint["failed"]["latest_identity_response_at"] = checkpoint["failed"]["failed_ended_at"]
        with pytest.raises(ValueError):
            K.verify_admitted(checkpoint, out, plan["parent"], baseline)
