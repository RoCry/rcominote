"""Pre-I/O immutable-plan and prepared-producer guards; no captures."""

from unittest.mock import Mock, patch

import pytest
from test_dual_probe import info
from test_status_remaining_job import plan_fixture as remaining_plan
from test_status_window_job import original_fixture, plan_fixture

from rcominote.experiments import fixed_window_job as K
from rcominote.experiments import status_remaining_job as R


@pytest.mark.parametrize("fault", ["count", "producer", "in-memory-plan"])
def test_pre_io_plan_binding_rejects_before_any_pair_capture(tmp_path, fault):
    plan, _ = plan_fixture()
    reports = [original_fixture(plan, i) for i in range(4)]
    K.S.save(tmp_path / "job-plan.json", plan)
    job = {"plan": K.J.reference(tmp_path, tmp_path / "job-plan.json"), "completed": []}
    if fault == "count":
        reports.pop()
    elif fault == "producer":
        reports[1]["operations"][0]["producer"] = "dbg fread spi_flash 0x2800"
    else:
        plan["max_connections"] = 5
    capture = Mock()
    with pytest.raises(ValueError):
        K.acquire_slots(job, plan, reports, tmp_path, tmp_path, run_pair=capture)
    capture.assert_not_called()
    assert job["completed"] == []


def test_changed_checkpoint_after_prepare_fails_before_authorization(tmp_path):
    plan, _ = remaining_plan()
    reports = [
        original_fixture(plan, i)
        | {"startup_policy": plan["startup_policy"], "control_parent": plan["control_parent"]}
        for i in range(len(plan["slots"]))
    ]
    with (
        patch.object(R, "prepare", return_value=(plan, reports)),
        patch.object(R.checkpoint, "verify", return_value=(bytes(3584), info(), plan["checkpoint"])),
        patch.object(R.W, "authorize") as authorize,
        patch.object(R.W, "run_pair") as capture,
        pytest.raises(ValueError, match="checkpoint state/prefix/source proof"),
    ):
        R.main(tmp_path, tmp_path, tmp_path, tmp_path / "out")
    authorize.assert_not_called()
    capture.assert_not_called()
