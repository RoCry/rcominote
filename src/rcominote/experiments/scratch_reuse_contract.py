"""One fixed owned scratch, boot0 then4200, two fresh nonces; no coverage claim."""

import secrets
from pathlib import Path

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import scratch_reuse_sources as sources
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as E
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.experiments.sd_bridge import console_packet
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE

PROFILE = "known-nor-single-scratch-uptime-reuse-v1"
STAGES = ("baseline", "first", "second")
STAGE_SCOPE = "post-startup-baseline-and-each-complete-overwrite-transfer"
BUDGET = {
    "connections": 1,
    "producers": 2,
    "sd_writes": 2,
    "new_files": 0,
    "downloads": 3,
    "stage_seconds": 18,
    "active_seconds": 60,
    "monitor_seconds": 70,
    "cleanup_stop_seconds": 2,
    "disconnect_observation_seconds": 8,
    "new_raw_nor_coverage_bytes": 0,
}


def recipe(op):
    label = op.get("operation_id")
    if label not in ("first", "second"):
        raise ValueError("Only fixed first/second overwrite operations permitted")
    offset = 0 if label == "first" else 0x4200
    nonce = op.get("nonce")
    if not isinstance(nonce, str) or F.NONCE.fullmatch(nonce) is None or nonce == F.NAME:
        raise ValueError("Overwrite requires distinct fixed-format uptime nonce")
    producer = f"dbg fread spi_flash {'0' if offset == 0 else hex(offset)}"
    if any(
        op.get(key) != value
        for key, value in {
            "name": F.NAME,
            "nor_offset": offset,
            "uptime_command": f"kernel uptime {nonce}",
            "producer": producer,
            "dump_command": F.DUMP,
        }.items()
    ):
        raise ValueError("Fixed nonce/target/path command recipe changed")
    body = [console_packet(op[key]) for key in ("uptime_command", "producer", "dump_command")]
    return [PREPARE, START, *body, STOP]


def validate_plan(plan):
    if (
        plan.get("profile") != PROFILE
        or plan.get("serial") != OWNED_SERIAL
        or plan.get("name") != F.NAME
        or plan.get("budget") != BUDGET
        or plan.get("startup_policy") != startup.LEGACY_POLICY
        or plan.get("status_event_policy") != E.POLICY
        or plan.get("stages") != list(STAGES)
        or plan.get("stage_timeout_scope") != STAGE_SCOPE
        or plan.get("expected_before") != plan["sources"]["state_parent"]["latest_info"]
    ):
        raise ValueError("Requires fixed FAST-only known scratch reuse plan and budgets")
    if any(type(plan["budget"][key]) is not int for key in BUDGET):
        raise ValueError("Budget types must remain exact integers")
    ops = plan["operations"]
    if len(ops) != 2 or [op["operation_id"] for op in ops] != ["first", "second"]:
        raise ValueError("Requires exact ordered boot0/4200 slots")
    for op in ops:
        recipe(op)
    if len({op["nonce"] for op in ops}) != 2:
        raise ValueError("Both nonce values must be independently distinct")
    verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    J.time_order(plan["sources"]["state_parent"]["ended_at"], plan["planned_at"])


def prepare(image: Path, known_parent: Path, state_parent: Path):
    baseline, state, summary = sources.verify(image, known_parent, state_parent)
    nonces = ["rc" + secrets.token_hex(5) for _ in range(2)]
    operations = [
        {
            "operation_id": label,
            "name": F.NAME,
            "nonce": nonce,
            "nor_offset": offset,
            "uptime_command": f"kernel uptime {nonce}",
            "producer": f"dbg fread spi_flash {'0' if offset == 0 else hex(offset)}",
            "dump_command": F.DUMP,
        }
        for label, nonce, offset in zip(("first", "second"), nonces, (0, 0x4200), strict=True)
    ]
    plan = {
        "profile": PROFILE,
        "serial": OWNED_SERIAL,
        "name": F.NAME,
        "planned_at": S.now(),
        "sources": summary,
        "expected_before": state,
        "startup_policy": startup.LEGACY_POLICY,
        "status_event_policy": E.POLICY,
        "stages": list(STAGES),
        "stage_timeout_scope": STAGE_SCOPE,
        "budget": BUDGET.copy(),
        "operations": operations,
    }
    validate_plan(plan)
    F.absent(baseline, nonces)
    return plan, baseline


def source_gate(plan, image):
    validate_plan(plan)
    baseline, state, summary = sources.verify(
        image,
        Path(plan["sources"]["known_parent"]["directory"]),
        Path(plan["sources"]["state_parent"]["directory"]),
    )
    if summary != plan["sources"] or state != plan["expected_before"]:
        raise ValueError("Current source chain differs from immutable scratch plan")
    F.absent(baseline, [op["nonce"] for op in plan["operations"]])
    return baseline


def report(plan):
    validate_plan(plan)
    return {
        "profile": PROFILE,
        "started_at": S.now(),
        "expected_before": plan["expected_before"],
        "startup_policy": startup.LEGACY_POLICY,
        "status_event_policy": E.POLICY,
        "budget": BUDGET.copy(),
        "stage_timeout_scope": STAGE_SCOPE,
        "transport": {},
        "ok": False,
        "baseline": {"operation_id": "baseline", "name": F.NAME, "live_complete": False, "ok": False},
        "operations": [op | {"live_complete": False, "ok": False} for op in plan["operations"]],
    }


def payload(op, current, previous, plan):
    recipe(op)
    sector, proof = F.parse_ring(current, previous, nonce=op["nonce"], nor_offset=op["nor_offset"])
    oracle = plan["sources"]["oracles"]["boot0" if op["operation_id"] == "first" else "4200"]
    if len(sector) != 512 or A.sha(sector) != oracle["sha256"]:
        raise ValueError("Fresh retained candidate differs from independent known target oracle")
    return {"freshness": proof, "sector_hex": sector.hex(), "oracle": oracle}
