"""Preauthorization gates and bounded page runner; no device calls."""

import asyncio
import copy
import json
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_paired_nor_audit import archive, fixture, two_page_archive

from rcominote.experiments import paired_nor_runtime as R


def test_live_output_guard_precedes_even_source_or_authorization(tmp_path):
    with (
        patch.object(R.C, "source_gate") as source,
        patch.object(R, "authorize") as auth,
        pytest.raises(ValueError, match="private repo artifacts"),
    ):
        R.main(tmp_path / "image", tmp_path / "nonexistent-plan", tmp_path / "public-output")
    source.assert_not_called()
    auth.assert_not_called()
    assert not (tmp_path / "public-output").exists()


def test_private_output_resolves_symlink_escape(tmp_path):
    # Guard uses resolved paths, independent of the lexical name artifacts.
    path = tmp_path / "artifacts"
    path.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        R.private_output(path / "capture")
    root = R.Path(R.__file__).resolve().parents[3] / "artifacts"
    R.private_output(root / "new-unused-capture")


@pytest.mark.parametrize("fail_index", [None, 0, 1])
def test_runner_replays_full_completed_pages_and_stops_first_failure(tmp_path, fail_index):
    source = tmp_path / "synthetic"
    _original, plan, baseline = two_page_archive(source)
    out, clock, seen = tmp_path / "live-mock", ["2026-10-14T10:01:00+00:00"], []

    async def capture(page, page_plan, previous, target):
        index = page_plan["page_index"]
        seen.append(index)
        expected = (
            baseline
            if index == 0
            else (source / plan["pages"][0]["directory"] / "second/download.bin").read_bytes()
        )
        assert previous == expected
        if index == fail_index:
            page["operations"][0].update(producer_attempted=True, sd_write_attempted=True)
            (target / "first/download.bin").write_bytes(b"actual partial")
            raise ValueError("bounded capture failure")
        template = json.loads((source / target.name / "report.json").read_bytes())
        reference = page["plan"]
        page.update(template, plan=reference)
        clock[0] = template["ended_at"]
        for path in (source / target.name).rglob("*"):
            if path.is_file() and path.name != "report.json":
                dest = target / path.relative_to(source / target.name)
                shutil.copyfile(path, dest)

    with (
        patch.object(R, "private_output"),
        patch.object(R.C, "source_gate", return_value=baseline),
        patch.object(R.C.S, "now", side_effect=lambda: clock[0]),
        patch.object(R, "authorize") as auth,
        patch.object(R, "capture", new=AsyncMock(side_effect=capture)),
    ):
        if fail_index is None:
            R.main(tmp_path / "image", source / "plan.json", out)
        else:
            with pytest.raises(ValueError, match="bounded capture failure"):
                R.main(tmp_path / "image", source / "plan.json", out)
    auth.assert_called_once()
    saved = json.loads((out / "report.json").read_bytes())
    assert seen == ([0, 1] if fail_index is None or fail_index == 1 else [0])
    assert len(saved["completed"]) == (2 if fail_index is None else fail_index)
    assert saved["ok"] is (fail_index is None)
    # Actual validator, not mocked: prior completed pages remain independently provable.
    proofs, _ring, _state = R.audit.completed_prefix(saved, plan, out, baseline)
    assert len(proofs) == len(saved["completed"])
    if fail_index is not None:
        assert "verification" not in saved
        assert (
            out / plan["pages"][fail_index]["directory"] / "first/download.bin"
        ).read_bytes() == b"actual partial"
        for slot in plan["pages"][fail_index + 1 :]:
            assert all(not list((out / slot["directory"] / label).iterdir()) for label in R.C.STAGES)


@pytest.mark.parametrize("fault", ["nonce", "offset", "count", "reference", "state"])
def test_page_gate_rejects_mutated_producer_or_prestate_before_capture(tmp_path, fault):
    job, plan, _baseline = archive(tmp_path)
    job["completed"] = []
    R.save_job(tmp_path, job)
    page_plan = R.C.page_plan(plan, 0, plan["expected_before"], plan["parent"]["ended_at"])
    page = R.C.report(page_plan) | {"plan": job["plan"]}
    if fault == "nonce":
        page["operations"][0]["nonce"] = "rc0000000000"
    elif fault == "offset":
        page["operations"][0]["nor_offset"] = 0x24600
    elif fault == "count":
        page["operations"].pop()
    elif fault == "reference":
        page["plan"] = page["plan"] | {"file": "../elsewhere"}
    else:
        page_plan = copy.deepcopy(page_plan)
        page_plan["expected_before"] = {}
    with (
        patch.object(R, "find_device", new=AsyncMock()) as scan,
        pytest.raises((ValueError, FileNotFoundError)),
    ):
        asyncio.run(R.capture(page, page_plan, bytes(4096), tmp_path / "page0-024400"))
    scan.assert_not_called()


@pytest.mark.parametrize("stage", ["baseline", "first", "second"])
def test_connected_failure_preserves_partial_and_never_calls_next_producer(tmp_path, stage):
    _original, _plan, page_plan, baseline = fixture(tmp_path / "fixture")
    report = R.C.report(page_plan) | {"att_packets": [], "transport": {"link": {}}}
    out = tmp_path / "new"
    for label in R.C.STAGES:
        (out / label).mkdir(parents=True)
    tx = {"update": {"record": 1}}
    conn = SimpleNamespace(file_list=AsyncMock(return_value=[]))
    actions = SimpleNamespace(run_commands=AsyncMock())

    async def identity(_c, owner, key, state, **_kw):
        owner[key] = state

    async def download(_c, _r, op, target):
        data = baseline if op["operation_id"] == "baseline" else bytes(4096)
        (target / "download.bin").write_bytes(b"partial" if op["operation_id"] == stage else data)
        if op["operation_id"] == stage:
            raise ValueError("transfer failure")
        return data

    async def normalize(_m, _c, _r, op, _cursor):
        op["normalization"] = tx

    async def finish(_c, _m, _r, op, _cursor, state, **_kw):
        op.update(after=state, slow_settlement=tx, verified_end=0)

    async def commands(op, body, *, sd_write_command_index):
        assert body == R.C.recipe(op)[2:-1] and sd_write_command_index == 2
        op.update(writes=[{}] * 6, sd_write_attempted=True)

    actions.run_commands.side_effect = commands
    snapshots = [(report, {"transactions": [tx] * n, "pending": []}, []) for n in (3, 4, 6, 7, 9)]
    with (
        patch.object(R, "plan_gate"),
        patch.object(R.shared, "identity", new=AsyncMock(side_effect=identity)),
        patch.object(R.C.startup, "wait_startup", new=AsyncMock(return_value=(tx, {}))),
        patch.object(R.R, "normalize", new=AsyncMock(side_effect=normalize)),
        patch.object(R.shared, "download", new=AsyncMock(side_effect=download)),
        patch.object(R.shared, "finish_stage", new=AsyncMock(side_effect=finish)),
        patch.object(R.C.startup, "live_wire", new=AsyncMock(side_effect=snapshots)),
        patch.object(
            R.R,
            "observe",
            side_effect=lambda *_: {
                "transactions": [tx]
                * (
                    1
                    if not report["baseline"].get("live_complete")
                    else 6
                    if report["operations"][0].get("live_complete")
                    else 3
                ),
                "pending": [],
            },
        ),
        patch.object(R.audit.shared, "baseline_window"),
        patch.object(R.audit.shared, "barrier"),
        patch.object(R.C, "actions", return_value={}),
        patch.object(R.N, "pre_download_fast", new=AsyncMock(return_value=[tx])),
        patch.object(R.W, "default_activity_fast", return_value={}),
        patch.object(R.W, "download_window"),
        patch.object(R.C, "payload", return_value={"sector_hex": "00" * 512}),
        pytest.raises(ValueError, match="transfer failure"),
    ):
        asyncio.run(R.connected(conn, actions, None, report, page_plan, baseline, out))
    index = R.C.STAGES.index(stage)
    assert actions.run_commands.await_count == index
    assert (out / stage / "download.bin").read_bytes() == b"partial"
    assert all(not list((out / label).iterdir()) for label in R.C.STAGES[index + 1 :])
