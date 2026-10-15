"""Synthetic full6transaction failed communication; no private capture fixtures."""

import json
from unittest.mock import patch

import pytest
import test_scratch_reuse_audit as old_fixture
from test_hci_interval import record
from test_paired_nor_audit import fixture as full_fixture
from test_paired_nor_audit import replace_baseline, replace_download
from test_paired_nor_padding import padding_case
from test_sd_nor_probe import info

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_checkpoint as K
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import paired_nor_runtime as R


def save(path, value):
    path.write_text(json.dumps(value))


def fixture(root):
    directory = root / "page0-024a00"
    with patch.object(old_fixture, "info", return_value=info(9)):
        page, plan, _page_plan, baseline = full_fixture(directory, offset=0x24A00)
    current, _prior = padding_case()
    baseline = bytearray(baseline)
    baseline[4095] = 0x20
    baseline = bytes(baseline)
    replace_baseline(page, directory, baseline)
    replace_download(page, directory, "first", current)
    first = page["operations"][0]
    capture = (directory / "session.btsnoop").read_bytes()
    wire = A.common.wire_positions(page, capture)
    end = first["verified_end"]
    selected = [*range(end), *range(*page["after_span"])]
    final_records = {n for i in range(*page["after_span"]) for n in range(wire[i][0], wire[i][1] + 1)}
    all_records = list(A.P.records(capture, page["hci_capture"]["records"]))
    retained = [
        row
        for row in all_records
        if row[0] <= wire[end - 1][1] or row[0] in final_records or row == all_records[-1]
    ]
    raw = A.P.H.HEADER + b"".join(
        record(packet, opcode, stamp=stamp) for _, opcode, stamp, packet in retained
    )
    (directory / "session.btsnoop").write_bytes(raw)
    page["att_packets"] = [page["att_packets"][i] for i in selected]
    page["after_span"] = [end, len(selected)]
    page["baseline"].update(ok=True, live_complete=True)
    first.update(ok=False, live_complete=False, barrier_complete=True, error=K.CONTENT_ERROR)
    del first["verification"]
    (directory / "first/sector.bin").unlink()
    for path in (directory / "second").iterdir():
        path.unlink()
    page["operations"][1] = plan["pages"][0]["operations"][1] | {"live_complete": False, "ok": False}
    observed = A.P.inspect(raw, link=page["transport"]["link"], final=True)
    assert len(observed["transactions"]) == 6
    page["hci_capture"] = {"bytes": len(raw), "sha256": A.A.sha(raw), "records": observed["records"]}
    page["att_hci_binding"] = A.dual_hci.bind(page, raw)
    page["disconnect_observation"]["event"] = observed["disconnects"][0]
    page.update(ok=False, error=K.CONTENT_ERROR, capture_error=K.CONTENT_ERROR)
    C.S.save(root / "plan.json", plan)
    ref = C.J.reference(root, root / "plan.json")
    page["plan"] = ref
    C.S.save(directory / "report.json", page)
    job = {
        "profile": C.PROFILE,
        "budget": plan["budget"],
        "plan": ref,
        "started_at": page["started_at"],
        "ended_at": page["ended_at"],
        "completed": [],
        "ok": False,
        "error": K.CONTENT_ERROR,
    }
    C.S.save(root / "report.json", job)
    snapshot = root / "source-snapshot"
    entries, code_pins = [], {}
    for name in K.STRICT_CAPTURE_CODE:
        path = snapshot / "src/rcominote/experiments" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic strict source identity {name}".encode())
        sha = A.A.sha(path.read_bytes())
        code_pins[name] = sha
        entries.append({"path": str(path.relative_to(snapshot)), "bytes": path.stat().st_size, "sha256": sha})
    C.S.save(
        snapshot / "manifest.json",
        {"source_files": entries, "test_files": [], "created_at": plan["planned_at"]},
    )
    return job, page, plan, baseline, current, code_pins


def test_full_failed_communication_produces_only_current_state_and_history_without_promotion(tmp_path):
    job, page, plan, baseline, current, pins = fixture(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with patch.object(K, "STRICT_CAPTURE_CODE", pins):
        actual, state, result = K.failed_communication(tmp_path, plan["parent"], baseline)
    assert actual == current and state == page["after"]
    assert result["communication"]["parameter_transactions"] == 6
    assert result["communication"]["new_raw_nor_coverage_bytes"] == 0
    assert result["communication"]["failed_content_accepted"] is False
    assert set(C.nonces(plan)).issubset(result["prior_names"])
    assert not job["ok"] and not page["ok"] and not page["operations"][0]["ok"]
    assert before == {p: p.read_bytes() for p in before}
    with pytest.raises(ValueError, match="failed whole"):
        A.replay(tmp_path, None)


@pytest.mark.parametrize(
    "fault",
    [
        "job-extra-error",
        "page-extra-error",
        "first-flag",
        "error",
        "barrier",
        "second-attempt",
        "second-file",
        "short",
        "binding",
        "state",
        "ack",
        "prefix-now-passes",
        "snapshot",
        "snapshot-path",
    ],
)
def test_checkpoint_rejects_incomplete_wire_artifact_mixing_or_arbitrary_content_labels(tmp_path, fault):
    job, page, plan, baseline, _current, pins = fixture(tmp_path)
    directory = tmp_path / "page0-024a00"
    first = page["operations"][0]
    if fault == "job-extra-error":
        job["transport_error"] = "actual failed capture"
    elif fault == "page-extra-error":
        page["after_error"] = "final identity missing"
    elif fault == "first-flag":
        first["ok"] = True
    elif fault == "error":
        first["error"] = "ValueError: unrelated"
    elif fault == "barrier":
        first["barrier_complete"] = False
    elif fault == "second-attempt":
        page["operations"][1]["producer_attempted"] = True
    elif fault == "second-file":
        (directory / "second/partial.bin").write_bytes(b"later attempt")
    elif fault == "short":
        (directory / "first/download.bin").write_bytes(b"partial")
    elif fault == "binding":
        page["att_hci_binding"] = {}
    elif fault == "state":
        page["state_verification"] = {}
    elif fault == "ack":
        first["frames"].pop()
    elif fault == "prefix-now-passes":
        # A convincing exception label is insufficient: original strict failure must replay.
        baseline = bytearray(baseline)
        baseline[4095] = ord(".")
        baseline = bytes(baseline)
        replace_baseline(page, directory, baseline)
    else:
        path = tmp_path / "source-snapshot/manifest.json"
        manifest = json.loads(path.read_bytes())
        entry = manifest["source_files"][0]
        if fault == "snapshot":
            (path.parent / entry["path"]).write_bytes(b"changed")
        else:
            previous = path.parent / entry["path"]
            entry["path"] = "other/" + previous.name
            target = path.parent / entry["path"]
            target.parent.mkdir()
            target.write_bytes(previous.read_bytes())
            save(path, manifest)
    save(tmp_path / "report.json", job)
    save(directory / "report.json", page)
    with patch.object(K, "STRICT_CAPTURE_CODE", pins), pytest.raises((ValueError, FileNotFoundError)):
        K.failed_communication(tmp_path, plan["parent"], baseline)


def test_offline_create_and_verify_checkpoint_are_distinct_from_live_capture(tmp_path):
    failed, out = tmp_path / "failed", tmp_path / "checkpoint"
    _job, _page, plan, baseline, current, pins = fixture(failed)
    with (
        patch.object(K, "STRICT_CAPTURE_CODE", pins),
        patch.object(R, "private_output"),
        patch.object(C.S, "now", return_value="2026-10-14T10:03:00+00:00"),
        patch.object(C, "parent_gate", return_value=(baseline, plan["expected_before"], plan["parent"])),
    ):
        ring, state, summary = K.create(None, failed, out)
    checkpoint = json.loads((out / "checkpoint.json").read_bytes())
    assert ring == current and state == summary["latest_info"]
    assert checkpoint["live_capture_performed"] is False and "ok" not in checkpoint
    assert checkpoint["new_raw_nor_coverage_bytes"] == 0
    assert not (out / "report.json").exists()
    with patch.object(K, "STRICT_CAPTURE_CODE", pins):
        assert K.verify_admitted(checkpoint, out, plan["parent"], baseline)[2] == summary
    checkpoint["failed"]["prior_names"].pop()
    with patch.object(K, "STRICT_CAPTURE_CODE", pins), pytest.raises(ValueError, match="source changed"):
        K.verify_admitted(checkpoint, out, plan["parent"], baseline)


def test_checkpoint_cycle_checked_before_source_admission(tmp_path):
    out = tmp_path / "cycle"
    out.mkdir()
    checkpoint = {
        "profile": K.PROFILE,
        "communication_verified": True,
        "live_capture_performed": False,
        "original_job_ok": False,
        "original_page_ok": False,
        "original_first_ok": False,
        "new_raw_nor_coverage_bytes": 0,
        "observed_ended_at": "2026-10-14T09:00:00+00:00",
        "created_at": "2026-10-14T10:00:00+00:00",
        "parent": {"directory": str(out)},
    }
    C.S.save(out / "checkpoint.json", checkpoint)
    with patch.object(K, "verify_admitted") as verify, pytest.raises(ValueError, match="Cycle"):
        C.parent_gate(out, None)
    verify.assert_not_called()


def test_iterative_checkpoint_parent_then_v3_prepare_replays_real_wire_without_failed_promotion(tmp_path):
    failed, anchor, out = tmp_path / "failed", tmp_path / "legacy", tmp_path / "checkpoint"
    job, page, plan, baseline, current, pins = fixture(failed)
    (anchor / "second").mkdir(parents=True)
    report = {
        "profile": C.legacy.PROFILE,
        "ok": True,
        "after": plan["expected_before"],
        "ended_at": plan["parent"]["ended_at"],
    }
    anchor_plan, anchor_proof = {"prior_names": plan["parent"]["prior_names"]}, {"verified": True}
    C.S.save(anchor / "report.json", report)
    C.S.save(anchor / "plan.json", anchor_plan)
    (anchor / "second/download.bin").write_bytes(baseline)
    (anchor / "session.btsnoop").write_bytes(b"synthetic legacy anchor; only its outer replay stubbed")
    anchor_pins = {name: A.A.sha((anchor / name).read_bytes()) for name in C.LEGACY_PINS}
    refs = {name: C.pins.pinned(anchor / name, sha)[1] for name, sha in anchor_pins.items()}
    plan["parent"] = C.source_summary(
        anchor, report, anchor_plan, anchor_proof, baseline, report["after"], refs
    )
    save(failed / "plan.json", plan)
    job["plan"] = page["plan"] = C.J.reference(failed, failed / "plan.json")
    save(failed / "report.json", job)
    save(failed / "page0-024a00/report.json", page)
    with (
        patch.object(K, "STRICT_CAPTURE_CODE", pins),
        patch.object(C, "LEGACY_PINS", anchor_pins),
        patch.object(C.old, "replay", return_value=anchor_proof),
        patch.object(R, "private_output"),
        patch.object(C.S, "now", return_value="2026-10-14T10:03:00+00:00"),
    ):
        K.create(None, failed, out)
        ring, state, summary = C.parent_gate(out, None)
        next_plan, next_baseline = C.prepare(None, out, [0x24A00], prefix_policy=C.F.PADDING_POLICY)
        assert C.source_gate(next_plan, None) == current
        assert next_baseline == ring == current and state == page["after"]
        assert summary["profile"] == K.PROFILE and summary["verification"]["new_raw_nor_coverage_bytes"] == 0
        assert set(C.nonces(plan)).issubset(summary["prior_names"])
        assert next_plan["profile"] == C.PROFILE_V3
        with pytest.raises(ValueError, match="failed parent"):
            C.parent_gate(failed, None)
