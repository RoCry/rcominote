"""Synthetic exact GATT/HCI failure bytes; mocked historical NOR replay only."""

import copy
import struct
from unittest.mock import patch

import pytest
from test_dual_probe import acl, info
from test_hci_interval import HANDLE, addr, event, record
from test_param_window import CONTROL
from test_status_window_job import original_fixture, plan_fixture

from rcominote.experiments import status_remaining_checkpoint as K


def failure_fixture(plan, good, *, reason=8, extra=None):
    report = original_fixture(plan, 1)
    report.update(
        ok=False,
        pair_verified=False,
        final_audit_complete=False,
        status_events=[],
        error=K.ERROR,
        capture_error=K.ERROR,
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
        expected_before=good["after"],
    )
    for key in ("before", "after", "predecessor_state_verification"):
        report.pop(key)
    report["transport"]["update_attempted"] = False
    for op in report["operations"]:
        op.update(ok=False, sd_write_attempted=False)
        op.pop("live_complete")
    report["att_packets"] = [
        {"direction": d, "hex": h, "monotonic_ns": i} for i, (d, h) in enumerate(K.GATT_TRACE)
    ]
    body = b"\0" + struct.pack("<HBB", HANDLE, 0, 0) + addr(K.H.PEER) + bytes(12)
    connect = event(0x3E, b"\x0a" + body + struct.pack("<HHHB", 48, 4, 600, 0))
    rows = [CONTROL, (3, connect)]
    rows.extend((4 if d == "tx" else 5, acl(bytes.fromhex(h), d)) for d, h in K.GATT_TRACE)
    if extra:
        rows.append((4, acl(extra, "tx")))
    rows.append((3, event(5, struct.pack("<BHB", 0, HANDLE, reason))))
    raw = K.H.HEADER + b"".join(record(p, op, stamp=100 + i) for i, (op, p) in enumerate(rows))
    report["hci_capture"] = {"bytes": len(raw), "sha256": K.W.S.audit.sha(raw), "records": len(rows)}
    return report, raw


def test_discovery_failure_proves_no_producers_writes_identity_or_coverage():
    plan, _ = plan_fixture()
    good = original_fixture(plan, 0)
    report, raw = failure_fixture(plan, good)
    original = copy.deepcopy(report)
    result = K.discovery_failure(report, raw, plan, good)
    assert result["att_packets"] == 19 and result["disconnect"]["reason"] == 8
    assert result["producer_executions"] == result["sd_write_attempts"] == 0
    assert result["identity_observations"] == result["new_raw_nor_coverage_bytes"] == 0
    assert report == original


@pytest.mark.parametrize(
    "fault",
    [
        "ok",
        "before",
        "write",
        "action",
        "nonce",
        "target",
        "state",
        "status",
        "hci",
        "att",
        "terminal",
        "reason",
        "extra",
    ],
)
def test_discovery_failure_rejects_promotion_missing_bytes_or_execution(fault):
    plan, _ = plan_fixture()
    good = original_fixture(plan, 0)
    report, raw = failure_fixture(
        plan,
        good,
        reason=22 if fault == "reason" else 8,
        extra=b"\x52\x22\0hello" if fault == "extra" else None,
    )
    if fault == "ok":
        report["ok"] = True
    elif fault == "before":
        report["before"] = info()
    elif fault == "write":
        report["operations"][0]["sd_write_attempted"] = True
    elif fault == "action":
        report["operations"][0]["actions_start"] = 19
    elif fault == "nonce":
        report["operations"][0]["name"] = "rcfffffffffe"
    elif fault == "target":
        report["operations"][0]["producer"] = "dbg fread spi_flash 0x2800"
    elif fault == "state":
        report["expected_before"] = info(1)
    elif fault == "status":
        report["status_events"] = [{}]
    elif fault == "hci":
        raw = raw[:-1]
    elif fault == "att":
        report["att_packets"].pop()
    elif fault == "terminal":
        report["att_packets"][-1]["hex"] = "042b002b00"
    with pytest.raises(ValueError):
        K.discovery_failure(report, raw, plan, good)


def synthetic_checkpoint(root, monkeypatch):
    plan, prefix = plan_fixture()
    good = original_fixture(plan, 0)
    failed, raw = failure_fixture(plan, good)
    for label in ("2800", "2a00", "2c00", "2e00"):
        for name in ("first", "second"):
            (root / label / name).mkdir(parents=True)
    block = bytes([0xA8]) * 512
    (root / "2800/first/sector.bin").write_bytes(block)
    (root / "2800/session.btsnoop").write_bytes(b"explicitly mocked complete pair capture")
    (root / "2a00/session.btsnoop").write_bytes(raw)
    K.W.S.save(root / "2800/report.json", good)
    K.W.S.save(root / "2a00/report.json", failed)
    K.W.S.save(root / "job-plan.json", plan)
    result = {"nor_range": [0x2800, 0x2A00], "bytes": 512, "sha256": K.W.S.audit.sha(block)}
    job = {
        "profile": K.W.PROFILE,
        "ok": False,
        "error": K.ERROR,
        "active_slot": "2a00",
        "plan": K.W.J.reference(root, root / "job-plan.json"),
        "started_at": "2026-10-14T10:02:00+00:00",
        "ended_at": failed["ended_at"],
        "completed": [{"report": K.W.J.reference(root, root / "2800/report.json"), "verification": result}],
    }
    snapshot = {
        key: ("2800" if key == "active_slot" else value)
        for key, value in job.items()
        if key not in ("error", "ended_at")
    }
    K.W.S.save(root / "checkpoint-2800.json", snapshot)
    K.W.S.save(root / "report.json", job)
    monkeypatch.setattr(K, "PINS", {name: K.W.S.audit.sha((root / name).read_bytes()) for name in K.PINS})
    return plan, prefix, block, result


def test_checkpoint_assembles_only_replayed_prefix_and_success2800(tmp_path, monkeypatch):
    plan, prefix, block, result = synthetic_checkpoint(tmp_path, monkeypatch)
    with (
        patch.object(K.previous, "verify", return_value=(prefix, info(), plan["checkpoint"])),
        patch.object(K.W.N, "replay", return_value=result) as replay,
    ):
        actual, state, summary = K.verify(tmp_path, tmp_path)
    assert actual == prefix + block and len(actual) == 2560
    assert state == info() and summary["verified_prefix"] == [0x2000, 0x2A00]
    assert summary["original_job_ok"] is summary["original_failed_pair_verified"] is False
    assert summary["failed_discovery"]["new_raw_nor_coverage_bytes"] == 0
    assert set(summary["prior_names"]) >= {n for slot in plan["slots"] for n in slot["names"]}
    replay.assert_called_once_with(tmp_path / "2800", tmp_path)


@pytest.mark.parametrize("fault", ["pin", "plan", "source", "provenance", "later", "output"])
def test_checkpoint_rejects_changed_source_provenance_or_later_activity(tmp_path, monkeypatch, fault):
    plan, prefix, _, result = synthetic_checkpoint(tmp_path, monkeypatch)
    old = copy.deepcopy(plan["checkpoint"])
    if fault == "pin":
        (tmp_path / "2a00/report.json").write_text("{}")
    elif fault == "plan":
        (tmp_path / "job-plan.json").write_text("{}")
    elif fault == "source":
        (tmp_path / "2800/first/sector.bin").write_bytes(bytes(512))
    elif fault == "provenance":
        old["pins"] = {"different": True}
    elif fault == "later":
        (tmp_path / "2c00/first/extra").write_bytes(b"unexpected")
    elif fault == "output":
        (tmp_path / "fw1_boot.bin").write_bytes(bytes(4096))
    with (
        patch.object(K.previous, "verify", return_value=(prefix, info(), old)),
        patch.object(K.W.N, "replay", return_value=result),
        pytest.raises(ValueError),
    ):
        K.verify(tmp_path, tmp_path)
