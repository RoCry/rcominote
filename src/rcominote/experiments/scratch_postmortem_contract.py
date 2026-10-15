"""Fixed readonly retained-file postmortem; original failed trial stays failed."""

from datetime import datetime
from itertools import pairwise
from pathlib import Path

from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import param_window as P
from rcominote.experiments import scratch_postmortem_sources as sources
from rcominote.experiments import scratch_reuse_audit as shared
from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as E
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state

PROFILE = "known-scratch-retained-file-readonly-postmortem-v1"
NONCE = "rc8f8e3060d3"
BUDGET = {
    "connections": 1,
    "downloads": 1,
    "actions": 0,
    "producers": 0,
    "sd_writes": 0,
    "new_files": 0,
    "stage_seconds": 18,
    "active_seconds": 42,
    "monitor_seconds": 55,
    "disconnect_observation_seconds": 8,
    "new_raw_nor_coverage_bytes": 0,
}
STAGE_SCOPE = "post-startup-normalization-download-slow-identity"


def validate_plan(plan):
    if (
        plan.get("profile") != PROFILE
        or plan.get("name") != F.NAME
        or plan.get("nonce") != NONCE
        or type(plan.get("nor_offset")) is not int
        or plan["nor_offset"] != 0
        or plan.get("budget") != BUDGET
        or any(type(plan["budget"][key]) is not int for key in BUDGET)
        or plan.get("stage_timeout_scope") != STAGE_SCOPE
        or plan.get("startup_policy") != startup.LEGACY_POLICY
        or plan.get("status_event_policy") != E.POLICY
        or plan.get("expected_before") != plan["parent"]["latest_info"]
        or plan["parent"].get("nonce") != NONCE
        or plan["parent"].get("name") != F.NAME
        or plan["parent"].get("nor_offset") != 0
        or plan["parent"].get("original_failed_retained") is not True
    ):
        raise ValueError("Requires fixed zero-write retained-file postmortem plan")
    verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    J.time_order(plan["parent"]["ended_at"], plan["planned_at"])


def prepare(failed: Path, image: Path):
    previous, state, parent = sources.verify(failed, image)
    plan = {
        "profile": PROFILE,
        "name": F.NAME,
        "nonce": NONCE,
        "nor_offset": 0,
        "budget": BUDGET.copy(),
        "stage_timeout_scope": STAGE_SCOPE,
        "startup_policy": startup.LEGACY_POLICY,
        "status_event_policy": E.POLICY,
        "expected_before": state,
        "parent": parent,
        "planned_at": S.now(),
    }
    validate_plan(plan)
    return plan, previous


def source_gate(plan, image):
    validate_plan(plan)
    previous, state, parent = sources.verify(Path(plan["parent"]["directory"]), image)
    if state != plan["expected_before"] or parent != plan["parent"]:
        raise ValueError("Original failed parent changed before readonly postmortem")
    return previous


def report(plan):
    validate_plan(plan)
    return {
        key: plan[key]
        for key in (
            "profile",
            "expected_before",
            "budget",
            "stage_timeout_scope",
            "startup_policy",
            "status_event_policy",
        )
    } | {
        "started_at": S.now(),
        "transport": {},
        "ok": False,
        "sd_write_attempted": False,
        "operation": {"operation_id": "retained", "name": F.NAME, "live_complete": False, "ok": False},
    }


def readonly(report, directory, plan):
    """Independent transport proof is saved before any retained-content parsing."""
    validate_plan(plan)
    # Content verdict belongs to the later independent layer. This audit may
    # recheck retained transport proof after content failed, without promoting it.
    common.no_errors({key: value for key, value in report.items() if key != "content_error"})
    if (
        any(
            report.get(key) != plan[key]
            for key in (
                "profile",
                "expected_before",
                "budget",
                "stage_timeout_scope",
                "startup_policy",
                "status_event_policy",
            )
        )
        or report.get("sd_write_attempted") is not False
    ):
        raise ValueError("Readonly fixed profile/state/policy or zero-write flag changed")
    op = report["operation"]
    if (
        op.get("operation_id") != "retained"
        or op.get("name") != F.NAME
        or op.get("live_complete") is not True
        or any(key in op for key in ("actions_start", "producer", "dump_command", "sd_write_attempted"))
        or "operations" in report
    ):
        raise ValueError("Only one fixed original readonly download is permitted")
    J.time_order(
        plan["parent"]["ended_at"],
        plan["planned_at"],
        report["started_at"],
        op["started_at"],
        op["ended_at"],
        report["ended_at"],
    )
    if (
        datetime.fromisoformat(op["ended_at"]) - datetime.fromisoformat(op["started_at"])
    ).total_seconds() > 18:
        raise ValueError("Post-startup readonly stage exceeds18-second bound")
    if report.get("monitor_exit") != 0 or report.get("monitor_stop") != {
        "signal": "SIGINT",
        "requested": True,
        "delivery": "sent",
    }:
        raise ValueError("Readonly capture lacks clean owned SIGINT stop")
    rows = report["att_packets"]
    if any(type(row["monotonic_ns"]) is not int for row in rows) or any(
        a["monotonic_ns"] > b["monotonic_ns"] for a, b in pairwise(rows)
    ):
        raise ValueError("Readonly original ATT timestamps changed")
    _, event_proof = E.verify(report)
    raw = (directory / "session.btsnoop").read_bytes()
    observed = P.inspect(raw, link=report["transport"]["link"], final=True)
    if (
        observed["pending"]
        or len(observed["transactions"]) != 3
        or report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
        or report["gatt_proof"] != A.setup(report)
        or report["att_hci_binding"] != dual_hci.bind(report, raw)
    ):
        raise ValueError("Requires complete original GATT/ATT/HCI and three exact negotiations")
    wire = common.wire_positions(report, raw)
    disconnects = observed["disconnects"]
    if (
        len(disconnects) != 1
        or disconnects[0]["status"] != 0
        or disconnects[0]["reason"] != 0x16
        or disconnects[0]["record"] <= max(row[1] for row in wire)
        or report.get("disconnect_observation")
        != {"observed": True, "event": disconnects[0], "max_wait_seconds": 8}
    ):
        raise ValueError("Requires actual sole normal local disconnect after final readonly ATT")
    requested, completed, recorded = [
        report[key] for key in ("close_requested_us", "close_completed_us", "disconnect_observed_us")
    ]
    if (
        any(type(value) is not int for value in (requested, completed, recorded))
        or not requested <= completed <= recorded <= completed + 8_000_000
        or not requested <= disconnects[0]["timestamp_us"] <= completed + 8_000_000
    ):
        raise ValueError("Actual readonly close observation exceeds bounded timing")
    E.bridge(report, report["setup_end"], report["before_span"][0])
    A.identity(report, report, "before")
    if report["predecessor_state_verification"] != verify_state(
        plan["expected_before"], report["before"], sd_write=False
    ):
        raise ValueError("Readonly initial state differs from failed original final identity")
    E.bridge(report, report["before_span"][1], report["file_list_span"][0])
    if common.file_list(report) != report["listed_count"]:
        raise ValueError("Readonly original visible inventory changed")
    E.bridge(report, report["file_list_span"][1], op["download_start"])
    startup_tx, normal, slow = observed["transactions"]
    classification = startup.classify(startup_tx)
    if (
        report["startup_settlement"] != startup_tx
        or report["startup_classification"] != classification
        or op["before"] != report["before"]
    ):
        raise ValueError("Readonly startup is not original strict FAST before its fixed download")
    shared.baseline_window(report, op, wire, startup_tx, normal, slow)
    data = shared.download(report, op, directory)
    shared.barrier(report, op, report["before"], writing=False)
    E.bridge(report, op["verified_end"], report["after_span"][0])
    A.identity(report, report, "after")
    E.bridge(report, report["after_span"][1], len(rows))
    if report["state_verification"] != verify_state(op["after"], report["after"], sd_write=False):
        raise ValueError("Final readonly state differs from its immediate download barrier")
    return {
        "verified": True,
        "connections": 1,
        "downloads": 1,
        "bytes": 4096,
        "sha256": A.sha(data),
        "parameter_transactions": 3,
        "actions": 0,
        "producers": 0,
        "sd_writes": 0,
        "new_files": 0,
        "new_raw_nor_coverage_bytes": 0,
        "status_events": event_proof,
    }


def content(data, previous, plan):
    validate_plan(plan)
    sector, proof = F.parse_ring(data, previous, nonce=NONCE, nor_offset=0)
    oracle = plan["parent"]["sources"]["oracles"]["boot0"]
    if A.sha(sector) != oracle["sha256"]:
        raise ValueError("Retained coherent boot0 text differs from independent raw oracle")
    return {
        "verified": True,
        "observation": "readonly-retained-known-file",
        "freshness": proof,
        "sector_hex": sector.hex(),
        "oracle": oracle,
        "original_trial_ok": False,
        "reuse_pair_complete": False,
        "new_raw_nor_coverage_bytes": 0,
    }
