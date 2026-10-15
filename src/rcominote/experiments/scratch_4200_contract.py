"""Fixed known4200 single overwrite after exact live baseline; independent policy."""

import secrets
from datetime import datetime
from itertools import pairwise
from pathlib import Path

from rcominote import protocol as Boyi
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import param_window as P
from rcominote.experiments import scratch_4200_sources as sources
from rcominote.experiments import scratch_reuse_audit as shared
from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as E
from rcominote.experiments import window_nor_audit as W
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.experiments.sd_bridge import console_packet
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE

PROFILE = "known-scratch-4200-single-overwrite-v1"
ACTIONS_POLICY = "exact-six-acks-f1-pending-empty-all-f0-retained"
STAGE_SCOPE = "post-startup-baseline-and-one-complete-overwrite-transfer"
BUDGET = {
    "connections": 1,
    "downloads": 2,
    "producers": 1,
    "sd_writes": 1,
    "new_files": 0,
    "stage_seconds": 18,
    "active_seconds": 60,
    "monitor_seconds": 70,
    "cleanup_stop_seconds": 2,
    "disconnect_observation_seconds": 8,
    "new_raw_nor_coverage_bytes": 0,
}


def recipe(op):
    nonce = op.get("nonce")
    if not isinstance(nonce, str) or F.NONCE.fullmatch(nonce) is None:
        raise ValueError("Requires fixed rc10hex uptime nonce")
    if (
        any(
            op.get(key) != value
            for key, value in {
                "operation_id": "overwrite",
                "name": F.NAME,
                "nor_offset": 0x4200,
                "uptime_command": f"kernel uptime {nonce}",
                "producer": "dbg fread spi_flash 0x4200",
                "dump_command": F.DUMP,
            }.items()
        )
        or type(op["nor_offset"]) is not int
    ):
        raise ValueError("Only fixed single4200 same-file command recipe permitted")
    return [
        PREPARE,
        START,
        *(console_packet(op[key]) for key in ("uptime_command", "producer", "dump_command")),
        STOP,
    ]


def actions(report, op):
    proof = A.action_frames(report, op, expected=recipe(op))
    return proof | {
        "f0_frames": sum(frame["command"] == 0xF0 for frame in op["frames"]),
        "uptime_body_required": False,
        "policy": ACTIONS_POLICY,
    }


def validate_plan(plan):
    if (
        plan.get("profile") != PROFILE
        or plan.get("name") != F.NAME
        or plan.get("budget") != BUDGET
        or any(type(plan["budget"][key]) is not int for key in BUDGET)
        or plan.get("actions_policy") != ACTIONS_POLICY
        or plan.get("stage_timeout_scope") != STAGE_SCOPE
        or plan.get("startup_policy") != startup.LEGACY_POLICY
        or plan.get("status_event_policy") != E.POLICY
        or plan.get("expected_before") != plan["parent"]["latest_info"]
        or plan["parent"].get("original_failed_retained") is not True
        or plan["parent"].get("reuse_pair_complete") is not False
    ):
        raise ValueError("Requires fixed FAST-only one-overwrite known4200 plan and budgets")
    recipe(plan["operation"])
    if plan["operation"]["nonce"] in plan["parent"]["prior_names"]:
        raise ValueError("Fresh nonce must differ from every original planned nonce and owned name")
    verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    J.time_order(plan["parent"]["ended_at"], plan["planned_at"])


def prepare(image: Path, parent: Path):
    baseline, state, source = sources.verify(parent, image)
    nonce = "rc" + secrets.token_hex(5)
    plan = {
        "profile": PROFILE,
        "name": F.NAME,
        "planned_at": S.now(),
        "parent": source,
        "expected_before": state,
        "budget": BUDGET.copy(),
        "actions_policy": ACTIONS_POLICY,
        "stage_timeout_scope": STAGE_SCOPE,
        "startup_policy": startup.LEGACY_POLICY,
        "status_event_policy": E.POLICY,
        "operation": {
            "operation_id": "overwrite",
            "name": F.NAME,
            "nonce": nonce,
            "nor_offset": 0x4200,
            "uptime_command": f"kernel uptime {nonce}",
            "producer": "dbg fread spi_flash 0x4200",
            "dump_command": F.DUMP,
        },
    }
    validate_plan(plan)
    F.absent(baseline, [nonce])
    return plan, baseline


def source_gate(plan, image):
    validate_plan(plan)
    baseline, state, source = sources.verify(Path(plan["parent"]["directory"]), image)
    if state != plan["expected_before"] or source != plan["parent"]:
        raise ValueError("Successful retained-file parent changed before known4200 control")
    F.absent(baseline, [plan["operation"]["nonce"]])
    return baseline


def report(plan):
    validate_plan(plan)
    return {
        key: plan[key]
        for key in (
            "profile",
            "expected_before",
            "budget",
            "actions_policy",
            "stage_timeout_scope",
            "startup_policy",
            "status_event_policy",
        )
    } | {
        "started_at": S.now(),
        "transport": {},
        "ok": False,
        "baseline": {"operation_id": "baseline", "name": F.NAME, "live_complete": False, "ok": False},
        "operation": plan["operation"] | {"live_complete": False, "ok": False},
    }


def payload(op, current, previous, plan):
    recipe(op)
    sector, proof = F.parse_ring(current, previous, nonce=op["nonce"], nor_offset=0x4200)
    oracle = plan["parent"]["sources"]["oracles"]["4200"]
    if A.sha(sector) != oracle["sha256"]:
        raise ValueError("Fresh retained4200 candidate differs from independent raw oracle")
    return {
        "freshness": proof,
        "sector_hex": sector.hex(),
        "oracle": oracle,
        "original_trial_ok": False,
        "new_raw_nor_coverage_bytes": 0,
    }


def inventory(report, plan):
    count = common.file_list(report)
    for row in E.rows(report, *report["file_list_span"])[1:]:
        _, payload = Boyi.parse(bytes.fromhex(row["hex"])[3:])
        if payload[:1] == b"\0" and Boyi.parse_file_entry(payload).name in (
            F.NAME,
            plan["operation"]["nonce"],
        ):
            raise ValueError("Visible inventory collides with dedicated scratch/fresh nonce")
    return count


def validate(report, directory, plan, baseline):
    validate_plan(plan)
    common.no_errors(report)
    if (
        any(
            report.get(key) != plan[key]
            for key in (
                "profile",
                "expected_before",
                "budget",
                "actions_policy",
                "stage_timeout_scope",
                "startup_policy",
                "status_event_policy",
            )
        )
        or "operations" in report
    ):
        raise ValueError("Actual fixed single4200 report differs from immutable plan")
    warm, op = report["baseline"], report["operation"]
    if (
        any(op.get(key) != value for key, value in plan["operation"].items())
        or warm.get("name") != F.NAME
        or warm.get("operation_id") != "baseline"
        or any(key in warm for key in ("actions_start", "producer", "sd_write_attempted"))
    ):
        raise ValueError("Actual baseline or single overwrite recipe changed")
    for stage in (warm, op):
        if stage.get("live_complete") is not True:
            raise ValueError("Both original stages must complete before full success audit")
        J.time_order(report["started_at"], stage["started_at"], stage["ended_at"], report["ended_at"])
        if (
            datetime.fromisoformat(stage["ended_at"]) - datetime.fromisoformat(stage["started_at"])
        ).total_seconds() > 18:
            raise ValueError("Original post-startup stage exceeds18-second deadline")
    J.time_order(
        plan["parent"]["ended_at"],
        plan["planned_at"],
        report["started_at"],
        warm["ended_at"],
        op["started_at"],
    )
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
        or len(observed["transactions"]) != 6
        or report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
        or report["gatt_proof"] != A.setup(report)
        or report["att_hci_binding"] != dual_hci.bind(report, raw)
    ):
        raise ValueError("Requires full GATT/ATT/HCI and exactly six complete parameter transactions")
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
        raise ValueError("Initial actual state differs from successful postmortem predecessor")
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
        raise ValueError("Live baseline differs from full successful postmortem retained file")
    F.absent(previous, [op["nonce"]])
    shared.barrier(report, warm, report["before"], writing=False)
    if (
        op["before"] != warm["after"]
        or op.get("sd_write_attempted") is not True
        or op.get("producer_attempted") is not True
    ):
        raise ValueError("Overwrite requires exact baseline state and original producer/SD attempts")
    E.bridge(report, warm["verified_end"], op["actions_start"])
    E.bridge(report, op["actions_end"], op["download_start"])
    if actions(report, op) != op["actions_verification"]:
        raise ValueError("Original exact six-ACK/F1/all-F0 receipt changed")
    normal, slow, cursor = W.parameter_stage(
        observed["transactions"], 3, op, warm["slow_settlement"], first_fast_required=True
    )
    if cursor != 6 or op["activity_fast_verification"] != W.default_activity_fast(
        report, op, warm["slow_settlement"], op["pre_download_fast"][0], wire
    ):
        raise ValueError("Actual FAST request precedes overwrite Actions or prior SLOW settlement")
    W.download_window(wire, op, normal, slow, report=report)
    data = shared.download(report, op, directory)
    decoded = payload(op, data, previous, plan)
    if decoded != op["verification"] or (directory / "overwrite/sector.bin").read_bytes() != bytes.fromhex(
        decoded["sector_hex"]
    ):
        raise ValueError("Saved known4200 sector differs from complete current retained file")
    shared.barrier(report, op, warm["after"], writing=True)
    E.bridge(report, op["verified_end"], report["after_span"][0])
    A.identity(report, report, "after")
    E.bridge(report, report["after_span"][1], len(rows))
    if report["state_verification"] != verify_state(op["after"], report["after"], sd_write=False):
        raise ValueError("Final identity differs from last complete overwrite barrier")
    return {
        "verified": True,
        "connections": 1,
        "downloads": 2,
        "producers": 1,
        "sd_writes": 1,
        "new_files": 0,
        "known_offset": 0x4200,
        "parameter_transactions": 6,
        "actions": op["actions_verification"],
        "original_trial_ok": False,
        "new_raw_nor_coverage_bytes": 0,
        "status_events": event_proof,
    }
