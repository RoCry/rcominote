"""Synthetic feature-event bytes and job linkage; historical NOR/control replay mocked."""

import copy
import json
import struct
from pathlib import Path
from unittest.mock import patch

import pytest
from test_hci_interval import HANDLE, addr, event, record
from test_param_window import CONTROL
from test_sd_nor_probe import info
from test_status_window_job import original_fixture
from test_status_window_job import plan_fixture as parent_plan

from rcominote.experiments import controlled_tail_checkpoint as K


def historical_plan():
    old, prefix = parent_plan()
    prefix += bytes([0xA8]) * 512
    basis = old["checkpoint"] | {
        "directory": "/synthetic/latest-preproducer",
        "latest_info": info(),
        "verified_prefix": [0x2000, 0x2A00],
        "bytes": 2560,
        "sha256": K.A.sha(prefix),
        "prior_names": [f"rc{100 + i:010x}" for i in range(31)],
        "original_job_ok": False,
        "original_failed_pair_verified": False,
    }
    control = {
        "directory": "/synthetic/successful-control",
        "pins": dict(K.control_source.PINS),
        "verification": dict(K.control_source.EXPECTED),
        "latest_info": info(),
        "ended_at": "2026-10-14T10:00:30+00:00",
        "source_image_sha256": old["source_image_sha256"],
    }
    plan = old | {
        "profile": K.PROFILE,
        "checkpoint_directory": basis["directory"],
        "checkpoint": basis,
        "verified_prefix": [0x2000, 0x2A00],
        "new_range": [0x2A00, 0x3000],
        "max_connections": 3,
        "max_producer_executions": 6,
        "max_sd_test_files": 6,
        "startup_policy": K.startup.POLICY,
        "control_parent": control,
        "slots": [
            {
                "nor_offset": offset,
                "directory": f"{offset:04x}",
                "names": [f"rc{1000 + 2 * index + number:010x}" for number in (0, 1)],
            }
            for index, offset in enumerate(K.OFFSETS)
        ],
    }
    return plan, prefix


def feature_fixture(plan):
    report = original_fixture(plan, 2)
    report.update(
        ok=False,
        pair_verified=False,
        final_audit_complete=False,
        error=K.ERROR,
        capture_error=K.ERROR,
        att_packets=[],
        status_events=[],
        status_event_policy=K.events.POLICY,
        startup_policy=K.startup.POLICY,
        control_parent=plan["control_parent"],
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
        transport={"update_attempted": False, "policy": K.C.POLICY},
    )
    for key in ("before", "after", "predecessor_state_verification"):
        report.pop(key)
    for operation in report["operations"]:
        operation.pop("live_complete")
        operation.update(ok=False, sd_write_attempted=False)
    body = b"\0" + struct.pack("<HBB", HANDLE, 0, 0) + addr(K.parameters.H.PEER) + bytes(12)
    connect = event(0x3E, b"\x0a" + body + struct.pack("<HHHB", 48, 4, 600, 0))
    rows = [(0xFFFF000C, b"synthetic filler".ljust(17, b".")) for _ in range(23)]
    rows[2], rows[17], rows[19] = CONTROL, (3, connect), (0xFFFF000C, b"synthetic filler".ljust(19, b"."))
    rows[20:] = [
        (2, b"\x16\x20\x02" + struct.pack("<H", HANDLE)),
        (3, bytes.fromhex("0f0400011620")),
        (3, b"\x3e\x0c\x04\x3e" + struct.pack("<H", HANDLE) + bytes(8)),
    ]
    raw = K.parameters.H.HEADER + b"".join(
        record(packet, opcode & 0xFFFF, index=opcode >> 16, stamp=100 + i)
        for i, (opcode, packet) in enumerate(rows)
    )
    report["hci_capture"] = {"bytes": len(raw), "sha256": K.A.sha(raw), "records": len(rows)}
    assert len(raw) == 950
    return report, raw


def test_failed_feature_exchange_proves_zero_execution_and_preserves_original_flags():
    plan, _ = historical_plan()
    report, raw = feature_fixture(plan)
    original = copy.deepcopy(report)
    proof = K.feature_failure(report, raw)
    assert proof["feature_complete_status"] == 0x3E and proof["reported_errno"] == 38
    assert proof["acl_packets"] == proof["att_packets"] == proof["identity_observations"] == 0
    assert (
        proof["producer_executions"] == proof["sd_write_attempts"] == proof["new_raw_nor_coverage_bytes"] == 0
    )
    assert report == original


@pytest.mark.parametrize("fault", ["promoted", "write", "identity", "att", "feature-status", "hci-partial"])
def test_feature_failure_rejects_promotion_execution_or_changed_hci(fault):
    plan, _ = historical_plan()
    report, raw = feature_fixture(plan)
    if fault == "promoted":
        report["ok"] = True
    elif fault == "write":
        report["operations"][0]["sd_write_attempted"] = True
    elif fault == "identity":
        report["before"] = info()
    elif fault == "att":
        report["att_packets"] = [{"direction": "tx", "hex": "02f700"}]
    elif fault == "feature-status":
        raw = raw[:-11] + b"\0" + raw[-10:]
        report["hci_capture"]["sha256"] = K.A.sha(raw)
    else:
        raw = raw[:-1]
    with pytest.raises(ValueError):
        K.feature_failure(report, raw)


def synthetic_job(root, monkeypatch):
    plan, prefix = historical_plan()
    results, completed = {}, []
    for index, slot in enumerate(plan["slots"]):
        label = slot["directory"]
        for name in ("first", "second"):
            (root / label / name).mkdir(parents=True)
        if index < 2:
            report = original_fixture(plan, index) | {
                "startup_policy": K.startup.POLICY,
                "control_parent": plan["control_parent"],
            }
            raw = bytes([0xAA + index * 2]) * 512
            (root / label / "first/sector.bin").write_bytes(raw)
            capture = b"historical complete pair capture replay explicitly mocked"
            result = {
                "nor_range": [slot["nor_offset"], slot["nor_offset"] + 512],
                "bytes": 512,
                "sha256": K.A.sha(raw),
            }
            results[label] = result
        else:
            report, capture = feature_fixture(plan)
        (root / label / "report.json").write_text(json.dumps(report))
        (root / label / "session.btsnoop").write_bytes(capture)
        if index < 2:
            completed.append(
                {"report": K.J.reference(root, root / label / "report.json"), "verification": results[label]}
            )
    (root / "job-plan.json").write_text(json.dumps(plan))
    job = {
        "profile": K.PROFILE,
        "ok": False,
        "error": K.ERROR,
        "active_slot": "2e00",
        "completed": completed,
        "plan": K.J.reference(root, root / "job-plan.json"),
        "started_at": "2026-10-14T10:02:00+00:00",
        "ended_at": "2026-10-14T10:08:00+00:00",
    }
    (root / "report.json").write_text(json.dumps(job))
    for index, label in enumerate(("2a00", "2c00")):
        snapshot = {
            key: label if key == "active_slot" else completed[: index + 1] if key == "completed" else value
            for key, value in job.items()
            if key not in ("error", "ended_at")
        }
        (root / f"checkpoint-{label}.json").write_text(json.dumps(snapshot))
    monkeypatch.setattr(K, "PINS", {name: K.A.sha((root / name).read_bytes()) for name in K.PINS})
    return plan, prefix, results


def test_prefix_uses_only_actual2560_anchor_and_two_successful_sectors(tmp_path, monkeypatch):
    plan, prefix, results = synthetic_job(tmp_path, monkeypatch)
    with (
        patch.object(K.state_source, "verify", return_value=(prefix, info(), plan["checkpoint"])),
        patch.object(K.control_source, "verify", return_value=plan["control_parent"]) as control,
        patch.object(K.N, "replay", side_effect=lambda directory, image: results[directory.name]) as replay,
    ):
        data, state, summary = K.verify(tmp_path, tmp_path)
    assert data == prefix + bytes([0xAA]) * 512 + bytes([0xAC]) * 512 and len(data) == 3584
    assert state == info() and len(summary["prior_names"]) == 37
    assert summary["control_state_parent"] == plan["checkpoint"]
    assert summary["original_job_ok"] is summary["original_failed_pair_verified"] is False
    assert replay.call_count == 2
    control.assert_called_once_with(Path(plan["control_parent"]["directory"]), tmp_path, plan["checkpoint"])


@pytest.mark.parametrize(
    "fault", ["pin", "checkpoint", "source", "provenance", "failed-payload", "output", "prestate"]
)
def test_changed_sources_or_failed_candidates_never_promote_coverage(tmp_path, monkeypatch, fault):
    plan, prefix, results = synthetic_job(tmp_path, monkeypatch)
    basis = copy.deepcopy(plan["checkpoint"])
    if fault == "pin":
        (tmp_path / "2e00/report.json").write_text("{}")
    elif fault == "checkpoint":
        path = tmp_path / "checkpoint-2a00.json"
        path.write_text("{}")
        K.PINS[path.name] = K.A.sha(path.read_bytes())
    elif fault == "source":
        (tmp_path / "2a00/first/sector.bin").write_bytes(bytes(512))
    elif fault == "provenance":
        basis["sha256"] = "0" * 64
    elif fault == "failed-payload":
        (tmp_path / "2e00/first/sector.bin").write_bytes(bytes(512))
    elif fault == "output":
        (tmp_path / "fw1_boot.bin").write_bytes(bytes(4096))
    elif fault == "prestate":
        path = tmp_path / "2e00/report.json"
        report = json.loads(path.read_bytes())
        report["expected_before"] = info(1)
        path.write_text(json.dumps(report))
        K.PINS["2e00/report.json"] = K.A.sha(path.read_bytes())
    with (
        patch.object(K.state_source, "verify", return_value=(prefix, info(), basis)),
        patch.object(K.control_source, "verify", return_value=plan["control_parent"]),
        patch.object(K.N, "replay", side_effect=lambda directory, image: results[directory.name]),
        pytest.raises(ValueError),
    ):
        K.verify(tmp_path, tmp_path)
