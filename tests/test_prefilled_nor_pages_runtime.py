"""Bounded generic runner consumes full synthetic five-stage page captures."""

import copy
import json
import shutil
from unittest.mock import AsyncMock, patch

import pytest
from test_prefilled_nor_control import RAM
from test_prefilled_nor_pages_audit import archive

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import paired_nor_runtime as R
from rcominote.experiments import prefilled_nor_control as P


@pytest.mark.parametrize("failure", [None, 0, 1])
def test_job_runner_replays_each_complete_prefix_and_first_failure_stops_next_page(tmp_path, failure):
    source, out = tmp_path / "synthetic-source", tmp_path / "new-out"
    original, plan, baseline = archive(source, two=True)
    pages = [json.loads((source / slot["directory"] / "report.json").read_bytes()) for slot in plan["pages"]]
    clock, calls = [original["started_at"]], []

    async def capture(actual, page, previous, directory):
        index = page["page_index"]
        calls.append(index)
        if index:
            assert (
                previous == (out / plan["pages"][index - 1]["directory"] / "second/download.bin").read_bytes()
            )
        clock[0] = pages[index]["ended_at"]
        if index == failure:
            raise TimeoutError("synthetic terminal capture timeout")
        reference = actual["plan"]
        actual.update(copy.deepcopy(pages[index]))
        actual.update(plan=reference, ok=False)
        shutil.copytree(source / plan["pages"][index]["directory"], directory, dirs_exist_ok=True)
        # The runner writes its new original report after independent full audit.
        (directory / "report.json").unlink()

    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
        patch.object(C, "source_gate", return_value=baseline),
        patch.object(R, "private_output"),
        patch.object(R, "authorize") as authorize,
        patch.object(R, "capture", AsyncMock(side_effect=capture)),
        patch.object(C.S, "now", side_effect=lambda: clock[0]),
    ):
        if failure is None:
            R.main(None, source / "plan.json", out)
        else:
            with pytest.raises(TimeoutError, match="terminal capture timeout"):
                R.main(None, source / "plan.json", out)
        saved = json.loads((out / "report.json").read_bytes())
        proofs, _current, _state = A.completed_prefix(saved, plan, out, baseline)
        assert len(proofs) == (2 if failure is None else failure)
        if failure is None:
            assert saved["ok"] is True
            assert A._replay_admitted(saved, plan, out, baseline)["paired_bytes"] == 1024
        else:
            assert saved["ok"] is False and saved["error"].startswith("TimeoutError:")
    authorize.assert_called_once()
    assert calls == ([0, 1] if failure in (None, 1) else [0])
    assert all(
        (out / slot["directory"] / label).is_dir() for slot in plan["pages"] for label in C.stages(plan)
    )
    if failure == 0:
        assert not list((out / plan["pages"][1]["directory"]).rglob("*.bin"))
