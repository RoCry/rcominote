"""Pinned-role linkage tests; full paired-prefix audit is independently tested.

Only the existing heavy completed-prefix body/identity timeline are stubbed;
partial discovery HCI/ATT is synthetic real bytes, parsed without mocks.
"""

import json
import struct
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from test_hci_interval import record
from test_prefilled_nor_control import RAM
from test_sd_nor_probe import info

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_link_checkpoint as K
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_nor_pages as N


def stamp(iso):
    return A.P.H.EPOCH_US + int(A.datetime.fromisoformat(iso).timestamp() * 1_000_000)


def wire(report, *, fault=None):
    start = stamp(report["started_at"]) + 1000
    rows = [(8, b"", start + i * 10_000) for i in range(1, 59)]
    rows[2] = (0, bytes.fromhex("0001f82b268e19ac6863693000000000"), rows[2][2])
    rows[17] = (
        3,
        bytes.fromhex("3e1f0a00000800000e7caef0c05000000000000000000000000030000400580200"),
        rows[17][2],
    )
    indices = [24, 26, 27, 30, 31, 32, 33, 36, 37, 39, 40, 42, 43, 45, 47, 49, 50, 52, 53, 55, 56]
    report["att_packets"] = []
    for index, (direction, packet) in zip(indices, K.ATT, strict=True):
        body = bytes.fromhex(packet)
        if fault == "app-write" and index == 56:
            body = b"\x12\x22\0app"
        l2cap = struct.pack("<HH", len(body), 4) + body
        packet = struct.pack("<HH", 2048 | (2 << 12), len(l2cap)) + l2cap
        rows[index - 1] = (4 if direction == "tx" else 5, packet, rows[index - 1][2])
        report["att_packets"].append({"direction": direction, "hex": body.hex(), "monotonic_ns": index})
    disconnect = b"\x05\x04\0\0\x08" + bytes([0x16 if fault == "reason" else 8])
    rows[56] = (3, disconnect, start + 6_560_000)
    rows[57] = (8, b"", start + 6_560_001)
    raw = A.P.H.HEADER + b"".join(record(packet, opcode, stamp=when) for opcode, packet, when in rows)
    report.update(
        hci_capture={"bytes": len(raw), "records": 58, "sha256": A.A.sha(raw)},
        close_completed_us=rows[-1][2] + 1,
    )
    return raw


@pytest.fixture
def evidence(tmp_path):
    failed = tmp_path / "failed"
    failed.mkdir()
    state = info(9)
    baseline, current = b"b" * 4096, b"c" * 4096
    source = {
        "directory": str(tmp_path / "known-v2"),
        "profile": P.PROFILE_V2,
        "ended_at": "2026-10-14T15:00:00+00:00",
        "latest_info": state,
        "prior_names": [C.F.NAME, *[f"rc{i:010x}" for i in range(53)]],
    }
    oracle = {
        "image": {"file": "/synthetic/image"},
        "sha256": A.A.sha(RAM),
        "bytes": 4096,
        "last_byte": "48",
        "cpu_address": P.RAM.ADDRESS,
        "image_slice": list(P.RAM_SLICE),
        "permanent_ram_stability_assumed": False,
    }
    with ExitStack() as stack:
        stack.enter_context(patch.object(P, "RAM_SHA", A.A.sha(RAM)))
        stack.enter_context(patch.object(P, "ram_source", return_value=(RAM, oracle)))
        with patch.object(C, "parent_gate", return_value=(baseline, state, source)):
            plan, _ = N.prepare(None, None, [0x1EC200, 0x1EC400, 0x1EC600, 0x1EC800])
        plan["planned_at"] = "2026-10-14T16:00:00+00:00"
        C.S.save(failed / "plan.json", plan)
        reference = C.J.reference(failed, failed / "plan.json")
        page = C.page_plan(plan, 3, state, "2026-10-14T16:40:44+00:00")
        report = C.report(page) | {
            "started_at": "2026-10-14T16:40:45+00:00",
            "ended_at": "2026-10-14T16:40:53+00:00",
            "plan": reference,
            "status_events": [],
            "capture_error": K.ERROR,
            "error": K.ERROR,
            "monitor_exit": 0,
            "monitor_stop": {"signal": "SIGINT", "requested": True, "delivery": "sent"},
        }
        raw = wire(report)
        directory = failed / K.PAGE
        directory.mkdir()
        for label in C.stages(page):
            (directory / label).mkdir()
        (directory / "session.btsnoop").write_bytes(raw)
        C.S.save(directory / "report.json", report)
        job = {
            "profile": N.PROFILE,
            "budget": plan["budget"],
            "started_at": "2026-10-14T16:01:00+00:00",
            "ended_at": "2026-10-14T16:40:54+00:00",
            "plan": reference,
            "ok": False,
            "error": K.ERROR,
            "completed": [
                {"ended_at": f"2026-10-14T16:40:{20 + i * 12:02d}+00:00", "after": state} for i in range(3)
            ],
        }
        C.S.save(failed / "report.json", job)
        third = failed / plan["pages"][2]["directory"]
        third.mkdir()
        C.S.save(third / "report.json", {"after_span": [0, 1]})
        (third / "session.btsnoop").write_bytes(b"prefix communication independently audited elsewhere")
        snapshot = failed / "source-snapshot"
        snapshot.mkdir()
        entries = []
        for i in range(278):
            name = (
                "src/rcominote/experiments/synthetic.py"
                if i == 0
                else f"{'src' if i < 146 else 'tests'}/fixture{i}.py"
            )
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"synthetic source")
            entries.append(
                {"path": name, "bytes": target.stat().st_size, "sha256": A.A.sha(target.read_bytes())}
            )
        manifest = {
            "created_at": "2026-10-14T15:30:00+00:00",
            "source_files": entries[:146],
            "test_files": entries[146:],
        }
        C.S.save(snapshot / "manifest.json", manifest)
        stack.enter_context(
            patch.object(K, "MANIFEST_SHA", A.A.sha((snapshot / "manifest.json").read_bytes()))
        )
        stack.enter_context(patch.object(K, "CODE", {"synthetic.py": entries[0]["sha256"]}))
        pins = {name: A.A.sha((failed / name).read_bytes()) for name in K.PINS}
        stack.enter_context(patch.object(K, "PINS", pins))
        stack.enter_context(
            patch.object(A, "completed_prefix", return_value=([{"pair_verified": True}] * 3, current, state))
        )
        stack.enter_context(
            patch.object(
                A.common, "wire_positions", return_value=[(0, 0, stamp("2026-10-14T16:40:42+00:00"))]
            )
        )
        yield failed, source, baseline, current, state, job, plan, report, pins


def save_changes(e):
    failed, _source, _base, _current, _state, job, _plan, report, pins = e
    (failed / "report.json").write_text(json.dumps(job))
    (failed / K.PAGE / "report.json").write_text(json.dumps(report))
    for name in pins:
        pins[name] = A.A.sha((failed / name).read_bytes())


def test_zero_coverage_ownership_preserves_last_identity_epoch_and_all_unsent_names(evidence):
    failed, source, baseline, current, state, *_ = evidence
    actual, info, result = K.failed_prefix(failed, source, baseline)
    assert actual == current and info == state and len(result["prior_names"]) == 62
    assert (
        result["latest_identity_response_at"]
        < result["last_successful_page_ended_at"]
        < result["failed_ended_at"]
    )
    assert result["failure"]["application_writes"] == 0 and result["failure"]["identity_observed"] is False
    assert json.loads((failed / "report.json").read_bytes())["ok"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "jobflag",
        "pageflag",
        "stageflag",
        "started",
        "identity",
        "transport",
        "error",
        "attempt",
        "file",
        "app-write",
        "reason",
        "epoch",
        "omitted",
        "source",
        "pin",
    ],
)
def test_exact_role_cannot_absorb_extra_activity_or_transport_evidence(evidence, fault):
    failed, source, baseline, _current, _state, job, _plan, report, _pins = evidence
    if fault == "jobflag":
        job["ok"] = True
    elif fault == "pageflag":
        report["ok"] = True
    elif fault == "stageflag":
        report["operations"][0]["ok"] = 0
    elif fault == "started":
        report["operations"][0]["started_at"] = report["started_at"]
    elif fault == "identity":
        report["before"] = {}
    elif fault == "transport":
        report["transport"]["link"] = K.LINK
    elif fault == "error":
        report["after_error"] = "unrelated failure"
    elif fault == "attempt":
        report["operations"][1]["sd_write_attempted"] = False
    elif fault == "file":
        (failed / K.PAGE / "baseline/download.bin").write_bytes(b"partial")
    elif fault in ("app-write", "reason"):
        (failed / K.PAGE / "session.btsnoop").write_bytes(wire(report, fault=fault))
    elif fault == "epoch":
        report["started_at"] = "2026-10-14T16:40:52+00:00"
    elif fault == "omitted":
        report["att_packets"].pop()
    elif fault == "source":
        source["profile"] = C.PROFILE
    else:
        (failed / K.PAGE / "session.btsnoop").write_bytes(b"mixed capture")
        with pytest.raises(ValueError):
            K.failed_prefix(failed, source, baseline)
        return
    save_changes(evidence)
    with pytest.raises((ValueError, KeyError)):
        K.failed_prefix(failed, source, baseline)


def test_source_snapshot_all_originals_and_critical_path_pins_are_required(evidence):
    failed, source, baseline, *_ = evidence
    (failed / "source-snapshot/src/rcominote/experiments/synthetic.py").write_bytes(b"substituted")
    with pytest.raises(ValueError):
        K.failed_prefix(failed, source, baseline)


def test_host_create_and_forward_admission_only_seed_prefilled_unknown(evidence, tmp_path):
    failed, source, baseline, current, state, *_ = evidence
    out = tmp_path / "checkpoint"
    from rcominote.experiments import paired_nor_runtime as R

    with (
        patch.object(R, "private_output"),
        patch.object(C, "parent_gate", return_value=(baseline, state, source)),
    ):
        actual, info, summary = K.create(None, failed, out)
    assert actual == current and info == state and summary["verification"]["new_raw_nor_coverage_bytes"] == 0
    assert (
        summary["verification"]["device_io"] == 0
        and summary["current_object_live_download_required_before_overwrite"] is True
    )
    checkpoint = json.loads((out / "checkpoint.json").read_bytes())
    assert K.verify_admitted(checkpoint, out, source, baseline)[2] == summary
    with patch.object(C, "parent_gate", return_value=(current, state, summary)):
        plan, _ = N.prepare(None, out, [0x1EC800])
        assert set(C.nonces(plan)).isdisjoint(summary["prior_names"])
        with pytest.raises(ValueError, match="only prefilled unknown"):
            C.prepare(None, out, [0x1EC800])
        with pytest.raises(ValueError, match="restricted to prefilled unknown"):
            P.prepare_v2(None, out)
    checkpoint["parent"]["directory"] = str(out)
    (out / "checkpoint.json").write_text(json.dumps(checkpoint))
    with pytest.raises(ValueError, match="Cycle"):
        C.parent_gate(out, None)


@pytest.mark.parametrize("fault", ["current", "history", "created", "flag", "extra-error"])
def test_checkpoint_cannot_change_actual_current_history_or_observation_boundary(evidence, tmp_path, fault):
    failed, source, baseline, _current, state, *_ = evidence
    from rcominote.experiments import paired_nor_runtime as R

    out = tmp_path / "checkpoint"
    with (
        patch.object(R, "private_output"),
        patch.object(C, "parent_gate", return_value=(baseline, state, source)),
    ):
        K.create(None, failed, out)
    checkpoint = json.loads((out / "checkpoint.json").read_bytes())
    if fault == "current":
        (out / "baseline.bin").write_bytes(b"substituted" * 372 + b"x" * 4)
        checkpoint["baseline"] = C.J.reference(out, out / "baseline.bin")
    elif fault == "history":
        checkpoint["failed"]["prior_names"].pop()
    elif fault == "created":
        checkpoint["created_at"] = "2026-10-14T16:40:45+00:00"
    elif fault == "flag":
        checkpoint["original_job_ok"] = True
    else:
        checkpoint["transport_error"] = "unexplained"
    with pytest.raises(ValueError):
        K.verify_admitted(checkpoint, out, source, baseline)


def test_iterative_walker_dispatches_distinct_checkpoint_without_legacy_role_relabel(evidence, tmp_path):
    failed, source, baseline, current, state, *_ = evidence
    from rcominote.experiments import paired_nor_runtime as R

    out = tmp_path / "checkpoint"
    with (
        patch.object(R, "private_output"),
        patch.object(C, "parent_gate", return_value=(baseline, state, source)),
    ):
        _data, _state, expected = K.create(None, failed, out)
    # Outer legacy/known bodies have their own complete-wire tests. Here their
    # stubs isolate the new real-file iterative dispatch and full failure edge.
    anchor, known = tmp_path / "anchor", Path(source["directory"])
    (anchor / "second").mkdir(parents=True)
    known.mkdir()
    old = {"profile": C.legacy.PROFILE, "ok": True, "after": state, "ended_at": source["ended_at"]}
    C.S.save(anchor / "report.json", old)
    C.S.save(anchor / "plan.json", {})
    (anchor / "session.btsnoop").write_bytes(b"outer admission stub")
    (anchor / "second/download.bin").write_bytes(baseline)
    C.S.save(known / "plan.json", {"profile": P.PROFILE_V2, "parent": {"directory": str(anchor)}})
    C.S.save(
        known / "report.json",
        {"profile": P.PROFILE_V2, "ok": True, "plan": C.J.reference(known, known / "plan.json")},
    )
    pins = {name: A.A.sha((anchor / name).read_bytes()) for name in C.LEGACY_PINS}
    with (
        patch.object(C, "LEGACY_PINS", pins),
        patch.object(C.old, "replay", return_value={"verified": True}),
        patch.object(P, "validate_plan"),
        patch.object(P, "replay_admitted", return_value=(baseline, state, source)),
        patch.object(K.K, "header", side_effect=AssertionError("wrong legacy role")),
    ):
        data, info, summary = C.parent_gate(out, None)
    assert data == current and info == state and summary == expected
