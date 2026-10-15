"""Readonly ownership is independent from NOR text and historical file equality."""

import asyncio
import copy
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from test_paired_nor_audit import relocate_wire
from test_scratch_postmortem_contract import fixture as readonly_fixture

from rcominote.experiments import owned_file_recovery as O
from rcominote.experiments import paired_nor_runtime as runtime


def fixture(directory, *, fault=None, prior_delta=0):
    actual, old_plan, previous = readonly_fixture(directory, fault=fault)
    actual.pop("stage_timeout_scope")
    latest = copy.deepcopy(actual["before"])
    # Latest observed predecessor may precede exactly one unverified SD write.
    raw = bytearray.fromhex(latest["device"]["raw"])
    import struct

    struct.pack_into(">I", raw, 4, latest["device"]["free_capacity"] + prior_delta)
    latest["device"] = O.A.Boyi.parse_device_info(bytes(raw))
    failed = {
        "last_verified_state": latest,
        "ended_at": "2026-10-14T09:00:00+00:00",
        "current_file_unknown": True,
        "original_failed_retained": True,
        "pending_prior_writes": 1,
        "directory": "/synthetic/failed",
        "prior_names": ["rc0123456789"],
    }
    plan = {
        "profile": O.PROFILE,
        "name": O.C.F.NAME,
        "budget": O.BUDGET.copy(),
        "expected_before": latest,
        "parent": old_plan["parent"],
        "failed": failed,
        "planned_at": old_plan["planned_at"],
        "startup_policy": O.C.startup.LEGACY_POLICY,
        "status_event_policy": O.C.E.POLICY,
    }
    actual.update({k: plan[k] for k in O.FIELDS})
    actual["producer_attempted"] = False
    actual["predecessor_state_verification"] = (
        O.verify_state(latest, actual["before"], sd_write=True) if prior_delta < 2 else {}
    )
    # The older fixture predates the mandatory HCI/page UTC epoch gate.
    timestamp = O.A.P.H.EPOCH_US + int(
        datetime.fromisoformat("2026-10-14T10:01:10+00:00").timestamp() * 1_000_000
    )
    relocate_wire(actual, directory, timestamp - 1000)
    O.C.S.save(directory / "plan.json", plan)
    actual["plan"] = O.C.J.reference(directory, directory / "plan.json")
    return actual, plan, previous


@pytest.mark.parametrize("delta", [0, 1])
def test_full_wire_new_current_file_may_differ_from_historical_ring(tmp_path, delta):
    actual, plan, historical = fixture(tmp_path, prior_delta=delta)
    data = (tmp_path / "retained/download.bin").read_bytes()
    assert data != historical
    original = copy.deepcopy(actual)
    proof = O.validate_readonly(actual, tmp_path, plan)
    assert proof["sha256"] == O.A.A.sha(data)
    assert proof["ownership_only"] is True and proof["original_failed_retained"] is True
    assert proof["new_raw_nor_coverage_bytes"] == proof["actions"] == proof["sd_writes"] == 0
    assert actual == original and actual["ok"] is False


@pytest.mark.parametrize("fault", ["default", "early-slow", "actions", "extra", "pending", "disconnect"])
def test_full_wire_faults_reject_without_content_salvage(tmp_path, fault):
    actual, plan, _previous = fixture(tmp_path, fault=fault)
    with pytest.raises(ValueError):
        O.validate_readonly(actual, tmp_path, plan)


@pytest.mark.parametrize(
    "fault", ["two-MiB", "partial", "extra-error", "flag", "time", "write", "nonce", "late-identity"]
)
def test_readonly_original_proof_mutations_fail(tmp_path, fault):
    actual, plan, _previous = fixture(tmp_path, prior_delta=2 if fault == "two-MiB" else 0)
    if fault == "partial":
        (tmp_path / "retained/download.bin").write_bytes(b"partial")
    elif fault == "extra-error":
        actual["unexpected_error"] = "transport failed"
    elif fault == "flag":
        actual["operation"]["live_complete"] = False
    elif fault == "time":
        actual["started_at"] = "2026-10-14T10:01:15+00:00"
    elif fault == "write":
        actual["sd_write_attempted"] = True
    elif fault == "nonce":
        actual["operation"]["nonce"] = "rc0123456789"
    elif fault == "late-identity":
        actual["state_verification"] = {}
    with pytest.raises(ValueError):
        O.validate_readonly(actual, tmp_path, plan)


@pytest.mark.parametrize(
    "fault", ["bool-budget", "offset", "pending-zero", "source-time", "target", "policy"]
)
def test_fixed_plan_rejects_broader_capability_before_source_io(tmp_path, monkeypatch, fault):
    _actual, plan, _previous = fixture(tmp_path)
    if fault == "bool-budget":
        plan["budget"]["sd_writes"] = False
    elif fault == "offset":
        plan["nor_offset"] = 0x4200
    elif fault == "pending-zero":
        plan["failed"]["pending_prior_writes"] = 0
    elif fault == "source-time":
        plan["planned_at"] = "2026-10-14T08:00:00+00:00"
    elif fault == "target":
        plan["name"] = "other"
    else:
        plan["startup_policy"] = O.C.startup.POLICY
    gate = Mock()
    monkeypatch.setattr(O.C, "parent_gate", gate)
    with pytest.raises(ValueError):
        O.source_gate(plan, None)
    gate.assert_not_called()


@pytest.mark.parametrize("top,stage", [(False, True), (True, False)])
def test_original_failed_recovery_never_becomes_admissible_parent(tmp_path, top, stage):
    actual, plan, previous = fixture(tmp_path)
    actual["ok"], actual["operation"]["ok"] = top, stage
    with pytest.raises(ValueError, match="Original failed"):
        O.replay_admitted(actual, plan, tmp_path, {}, previous)


@pytest.mark.parametrize("exception", [ValueError("stage"), TimeoutError(), asyncio.CancelledError()])
def test_runtime_failure_stops_download_and_timeout_omits_final_identity(tmp_path, monkeypatch, exception):
    actual, plan, _previous = fixture(tmp_path)
    actual["operation"] = {
        "operation_id": "retained",
        "name": O.C.F.NAME,
        "live_complete": False,
        "ok": False,
    }
    conn = SimpleNamespace(file_list=AsyncMock(return_value=[]))
    identity = AsyncMock()
    monkeypatch.setattr(O.shared, "identity", identity)
    monkeypatch.setattr(O.C.startup, "wait_startup", AsyncMock(return_value=({}, {})))
    monkeypatch.setattr(O, "plan_gate", Mock())
    monkeypatch.setattr(O.R, "normalize", AsyncMock(side_effect=exception))
    download = AsyncMock()
    monkeypatch.setattr(O.shared, "download", download)
    monkeypatch.setattr(O.R, "observe", Mock())
    with pytest.raises(type(exception)):
        asyncio.run(O.connected(conn, Mock(), actual, plan, tmp_path))
    download.assert_not_called()
    assert identity.await_count == (1 if isinstance(exception, (TimeoutError, asyncio.CancelledError)) else 2)
    assert actual["operation"]["live_complete"] is False


def test_private_output_rejects_before_recovery_auth_or_source(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "authorize", Mock(side_effect=AssertionError("authorization")))
    with pytest.raises(ValueError, match="private repo"):
        runtime.main(None, tmp_path / "missing-plan", tmp_path / "outside")


def test_capture_closed_dispatch_uses_readonly_guard_monitor_and_single_connection(tmp_path, monkeypatch):
    actual, plan, previous = fixture(tmp_path)
    device = SimpleNamespace(address=runtime.H.PEER)
    client = SimpleNamespace(start_notify=AsyncMock(), receive_guard=None)

    class Connection:
        offline_allowed = False

        def __init__(self, _device, _actual):
            self.client = client

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    monitor = SimpleNamespace(start=AsyncMock(), close=AsyncMock(return_value=0), stop={})
    monitor_factory = Mock(return_value=monitor)
    connected = AsyncMock()
    monkeypatch.setattr(runtime, "find_device", AsyncMock(return_value=device))
    monkeypatch.setattr(runtime, "Monitor", monitor_factory)
    monkeypatch.setattr(runtime, "DualConnection", Connection)
    monkeypatch.setattr(runtime, "Actions", Mock(side_effect=AssertionError("Actions capability")))
    monkeypatch.setattr(runtime.N, "attach_status_observer", Mock())
    monkeypatch.setattr(runtime.A, "setup", Mock(return_value={}))
    monkeypatch.setattr(runtime, "active_link", Mock(return_value={}))
    monkeypatch.setattr(runtime.closing, "observe_disconnect", AsyncMock())
    monkeypatch.setattr(O, "connected", connected)
    # Stop after closure/evidence entry; this unit tests wiring, not fake HCI proof.
    monitor.path = SimpleNamespace(read_bytes=Mock(side_effect=ValueError("synthetic final capture")))
    with pytest.raises(ValueError, match="synthetic final capture"):
        asyncio.run(runtime.capture(actual, plan, previous, tmp_path))
    assert monitor_factory.call_args.kwargs["seconds"] == 55
    assert client.start_notify.await_args.args[1] is O.readonly.forbidden_notification
    connected.assert_awaited_once()
    with pytest.raises(ValueError, match="Actions"):
        client.receive_guard(b"\x1b\x18\0stray")
    with pytest.raises(ValueError, match="outside sole"):
        client.receive_guard(b"\x1b\x2a\0stray")


def test_successful_readonly_node_admitted_iteratively_as_current_parent(tmp_path, monkeypatch):
    import test_scratch_postmortem_contract as readonly_fixture_module
    from test_sd_nor_probe import info

    root, anchor = tmp_path / "recovery", tmp_path / "anchor"
    monkeypatch.setattr(readonly_fixture_module, "info", lambda: info(9))
    actual, plan, historical = fixture(root)
    (anchor / "second").mkdir(parents=True)
    original = {
        "profile": O.C.legacy.PROFILE,
        "ok": True,
        "after": plan["expected_before"],
        "ended_at": plan["parent"]["ended_at"],
    }
    anchor_plan, anchor_proof = {"prior_names": ["rc0123456789"]}, {"verified": True}
    O.C.S.save(anchor / "report.json", original)
    O.C.S.save(anchor / "plan.json", anchor_plan)
    (anchor / "second/download.bin").write_bytes(historical)
    (anchor / "session.btsnoop").write_bytes(b"outer historical fixture only")
    pins = {name: O.A.A.sha((anchor / name).read_bytes()) for name in O.C.LEGACY_PINS}
    refs = {name: O.C.pins.pinned(anchor / name, sha)[1] for name, sha in pins.items()}
    plan["parent"] = O.C.source_summary(
        anchor, original, anchor_plan, anchor_proof, historical, original["after"], refs
    )
    (root / "plan.json").write_text(json.dumps(plan))
    actual["plan"] = O.C.J.reference(root, root / "plan.json")
    actual["verification"] = O.validate_readonly(actual, root, plan)
    actual["ok"] = actual["operation"]["ok"] = True
    O.C.S.save(root / "report.json", actual)
    monkeypatch.setattr(O.C, "LEGACY_PINS", pins)
    monkeypatch.setattr(O.C.old, "replay", Mock(return_value=anchor_proof))
    edge = Mock(return_value=plan["failed"])
    monkeypatch.setattr(O, "failed_source", edge)
    current, state, summary = O.C.parent_gate(root, None)
    assert current != historical and current == (root / "retained/download.bin").read_bytes()
    assert state == actual["after"] and summary["prior_names"] == plan["failed"]["prior_names"]
    assert summary["profile"] == O.PROFILE and summary["verification"]["ownership_only"]
    edge.assert_called_once_with(Path(plan["failed"]["directory"]), plan["parent"], historical)
    next_plan, next_baseline = O.C.prepare(None, root, [0x25000])
    assert next_baseline == current and O.C.source_gate(next_plan, None) == current
    actual["ok"] = False
    (root / "report.json").write_text(json.dumps(actual))
    with pytest.raises(ValueError, match="failed parent"):
        O.C.parent_gate(root, None)
