"""Fixed existing-RAM DEFAULT/activity control; source and state gates only."""

from pathlib import Path

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import preproducer_state_checkpoint as state_source
from rcominote.experiments import sd_warm_download as RAM
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as events
from rcominote.experiments.sd_bootstrap import verify_state

PROFILE = "known-ram-default-activity-fast-control"
PHASES = ("seed", "data")


def validate_plan(plan: dict) -> None:
    if (
        plan.get("profile") != PROFILE
        or plan.get("serial") != OWNED_SERIAL
        or plan.get("name") != RAM.NAME
        or plan.get("source_image_sha256") != RAM.IMAGE_SHA
        or plan.get("expected_sha256") != RAM.ORACLE_SHA
        or plan.get("startup_policy") != startup.POLICY
        or plan.get("status_event_policy") != events.POLICY
        or plan.get("phases") != list(PHASES)
        or any(
            type(plan.get(key)) is not int or plan[key] != value
            for key, value in (
                ("max_connections", 2),
                ("activity_pulses", 2),
                ("downloads", 2),
                ("sd_writes", 0),
                ("producer_executions", 0),
                ("new_raw_nor_coverage_bytes", 0),
            )
        )
        or plan["state_parent"].get("directory") != plan.get("state_parent_directory")
        or plan["state_parent"].get("latest_info") != plan.get("expected_before")
    ):
        raise ValueError("Requires fixed two-connection existing-RAM DEFAULT/activity control plan")
    verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    J.time_order(plan["state_parent"]["ended_at"], plan["planned_at"])


def prepare(image: Path, parent_ram: Path, state_parent: Path) -> tuple[dict, bytes]:
    oracle, parent = RAM.validate_inputs(image, parent_ram)
    _, state, source = state_source.verify(state_parent, image)
    plan = {
        "profile": PROFILE,
        "serial": OWNED_SERIAL,
        "name": RAM.NAME,
        "planned_at": S.now(),
        "source_image_sha256": RAM.IMAGE_SHA,
        "expected_sha256": RAM.ORACLE_SHA,
        "oracle_parent": parent,
        "state_parent_directory": str(state_parent.resolve()),
        "state_parent": source,
        "expected_before": state,
        "startup_policy": startup.POLICY,
        "status_event_policy": events.POLICY,
        "phases": list(PHASES),
        "max_connections": 2,
        "activity_pulses": 2,
        "downloads": 2,
        "sd_writes": 0,
        "producer_executions": 0,
        "new_raw_nor_coverage_bytes": 0,
    }
    validate_plan(plan)
    return plan, oracle


def source_gate(plan: dict, image: Path) -> bytes:
    validate_plan(plan)
    oracle, parent = RAM.validate_inputs(image, Path(plan["oracle_parent"]["directory"]))
    prefix, state, source = state_source.verify(Path(plan["state_parent_directory"]), image)
    if (
        parent != plan["oracle_parent"]
        or source != plan["state_parent"]
        or state != plan["expected_before"]
        or len(prefix) != 2560
        or S.audit.sha(prefix) != source["sha256"]
    ):
        raise ValueError("Actual existing-RAM/state source differs from immutable control plan")
    return oracle


def phase(plan: dict, kind: str) -> dict:
    validate_plan(plan)
    if kind not in PHASES:
        raise ValueError("Only fixed seed/data phases permitted")
    return {
        "profile": f"{PROFILE}/{kind}",
        "started_at": S.now(),
        "expected_before": plan["expected_before"],
        "startup_policy": startup.LEGACY_POLICY if kind == "seed" else startup.POLICY,
        "status_event_policy": events.POLICY,
        "sd_write_attempted": False,
        "transport": {},
        "operations": []
        if kind == "seed"
        else [
            {
                "operation_id": label,
                "name": RAM.NAME,
                "sd_write_attempted": False,
                "live_complete": False,
                "ok": False,
            }
            for label in ("first", "second")
        ],
        "ok": False,
    }
