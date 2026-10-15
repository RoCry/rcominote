"""Actual synthetic NOR/HCI bytes plus isolated startup runtime fail-stop tests."""

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from test_sd_nor_probe import info
from test_startup_policy import transaction
from test_window_nor_audit import fixture, validate

from rcominote.experiments import window_nor_audit as V
from rcominote.experiments import window_nor_probe as N


@pytest.mark.parametrize(
    "mode,optional,status_at",
    [("fast", False, None), ("default", True, None), ("default", True, "first-actions-leading")],
)
def test_explicit_startup_preserves_complete_six_or_seven_transaction_proof(
    tmp_path, mode, optional, status_at
):
    report = fixture(tmp_path, startup=mode, optional=optional, status_at=status_at)
    original = copy.deepcopy(report)
    proof = validate(report, tmp_path)
    assert proof["parameter_transactions"] == 6 + optional
    assert report["startup_classification"]["mode"] == mode
    if mode == "default":
        first = report["operations"][0]
        wire = V.common.wire_positions(report, (tmp_path / "session.btsnoop").read_bytes())
        actual_first, _ = V.events.edge(report, first["actions_start"], first["actions_end"])
        assert first["default_activity_fast_verification"]["actions_first_record"] == wire[actual_first][0]
        if status_at:
            assert actual_first > first["actions_start"]
    assert report == original


@pytest.mark.parametrize(
    "fault", ["no-first-fast", "stale-first-fast", "unflagged-default", "proof", "classification"]
)
def test_default_never_skips_fresh_first_actions_fast_or_reclassifies_legacy(tmp_path, fault):
    report = fixture(
        tmp_path,
        startup="unflagged-default" if fault == "unflagged-default" else "default",
        optional=fault != "no-first-fast",
        fault="stale-first-fast" if fault == "stale-first-fast" else None,
    )
    if fault == "proof":
        report["operations"][0]["default_activity_fast_verification"] = {}
    elif fault == "classification":
        report["startup_classification"]["mode"] = "fast"
    with pytest.raises(ValueError):
        validate(report, tmp_path)


@pytest.mark.parametrize("stale", [False, True])
def test_live_default_ordering_proof_uses_original_complete_monitor_prefix(tmp_path, stale):
    report = fixture(tmp_path, startup="default", optional=True, fault="stale-first-fast" if stale else None)
    first = report["operations"][0]
    raw = (tmp_path / "session.btsnoop").read_bytes()
    cutoff = first["normalization"]["request"]["record"]
    records = list(V.parameters.records(raw, report["hci_capture"]["records"]))
    from test_hci_interval import record

    prefix = V.parameters.H.HEADER + b"".join(
        record(packet, opcode, stamp=stamp) for number, opcode, stamp, packet in records if number < cutoff
    )
    path = tmp_path / "live.btsnoop"
    path.write_bytes(prefix)
    current = copy.deepcopy(report)
    current["att_packets"] = current["att_packets"][: first["actions_end"]]
    monitor = SimpleNamespace(path=path)
    with patch.object(N.R, "observe"):
        if stale:
            with pytest.raises(ValueError, match="precedes Actions"):
                asyncio.run(N.default_fast_proof(monitor, None, current, current["operations"][0]))
        else:
            assert (
                asyncio.run(N.default_fast_proof(monitor, None, current, current["operations"][0]))
                == first["default_activity_fast_verification"]
            )


@pytest.mark.parametrize(
    "mode,fault", [("fast", None), ("default", None), ("default", "no-fast"), ("default", "preexisting-fast")]
)
def test_runtime_default_requires_fast_before_normalization_and_stops_on_ambiguity(tmp_path, mode, fault):
    warm = transaction(default=mode == "default")
    fast = transaction()
    report = {
        "att_packets": [],
        "transport": {},
        "expected_before": info(),
        "startup_policy": N.startup.POLICY,
        "operations": [
            {"operation_id": label, "name": label, "sd_write_attempted": False}
            for label in ("first", "second")
        ],
    }
    conn = SimpleNamespace(
        client=SimpleNamespace(start_notify=AsyncMock()), file_list=AsyncMock(return_value=[])
    )
    actions = SimpleNamespace(receive=Mock(), run=AsyncMock())
    events = []

    async def identity(_conn, owner, key):
        owner[key] = info()

    async def run(operation):
        operation["sd_write_attempted"] = True
        events.append("actions")

    async def live_proof(*args):
        events.append("causal-proof")
        return {"checked": True}

    async def normalize(*args):
        events.append("normalize")

    actions.run.side_effect = run
    observed = {"transactions": [warm, fast] if fault == "preexisting-fast" else [warm], "pending": []}
    with (
        patch.object(N, "Actions", return_value=actions),
        patch.object(N, "active_link", return_value={}),
        patch.object(N.A, "setup", return_value={}),
        patch.object(N.A, "actions", return_value={}),
        patch.object(N.S, "read_identity", side_effect=identity),
        patch.object(N.R, "observe", return_value=observed),
        patch.object(
            N.startup, "wait_startup", return_value=(warm, N.startup.classify(warm, policy=N.startup.POLICY))
        ),
        patch.object(N.R, "wait_transaction", return_value={}),
        patch.object(
            N,
            "pre_download_fast",
            side_effect=TimeoutError("no actual FAST") if fault == "no-fast" else None,
            return_value=[fast] if mode == "default" else [],
        ) as pre_fast,
        patch.object(N, "default_fast_proof", side_effect=live_proof),
        patch.object(N.R, "normalize", side_effect=normalize) as host,
        patch.object(N, "download", new=AsyncMock()),
        patch.object(N, "decode", side_effect=ValueError("stop at first barrier")),
        pytest.raises((ValueError, TimeoutError)),
    ):
        asyncio.run(N.connected(conn, None, report, tmp_path))
    if fault == "preexisting-fast":
        actions.run.assert_not_awaited()
        pre_fast.assert_not_awaited()
        host.assert_not_awaited()
    else:
        assert pre_fast.call_args.kwargs["required"] is (mode == "default")
        assert actions.run.await_count == 1
        if fault:
            host.assert_not_awaited()
        elif mode == "default":
            assert events == ["actions", "causal-proof", "normalize"]
        else:
            assert events == ["actions", "normalize"]
    assert report["operations"][1]["sd_write_attempted"] is False
