"""Second CLOSED discovery case; original heavy prefix audit is separately tested.

Synthetic HCI bytes are parsed without mocks. Only the already tested completed
prefix/current-file proof and its identity timeline are supplied by the fixture.
"""

import json
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from test_prefilled_link_checkpoint import evidence as old_evidence
from test_prefilled_link_checkpoint import wire

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_link_checkpoint as K
from rcominote.experiments import prefilled_nor_pages as N


@pytest.fixture
def evidence(tmp_path):
    generator = old_evidence.__wrapped__(tmp_path)
    original = next(generator)
    failed, source, baseline, current, state, job, _plan, old_report, _old_pins = original
    with ExitStack() as stack:
        source["profile"] = C.PREFILLED_PROFILE
        source["prior_names"] = [C.F.NAME, *(f"rc{i:010x}" for i in range(81))]
        with patch.object(C, "parent_gate", return_value=(baseline, state, source)):
            plan, _ = N.prepare(
                None,
                None,
                [0x1ED600, 0x1ED800, 0x1EDA00, 0x1EDC00],
                gap_policy=C.F.PREFILL_WAKE_GAP_POLICY,
                startup_policy=C.startup.POLICY,
            )
        plan["planned_at"] = "2026-10-14T16:00:00+00:00"
        (failed / "plan.json").write_text(json.dumps(plan))
        reference = C.J.reference(failed, failed / "plan.json")
        job.update(plan=reference, budget=plan["budget"], completed=[job["completed"][-1]])
        page = C.page_plan(plan, 1, state, job["completed"][0]["ended_at"])
        report = C.report(page) | {
            k: old_report[k]
            for k in (
                "started_at",
                "ended_at",
                "status_events",
                "capture_error",
                "error",
                "monitor_exit",
                "monitor_stop",
            )
        }
        report["plan"] = reference
        with patch.object(K, "ATT", K.NEXT_HCI_ATT):
            raw = wire(report)
        report["att_packets"] = [
            {**row, "direction": direction, "hex": pdu}
            for row, (direction, pdu) in zip(report["att_packets"], K.NEXT_HOST_ATT, strict=True)
        ]
        directory = failed / K.NEXT_PAGE
        directory.mkdir()
        for label in C.stages(page):
            (directory / label).mkdir()
        (directory / "session.btsnoop").write_bytes(raw)
        (directory / "report.json").write_text(json.dumps(report))
        (failed / "report.json").write_text(json.dumps(job))
        accepted = failed / plan["pages"][0]["directory"]
        accepted.mkdir()
        (accepted / "report.json").write_text(json.dumps({"after_span": [0, 1]}))
        (accepted / "session.btsnoop").write_bytes(b"separately verified complete prefix capture")
        snapshot = failed / "source-snapshot"
        manifest = json.loads((snapshot / "manifest.json").read_bytes())
        for label, count in (("source_files", 7), ("test_files", 8)):
            for i in range(count):
                rel = f"{'src' if label == 'source_files' else 'tests'}/extra{i}.py"
                target = snapshot / rel
                target.write_bytes(b"synthetic immutable extra")
                manifest[label].append(
                    {"path": rel, "bytes": target.stat().st_size, "sha256": A.A.sha(target.read_bytes())}
                )
        (snapshot / "manifest.json").write_text(json.dumps(manifest))
        pins = {name: A.A.sha((failed / name).read_bytes()) for name in K.NEXT_PINS}
        stack.enter_context(patch.object(K, "NEXT_PINS", pins))
        stack.enter_context(
            patch.object(K, "NEXT_MANIFEST_SHA", A.A.sha((snapshot / "manifest.json").read_bytes()))
        )
        stack.enter_context(patch.object(K, "NEXT_CODE", K.CODE))
        stack.enter_context(
            patch.object(A, "completed_prefix", return_value=([{"pair_verified": True}], current, state))
        )
        yield failed, source, baseline, current, state, job, plan, report, pins
    generator.close()


def reseal(e):
    failed, _source, _baseline, _current, _state, job, plan, report, pins = e
    (failed / "plan.json").write_text(json.dumps(plan))
    job["plan"] = report["plan"] = C.J.reference(failed, failed / "plan.json")
    (failed / "report.json").write_text(json.dumps(job))
    (failed / K.NEXT_PAGE / "report.json").write_text(json.dumps(report))
    for name in pins:
        pins[name] = A.A.sha((failed / name).read_bytes())


def test_closed_new_case_preserves90_unsent_history_and_accepted_identity_not_failed_or_cli(evidence):
    failed, source, baseline, current, state, _job, _plan, report, _pins = evidence
    raw = (failed / K.NEXT_PAGE / "session.btsnoop").read_bytes()
    with pytest.raises(ValueError):
        K.link_failure(report, raw)  # Never silently widen old trace.
    proof = K.link_failure(report, raw, host_att=K.NEXT_HOST_ATT, hci_att=K.NEXT_HCI_ATT)
    assert proof["application_writes"] == proof["parameter_transactions"] == 0
    data, info, result = K.failed_prefix(failed, source, baseline)
    assert data == current and info == state and len(result["prior_names"]) == 90
    assert len(result["original_completed_prefix"]) == 1
    assert (
        result["latest_identity_response_at"]
        < result["last_successful_page_ended_at"]
        < result["failed_ended_at"]
    )
    with pytest.raises(ValueError, match="failed"):
        C.parent_gate(failed, None)


@pytest.mark.parametrize(
    "fault",
    [
        "host-order",
        "host-byte",
        "hci-order",
        "hci-byte",
        "identity",
        "stage",
        "later",
        "prefix",
        "history",
        "source",
        "flag",
        "epoch",
        "error",
        "snapshot",
        "plan",
    ],
)
def test_copied_metadata_cannot_bypass_exact_both_directional_traces_zero_io_and_prefix(evidence, fault):
    failed, source, baseline, _current, _state, job, plan, report, _pins = evidence
    if fault == "host-order":
        report["att_packets"][3], report["att_packets"][4] = (
            report["att_packets"][4],
            report["att_packets"][3],
        )
    elif fault == "host-byte":
        report["att_packets"][-1]["hex"] = "042a002b00"
    elif fault in ("hci-order", "hci-byte"):
        pattern = list(K.NEXT_HCI_ATT)
        if fault == "hci-order":
            pattern[3], pattern[4] = pattern[4], pattern[3]
        else:
            pattern[-1] = ("tx", "12160000")
        host = report["att_packets"]
        with patch.object(K, "ATT", pattern):
            raw = wire(report)
        report["att_packets"] = host
        (failed / K.NEXT_PAGE / "session.btsnoop").write_bytes(raw)
    elif fault == "identity":
        report["after"] = source["latest_info"]
    elif fault == "stage":
        report["operations"][0]["sd_write_attempted"] = False
    elif fault == "later":
        folder = failed / plan["pages"][2]["directory"]
        folder.mkdir()
        (folder / "report.json").write_text("unexpected")
    elif fault == "prefix":
        job["completed"] *= 2
    elif fault == "history":
        source["prior_names"].pop()
    elif fault == "source":
        source["profile"] = C.PREFILL_PROFILE_V2
    elif fault == "flag":
        job["ok"] = True
    elif fault == "epoch":
        report["started_at"] = report["ended_at"]
    elif fault == "error":
        report["after_error"] = "independent CLI cannot repair this"
    elif fault == "snapshot":
        (failed / "source-snapshot/tests/extra0.py").write_bytes(b"substituted")
    else:
        plan["offsets"].reverse()
    reseal(evidence)
    with pytest.raises((ValueError, KeyError)):
        K.failed_prefix(failed, source, baseline)


def test_host_create_forward_replay_requires_exact_current_copy_and_original_case(evidence, tmp_path):
    failed, source, baseline, current, state, *_ = evidence
    from rcominote.experiments import paired_nor_runtime as runtime

    out = tmp_path / "next-checkpoint"
    with (
        patch.object(runtime, "private_output"),
        patch.object(C, "parent_gate", return_value=(baseline, state, source)),
    ):
        data, info, summary = K.create(None, failed, out)
    checkpoint = json.loads((out / "checkpoint.json").read_bytes())
    assert (
        data == current
        and info == state
        and K.verify_admitted(checkpoint, out, source, baseline)[2] == summary
    )
    assert summary["verification"]["new_raw_nor_coverage_bytes"] == summary["verification"]["device_io"] == 0
    assert summary["current_object_live_download_required_before_overwrite"] is True
    checkpoint["failed"]["prior_names"].pop()
    with pytest.raises(ValueError):
        K.verify_admitted(checkpoint, out, source, baseline)


def test_new_source_cannot_be_reclassified_as_old_case_by_whole_hash_or_schema_labels(evidence):
    failed, source, baseline, _current, _state, job, _plan, _report, pins = evidence
    with patch.object(K, "NEXT_PINS", pins | {"report.json": "f" * 64}), pytest.raises(ValueError):
        K.failed_prefix(failed, source, baseline)
    # Resealing only the report selector cannot replace its original plan pin.
    changed = pins.copy()
    job["error"] = "not the closed discovery error"
    (failed / "report.json").write_text(json.dumps(job))
    changed["report.json"] = A.A.sha((failed / "report.json").read_bytes())
    with patch.object(K, "NEXT_PINS", changed), pytest.raises(ValueError):
        K.failed_prefix(failed, source, baseline)
