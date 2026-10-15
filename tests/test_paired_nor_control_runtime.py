"""Single-session fail-stop, immutable recipe and exact continuation ledger gates."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_paired_nor_control import fixture

from rcominote.experiments import paired_nor_runtime as R


@pytest.mark.parametrize("failure", range(6))
@pytest.mark.parametrize("error_type", [ValueError, TimeoutError, asyncio.CancelledError])
def test_any_of_six_stage_failures_preserves_partial_and_stops_later_producers(tmp_path, failure, error_type):
    source, out = tmp_path / "source", tmp_path / "output"
    _original, plan, baseline, oracles = fixture(source)
    for page in plan["pages"]:
        for label in R.C.STAGES:
            (out / page["directory"] / label).mkdir(parents=True)
    with patch.object(R.C.pins, "oracles", return_value=oracles):
        report = R.C.control_report(plan) | {"att_packets": [], "transport": {"link": {}}}
    conn = SimpleNamespace(file_list=AsyncMock(return_value=[]))
    actions = SimpleNamespace(run_commands=AsyncMock())
    tx = {"request": {"record": 100, "timestamp_us": 100}, "update": {"record": 200, "timestamp_us": 200}}
    ledger, downloads, identities = [1], [], []

    async def identity(_conn, owner, key, state, **_kw):
        identities.append(key)
        owner[key] = state

    async def download(_c, _r, op, target):
        label = (target.parent.name, target.name)
        downloads.append(label)
        data = (source / label[0] / label[1] / "download.bin").read_bytes()
        (target / "download.bin").write_bytes(b"actual partial" if len(downloads) - 1 == failure else data)
        if len(downloads) - 1 == failure:
            raise error_type("stage transfer failed")
        return data

    async def normalize(_m, _c, _r, op, index):
        op["normalization"] = tx
        ledger[0] = index + 1

    async def finish(_c, _m, _r, op, index, state, **_kw):
        op.update(after=state, slow_settlement=tx, verified_end=1, barrier_complete=True)
        ledger[0] = index + 1

    async def commands(op, body, *, sd_write_command_index):
        assert body == R.C.recipe(op)[2:-1] and sd_write_command_index == 2
        op.update(writes=[{}] * 6, sd_write_attempted=True)

    async def fast(*_args, cursor, **_kw):
        ledger[0] = cursor + 1
        return [tx]

    def payload(op, _data, _previous):
        index = 0 if op["nor_offset"] == 0 else 1
        return {"sector_hex": R.C.oracle(plan, index).hex()}

    actions.run_commands.side_effect = commands
    with (
        patch.object(R, "plan_gate"),
        patch.object(R.shared, "identity", new=AsyncMock(side_effect=identity)),
        patch.object(R.C.startup, "wait_startup", new=AsyncMock(return_value=(tx, {}))),
        patch.object(
            R.R, "observe", side_effect=lambda *_: {"transactions": [tx] * ledger[0], "pending": []}
        ),
        patch.object(R.R, "normalize", new=AsyncMock(side_effect=normalize)),
        patch.object(R.shared, "download", new=AsyncMock(side_effect=download)),
        patch.object(R.shared, "finish_stage", new=AsyncMock(side_effect=finish)),
        patch.object(
            R.C.startup,
            "live_wire",
            new=AsyncMock(
                side_effect=lambda *_: (
                    report,
                    {"transactions": [tx] * ledger[0], "pending": []},
                    [(0, 0, 0)],
                )
            ),
        ),
        patch.object(R.audit.shared, "baseline_window"),
        patch.object(R.audit.shared, "barrier"),
        patch.object(R.C, "actions", return_value={}),
        patch.object(R.N, "pre_download_fast", new=AsyncMock(side_effect=fast)),
        patch.object(R.W, "default_activity_fast", return_value={}),
        patch.object(R.W, "download_window"),
        patch.object(R.C, "payload", side_effect=payload),
        pytest.raises(error_type, match="stage transfer failed"),
    ):
        asyncio.run(R.connected(conn, actions, None, report, plan, baseline, out))
    assert len(downloads) == failure + 1
    assert actions.run_commands.await_count == [0, 1, 2, 2, 3, 4][failure]
    assert not report["ok"]
    stages = [op for group in report["groups"] for op in [group["baseline"], *group["operations"]]]
    assert all(not op.get("producer_attempted") for op in stages[failure + 1 :])
    assert report["groups"][0]["candidate"] is (failure >= 3)
    assert not report["groups"][1]["candidate"]
    assert identities == (["before", "after"] if error_type is ValueError else ["before"])
    for index, (page, label) in enumerate(
        (p["directory"], label) for p in plan["pages"] for label in R.C.STAGES
    ):
        files = list((out / page / label).iterdir())
        assert bool(files) is (index <= failure)


@pytest.mark.parametrize("pending", [False, True])
def test_unexpected_fast_or_pending_before_second_baseline_stops_before_host_update(tmp_path, pending):
    op = {"operation_id": "baseline"}
    context = {"state": {}, "previous": bytes(4096), "previous_tx": {}, "cursor": 9, "boundary": 1}
    report = {"transport": {"link": {}}}
    snapshot = {"transactions": [{}] * (9 if pending else 10), "pending": [{}] if pending else []}
    with (
        patch.object(R.R, "observe", return_value=snapshot),
        patch.object(R.R, "normalize", new=AsyncMock()) as normalize,
        patch.object(R.shared, "download", new=AsyncMock()) as download,
        pytest.raises(ValueError, match="Extra/pending"),
    ):
        asyncio.run(R.baseline_transfer(None, None, report, op, context, tmp_path, []))
    normalize.assert_not_called()
    download.assert_not_called()


@pytest.mark.parametrize("fault", ["offset", "nonce", "count", "baseline", "policy", "budget"])
def test_fixed_control_plan_recipe_and_slots_reject_before_scan(tmp_path, fault):
    _original, plan, _baseline, oracles = fixture(tmp_path)
    with patch.object(R.C.pins, "oracles", return_value=oracles):
        report = R.C.control_report(plan) | {"plan": R.J.reference(tmp_path, tmp_path / "plan.json")}
        if fault == "offset":
            report["groups"][1]["operations"][0]["nor_offset"] = 0x24A00
        elif fault == "nonce":
            report["groups"][1]["operations"][0]["nonce"] = report["groups"][0]["operations"][0]["nonce"]
        elif fault == "count":
            report["groups"].pop()
        elif fault == "baseline":
            report["groups"][1]["baseline"]["name"] = "rc0000000000"
        elif fault == "policy":
            report["prefix_policy"] = R.C.F.STRICT_POLICY
        else:
            plan["budget"]["connections"] = True
        with patch.object(R, "find_device", new=AsyncMock()) as scan, pytest.raises(ValueError):
            asyncio.run(R.capture(report, plan, bytes(4096), tmp_path))
        scan.assert_not_called()


def test_failed_control_main_retains_exact_original_false_and_partial_file(tmp_path):
    source, out = tmp_path / "source", tmp_path / "output"
    _original, plan, baseline, oracles = fixture(source)

    async def failed(report, *_args):
        report["groups"][0].update(live_complete=True, candidate=True)
        report["groups"][1]["operations"][0].update(producer_attempted=True, sd_write_attempted=True)
        (out / plan["pages"][1]["directory"] / "first/download.bin").write_bytes(b"actual partial")
        raise ValueError("known control failed")

    with (
        patch.object(R.C.pins, "oracles", return_value=oracles),
        patch.object(R, "private_output"),
        patch.object(R.C, "source_gate", return_value=baseline),
        patch.object(R, "authorize"),
        patch.object(R, "capture", new=AsyncMock(side_effect=failed)),
        patch.object(R.audit, "validate_control") as validate,
        pytest.raises(ValueError, match="known control failed"),
    ):
        R.main(tmp_path / "image", source / "plan.json", out)
    validate.assert_not_called()
    saved = json.loads((out / "report.json").read_bytes())
    assert saved["ok"] is False and "verification" not in saved
    with (
        patch.object(R.C.pins, "oracles", return_value=oracles),
        pytest.raises(ValueError, match="failed parent"),
    ):
        R.C.parent_gate(out, None)
