"""Exact successful DEFAULT/activity/RAM control admission; no NOR coverage."""

import json
from pathlib import Path

from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import startup_ram_probe as control
from rcominote.experiments.window_state_checkpoint import pinned

PINS = {
    "report.json": "48ec93559b6702abe67c0a00298bcc8abf5d555710a9896fb183c81da76b7da4",
    "seed/report.json": "819c230097d813bf3c866c65f3b61b947b1cf00b060314c157acec55da87468c",
    "seed/session.btsnoop": "c047e44e6529e1eadccb8e55b613dd3ebb752889cd238ddc90d84e372577f419",
    "data/report.json": "48ac2921d95c78449b68b877c64c7a909f9ebb56f9b7e435b109922dcdacc546",
    "data/session.btsnoop": "1d990035568dea10dc852ea2bb000fffe430ad23d490f07451b0dd8696f2e2a5",
}
EXPECTED = {
    "verified": True,
    "connections": 2,
    "actual_default_tested": True,
    "parameter_transactions": 8,
    "activity_pulses": 2,
    "downloads": 2,
    "sd_writes": 0,
    "new_raw_nor_coverage_bytes": 0,
}


def validate_wrapper(wrapper: dict, state_parent: dict, *, planned_at: str) -> None:
    if (
        not isinstance(wrapper, dict)
        or not isinstance(wrapper.get("directory"), str)
        or not wrapper["directory"]
        or wrapper.get("pins") != PINS
        or wrapper.get("verification") != EXPECTED
        or wrapper.get("latest_info") != state_parent["latest_info"]
        or wrapper.get("source_image_sha256") != control.C.RAM.IMAGE_SHA
    ):
        raise ValueError("Requires exact successful DEFAULT/activity/RAM control and latest unchanged state")
    J.time_order(state_parent["ended_at"], wrapper["ended_at"], planned_at)


def verify(directory: Path, image: Path, state_parent: dict) -> dict:
    directory = directory.resolve()
    inputs = {name: pinned(directory / name, digest) for name, digest in PINS.items()}
    job, seed, data = [
        json.loads(inputs[name][0]) for name in ("report.json", "seed/report.json", "data/report.json")
    ]
    if job["plan"]["file"] != "plan.json":
        raise ValueError("Unexpected immutable RAM-control plan path")
    plan = json.loads(J.check_reference(directory, job["plan"]).read_bytes())
    result = control.replay(directory, image)
    state = state_parent["latest_info"]
    if (
        result != EXPECTED
        or plan["state_parent"] != state_parent
        or plan["expected_before"] != state
        or any(
            report[key] != state for report in (seed, data) for key in ("expected_before", "before", "after")
        )
    ):
        raise ValueError("Actual RAM control source/latest identity differs from NOR state parent")
    J.time_order(
        state_parent["ended_at"],
        plan["planned_at"],
        job["started_at"],
        seed["started_at"],
        seed["ended_at"],
        data["started_at"],
        data["ended_at"],
        job["ended_at"],
    )
    return {
        "directory": str(directory),
        "pins": dict(PINS),
        "verification": result,
        "latest_info": data["after"],
        "ended_at": job["ended_at"],
        "source_image_sha256": plan["source_image_sha256"],
        "references": {name: value[1] for name, value in inputs.items()},
        "plan": J.reference(directory, directory / "plan.json"),
    }
