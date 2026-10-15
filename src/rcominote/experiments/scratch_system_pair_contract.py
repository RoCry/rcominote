"""One fixed unknown system24200 pair; no mapped, reconstructed or raw oracle."""

import secrets
from datetime import datetime
from itertools import pairwise

from rcominote import protocol as Boyi
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import param_window as P
from rcominote.experiments import scratch_reuse_audit as shared
from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import scratch_system_pair_sources as sources
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as E
from rcominote.experiments import window_nor_audit as W
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.experiments.sd_bridge import console_packet
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE

PROFILE = "fixed-unknown-system24200-same-scratch-pair-v1"
OFFSET = 0x24200
OUTPUT = "system24200.bin"
STAGES = ("baseline", "first", "second")
ACTIONS_POLICY = "exact-six-acks-f1-pending-empty-all-f0-retained"
STAGE_SCOPE = "post-startup-baseline-and-two-complete-overwrite-transfers"
BUDGET = {
    "connections": 1,
    "downloads": 3,
    "producers": 2,
    "sd_writes": 2,
    "new_files": 0,
    "stage_seconds": 18,
    "active_seconds": 60,
    "monitor_seconds": 70,
    "cleanup_stop_seconds": 2,
    "disconnect_observation_seconds": 8,
    "new_raw_nor_coverage_bytes": 512,
}
FIELDS = (
    "profile",
    "expected_before",
    "budget",
    "actions_policy",
    "stage_timeout_scope",
    "startup_policy",
    "status_event_policy",
)


def recipe(op):
    nonce = op.get("nonce")
    if (
        not isinstance(nonce, str)
        or F.NONCE.fullmatch(nonce) is None
        or op.get("operation_id") not in ("first", "second")
    ):
        raise ValueError("Requires two fixed first/second rc10hex nonce operations")
    if (
        any(
            op.get(key) != value
            for key, value in {
                "name": F.NAME,
                "nor_offset": OFFSET,
                "uptime_command": f"kernel uptime {nonce}",
                "producer": "dbg fread spi_flash 0x24200",
                "dump_command": F.DUMP,
            }.items()
        )
        or type(op["nor_offset"]) is not int
    ):
        raise ValueError("Only fixed unknown24200 same-file recipe permitted")
    return [
        PREPARE,
        START,
        *(console_packet(op[key]) for key in ("uptime_command", "producer", "dump_command")),
        STOP,
    ]


def actions(report, op):
    return A.action_frames(report, op, expected=recipe(op)) | {
        "f0_frames": sum(frame["command"] == 0xF0 for frame in op["frames"]),
        "uptime_body_required": False,
        "policy": ACTIONS_POLICY,
    }


def validate_plan(plan):
    if (
        plan.get("profile") != PROFILE
        or plan.get("name") != F.NAME
        or type(plan.get("nor_offset")) is not int
        or plan["nor_offset"] != OFFSET
        or plan.get("budget") != BUDGET
        or any(type(plan["budget"][key]) is not int for key in BUDGET)
        or plan.get("actions_policy") != ACTIONS_POLICY
        or plan.get("stage_timeout_scope") != STAGE_SCOPE
        or plan.get("startup_policy") != startup.LEGACY_POLICY
        or plan.get("status_event_policy") != E.POLICY
        or plan.get("expected_before") != plan["parent"]["latest_info"]
        or plan["parent"].get("original_failed_retained") is not True
        or plan["parent"].get("unknown_raw_oracle") is not False
        or plan.get("independent_oracle") is not False
    ):
        raise ValueError("Requires fixed FAST-only unknown24200 pair plan and bounded budgets")
    ops = plan["operations"]
    if len(ops) != 2 or [op["operation_id"] for op in ops] != ["first", "second"]:
        raise ValueError("Requires exactly ordered first/second producer slots")
    for op in ops:
        recipe(op)
    nonces = {op["nonce"] for op in ops}
    if len(nonces) != 2 or nonces.intersection(plan["parent"]["prior_names"]):
        raise ValueError("Both fresh nonces must differ from each other and every original planned name")
    verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    J.time_order(plan["parent"]["ended_at"], plan["planned_at"])


def prepare(image, parent):
    baseline, state, source = sources.verify(parent, image)
    operations = []
    for label in ("first", "second"):
        nonce = "rc" + secrets.token_hex(5)
        operations.append(
            {
                "operation_id": label,
                "name": F.NAME,
                "nonce": nonce,
                "nor_offset": OFFSET,
                "uptime_command": f"kernel uptime {nonce}",
                "producer": "dbg fread spi_flash 0x24200",
                "dump_command": F.DUMP,
            }
        )
    plan = {
        "profile": PROFILE,
        "name": F.NAME,
        "nor_offset": OFFSET,
        "planned_at": S.now(),
        "parent": source,
        "expected_before": state,
        "budget": BUDGET.copy(),
        "actions_policy": ACTIONS_POLICY,
        "stage_timeout_scope": STAGE_SCOPE,
        "startup_policy": startup.LEGACY_POLICY,
        "status_event_policy": E.POLICY,
        "operations": operations,
        "independent_oracle": False,
    }
    validate_plan(plan)
    F.absent(baseline, [op["nonce"] for op in operations])
    return plan, baseline


def source_gate(plan, image):
    from pathlib import Path

    validate_plan(plan)
    baseline, state, source = sources.verify(Path(plan["parent"]["directory"]), image)
    if state != plan["expected_before"] or source != plan["parent"]:
        raise ValueError("Latest known4200 current-file source differs from immutable pair plan")
    F.absent(baseline, [op["nonce"] for op in plan["operations"]])
    return baseline


def report(plan):
    validate_plan(plan)
    return {key: plan[key] for key in FIELDS} | {
        "started_at": S.now(),
        "transport": {},
        "ok": False,
        "baseline": {"operation_id": "baseline", "name": F.NAME, "live_complete": False, "ok": False},
        "operations": [op | {"live_complete": False, "ok": False} for op in plan["operations"]],
    }


def payload(op, current, previous):
    recipe(op)
    sector, proof = F.parse_system_ring(current, previous, nonce=op["nonce"])
    return {"freshness": proof, "sector_hex": sector.hex(), "independent_oracle": False}


def inventory(report, plan):
    count = common.file_list(report)
    forbidden = {F.NAME, *(op["nonce"] for op in plan["operations"])}
    for row in E.rows(report, *report["file_list_span"])[1:]:
        _, data = Boyi.parse(bytes.fromhex(row["hex"])[3:])
        if data[:1] == b"\0" and Boyi.parse_file_entry(data).name in forbidden:
            raise ValueError("Visible inventory collides with dedicated scratch/fresh nonces")
    return count


def validate(report, directory, plan, baseline):
    validate_plan(plan)
    common.no_errors(report)
    if (
        any(report.get(key) != plan[key] for key in FIELDS)
        or "operation" in report
        or len(report["operations"]) != 2
    ):
        raise ValueError("Actual fixed two-producer report differs from immutable plan")
    warm = report["baseline"]
    if (
        warm.get("name") != F.NAME
        or warm.get("operation_id") != "baseline"
        or any(key in warm for key in ("actions_start", "producer", "sd_write_attempted"))
    ):
        raise ValueError("Baseline must remain exact readonly dedicated-file download")
    for stage in (warm, *report["operations"]):
        if stage.get("live_complete") is not True:
            raise ValueError("All three original stages must complete before pair acceptance")
        J.time_order(report["started_at"], stage["started_at"], stage["ended_at"], report["ended_at"])
        if (
            datetime.fromisoformat(stage["ended_at"]) - datetime.fromisoformat(stage["started_at"])
        ).total_seconds() > 18:
            raise ValueError("Original post-startup stage exceeds18-second deadline")
    J.time_order(plan["parent"]["ended_at"], plan["planned_at"], report["started_at"])
    if report.get("monitor_exit") != 0 or report.get("monitor_stop") != {
        "signal": "SIGINT",
        "requested": True,
        "delivery": "sent",
    }:
        raise ValueError("Capture requires clean owned SIGINT stop")
    rows = report["att_packets"]
    if any(type(row["monotonic_ns"]) is not int for row in rows) or any(
        a["monotonic_ns"] > b["monotonic_ns"] for a, b in pairwise(rows)
    ):
        raise ValueError("Original ATT timestamps must remain complete and monotonic")
    _, event_proof = E.verify(report)
    raw = (directory / "session.btsnoop").read_bytes()
    observed = P.inspect(raw, link=report["transport"]["link"], final=True)
    if (
        observed["pending"]
        or len(observed["transactions"]) != 9
        or report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
        or report["gatt_proof"] != A.setup(report)
        or report["att_hci_binding"] != dual_hci.bind(report, raw)
    ):
        raise ValueError("Requires full GATT/ATT/HCI and exactly nine complete parameter transactions")
    wire = common.wire_positions(report, raw)
    disconnects = observed["disconnects"]
    if (
        len(disconnects) != 1
        or disconnects[0]["status"] != 0
        or disconnects[0]["reason"] != 0x16
        or disconnects[0]["record"] <= max(p[1] for p in wire)
        or report.get("disconnect_observation")
        != {"observed": True, "event": disconnects[0], "max_wait_seconds": 8}
    ):
        raise ValueError("Requires sole actual normal local disconnect after final ATT")
    requested, completed, recorded = [
        report[key] for key in ("close_requested_us", "close_completed_us", "disconnect_observed_us")
    ]
    if (
        any(type(value) is not int for value in (requested, completed, recorded))
        or not requested <= completed <= recorded <= completed + 8_000_000
        or not requested <= disconnects[0]["timestamp_us"] <= completed + 8_000_000
    ):
        raise ValueError("Original actual disconnect observation exceeds bounded close")
    E.bridge(report, report["setup_end"], report["before_span"][0])
    A.identity(report, report, "before")
    if report["predecessor_state_verification"] != verify_state(
        plan["expected_before"], report["before"], sd_write=False
    ):
        raise ValueError("Initial actual state differs from latest known4200 predecessor")
    E.bridge(report, report["before_span"][1], report["file_list_span"][0])
    if inventory(report, plan) != report["listed_count"]:
        raise ValueError("Actual complete visible inventory changed")
    E.bridge(report, report["file_list_span"][1], warm["download_start"])
    startup_tx, normal, slow = observed["transactions"][:3]
    if (
        report["startup_settlement"] != startup_tx
        or report["startup_classification"] != startup.classify(startup_tx)
        or warm["before"] != report["before"]
    ):
        raise ValueError("Baseline requires original strict startup FAST and actual initial state")
    shared.baseline_window(report, warm, wire, startup_tx, normal, slow)
    previous = shared.download(report, warm, directory)
    if previous != baseline:
        raise ValueError("Live baseline differs from full latest known4200 current file")
    F.absent(previous, [op["nonce"] for op in plan["operations"]])
    shared.barrier(report, warm, report["before"], writing=False)
    state, boundary, previous_tx, cursor, ended = (
        warm["after"],
        warm["verified_end"],
        warm["slow_settlement"],
        3,
        warm["ended_at"],
    )
    sectors, observations = [], []
    for slot, op in zip(plan["operations"], report["operations"], strict=True):
        if (
            any(op.get(key) != value for key, value in slot.items())
            or op["before"] != state
            or op.get("sd_write_attempted") is not True
            or op.get("producer_attempted") is not True
        ):
            raise ValueError("Original overwrite recipe/predecessor/producer/SD attempt changed")
        J.time_order(ended, op["started_at"])
        E.bridge(report, boundary, op["actions_start"])
        E.bridge(report, op["actions_end"], op["download_start"])
        if actions(report, op) != op["actions_verification"]:
            raise ValueError("Original exact six-ACK/F1/all-F0 receipt changed")
        normal, slow, cursor = W.parameter_stage(
            observed["transactions"], cursor, op, previous_tx, first_fast_required=True
        )
        if op["activity_fast_verification"] != W.default_activity_fast(
            report, op, previous_tx, op["pre_download_fast"][0], wire
        ):
            raise ValueError("Actual FAST request precedes current Actions or prior SLOW")
        W.download_window(wire, op, normal, slow, report=report)
        data = shared.download(report, op, directory)
        decoded = payload(op, data, previous)
        sector = bytes.fromhex(decoded["sector_hex"])
        if (
            decoded != op["verification"]
            or (directory / op["operation_id"] / "sector.bin").read_bytes() != sector
        ):
            raise ValueError("Saved sector differs from its own complete current retained file")
        if op["operation_id"] == "first":
            F.absent(data, [plan["operations"][1]["nonce"]])
        shared.barrier(report, op, state, writing=True)
        sectors.append(sector)
        observations.append(
            {
                "operation": op["operation_id"],
                "nonce": op["nonce"],
                "ring_sha256": A.sha(data),
                "sector_sha256": A.sha(sector),
            }
        )
        previous, state, boundary, previous_tx, ended = (
            data,
            op["after"],
            op["verified_end"],
            slow,
            op["ended_at"],
        )
    E.bridge(report, boundary, report["after_span"][0])
    A.identity(report, report, "after")
    E.bridge(report, report["after_span"][1], len(rows))
    if cursor != 9 or report["state_verification"] != verify_state(state, report["after"], sd_write=False):
        raise ValueError("Final identity or fully consumed parameter ledger changed")
    if any(len(sector) != 512 for sector in sectors) or sectors[0] != sectors[1]:
        raise ValueError("Two independent complete unknown24200 sectors differ; no oracle filling")
    return {
        "verified": True,
        "pair_verified": True,
        "connections": 1,
        "downloads": 3,
        "producers": 2,
        "sd_writes": 2,
        "new_files": 0,
        "raw_range": [OFFSET, OFFSET + 512],
        "bytes": 512,
        "sha256": A.sha(sectors[0]),
        "parameter_transactions": 9,
        "observations": observations,
        "independent_oracle": False,
        "new_raw_nor_coverage_bytes": 512,
        "status_events": event_proof,
    }
