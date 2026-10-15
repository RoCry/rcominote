"""Synthetic failed known-control source: full11txn wire, no private captures."""

import copy
import json
from datetime import datetime
from unittest.mock import patch

import pytest
import test_scratch_reuse_audit as old_fixture
from test_hci_interval import record
from test_paired_nor_control import fixture as control_fixture
from test_param_window import remote, update
from test_sd_nor_probe import info

from rcominote.experiments import owned_file_recovery as O


def save(path, value):
    path.write_text(json.dumps(value))


def fixture(root):
    with patch.object(old_fixture, "info", return_value=info(9)):
        report, plan, baseline, oracles = control_fixture(root)
    group = report["groups"][1]
    op = group["operations"][0]
    end = op["actions_end"]
    capture = (root / "session.btsnoop").read_bytes()
    wire = O.A.common.wire_positions(report, capture)
    records = list(O.A.P.records(capture, report["hci_capture"]["records"]))
    extra = O.A.P.inspect(capture, link=report["transport"]["link"], final=True)["transactions"][11]
    low, high = min(extra["remote_request"]["records"]), extra["update"]["record"]
    selected = [r for r in records if r[0] <= wire[end - 1][1] and not low <= r[0] <= high]
    timeout = "2026-10-14T10:01:18+00:00"
    closed = O.A.P.H.EPOCH_US + int(datetime.fromisoformat(timeout).timestamp() * 1_000_000)
    selected.append((0, records[-1][1], closed + 100, records[-1][3]))
    raw = O.A.P.H.HEADER + b"".join(
        record(packet, opcode, stamp=stamp) for _, opcode, stamp, packet in selected
    )
    (root / "session.btsnoop").write_bytes(raw)
    report["att_packets"] = report["att_packets"][:end]
    keep = {
        *plan["pages"][1]["operations"][0],
        "before",
        "started_at",
        "producer_attempted",
        "sd_write_attempted",
        "notifications",
        "writes",
        "frames",
        "log_session_complete",
        "actions_start",
        "actions_end",
        "ack_count",
        "end_received",
        "pending_hex",
        "actions_verification",
    }
    group["operations"][0] = {key: value for key, value in op.items() if key in keep} | {
        "ok": False,
        "live_complete": False,
        "error": "TimeoutError: ",
        "ended_at": timeout,
    }
    group["operations"][1] = plan["pages"][1]["operations"][1] | {
        "ok": False,
        "live_complete": False,
    }
    group.update(candidate=False, live_complete=False)
    for label in ("first", "second"):
        for path in (root / "page1-004200" / label).iterdir():
            path.unlink()
    for key in ("after", "after_span", "after_verification", "state_verification", "verification"):
        report.pop(key, None)
    report.update(
        ok=False,
        error="TimeoutError: ",
        capture_error="TimeoutError: ",
        after_error=O.OMITTED,
        close_requested_us=closed,
        close_completed_us=closed + 200,
        disconnect_observed_us=closed + 300,
    )
    observed = O.A.P.inspect(raw, link=report["transport"]["link"], final=True)
    assert len(observed["transactions"]) == 11 and not observed["pending"]
    report["hci_capture"] = {"bytes": len(raw), "sha256": O.A.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = O.A.dual_hci.bind(report, raw)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    snapshot = root / "source-snapshot"
    entries, code = [], {}
    for name in O.CODE:
        path = snapshot / "src/rcominote/experiments" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic frozen known-control source {name}".encode())
        code[name] = O.A.A.sha(path.read_bytes())
        entries.append(
            {"path": str(path.relative_to(snapshot)), "bytes": path.stat().st_size, "sha256": code[name]}
        )
    save(
        snapshot / "manifest.json",
        {"source_files": entries, "test_files": [], "created_at": plan["planned_at"]},
    )
    save(root / "report.json", report)
    pins = {name: O.A.A.sha((root / name).read_bytes()) for name in O.PINS}
    return report, plan, baseline, oracles, pins, code


def verify(root, plan, baseline, oracles, pins, code):
    with (
        patch.object(O, "PINS", pins),
        patch.object(O, "CODE", code),
        patch.object(O.C.pins, "oracles", return_value=oracles),
    ):
        return O.failed_source(root, plan["parent"], baseline)


def reseal(root, report, plan, pins):
    save(root / "plan.json", plan)
    report["plan"] = O.C.J.reference(root, root / "plan.json")
    save(root / "report.json", report)
    return {name: O.A.A.sha((root / name).read_bytes()) for name in pins}


def test_full_failed_source_proves_only_historical_state_and_unknown_current_file(tmp_path):
    report, plan, baseline, oracles, pins, code = fixture(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = verify(tmp_path, plan, baseline, oracles, pins, code)
    assert result["current_file_unknown"] is result["original_failed_retained"] is True
    assert result["last_verified_state"] == report["groups"][1]["baseline"]["after"]
    assert result["last_verified_state"]["device"]["free_capacity"] == 59589
    assert result["historical_ring_sha256"] == report["groups"][1]["baseline"]["download_sha256"]
    assert result["complete_downloads"] == 4 and result["parameter_transactions"] == 11
    assert result["pending_prior_writes"] == 1 and result["last_actions"]["f0_frames"] == 0
    assert set(result["prior_names"]) == set(plan["parent"]["prior_names"]) | set(O.C.nonces(plan))
    assert "verification" not in result and "raw_range" not in result
    assert before == {p: p.read_bytes() for p in before}
    assert report["ok"] is report["groups"][1]["operations"][0]["ok"] is False
    with pytest.raises(ValueError, match="Original failed"):
        O.A.replay(tmp_path, None)


@pytest.mark.parametrize("name", list(O.PINS))
def test_original_input_digest_is_checked_before_any_semantic_admission(tmp_path, name):
    _report, plan, baseline, oracles, pins, code = fixture(tmp_path)
    with (tmp_path / name).open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(ValueError):
        verify(tmp_path, plan, baseline, oracles, pins, code)


@pytest.mark.parametrize(
    "fault",
    [
        "top-success",
        "wrong-error",
        "capture-error",
        "missing-omission",
        "invented-final",
        "group-success",
        "failed-group-candidate",
        "failed-stage-success",
        "prior-stage-failure",
        "producer-not-attempted",
        "sd-not-attempted",
        "normalization",
        "download",
        "after",
        "second-started",
        "second-file",
        "first-file",
        "extra-error",
        "wrong-offset",
        "wrong-nonce",
        "wrong-last-before",
        "short-baseline",
        "mixed-baseline",
        "oracle",
        "ack",
        "binding",
        "wait-under-eight",
        "late-snapshot",
        "epoch",
        "history-collision",
    ],
)
def test_resealed_metadata_cannot_replace_missing_original_stage_proof(tmp_path, fault):
    report, plan, baseline, oracles, pins, code = fixture(tmp_path)
    group = report["groups"][1]
    op = group["operations"][0]
    if fault == "top-success":
        report["ok"] = True
    elif fault == "wrong-error":
        report["error"] = "ValueError: parser"
    elif fault == "capture-error":
        report["capture_error"] = "TimeoutError: outer60"
    elif fault == "missing-omission":
        report["after_error"] = "missing after"
    elif fault == "invented-final":
        report["after"] = copy.deepcopy(op["before"])
    elif fault == "group-success":
        report["groups"][0]["ok"] = True
    elif fault == "failed-group-candidate":
        group["candidate"] = True
    elif fault == "failed-stage-success":
        op["ok"] = True
    elif fault == "prior-stage-failure":
        report["groups"][0]["operations"][1]["live_complete"] = False
    elif fault == "producer-not-attempted":
        op["producer_attempted"] = False
    elif fault == "sd-not-attempted":
        op["sd_write_attempted"] = False
    elif fault in ("normalization", "download", "after"):
        op[
            {"normalization": "normalization_requested_us", "download": "download_start", "after": "after"}[
                fault
            ]
        ] = 0
    elif fault == "second-started":
        group["operations"][1]["started_at"] = op["started_at"]
    elif fault in ("first-file", "second-file"):
        (tmp_path / "page1-004200" / fault.split("-")[0] / "unexpected.bin").write_bytes(b"partial")
    elif fault == "extra-error":
        report["transport_error"] = "unexpected"
    elif fault == "wrong-offset":
        op["nor_offset"] = 0
    elif fault == "wrong-nonce":
        op["nonce"] = report["groups"][0]["operations"][0]["nonce"]
    elif fault == "wrong-last-before":
        op["before"] = info(8)
    elif fault in ("short-baseline", "mixed-baseline"):
        (tmp_path / "page1-004200/baseline/download.bin").write_bytes(
            b"partial" if fault == "short-baseline" else baseline
        )
    elif fault == "oracle":
        (tmp_path / "oracle-boot0.bin").write_bytes(bytes(512))
    elif fault == "ack":
        op["frames"].pop()
    elif fault == "binding":
        report["att_hci_binding"] = {}
    elif fault == "wait-under-eight":
        op["ended_at"] = "2026-10-14T10:01:09.100000+00:00"
    elif fault == "late-snapshot":
        path = tmp_path / "source-snapshot/manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["created_at"] = report["ended_at"]
        save(path, manifest)
    elif fault == "epoch":
        report["started_at"] = "2026-10-14T10:01:05+00:00"
    else:
        plan["parent"]["prior_names"].append(op["nonce"])
    pins = reseal(tmp_path, report, plan, pins)
    with pytest.raises((ValueError, KeyError)):
        verify(tmp_path, plan, baseline, oracles, pins, code)


@pytest.mark.parametrize("fault", ["missing-code", "source-bytes", "duplicate-path", "path-escape"])
def test_snapshot_manifest_must_preserve_frozen_code_bytes_and_directory(tmp_path, fault):
    report, plan, baseline, oracles, pins, code = fixture(tmp_path)
    path = tmp_path / "source-snapshot/manifest.json"
    manifest = json.loads(path.read_bytes())
    if fault == "missing-code":
        manifest["source_files"].pop()
    elif fault == "source-bytes":
        target = path.parent / manifest["source_files"][0]["path"]
        target.write_bytes(b"different source")
    elif fault == "duplicate-path":
        manifest["test_files"].append(manifest["source_files"][0])
    else:
        manifest["source_files"][0]["path"] = "../../plan.json"
    save(path, manifest)
    pins = reseal(tmp_path, report, plan, pins)
    with pytest.raises(ValueError):
        verify(tmp_path, plan, baseline, oracles, pins, code)


@pytest.mark.parametrize("complete", [False, True])
def test_actual_extra_remote_fast_or_pending_request_refuses_wait_fast_failure(tmp_path, complete):
    report, plan, baseline, oracles, pins, code = fixture(tmp_path)
    raw = (tmp_path / "session.btsnoop").read_bytes()
    rows = list(O.A.P.records(raw, report["hci_capture"]["records"]))
    extra = remote(identifier=111) + ([update(12)] if complete else [])
    stamp = rows[-1][2] - 100
    rows = (
        rows[:-1] + [(0, opcode, stamp + n, packet) for n, (opcode, packet) in enumerate(extra)] + rows[-1:]
    )
    raw = O.A.P.H.HEADER + b"".join(record(packet, opcode, stamp=stamp) for _, opcode, stamp, packet in rows)
    (tmp_path / "session.btsnoop").write_bytes(raw)
    observed = O.A.P.inspect(raw, link=report["transport"]["link"], final=True)
    assert len(observed["transactions"]) == 11 + complete and bool(observed["pending"]) is not complete
    report["hci_capture"] = {"bytes": len(raw), "sha256": O.A.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = O.A.dual_hci.bind(report, raw)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    pins = reseal(tmp_path, report, plan, pins)
    with pytest.raises(ValueError, match="exactly 11"):
        verify(tmp_path, plan, baseline, oracles, pins, code)
