"""Failed continuous control: full synthetic9txn, distinct zero-coverage receipt.

Final parser exception alone is injected; original first parser and every wire,
state and ownership gate run. Real statusliteral counterexamples live separately.
"""

import copy
import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest
import test_scratch_reuse_audit as old_fixture
from test_hci_interval import record
from test_paired_nor_continuous_control import fixture as continuous_fixture
from test_paired_nor_control import rewrite_capture
from test_paired_nor_status_control import fixture as status_fixture
from test_param_window import remote, update
from test_sd_nor_probe import info

from rcominote.experiments import paired_nor_checkpoint as K

A, C = K.A, K.C


def save(path, value):
    path.write_text(json.dumps(value))


def fixture(root, *, profile=C.CONTINUOUS_CONTROL):
    with patch.object(old_fixture, "info", return_value=info(9)):
        report, plan, baseline, oracles = (
            status_fixture if profile == C.STATUS_CONTROL else continuous_fixture
        )(root)
    group = report["groups"][0]
    second = group["operations"][1]
    end = second["verified_end"]
    capture = (root / "session.btsnoop").read_bytes()
    wire = A.common.wire_positions(report, capture)
    final = {n for i in range(*report["after_span"]) for n in range(wire[i][0], wire[i][1] + 1)}
    records = list(A.P.records(capture, report["hci_capture"]["records"]))
    selected = [row for row in records if row[0] <= wire[end - 1][1] or row[0] in final or row == records[-1]]
    raw = A.P.H.HEADER + b"".join(
        record(packet, opcode, stamp=stamp) for _, opcode, stamp, packet in selected
    )
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
    second.update(ok=False, live_complete=False, barrier_complete=True, error=K.CONTENT_ERROR)
    second.pop("verification")
    second.pop("oracle_verification")
    (root / "page0-000000/second/sector.bin").unlink()
    group.update(candidate=False, live_complete=False)
    report["groups"][1] = {
        "group_index": 1,
        "nor_offset": 0x4200,
        "operations": [op | {"ok": False, "live_complete": False} for op in plan["pages"][1]["operations"]],
        "candidate": False,
        "live_complete": False,
        "continuation": None,
    }
    for path in (root / "page1-004200").rglob("*"):
        if path.is_file():
            path.unlink()
    report.update(ok=False, error=K.CONTENT_ERROR, capture_error=K.CONTENT_ERROR)
    snapshot = root / "source-snapshot"
    code, entries = {}, []
    names = ["paired_nor_plan.py", "paired_nor_audit.py", "paired_nor_runtime.py", "scratch_reuse_parser.py"]
    if profile == C.STATUS_CONTROL:
        names.append("paired_nor_recipe.py")
    for name in names:
        path = snapshot / "src/rcominote/experiments" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic frozen failed continuous source {name}".encode())
        code[name] = A.A.sha(path.read_bytes())
        entries.append(
            {"path": str(path.relative_to(snapshot)), "bytes": path.stat().st_size, "sha256": code[name]}
        )
    save(
        snapshot / "manifest.json",
        {"source_files": entries, "test_files": [], "created_at": plan["planned_at"]},
    )
    save(root / "report.json", report)
    current = (root / "page0-000000/second/download.bin").read_bytes()
    return report, plan, baseline, current, oracles, code


@contextmanager
def failure_gate(oracles, code, *, payload_failure=True):
    original = C.payload

    def payload(op, current, previous):
        if op["operation_id"] == "second" and op["nor_offset"] == 0 and payload_failure:
            message = K.CONTENT_ERROR if payload_failure is True else payload_failure
            raise ValueError(message.removeprefix("ValueError: "))
        return original(op, current, previous)

    with (
        patch.object(K, "CONTROL_CAPTURE_CODE", code),
        patch.object(K, "STATUS_CAPTURE_CODE", code),
        patch.object(C.pins, "oracles", return_value=oracles),
        patch.object(C, "payload", side_effect=payload),
    ):
        yield


def verify(root, plan, baseline, oracles, code, *, payload_failure=True, source=None):
    with failure_gate(oracles, code, payload_failure=payload_failure):
        return K.control_content_communication(root, plan["parent"] if source is None else source, baseline)


def reseal(root, report, plan):
    save(root / "plan.json", plan)
    report["plan"] = C.J.reference(root, root / "plan.json")
    save(root / "report.json", report)


def test_nine_transaction_communication_is_current_object_only_original_failure_retained(tmp_path):
    report, plan, baseline, current, oracles, code = fixture(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    actual, state, result = verify(tmp_path, plan, baseline, oracles, code)
    assert actual == current and state == report["after"]
    assert state["device"]["free_capacity"] == 59589
    assert result["current_ring_sha256"] == A.A.sha(current)
    assert result["latest_info"] == state and result["observed_ended_at"] == report["ended_at"]
    assert set(result["prior_names"]) == set(plan["parent"]["prior_names"]) | set(C.nonces(plan))
    proof = result["communication"]
    assert proof["complete"] is True and proof["parameter_transactions"] == 9 and proof["downloads"] == 3
    assert proof["failed_content_accepted"] is False and proof["new_raw_nor_coverage_bytes"] == 0
    assert proof["content_error_reproduced"] == K.CONTENT_ERROR
    assert before == {p: p.read_bytes() for p in before}
    assert (
        report["ok"]
        is report["groups"][0]["candidate"]
        is report["groups"][0]["operations"][1]["ok"]
        is False
    )
    for gate in (A.replay, C.parent_gate):
        with pytest.raises(ValueError):
            gate(tmp_path, None)


@pytest.mark.parametrize("failure", [False, "ValueError: another parser classification"])
def test_original_content_must_still_fail_even_when_complete_wire_passes(tmp_path, failure):
    _report, plan, baseline, _current, oracles, code = fixture(tmp_path)
    with pytest.raises(ValueError, match="unexpectedly passed|does not replay|must reproduce"):
        verify(tmp_path, plan, baseline, oracles, code, payload_failure=failure)


@pytest.mark.parametrize(
    "fault",
    [
        "top-success",
        "group-candidate",
        "group-live",
        "second-success",
        "second-live",
        "second-barrier",
        "baseline-failure",
        "first-failure",
        "wrong-error",
        "wrong-stage-error",
        "wrong-capture-error",
        "extra-error",
        "missing-final",
        "state",
        "missing-frame",
        "partial-current",
        "mixed-current",
        "mixed-baseline",
        "oracle",
        "first-sector",
        "unexpected-second-sector",
        "later-start",
        "later-file",
        "continuation",
        "extra-baseline",
        "binding",
        "wrong-nonce",
        "wrong-offset",
        "failed-verification",
        "history-collision",
        "short-epoch",
        "stage-time",
        "parent",
        "snapshot-time",
        "snapshot-bytes",
    ],
)
def test_content_label_cannot_replace_full_original_wire_state_and_failure_proof(tmp_path, fault):
    report, plan, baseline, current, oracles, code = fixture(tmp_path)
    group, later = report["groups"]
    second = group["operations"][1]
    if fault == "top-success":
        report["ok"] = True
    elif fault in ("group-candidate", "group-live"):
        group["candidate" if fault == "group-candidate" else "live_complete"] = True
    elif fault in ("second-success", "second-live"):
        second["ok" if fault == "second-success" else "live_complete"] = True
    elif fault == "second-barrier":
        second["barrier_complete"] = False
    elif fault == "baseline-failure":
        group["baseline"]["ok"] = False
    elif fault == "first-failure":
        group["operations"][0]["live_complete"] = False
    elif fault == "wrong-error":
        report["error"] = "TimeoutError: "
    elif fault == "wrong-stage-error":
        second["error"] = "ValueError: another parse error"
    elif fault == "wrong-capture-error":
        report["capture_error"] = "ValueError: another capture error"
    elif fault == "extra-error":
        report["after_error"] = "missing final identity"
    elif fault == "missing-final":
        report.pop("after_span")
    elif fault == "state":
        second["after"] = info(8)
    elif fault == "missing-frame":
        second["frames"].pop()
    elif fault in ("partial-current", "mixed-current"):
        (tmp_path / "page0-000000/second/download.bin").write_bytes(
            current[:2048] if fault == "partial-current" else baseline
        )
    elif fault == "mixed-baseline":
        (tmp_path / "page0-000000/baseline/download.bin").write_bytes(current)
    elif fault == "oracle":
        (tmp_path / "oracle-boot0.bin").write_bytes(bytes(512))
    elif fault == "first-sector":
        (tmp_path / "page0-000000/first/sector.bin").write_bytes(bytes(512))
    elif fault == "unexpected-second-sector":
        (tmp_path / "page0-000000/second/sector.bin").write_bytes(bytes(512))
    elif fault == "later-start":
        later["operations"][0]["started_at"] = report["started_at"]
    elif fault == "later-file":
        (tmp_path / "page1-004200/first/partial.bin").write_bytes(b"later attempt")
    elif fault == "continuation":
        later["continuation"] = C.continuation(second)
    elif fault == "extra-baseline":
        later["baseline"] = copy.deepcopy(group["baseline"])
    elif fault == "binding":
        report["att_hci_binding"] = {}
    elif fault == "wrong-nonce":
        second["nonce"] = group["operations"][0]["nonce"]
    elif fault == "wrong-offset":
        second["nor_offset"] = 0x4200
    elif fault == "failed-verification":
        second["verification"] = group["operations"][0]["verification"]
    elif fault == "history-collision":
        plan["parent"]["prior_names"].append(second["nonce"])
    elif fault == "short-epoch":
        report["ended_at"] = "2026-10-14T10:01:00.100000+00:00"
    elif fault == "stage-time":
        second["ended_at"] = "2026-10-14T10:01:19+00:00"
        second["started_at"] = report["started_at"]
    elif fault == "parent":
        source = copy.deepcopy(plan["parent"])
        source["directory"] = "/different-admitted-parent"
        with pytest.raises(ValueError):
            verify(tmp_path, plan, baseline, oracles, code, source=source)
        return
    elif fault == "snapshot-time":
        path = tmp_path / "source-snapshot/manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["created_at"] = report["ended_at"]
        save(path, manifest)
    else:
        path = tmp_path / "source-snapshot/src/rcominote/experiments/paired_nor_audit.py"
        path.write_bytes(b"different source")
    reseal(tmp_path, report, plan)
    with pytest.raises((ValueError, KeyError)):
        verify(tmp_path, plan, baseline, oracles, code)


@pytest.mark.parametrize("pending", [False, True])
def test_real_extra_or_pending_parameter_transaction_refuses_nine_transaction_proof(tmp_path, pending):
    report, plan, baseline, _current, oracles, code = fixture(tmp_path)
    raw = (tmp_path / "session.btsnoop").read_bytes()
    rows = [
        (op, stamp, packet) for _n, op, stamp, packet in A.P.records(raw, report["hci_capture"]["records"])
    ]
    insertion = len(rows) - 1
    extra = remote(identifier=111) + ([] if pending else [update(12)])
    rows[insertion:insertion] = [(op, rows[insertion - 1][1], packet) for op, packet in extra]
    observed = rewrite_capture(tmp_path, report, rows)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    assert observed["pending"] or len(observed["transactions"]) == 10
    reseal(tmp_path, report, plan)
    with pytest.raises(ValueError, match="exactly nine|exactly 9"):
        verify(tmp_path, plan, baseline, oracles, code)


@pytest.mark.parametrize("fault", [None, "role", "coverage", "operation-success", "baseline", "source"])
def test_distinct_content_checkpoint_replays_full_source_and_binds_role(tmp_path, fault):
    failed, out = tmp_path / "failed", tmp_path / "checkpoint"
    report, plan, baseline, current, oracles, code = fixture(failed)
    with failure_gate(oracles, code):
        actual, state, result = K.failed_communication(failed, plan["parent"], baseline)
        assert actual == current and state == report["after"]
        out.mkdir()
        (out / "baseline.bin").write_bytes(current)
        checkpoint = {
            "profile": K.CONTENT_PROFILE,
            "failure_role": "complete-second-transfer-content-proof-only",
            "created_at": "2026-10-14T10:01:21+00:00",
            "observed_ended_at": report["ended_at"],
            "parent": plan["parent"],
            "failed": result,
            "communication_verified": True,
            "live_capture_performed": False,
            "original_job_ok": False,
            "original_operation_ok": False,
            "new_raw_nor_coverage_bytes": 0,
            "baseline": C.J.reference(out, out / "baseline.bin"),
        }
        if fault == "role":
            checkpoint.update(profile=K.PROFILE, original_page_ok=False, original_first_ok=False)
        elif fault == "coverage":
            checkpoint["new_raw_nor_coverage_bytes"] = 512
        elif fault == "operation-success":
            checkpoint["original_operation_ok"] = True
        elif fault == "baseline":
            (out / "baseline.bin").write_bytes(baseline)
            checkpoint["baseline"] = C.J.reference(out, out / "baseline.bin")
        elif fault == "source":
            checkpoint["failed"]["current_ring_sha256"] = A.A.sha(baseline)
        save(out / "checkpoint.json", checkpoint)
        if fault:
            with pytest.raises(ValueError):
                K.verify_admitted(checkpoint, out, plan["parent"], baseline)
        else:
            copied, observed, summary = K.verify_admitted(checkpoint, out, plan["parent"], baseline)
            assert copied == current and observed == state
            assert summary["profile"] == K.CONTENT_PROFILE
            assert summary["verification"]["new_raw_nor_coverage_bytes"] == 0
            assert summary["original_failed_retained"] is True
            assert summary["current_object_live_download_required_before_overwrite"] is True
            assert report["ok"] is False


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing-capture-role",
        "wrong-capture-role",
        "cross-source-version",
        "policy-change",
        "extra-error",
        "partial-file",
    ],
)
def test_status_frozen_source_requires_its_own_policy_and_recipe_identity(tmp_path, fault):
    failed, out = tmp_path / "failed", tmp_path / "checkpoint"
    report, plan, baseline, current, oracles, code = fixture(failed, profile=C.STATUS_CONTROL)
    if fault == "cross-source-version":
        manifest_path = failed / "source-snapshot/manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["source_files"] = [
            entry for entry in manifest["source_files"] if not entry["path"].endswith("paired_nor_recipe.py")
        ]
        save(manifest_path, manifest)
    elif fault == "policy-change":
        plan["profile"] = C.CONTINUOUS_CONTROL
        reseal(failed, report, plan)
    elif fault == "extra-error":
        report["after_error"] = "transport failed"
        reseal(failed, report, plan)
    elif fault == "partial-file":
        (failed / "page0-000000/second/download.bin").write_bytes(current[:2048])
    with failure_gate(oracles, code):
        if fault in ("cross-source-version", "policy-change", "extra-error", "partial-file"):
            with pytest.raises(ValueError):
                K.failed_communication(failed, plan["parent"], baseline)
            return
        observed, state, result = K.failed_communication(failed, plan["parent"], baseline)
        assert observed == current and state == report["after"]
        assert result["original_capture_profile"] == C.STATUS_CONTROL
        assert result["communication"]["new_raw_nor_coverage_bytes"] == 0
        out.mkdir()
        (out / "baseline.bin").write_bytes(current)
        checkpoint = {
            "profile": K.CONTENT_PROFILE,
            "failure_role": "complete-second-transfer-content-proof-only",
            "original_capture_profile": C.STATUS_CONTROL,
            "created_at": "2026-10-14T10:01:21+00:00",
            "observed_ended_at": report["ended_at"],
            "parent": plan["parent"],
            "failed": result,
            "communication_verified": True,
            "live_capture_performed": False,
            "original_job_ok": False,
            "original_operation_ok": False,
            "new_raw_nor_coverage_bytes": 0,
            "baseline": C.J.reference(out, out / "baseline.bin"),
        }
        if fault == "missing-capture-role":
            del checkpoint["original_capture_profile"]
        elif fault == "wrong-capture-role":
            checkpoint["original_capture_profile"] = C.CONTINUOUS_CONTROL
        save(out / "checkpoint.json", checkpoint)
        if fault:
            with pytest.raises(ValueError, match="capture profile"):
                K.verify_admitted(checkpoint, out, plan["parent"], baseline)
        else:
            copied, actual, summary = K.verify_admitted(checkpoint, out, plan["parent"], baseline)
            assert copied == current and actual == state and summary["profile"] == K.CONTENT_PROFILE
            assert report["ok"] is False and report["groups"][0]["operations"][1]["ok"] is False
