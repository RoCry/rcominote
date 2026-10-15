"""Real synthetic v3 variable-tail failure and accepted-prefix separation.

No private fixtures or parser mocks: actual unchanged lowhex byte outsideprefix.
"""

import copy
import json
import shutil
from contextlib import contextmanager
from unittest.mock import patch

import pytest
import test_scratch_reuse_audit as old_fixture
from test_nor_freshness import place
from test_paired_nor_audit import replace_download, two_page_archive
from test_scratch_reuse_parser import SECTOR, chain
from test_sd_nor_probe import info

from rcominote.experiments import paired_nor_page_content as H

A, C, K = H.A, H.C, H.K


def save(path, value):
    path.write_text(json.dumps(value))


def fixture(root, *, prefix_count=1):
    with patch.object(old_fixture, "info", return_value=info(9)):
        job, plan, baseline = two_page_archive(root)
    plan.update(profile=C.PROFILE_V3, prefix_policy=C.F.PADDING_POLICY, budget=C.budgets(3))
    future = copy.deepcopy(plan["pages"][1])
    future.update(page_index=2, nor_offset=0x24800, directory="page2-024800")
    for op, nonce in zip(future["operations"], ("rcdead000001", "rcdead000002"), strict=True):
        op.update(
            nonce=nonce,
            uptime_command=f"kernel uptime {nonce}",
            nor_offset=0x24800,
            producer="dbg fread spi_flash 0x24800",
        )
    plan["pages"].append(future)
    plan["offsets"].append(0x24800)
    for slot in plan["pages"]:
        for op in slot["operations"]:
            op["prefix_policy"] = C.F.PADDING_POLICY
    save(root / "plan.json", plan)
    ref = C.J.reference(root, root / "plan.json")
    previous, state, ended = baseline, plan["expected_before"], plan["parent"]["ended_at"]
    completed = []
    for index, slot in enumerate(plan["pages"]):
        path = root / slot["directory"]
        if index > prefix_count:
            if path.exists():
                shutil.rmtree(path)
            for label in C.STAGES:
                (path / label).mkdir(parents=True, exist_ok=True)
            continue
        report = json.loads((path / "report.json").read_bytes())
        page = C.page_plan(plan, index, state, ended)
        report.update({key: page[key] for key in C.fields(page)})
        report["plan"] = ref
        for slot_op, op in zip(slot["operations"], report["operations"], strict=True):
            op.update(slot_op)
        for stage in [report["baseline"], *report["operations"]]:
            stage.update(ok=True, live_complete=True)
        if index == prefix_count:
            target = bytearray(SECTOR)
            target[25 * 16 + 10] = 0x9F
            target = bytes(target)
            first, second = report["operations"]
            first_data = bytearray(place(chain(first["nonce"], slot["nor_offset"], target), 1000))
            first_data[4095] = ord("f")
            first_data = bytes(first_data)
            replace_download(report, path, "first", first_data)
            body = chain(second["nonce"], slot["nor_offset"], target)
            at = body.index(b"       0:") + 25 * 60 + 41
            current = place(body, (4095 - at) % 4096)
            assert current[4095] == first_data[4095] == ord("f")
            replace_download(report, path, "second", current)
        first, second = report["operations"]
        first_data = (path / "first/download.bin").read_bytes()
        first["verification"] = C.payload(first, first_data, previous)
        (path / "first/sector.bin").write_bytes(bytes.fromhex(first["verification"]["sector_hex"]))
        if index < prefix_count:
            second_data = (path / "second/download.bin").read_bytes()
            second["verification"] = C.payload(second, second_data, first_data)
            proof = A.validate_page(report, path, page, previous)
            report.update(ok=True, verification=proof)
            save(path / "report.json", report)
            completed.append(A.ledger_entry(root, slot, report, proof))
            previous, state, ended = second_data, report["after"], report["ended_at"]
        else:
            try:
                C.payload(second, current, first_data)
            except ValueError as error:
                assert f"ValueError: {error}" == K.CONTENT_ERROR
            else:
                raise AssertionError("fixture must actually fail")
            second.update(ok=False, live_complete=False, barrier_complete=True, error=K.CONTENT_ERROR)
            second.pop("verification")
            (path / "second/sector.bin").unlink()
            report.update(ok=False, error=K.CONTENT_ERROR, capture_error=K.CONTENT_ERROR)
            report.pop("verification")
            save(path / "report.json", report)
            failed_page = report
    job.update(
        profile=C.PROFILE_V3,
        budget=plan["budget"],
        plan=ref,
        completed=completed,
        ended_at=failed_page["ended_at"],
        ok=False,
        error=K.CONTENT_ERROR,
    )
    job.pop("verification")
    save(root / "report.json", job)
    snapshot = root / "source-snapshot"
    code = {}
    entries = []
    for name in H.CAPTURE_CODE:
        path = snapshot / "src/rcominote/experiments" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic captured source {name}".encode())
        code[name] = A.A.sha(path.read_bytes())
        entries.append(
            {"path": str(path.relative_to(snapshot)), "bytes": path.stat().st_size, "sha256": code[name]}
        )
    save(
        snapshot / "manifest.json",
        {"source_files": entries, "test_files": [], "created_at": plan["planned_at"]},
    )
    return (
        job,
        failed_page,
        plan,
        baseline,
        current,
        {"code": code, "manifest": A.A.sha((snapshot / "manifest.json").read_bytes())},
    )


@contextmanager
def captured_source(pins):
    with (
        patch.object(H, "CAPTURE_CODE", pins["code"]),
        patch.object(H, "SOURCE_MANIFEST_SHA", pins["manifest"]),
    ):
        yield


def verify(root, plan, baseline, pins, *, source=None):
    with captured_source(pins):
        return H.verify(root, plan["parent"] if source is None else source, baseline)


def reseal(root, job, report, plan):
    save(root / "plan.json", plan)
    reference = C.J.reference(root, root / "plan.json")
    job["plan"] = report["plan"] = reference
    save(root / plan["pages"][len(job["completed"])]["directory"] / "report.json", report)
    save(root / "report.json", job)


@pytest.mark.parametrize("prefix_count", [0, 1])
def test_real_variable_tail_failure_adopts_only_communication_and_keeps_prefix_separate(
    tmp_path, prefix_count
):
    job, report, plan, baseline, current, pins = fixture(tmp_path, prefix_count=prefix_count)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    actual, state, result = verify(tmp_path, plan, baseline, pins)
    assert actual == current and state == report["after"]
    assert state["device"]["free_capacity"] == 59589
    assert len(result["original_completed_prefix"]) == prefix_count
    assert sum(proof["paired_bytes"] for proof in result["original_completed_prefix"]) == prefix_count * 512
    proof = result["communication"]
    assert proof["parameter_transactions"] == 9 and proof["downloads"] == 3
    assert proof["failed_content_accepted"] is False and proof["new_raw_nor_coverage_bytes"] == 0
    assert proof["content_error_reproduced"] == K.CONTENT_ERROR
    assert result["current_ring_sha256"] == A.A.sha(current)
    assert set(result["prior_names"]) == set(plan["parent"]["prior_names"]) | set(C.nonces(plan))
    assert before == {p: p.read_bytes() for p in before}
    assert job["ok"] is report["ok"] is report["operations"][1]["ok"] is False
    for gate in (A.replay, C.parent_gate):
        with pytest.raises(ValueError):
            gate(tmp_path, None)


@pytest.mark.parametrize(
    "fault",
    [
        "job-flag",
        "profile",
        "job-error",
        "job-extra-error",
        "page-extra-error",
        "stage-error",
        "warm-flag",
        "first-flag",
        "second-flag",
        "barrier",
        "content-proof",
        "second-sector",
        "later-file",
        "prefix-ledger",
        "prefix-flag",
        "prefix-sector",
        "plan-binding",
        "source",
        "partial",
        "mixed",
        "coherent-mix",
        "now-passes",
        "new-error",
        "state",
        "binding",
        "ack",
        "epoch",
        "stage-time",
        "source-bytes",
        "source-version",
        "source-time",
        "manifest-pin",
        "history-collision",
    ],
)
def test_resealed_failure_labels_cannot_replace_original_full_prefix_wire_or_policy(tmp_path, fault):
    job, report, plan, baseline, current, pins = fixture(tmp_path)
    index = len(job["completed"])
    path = tmp_path / plan["pages"][index]["directory"]
    second = report["operations"][1]
    if fault == "job-flag":
        job["ok"] = True
    elif fault == "profile":
        job["profile"] = C.PROFILE
    elif fault == "job-error":
        job["error"] = "TimeoutError: "
    elif fault == "job-extra-error":
        job["capture_error"] = "unexpected"
    elif fault == "page-extra-error":
        report["after_error"] = "missing final identity"
    elif fault == "stage-error":
        second["error"] = "ValueError: different grammar failure"
    elif fault == "warm-flag":
        report["baseline"]["live_complete"] = False
    elif fault == "first-flag":
        report["operations"][0]["ok"] = False
    elif fault == "second-flag":
        second["ok"] = True
    elif fault == "barrier":
        second["barrier_complete"] = False
    elif fault == "content-proof":
        second["verification"] = report["operations"][0]["verification"]
    elif fault == "second-sector":
        (path / "second/sector.bin").write_bytes(SECTOR)
    elif fault == "later-file":
        (tmp_path / "page2-024800/first/partial.bin").write_bytes(b"late")
    elif fault == "prefix-ledger":
        job["completed"].append(copy.deepcopy(job["completed"][0]))
    elif fault == "prefix-flag":
        prefix = tmp_path / plan["pages"][0]["directory"] / "report.json"
        data = json.loads(prefix.read_bytes())
        data["ok"] = False
        save(prefix, data)
        job["completed"][0]["report"] = C.J.reference(tmp_path, prefix)
    elif fault == "prefix-sector":
        (tmp_path / "page0-024400/first/sector.bin").write_bytes(bytes(512))
    elif fault == "plan-binding":
        report["plan"] = {"file": "unrelated.json"}
        save(path / "report.json", report)
    elif fault == "source":
        source = copy.deepcopy(plan["parent"])
        source["profile"] = C.PROFILE_V3
        with pytest.raises(ValueError):
            verify(tmp_path, plan, baseline, pins, source=source)
        return
    elif fault in ("partial", "mixed"):
        (path / "second/download.bin").write_bytes(current[:2048] if fault == "partial" else baseline)
    elif fault in ("coherent-mix", "now-passes", "new-error"):
        if fault == "coherent-mix":
            changed = (path / "first/download.bin").read_bytes()
        elif fault == "now-passes":
            changed = current[:4095] + b"e"
        else:
            changed = current.replace(second["nonce"].encode(), b"rcaaaaaaaaaa", 1)
            assert changed != current
        replace_download(report, path, "second", changed)
    elif fault == "state":
        report["after"] = info(8)
    elif fault == "binding":
        report["att_hci_binding"] = {}
    elif fault == "ack":
        second["frames"].pop()
    elif fault == "epoch":
        report["started_at"] = "2026-10-14T11:00:00+00:00"
    elif fault == "stage-time":
        second["started_at"] = report["started_at"]
    elif fault == "source-bytes":
        (tmp_path / "source-snapshot/src/rcominote/experiments/paired_nor_recipe.py").write_bytes(b"changed")
    elif fault == "manifest-pin":
        pins["manifest"] = "0" * 64
    elif fault in ("source-version", "source-time"):
        target = tmp_path / "source-snapshot/manifest.json"
        manifest = json.loads(target.read_bytes())
        if fault == "source-version":
            manifest["source_files"].pop()
        else:
            manifest["created_at"] = job["ended_at"]
        save(target, manifest)
        pins["manifest"] = A.A.sha(target.read_bytes())
    else:
        plan["parent"]["prior_names"].append(second["nonce"])
    if fault != "plan-binding":
        reseal(tmp_path, job, report, plan)
    with pytest.raises((ValueError, KeyError, FileNotFoundError)):
        verify(tmp_path, plan, baseline, pins)


@pytest.mark.parametrize("pending", [False, True])
def test_actual_additional_or_pending_parameter_transaction_rejects(tmp_path, pending):
    from test_paired_nor_control import rewrite_capture
    from test_param_window import remote, update

    job, report, plan, baseline, _current, pins = fixture(tmp_path)
    path = tmp_path / plan["pages"][1]["directory"]
    raw = (path / "session.btsnoop").read_bytes()
    rows = [
        (op, stamp, packet) for _n, op, stamp, packet in A.P.records(raw, report["hci_capture"]["records"])
    ]
    extra = remote(identifier=111) + ([] if pending else [update(12)])
    stamp = rows[-1][1]
    rows[-1:-1] = [(op, stamp, packet) for op, packet in extra]
    observed = rewrite_capture(path, report, rows)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    assert observed["pending"] or len(observed["transactions"]) == 10
    reseal(tmp_path, job, report, plan)
    with pytest.raises(ValueError, match="exactly 9"):
        verify(tmp_path, plan, baseline, pins)


@pytest.mark.parametrize(
    "fault", [None, "role", "capture-profile", "legacy-profile", "coverage", "baseline", "prefix-proof"]
)
def test_create_and_admission_bind_distinct_page_second_role_to_original_source(tmp_path, fault):
    from rcominote.experiments import paired_nor_runtime as runtime

    failed, out = tmp_path / "failed", tmp_path / "checkpoint"
    job, report, plan, baseline, current, pins = fixture(failed)
    with (
        captured_source(pins),
        patch.object(runtime, "private_output"),
        patch.object(C, "parent_gate", return_value=(baseline, plan["expected_before"], plan["parent"])),
        patch.object(C.S, "now", return_value="2026-10-14T10:10:00+00:00"),
    ):
        actual, state, summary = K.create(None, failed, out)
    assert actual == current and state == report["after"] and summary["profile"] == K.CONTENT_PROFILE
    assert (
        summary["verification"]["new_raw_nor_coverage_bytes"] == 0
        and summary["original_failed_retained"] is True
    )
    cp = json.loads((out / "checkpoint.json").read_bytes())
    assert cp["failure_role"] == H.ROLE and cp["original_capture_profile"] == C.PROFILE_V3
    if fault == "role":
        cp["failure_role"] = "complete-second-transfer-content-proof-only"
    elif fault == "capture-profile":
        cp["original_capture_profile"] = C.STATUS_CONTROL
    elif fault == "legacy-profile":
        cp.update(profile=K.PROFILE, original_page_ok=False, original_first_ok=False)
        cp.pop("failure_role")
        cp.pop("original_operation_ok")
        cp.pop("original_capture_profile")
    elif fault == "coverage":
        cp["new_raw_nor_coverage_bytes"] = 512
    elif fault == "baseline":
        (out / "baseline.bin").write_bytes(baseline)
        cp["baseline"] = C.J.reference(out, out / "baseline.bin")
    elif fault == "prefix-proof":
        cp["failed"]["original_completed_prefix"] = []
    if fault:
        save(out / "checkpoint.json", cp)
    with captured_source(pins):
        if fault:
            with pytest.raises(ValueError):
                K.verify_admitted(cp, out, plan["parent"], baseline)
        else:
            copied, latest, again = K.verify_admitted(cp, out, plan["parent"], baseline)
            assert copied == current and latest == state and again == summary
            assert job["ok"] is report["ok"] is False
