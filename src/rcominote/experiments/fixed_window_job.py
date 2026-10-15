"""Shared bookkeeping for caller-validated fixed status-window job plans.

Callers retain independent fixed profiles, offset sets, budgets and source
checkpoint gates. This module adds no CLI, target selection or retry path.
"""

import json
from collections.abc import Callable
from pathlib import Path

from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import window_nor_contract as C
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments.sd_bootstrap import verify_state


def bindings(plan: dict, report: dict) -> tuple[str, ...]:
    keys = ("parent", "window_parent", "status_event_policy")
    for key in ("startup_policy", "control_parent"):
        if (key in plan) != (key in report):
            raise ValueError("Explicit startup/control admission differs from immutable plan")
        if key in plan:
            keys += (key,)
    return keys


def checkpoint_gate(
    plan: dict,
    image: Path,
    *,
    prefix_bytes: int,
    verify: Callable[[Path, Path], tuple[bytes, dict, dict]],
) -> tuple[bytes, dict, dict]:
    prefix, state, summary = verify(Path(plan["checkpoint_directory"]), image)
    if (
        summary != plan["checkpoint"]
        or state != summary["latest_info"]
        or len(prefix) != prefix_bytes
        or S.audit.sha(prefix) != summary["sha256"]
    ):
        raise ValueError("Actual checkpoint state/prefix/source proof differs from immutable plan")
    return prefix, state, summary


def plan_gate(job: dict, plan: dict, reports: list[dict], directory: Path) -> None:
    if len(reports) != len(plan["slots"]):
        raise ValueError("Prepared report count differs from immutable fixed slots")
    if json.loads(J.check_reference(directory, job["plan"]).read_bytes()) != plan:
        raise ValueError("In-memory plan differs from original immutable plan file")
    for report, slot in zip(reports, plan["slots"], strict=True):
        C.recipe(report)
        if (
            report["nor_offset"] != slot["nor_offset"]
            or [op["name"] for op in report["operations"]] != slot["names"]
            or any(report[key] != plan[key] for key in bindings(plan, report))
        ):
            raise ValueError("Prepared pair target/nonce/parents/status policy differs from fixed plan")


def acquire_slots(
    job: dict,
    plan: dict,
    reports: list[dict],
    directory: Path,
    image: Path,
    *,
    run_pair: Callable[[dict, Path, Path], None],
    before_pair: Callable[[], None] | None = None,
) -> None:
    """One connection per validated slot; first capture/audit failure propagates."""
    plan_gate(job, plan, reports, directory)
    state = plan["checkpoint"]["latest_info"]
    for report, slot in zip(reports, plan["slots"], strict=True):
        plan_gate(job, plan, reports, directory)
        if before_pair is not None:
            before_pair()
        report["expected_before"] = state
        pair_dir = directory / slot["directory"]
        job["active_slot"] = slot["directory"]
        run_pair(report, pair_dir, image)
        J.require_success(report)
        result = N.replay(pair_dir, image)
        job["completed"].append(
            {"report": J.reference(directory, pair_dir / "report.json"), "verification": result}
        )
        state = report["after"]
        S.save(directory / f"checkpoint-{slot['directory']}.json", job)
        print(
            json.dumps({"completed_pairs": len(job["completed"]), "nor_offset": report["nor_offset"]}),
            flush=True,
        )


def replay_slots(
    report: dict,
    plan: dict,
    directory: Path,
    image: Path,
    *,
    state: dict,
    previous_end: str,
) -> list[tuple[int, bytes]]:
    """Recheck retained original flags, provenance, chronology and actual sectors."""
    sectors = []
    for slot, completed in zip(plan["slots"], report["completed"], strict=True):
        label, offset = slot["directory"], slot["nor_offset"]
        if completed["report"]["file"] != f"{label}/report.json":
            raise ValueError("Completed report path differs from fixed slot")
        original = json.loads(J.check_reference(directory, completed["report"]).read_bytes())
        J.require_success(original)
        C.recipe(original)
        if (
            original["nor_offset"] != offset
            or any(original[key] != plan[key] for key in bindings(plan, original))
            or [op["name"] for op in original["operations"]] != slot["names"]
        ):
            raise ValueError("Original pair target, nonce, policy or parent provenance changed")
        J.time_order(report["started_at"], original["started_at"], original["ended_at"], report["ended_at"])
        J.time_order(previous_end, original["started_at"])
        if original["expected_before"] != state or original["predecessor_state_verification"] != verify_state(
            state, original["before"], sd_write=False
        ):
            raise ValueError("Pair prestate does not match its actual completed predecessor")
        result = N.replay(directory / label, image)
        if (
            result != completed["verification"]
            or result["nor_range"] != [offset, offset + 512]
            or result["bytes"] != 512
        ):
            raise ValueError("Original fixed-sector complete replay result changed")
        sector = (directory / label / "first/sector.bin").read_bytes()
        if len(sector) != 512 or S.audit.sha(sector) != result["sha256"]:
            raise ValueError("Replayed first sector changed before assembly")
        sectors.append((offset, sector))
        state, previous_end = original["after"], original["ended_at"]
    return sectors
