"""Real synthetic nine-transaction v1 gap failure; no parser/private fixtures."""

import copy
import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from test_hci_interval import record
from test_nor_freshness import place
from test_paired_nor_audit import replace_download
from test_paired_nor_control import rewrite_capture
from test_param_window import remote, update
from test_prefilled_nor_control import RAM
from test_prefilled_nor_control import fixture as complete_fixture
from test_scratch_reuse_parser import SECTOR, chain

from rcominote.experiments import prefilled_nor_checkpoint as H

P, K, A, C = H.P, H.K, H.P.A, H.P.C
PLAIN = b"\n" + C.F.F.LOG_PREFIX
GAP = b"\n\r\n" + C.F.F.COMPOSER_FPS2 + C.F.F.LOG_PREFIX[2:]


def save(path, value):
    path.write_text(json.dumps(value))


def fixture(root):
    report, plan, baseline, oracles = complete_fixture(root)
    first = report["operations"][1]
    current = place(GAP.join(chain(first["nonce"]).rsplit(PLAIN, 1)), 300, initial=baseline)
    replace_download(report, root, "first", current)
    end = first["verified_end"]
    raw = (root / "session.btsnoop").read_bytes()
    wire = A.common.wire_positions(report, raw)
    final = {n for i in range(*report["after_span"]) for n in range(wire[i][0], wire[i][1] + 1)}
    rows = list(A.P.records(raw, report["hci_capture"]["records"]))
    selected = [row for row in rows if row[0] <= wire[end - 1][1] or row[0] in final or row == rows[-1]]
    raw = A.P.H.HEADER + b"".join(record(packet, op, stamp=stamp) for _, op, stamp, packet in selected)
    (root / "session.btsnoop").write_bytes(raw)
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
    first.update(ok=False, live_complete=False, barrier_complete=True, error=H.CONTENT_ERROR)
    first.pop("verification")
    (root / "first/sector.bin").unlink()
    for index in (2, 3):
        report["operations"][index] = plan["operations"][index] | {"ok": False, "live_complete": False}
        for path in (root / plan["operations"][index]["operation_id"]).rglob("*"):
            if path.is_file():
                path.unlink()
    report.update(ok=False, error=H.CONTENT_ERROR, capture_error=H.CONTENT_ERROR)
    snapshot, code, entries = root / "source-snapshot", {}, []
    for name in H.CAPTURE_CODE:
        path = snapshot / "src/rcominote/experiments" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic captured prefill-v1 {name}".encode())
        code[name] = A.A.sha(path.read_bytes())
        entries.append(
            {"path": str(path.relative_to(snapshot)), "bytes": path.stat().st_size, "sha256": code[name]}
        )
    path = snapshot / "tests/test_frozen.py"
    path.parent.mkdir()
    path.write_bytes(b"synthetic frozen test")
    tests = [
        {"path": "tests/test_frozen.py", "bytes": path.stat().st_size, "sha256": A.A.sha(path.read_bytes())}
    ]
    save(
        snapshot / "manifest.json",
        {"source_files": entries, "test_files": tests, "created_at": plan["planned_at"]},
    )
    save(root / "report.json", report)
    pins = {
        "code": code,
        "manifest": A.A.sha((snapshot / "manifest.json").read_bytes()),
        "counts": (len(entries), 1),
    }
    return report, plan, baseline, current, oracles, pins


@contextmanager
def gates(plan, oracles, pins):
    with (
        patch.object(H, "CAPTURE_CODE", pins["code"]),
        patch.object(H, "SOURCE_MANIFEST_SHA", pins["manifest"]),
        patch.object(H, "SOURCE_COUNTS", pins["counts"]),
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(C.pins, "oracles", return_value=oracles),
        patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
        patch.object(A, "oracle_proof", side_effect=AssertionError("Rejected NOR cannot reach oracle")),
    ):
        yield


def verify(root, plan, baseline, oracles, pins, *, source=None):
    with gates(plan, oracles, pins):
        return K.failed_communication(root, plan["parent"] if source is None else source, baseline)


def reseal(root, report, plan):
    save(root / "plan.json", plan)
    report["plan"] = C.J.reference(root, root / "plan.json")
    save(root / "report.json", report)


def test_full_original_wire_and_real_gap_error_adopt_only_private_current_and_state(tmp_path):
    report, plan, baseline, current, oracles, pins = fixture(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    actual, state, result = verify(tmp_path, plan, baseline, oracles, pins)
    assert actual == current and state == report["after"]
    assert result["current_ring_sha256"] == A.A.sha(current)
    assert set(result["prior_names"]) == set(plan["parent"]["prior_names"]) | set(P.nonces(plan))
    proof = result["communication"]
    assert proof["parameter_transactions"] == 9 and proof["downloads"] == 3
    assert (
        proof["ram_prefill_oracle_verified"] is True and proof["content_error_reproduced"] == H.CONTENT_ERROR
    )
    assert proof["failed_content_accepted"] is False and proof["new_raw_nor_coverage_bytes"] == 0
    assert report["ok"] is report["operations"][1]["ok"] is False
    assert before == {p: p.read_bytes() for p in before}
    with pytest.raises(ValueError, match="failed"):
        P.replay(tmp_path, None)
    with pytest.raises(ValueError):
        C.parent_gate(tmp_path, None)


@pytest.mark.parametrize(
    "fault",
    [
        "job-flag",
        "profile",
        "v2",
        "wrong-error",
        "capture-error",
        "stage-error",
        "extra-error",
        "warm-flag",
        "prefill-flag",
        "nor-flag",
        "nor-complete",
        "barrier",
        "NOR-proof",
        "oracle-proof",
        "sector",
        "later-file",
        "later-flag",
        "later-field",
        "partial",
        "mixed",
        "coherent-mix",
        "now-passes",
        "different-parser-error",
        "RAM-mix",
        "RAM-proof",
        "RAM-oracle",
        "state",
        "binding",
        "ack",
        "epoch",
        "stage-time",
        "source-bytes",
        "source-test",
        "source-version",
        "source-counts",
        "manifest-pin",
        "source-time",
        "history-collision",
        "source-parent",
        "plan-reference",
        "plan-target",
    ],
)
def test_labels_cannot_replace_original_wire_source_ram_or_failed_policy(tmp_path, fault):
    report, plan, baseline, current, oracles, pins = fixture(tmp_path)
    first = report["operations"][1]
    if fault == "job-flag":
        report["ok"] = True
    elif fault == "profile":
        report["profile"] = C.STATUS_CONTROL
    elif fault == "v2":
        plan.update(profile=P.PROFILE_V2, gap_policy=C.F.PREFILL_GAP_POLICY)
        report.update(profile=P.PROFILE_V2, gap_policy=C.F.PREFILL_GAP_POLICY)
    elif fault == "wrong-error":
        report["error"] = K.CONTENT_ERROR
    elif fault == "capture-error":
        report["capture_error"] = "TimeoutError:"
    elif fault == "stage-error":
        first["error"] = K.CONTENT_ERROR
    elif fault == "extra-error":
        report["baseline"]["error"] = "RuntimeError: unrelated"
    elif fault == "warm-flag":
        report["baseline"]["ok"] = False
    elif fault == "prefill-flag":
        report["operations"][0]["live_complete"] = False
    elif fault == "nor-flag":
        first["ok"] = True
    elif fault == "nor-complete":
        first["live_complete"] = True
    elif fault == "barrier":
        first["barrier_complete"] = False
    elif fault == "NOR-proof":
        first["verification"] = {"verified": True}
    elif fault == "oracle-proof":
        first["oracle_verification"] = {"verified": True}
    elif fault == "sector":
        (tmp_path / "first/sector.bin").write_bytes(SECTOR)
    elif fault == "later-file":
        (tmp_path / "second/partial.bin").write_bytes(b"late")
    elif fault == "later-flag":
        report["operations"][2]["ok"] = True
    elif fault == "later-field":
        report["operations"][3]["started_at"] = first["ended_at"]
    elif fault in ("partial", "mixed"):
        (tmp_path / "first/download.bin").write_bytes(current[:2048] if fault == "partial" else baseline)
    elif fault in ("coherent-mix", "now-passes", "different-parser-error", "RAM-mix"):
        changed = baseline if fault == "coherent-mix" else current
        if fault == "now-passes":
            changed = place(chain(first["nonce"]), 300, initial=baseline)
        elif fault == "different-parser-error":
            changed = current.replace(first["nonce"].encode(), b"rcaaaaaaaaaa", 1)
        elif fault == "RAM-mix":
            replace_download(report, tmp_path, "prefill-first", b"X" * 4095 + b"H")
        if fault != "RAM-mix":
            replace_download(report, tmp_path, "first", changed)
    elif fault == "RAM-proof":
        report["operations"][0]["verification"]["bytes"] = 4095
    elif fault == "RAM-oracle":
        plan["ram_oracle"]["sha256"] = "0" * 64
    elif fault == "state":
        report["after"] = {}
    elif fault == "binding":
        report["att_hci_binding"] = {}
    elif fault == "ack":
        first["frames"].pop()
    elif fault == "epoch":
        report["started_at"] = "2026-10-14T11:00:00+00:00"
    elif fault == "stage-time":
        first["started_at"] = report["started_at"]
    elif fault in ("source-bytes", "source-test"):
        path = (
            "src/rcominote/experiments/paired_nor_recipe.py"
            if fault == "source-bytes"
            else "tests/test_frozen.py"
        )
        (tmp_path / "source-snapshot" / path).write_bytes(b"changed")
    elif fault == "manifest-pin":
        pins["manifest"] = "0" * 64
    elif fault == "source-counts":
        pins["counts"] = (144, 127)
    elif fault in ("source-version", "source-time"):
        path = tmp_path / "source-snapshot/manifest.json"
        value = json.loads(path.read_bytes())
        if fault == "source-version":
            value["source_files"].pop()
        else:
            value["created_at"] = report["ended_at"]
        save(path, value)
        pins["manifest"] = A.A.sha(path.read_bytes())
    elif fault == "history-collision":
        plan["parent"]["prior_names"].append(first["nonce"])
    elif fault == "source-parent":
        source = copy.deepcopy(plan["parent"])
        source["profile"] = "different"
        with pytest.raises(ValueError):
            verify(tmp_path, plan, baseline, oracles, pins, source=source)
        return
    elif fault == "plan-reference":
        report["plan"] = {"file": "unrelated.json"}
        save(tmp_path / "report.json", report)
    elif fault == "plan-target":
        plan["operations"][1]["nor_offset"] = 0x4200
    if fault != "plan-reference":
        reseal(tmp_path, report, plan)
    with pytest.raises((ValueError, KeyError, FileNotFoundError)):
        verify(tmp_path, plan, baseline, oracles, pins)


@pytest.mark.parametrize("pending", [False, True])
def test_full_wire_rejects_additional_or_pending_transaction(tmp_path, pending):
    report, plan, baseline, _current, oracles, pins = fixture(tmp_path)
    raw = (tmp_path / "session.btsnoop").read_bytes()
    rows = [
        (op, stamp, packet) for _, op, stamp, packet in A.P.records(raw, report["hci_capture"]["records"])
    ]
    stamp = rows[-1][1]
    rows[-1:-1] = [
        (op, stamp, packet) for op, packet in remote(identifier=111) + ([] if pending else [update(12)])
    ]
    observed = rewrite_capture(tmp_path, report, rows)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    reseal(tmp_path, report, plan)
    with pytest.raises(ValueError, match="exactly 9"):
        verify(tmp_path, plan, baseline, oracles, pins)


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "page-role",
        "legacy-role",
        "legacy-profile",
        "v2-profile",
        "missing-profile",
        "coverage",
        "baseline",
        "result",
        "source-profile-status",
        "source-profile-page",
        "source-profile-legacy",
        "source-profile-v2",
    ],
)
def test_create_and_admission_keep_original_prefill_profile_role_and_bytes(tmp_path, fault):
    from rcominote.experiments import paired_nor_runtime as runtime

    failed, out = tmp_path / "failed", tmp_path / "checkpoint"
    report, plan, baseline, current, oracles, pins = fixture(failed)
    with (
        gates(plan, oracles, pins),
        patch.object(runtime, "private_output"),
        patch.object(C, "parent_gate", return_value=(baseline, plan["expected_before"], plan["parent"])),
        patch.object(C.S, "now", return_value="2026-10-14T12:00:00+00:00"),
    ):
        actual, state, summary = K.create(None, failed, out)
    assert actual == current and state == report["after"] and summary["original_failed_retained"] is True
    assert summary["verification"]["new_raw_nor_coverage_bytes"] == 0
    cp = json.loads((out / "checkpoint.json").read_bytes())
    assert (
        cp["profile"] == K.CONTENT_PROFILE
        and cp["failure_role"] == H.ROLE
        and cp["original_capture_profile"] == P.PROFILE
    )
    if fault == "page-role":
        cp.update(failure_role=K.PAGE_CONTENT_ROLE, original_capture_profile=C.PROFILE_V3)
    elif fault == "legacy-role":
        cp["failure_role"] = "complete-second-transfer-content-proof-only"
        cp.pop("original_capture_profile")
    elif fault == "legacy-profile":
        cp.update(profile=K.PROFILE, original_page_ok=False, original_first_ok=False)
        for key in ("failure_role", "original_operation_ok", "original_capture_profile"):
            cp.pop(key)
    elif fault == "v2-profile":
        cp["original_capture_profile"] = P.PROFILE_V2
    elif fault == "missing-profile":
        cp.pop("original_capture_profile")
    elif fault == "coverage":
        cp["new_raw_nor_coverage_bytes"] = 512
    elif fault == "baseline":
        (out / "baseline.bin").write_bytes(baseline)
        cp["baseline"] = C.J.reference(out, out / "baseline.bin")
    elif fault == "result":
        cp["failed"]["communication"]["failed_content_accepted"] = True
    elif fault and fault.startswith("source-profile-"):
        report["profile"] = {
            "source-profile-status": C.STATUS_CONTROL,
            "source-profile-page": C.PROFILE_V3,
            "source-profile-legacy": C.PROFILE,
            "source-profile-v2": P.PROFILE_V2,
        }[fault]
        save(failed / "report.json", report)
    if fault:
        save(out / "checkpoint.json", cp)
    with gates(plan, oracles, pins):
        if fault:
            with pytest.raises(ValueError):
                K.verify_admitted(cp, out, plan["parent"], baseline)
        else:
            copied, latest, again = K.verify_admitted(cp, out, plan["parent"], baseline)
            assert copied == current and latest == state and again == summary
            assert report["ok"] is False
