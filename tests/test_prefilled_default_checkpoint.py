"""Synthetic DEFAULT-only failed startup: no private artifact or fake download.

Outer notice-parent admission is supplied; complete original zero-write wire,
snapshot pins, state, immutable slots and legacy rejection are actually replayed.
"""

import copy
import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from test_hci_interval import record
from test_param_window import remote, update
from test_prefilled_nor_control import RAM
from test_prefilled_nor_pages import fixture as page_fixture

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_default_checkpoint as K
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_nor_pages as N


def save(path, value):
    path.write_text(json.dumps(value))


def fixture(root):
    report, plan, _page, baseline = page_fixture(root, 0x1ECC00)
    path = root / K.PAGE
    parent = root.with_name(root.name + "-parent")
    parent.mkdir()
    save(parent / "checkpoint.json", {"synthetic_admitted_notice": True})
    source = plan["parent"]
    names = set(source["prior_names"])
    for i in range(70 - len(names)):
        names.add(f"rc{i:010x}")
    source.update(
        directory=str(parent),
        profile=C.PREFILLED_NOTICE_CP,
        prior_names=sorted(names),
        baseline_sha256=A.A.sha(baseline),
        created_at=source["ended_at"],
    )
    plan["gap_policy"] = C.F.PREFILL_WAKE_GAP_POLICY
    with patch.object(P, "RAM_SHA", A.A.sha(RAM)):
        page = C.page_plan(plan, 0, source["latest_info"], source["ended_at"])
    report.update({k: page[k] for k in C.fields(page)})
    save(root / "plan.json", plan)
    report["plan"] = C.J.reference(root, root / "plan.json")
    raw = (path / "session.btsnoop").read_bytes()
    wire = A.common.wire_positions(report, raw)
    boundary = report["file_list_span"][1]
    final = {n for i in range(*report["after_span"]) for n in range(wire[i][0], wire[i][1] + 1)}
    original = list(A.P.records(raw, report["hci_capture"]["records"]))
    records = [(code, stamp, p) for n, code, stamp, p in original if n <= wire[boundary - 1][1]]
    records += [
        (code, records[-1][1] + i, p) for i, (code, p) in enumerate(remote(24, 40, 0, 500) + [update(36)], 1)
    ]
    records += [(code, stamp, p) for n, code, stamp, p in original if n in final or n == original[-1][0]]
    raw = A.P.H.HEADER + b"".join(record(p, code, stamp=t) for code, t, p in records)
    (path / "session.btsnoop").write_bytes(raw)
    report["att_packets"] = (
        report["att_packets"][:boundary] + report["att_packets"][slice(*report["after_span"])]
    )
    for i, row in enumerate(report["att_packets"]):
        row["monotonic_ns"] = i
    report["after_span"] = [boundary, len(report["att_packets"])]
    report["after_verification"] = A.A.identity(report, report, "after")
    report["before_verification"] = A.A.identity(report, report, "before")
    observed = A.P.inspect(raw, link=report["transport"]["link"], final=True)
    assert len(observed["transactions"]) == 1 and not observed["pending"]
    report["hci_capture"] = {"bytes": len(raw), "sha256": A.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = A.dual_hci.bind(report, raw)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    report.update(
        ok=False,
        error=K.ERROR,
        capture_error=K.ERROR,
        baseline={"operation_id": "baseline", "name": C.F.NAME, "live_complete": False, "ok": False},
        operations=[slot | {"ok": False, "live_complete": False} for slot in page["operations"]],
    )
    for k in ("startup_settlement", "startup_classification", "verification"):
        report.pop(k, None)
    for label in N.STAGES:
        for p in (path / label).rglob("*"):
            if p.is_file():
                p.unlink()
    job = {
        "profile": plan["profile"],
        "budget": plan["budget"],
        "started_at": report["started_at"],
        "ended_at": report["ended_at"],
        "completed": [],
        "plan": report["plan"],
        "ok": False,
        "error": K.ERROR,
    }
    save(path / "report.json", report)
    save(root / "report.json", job)
    frozen, code, entries = root / "source-snapshot", {}, []
    for name in K.CODE:
        p = frozen / "src/rcominote/experiments" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f"synthetic frozen original {name}".encode())
        code[name] = A.A.sha(p.read_bytes())
        entries.append({"path": str(p.relative_to(frozen)), "sha256": code[name], "bytes": p.stat().st_size})
    save(
        frozen / "manifest.json",
        {"created_at": source["created_at"], "source_files": entries, "test_files": []},
    )
    pins = {
        "code": code,
        "manifest": A.A.sha((frozen / "manifest.json").read_bytes()),
        "counts": (len(entries), 0),
        "parent": A.A.sha((parent / "checkpoint.json").read_bytes()),
        "shape": (report["setup_end"], report["before_span"], report["file_list_span"], report["after_span"]),
        "hci": observed["records"],
    }
    return job, plan, report, baseline, pins


@contextmanager
def gates(root, pins):
    bound = {name: A.A.sha((root / name).read_bytes()) for name in K.PINS}
    with (
        patch.object(K, "PINS", bound),
        patch.object(K, "PARENT_SHA", pins["parent"]),
        patch.object(K, "CODE", pins["code"]),
        patch.object(K, "MANIFEST_SHA", pins["manifest"]),
        patch.object(K, "SOURCE_COUNTS", pins["counts"]),
        patch.object(K, "WIRE_SHAPE", pins["shape"]),
        patch.object(K, "HCI_COUNT", pins["hci"]),
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
    ):
        yield


def test_full_zero_write_wire_adopts_old_owned_sd_and_separate_new_identity_history72(tmp_path):
    job, plan, report, baseline, pins = fixture(tmp_path)
    with gates(tmp_path, pins):
        data, state, result = K.failed_startup(tmp_path, plan["parent"], baseline)
    assert data == baseline and state == report["after"]
    assert (
        len(result["prior_names"]) == 72
        and result["verification"]["downloads"] == result["verification"]["actions"] == 0
    )
    assert result["owned_file_observed_ended_at"] == plan["parent"]["ended_at"]
    assert result["latest_identity_response_at"] != result["owned_file_observed_ended_at"]
    assert job["ok"] is report["ok"] is False
    with pytest.raises(ValueError, match="failed"):
        C.parent_gate(tmp_path, None)


@pytest.mark.parametrize(
    "fault",
    [
        "jobflag",
        "pageflag",
        "error",
        "extra-error",
        "stage",
        "file",
        "baseline",
        "history",
        "nonce",
        "state",
        "source",
        "plan",
        "fast-policy",
        "identity",
        "snapshot",
        "time",
    ],
)
def test_original_flags_zero_io_identity_history_and_source_remain_mandatory(tmp_path, fault):
    job, plan, report, baseline, pins = fixture(tmp_path)
    if fault == "jobflag":
        job["ok"] = True
    elif fault == "pageflag":
        report["ok"] = True
    elif fault == "error":
        report["error"] = "different failure"
    elif fault == "extra-error":
        report["after_error"] = "wire failure"
    elif fault == "stage":
        report["operations"][0]["sd_write_attempted"] = True
    elif fault == "file":
        (tmp_path / K.PAGE / "baseline/download.bin").write_bytes(b"unexpected")
    elif fault == "baseline":
        baseline = b"x" * 4096
    elif fault == "history":
        plan["parent"]["prior_names"].pop()
    elif fault == "nonce":
        plan["pages"][0]["operations"][1]["nonce"] = plan["parent"]["prior_names"][0]
    elif fault == "state":
        report["after"] = {}
    elif fault == "source":
        plan["parent"]["profile"] = C.PREFILLED_LINK_CP
    elif fault == "plan":
        plan["offsets"] = [0x1ECE00]
    elif fault == "fast-policy":
        plan["startup_policy"] = C.startup.POLICY
    elif fault == "identity":
        report["before_verification"] = {}
    elif fault == "snapshot":
        (tmp_path / "source-snapshot/src/rcominote/experiments/startup_policy.py").write_bytes(b"changed")
    else:
        report["started_at"] = report["ended_at"]
    save(tmp_path / "plan.json", plan)
    report["plan"] = job["plan"] = C.J.reference(tmp_path, tmp_path / "plan.json")
    save(tmp_path / K.PAGE / "report.json", report)
    save(tmp_path / "report.json", job)
    with gates(tmp_path, pins), pytest.raises((ValueError, KeyError)):
        K.failed_startup(tmp_path, plan["parent"], baseline)


def test_host_create_dispatch_and_unknown_only_admission_with_fresh_baseline_required(tmp_path):
    root, out = tmp_path / "failed", tmp_path / "checkpoint"
    _job, plan, report, baseline, pins = fixture(root)
    from rcominote.experiments import paired_nor_runtime as runtime

    with (
        gates(root, pins),
        patch.object(runtime, "private_output"),
        patch.object(C, "parent_gate", return_value=(baseline, report["after"], plan["parent"])),
    ):
        current, state, summary = K.create(None, root, out)
        checkpoint = json.loads((out / "checkpoint.json").read_bytes())
        assert K.verify_admitted(checkpoint, out, plan["parent"], baseline)[2] == summary
        assert (
            summary["verification"]["device_io"] == summary["verification"]["new_raw_nor_coverage_bytes"] == 0
        )
        assert summary["current_object_live_download_required_before_overwrite"] is True
        assert C.sources.checkpoint_module(K.PROFILE) is K
        with (
            patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
            patch.object(C, "parent_gate", return_value=(current, state, summary)),
        ):
            fresh, _old = N.prepare(None, out, [0x1ECC00], startup_policy=C.startup.POLICY)
            assert set(C.nonces(fresh)).isdisjoint(summary["prior_names"])
            with pytest.raises(ValueError, match="only prefilled unknown"):
                C.prepare(None, out, [0x1ECC00])
        changed = copy.deepcopy(checkpoint)
        changed["failed"]["prior_names"].pop()
        with pytest.raises(ValueError):
            K.verify_admitted(changed, out, plan["parent"], baseline)
