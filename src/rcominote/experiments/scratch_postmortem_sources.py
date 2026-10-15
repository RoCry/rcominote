"""Pinned failed scratch trial: complete baseline, attempted write, final state.

This admits a later read-only inspection without promoting the failed overwrite
or assuming that its current device object still equals its earlier baseline.
"""

import json
from datetime import datetime
from itertools import pairwise
from pathlib import Path

from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import param_window as P
from rcominote.experiments import scratch_reuse_audit as V
from rcominote.experiments import scratch_reuse_contract as C
from rcominote.experiments import scratch_reuse_probe as R
from rcominote.experiments import scratch_reuse_sources as sources
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as E
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state

REPORT_SHA = "58da00f07685e90b564b1f26f6046fdefd724cf25bd0ae616c13bcf49d2be280"
PLAN_SHA = "52b9b028a646ec24e80cac05de3bbe426ad1b7a78b57ad74f479a987aa06005e"
HCI_SHA = "82daa2ab80229a16326b4e646352e62ec58372b0155b004e0290301ac24a1010"
FAILURE = "ValueError: Requires one complete actual uptime F0 line after its command"


def failed_flags(report):
    baseline = report["baseline"]
    first, second = report["operations"]
    if (
        report.get("ok") is not False
        or any(op.get(k) is not False for op in (first, second) for k in ("ok", "live_complete"))
        or any(baseline.get(k) is not True for k in ("ok", "live_complete"))
        or any(report.get(k) != FAILURE for k in ("error", "capture_error"))
        or first.get("error") != FAILURE
        or any(first.get(k) is not True for k in ("producer_attempted", "sd_write_attempted"))
        or any(
            k in first
            for k in (
                "download_start",
                "download_end",
                "download_bytes",
                "received_bytes",
                "after",
                "verification",
                "actions_verification",
                "pre_download_fast",
                "normalization",
                "activity_fast_verification",
                "slow_settlement",
            )
        )
        or any(
            k in second
            for k in (
                "started_at",
                "ended_at",
                "writes",
                "actions_start",
                "actions_end",
                "producer_attempted",
                "sd_write_attempted",
                "download_start",
                "download_bytes",
                "received_bytes",
                "after",
                "verification",
            )
        )
    ):
        raise ValueError("Requires original failed uptime gate after only first attempted overwrite")
    return baseline, first, second


def wire_gate(report, raw):
    observed = P.inspect(raw, link=report["transport"]["link"], final=True)
    rows = report["att_packets"]
    if (
        report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
        or observed["pending"]
        or len(observed["transactions"]) != 3
        or report["gatt_proof"] != A.setup(report)
        or report["att_hci_binding"] != dual_hci.bind(report, raw)
        or report["monitor_exit"] != 0
        or report["monitor_stop"] != {"signal": "SIGINT", "requested": True, "delivery": "sent"}
        or any(type(row["monotonic_ns"]) is not int for row in rows)
        or any(a["monotonic_ns"] > b["monotonic_ns"] for a, b in pairwise(rows))
    ):
        raise ValueError("Failed parent requires full GATT/ATT/HCI and exactly three complete transactions")
    _, events = E.verify(report)
    if events["events"] != 0:
        raise ValueError("Pinned failed trial requires actual zero status events")
    tx = observed["transactions"]
    classification = startup.classify(tx[0])
    if report["startup_settlement"] != tx[0] or report["startup_classification"] != classification:
        raise ValueError("Original strict startup FAST settlement changed")
    return observed, common.wire_positions(report, raw)


def close_gate(report, observed, wire):
    disconnects = observed["disconnects"]
    if len(disconnects) != 1:
        raise ValueError("Requires exactly one observed normal local disconnect")
    event = disconnects[0]
    requested, completed, recorded = [
        report[k] for k in ("close_requested_us", "close_completed_us", "disconnect_observed_us")
    ]
    if (
        event["status"] != 0
        or event["reason"] != 0x16
        or event["record"] <= max(p[1] for p in wire)
        or report["disconnect_observation"] != {"observed": True, "event": event, "max_wait_seconds": 8}
        or not requested <= completed <= recorded <= completed + 8_000_000
        or not requested <= event["timestamp_us"] <= completed + 8_000_000
    ):
        raise ValueError("Normal disconnect must follow all ATT within original bounded close")


def baseline_gate(report, plan, baseline, directory, observed, wire):
    warm = report["baseline"]
    if (
        warm.get("operation_id") != "baseline"
        or warm.get("name") != sources.NAME
        or any(k in warm for k in ("actions_start", "producer", "sd_write_attempted"))
        or warm["before"] != report["before"]
    ):
        raise ValueError("Original complete baseline must remain strictly readonly")
    E.bridge(report, report["setup_end"], report["before_span"][0])
    A.identity(report, report, "before")
    if report["predecessor_state_verification"] != verify_state(
        plan["expected_before"], report["before"], sd_write=False
    ):
        raise ValueError("Actual initial identity differs from latest pinned predecessor")
    if V.inventory(report, plan) != report["listed_count"]:
        raise ValueError("Original complete inventory changed")
    E.bridge(report, report["file_list_span"][1], warm["download_start"])
    current = V.download(report, warm, directory)
    if current != baseline or len(current) != 4096 or A.sha(current) != sources.BASELINE_SHA:
        raise ValueError("Actual existing baseline differs from pinned original owned4096 object")
    C.F.absent(current, [slot["nonce"] for slot in plan["operations"]])
    V.baseline_window(report, warm, wire, *observed["transactions"])
    V.barrier(report, warm, report["before"], writing=False)
    checkpoint = json.loads((directory / "baseline/checkpoint.json").read_bytes())
    if (
        checkpoint["baseline"] != warm
        or checkpoint.get("ok") is not False
        or checkpoint["att_packets"] != report["att_packets"][: warm["verified_end"]]
        or checkpoint["operations"]
        != [slot | {"ok": False, "live_complete": False} for slot in plan["operations"]]
    ):
        raise ValueError("Baseline checkpoint must preserve original success before attempted overwrite")


def attempted_gate(report, first, second, directory):
    warm = report["baseline"]
    if first["before"] != warm["after"]:
        raise ValueError("Attempted overwrite predecessor must equal actual baseline after")
    E.bridge(report, warm["verified_end"], first["actions_start"])
    proof = A.action_frames(report, first, expected=C.recipe(first))
    if (
        first.get("ack_count") != 6
        or first.get("end_received") is not True
        or first.get("pending_hex") != ""
        or any(frame["command"] == 0xF0 for frame in first["frames"])
    ):
        raise ValueError("Original first attempted Actions requires six ACK/F1 and zero F0/pending")
    if any(next((directory / op["operation_id"]).iterdir(), None) for op in (first, second)):
        raise ValueError("Failed overwrite directories must remain empty without candidate/download")
    E.bridge(report, first["actions_end"], report["after_span"][0])
    A.identity(report, report, "after")
    E.bridge(report, report["after_span"][1], len(report["att_packets"]))
    state_proof = verify_state(warm["after"], report["after"], sd_write=False)
    if (
        report["before"] != warm["after"]
        or warm["after"] != report["after"]
        or report["after"]["device"]["free_capacity"] != 59589
        or report["state_verification"] != state_proof
    ):
        raise ValueError("Latest failed-trial actual final identity must remain exactly59589 unchanged")
    return proof, state_proof


def verify(failed_dir: Path, image: Path) -> tuple[bytes, dict, dict]:
    report_raw, report_ref = sources.pinned(failed_dir / "report.json", REPORT_SHA)
    plan_raw, plan_ref = sources.pinned(failed_dir / "plan.json", PLAN_SHA)
    raw, hci_ref = sources.pinned(failed_dir / "session.btsnoop", HCI_SHA)
    report, plan = json.loads(report_raw), json.loads(plan_raw)
    R.plan_gate(report, plan, failed_dir)
    warm, first, second = failed_flags(report)
    baseline = C.source_gate(plan, image)
    J.time_order(
        plan["sources"]["state_parent"]["ended_at"],
        plan["planned_at"],
        report["started_at"],
        warm["started_at"],
        warm["ended_at"],
        first["started_at"],
        first["ended_at"],
        report["ended_at"],
    )
    for op in (warm, first):
        if (
            datetime.fromisoformat(op["ended_at"]) - datetime.fromisoformat(op["started_at"])
        ).total_seconds() > 18:
            raise ValueError("Original failed-parent stage exceeds fixed18-second bound")
    observed, wire = wire_gate(report, raw)
    baseline_gate(report, plan, baseline, failed_dir, observed, wire)
    actions, state = attempted_gate(report, first, second, failed_dir)
    close_gate(report, observed, wire)
    baseline_path = failed_dir / "baseline/download.bin"
    return (
        baseline,
        report["after"],
        {
            "directory": str(failed_dir.resolve()),
            "references": {"report": report_ref, "plan": plan_ref, "capture": hci_ref},
            "report_sha256": REPORT_SHA,
            "ended_at": report["ended_at"],
            "latest_info": report["after"],
            "name": sources.NAME,
            "nonce": first["nonce"],
            "nor_offset": first["nor_offset"],
            "sources": plan["sources"],
            "baseline": {
                "file": str(baseline_path.resolve()),
                "bytes": len(baseline),
                "sha256": A.sha(baseline),
            },
            "original_failed_retained": True,
            "same_file_overwrite_attempted": True,
            "same_file_overwrite_content_confirmed": False,
            "current_object_equals_baseline_proven": False,
            "new_raw_nor_coverage_bytes": 0,
            "state_verification": state,
            "verification": {
                "att_packets": len(wire),
                "hci_records": observed["records"],
                "parameter_transactions": 3,
                "actions": actions,
                "f0_frames": 0,
                "new_files": 0,
            },
        },
    )
