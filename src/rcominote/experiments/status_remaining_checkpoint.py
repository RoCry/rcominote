"""Pinned failed status-job provenance: successful2800 coverage, discovery-only2a00.

The failed discovery supplies no identity, NOR or SD-write evidence. Latest
verified state remains successful2800.after and must be read again before Actions.
"""

import json
from itertools import pairwise
from pathlib import Path

from rcominote.experiments import dual_hci
from rcominote.experiments import hci_interval as H
from rcominote.experiments import status_window_job as W
from rcominote.experiments import window_state_checkpoint as previous
from rcominote.experiments.hci_monitor import Snoop

ERROR = "TimeoutError: [Errno 110] Connection timed out"
PINS = {
    "report.json": "075dcfc01378eec6c56b82071ea65416f715ad3c6989efa86f7aeb2446de4567",
    "job-plan.json": "02076a56b1a08c50ed90bfd5abae6aa0f91220d049e3d4c8cad017303da90d05",
    "checkpoint-2800.json": "1e3a920989692d14cfe0c7435b5aa400eb749a9438d0a5899b884043767de89d",
    "2800/report.json": "6e2dc06d842b55a8d34ac345d4596374e14bf44a342c98d052ebdd9bf5208d4a",
    "2800/session.btsnoop": "e961f9efe7ae814a622d0fcf0e1f3057a4b53e5056f67d90f47131fc9fcf6c0b",
    "2a00/report.json": "a9f6135cb1ee1b651dab6ff403feb027fc64f50f0974b467bd36dc0a72133eb3",
    "2a00/session.btsnoop": "11cbc06a536d823e6f2de3c0c35c42e973271b03ed09bf29f32d73e3358a204e",
}
GATT_TRACE = (
    ("tx", "02f700"),
    ("rx", "03f700"),
    ("rx", "02f700"),
    ("tx", "03f700"),
    ("tx", "100100ffff0028"),
    ("rx", "110601000800011809000f000018100013000f18"),
    ("tx", "101400ffff0028"),
    ("rx", "111414001900d19f1b1f80f2b28ee8119af601309ae4"),
    ("tx", "101a00ffff0028"),
    ("rx", "11061a001f00f0f520002b00e0e5"),
    ("tx", "102c00ffff0028"),
    ("rx", "01102c000a"),
    ("tx", "0820002b000328"),
    ("rx", "09072100042200e1e52300102400e2e52600102700e3e52900102a00e4e5"),
    ("tx", "082b002b000328"),
    ("rx", "01082b000a"),
    ("tx", "0425002500"),
    ("rx", "050125000229"),
    ("tx", "0428002800"),
)


def discovery_failure(report: dict, raw: bytes, plan: dict, good: dict) -> dict:
    W.C.recipe(report)
    slot = plan["slots"][1]
    if (
        any(report.get(key) is not False for key in ("ok", "pair_verified", "final_audit_complete"))
        or report.get("error") != ERROR
        or report.get("capture_error") != ERROR
        or report.get("status_event_policy") != W.E.POLICY
        or report.get("status_events") != []
        or report["nor_offset"] != slot["nor_offset"]
        or [op["name"] for op in report["operations"]] != slot["names"]
        or any(report[key] != plan[key] for key in ("parent", "window_parent"))
        or report["expected_before"] != good["after"]
        or any(key in report for key in ("before", "after", "setup_end", "gatt_proof", "pair_verification"))
        or report.get("monitor_exit") != 0
        or report.get("monitor_stop") != {"signal": "SIGINT", "requested": True, "delivery": "sent"}
        or report["transport"] != {"update_attempted": False, "policy": W.C.POLICY}
    ):
        raise ValueError("Requires original discovery-only failure, without identity or successful flags")
    for op in report["operations"]:
        if any(op.get(key) is not False for key in ("ok", "sd_write_attempted", "pair_verified")) or any(
            key in op
            for key in ("actions_start", "actions_end", "live_complete", "before", "after", "verification")
        ):
            raise ValueError("Failed discovery must have no Actions, producer, write or download execution")
    parser = Snoop()
    parser.feed(raw, final=True)
    if report["hci_capture"] != {
        "bytes": len(raw),
        "sha256": W.S.audit.sha(raw),
        "records": parser.records,
    } or [event["kind"] for event in parser.events] != ["controller", "connect", "disconnect"]:
        raise ValueError("Discovery failure HCI capture/event epoch changed")
    controller, connect, disconnect = parser.events
    if (
        controller["address"] != "AC:19:8E:26:2B:F8"
        or connect["status"] != 0
        or connect["address"] != H.PEER
        or connect["address_type"] != 0
        or connect["role"] != 0
        or [connect[k] for k in ("interval", "latency", "timeout")] != [48, 4, 600]
        or disconnect["status"] != 0
        or disconnect["reason"] != 8
        or disconnect["handle"] != connect["handle"]
        or connect["record"] >= disconnect["record"]
    ):
        raise ValueError("Requires owned successful connect followed by supervision-timeout disconnect08")
    wire = dual_hci.att_packets(raw, connect["handle"])
    rows = report["att_packets"]
    expected = list(GATT_TRACE)
    if (
        [(r["direction"], r["hex"]) for r in wire] != expected
        or [(r["direction"], r["hex"]) for r in rows] != expected
        or any(a["monotonic_ns"] > b["monotonic_ns"] for a, b in pairwise(rows))
    ):
        raise ValueError("Requires exactly19 matching GATT-discovery ATT rows ending in unanswered0428002800")
    return {
        "discovery_only": True,
        "att_packets": len(wire),
        "connect": connect,
        "disconnect": disconnect,
        "sd_write_attempts": 0,
        "producer_executions": 0,
        "new_raw_nor_coverage_bytes": 0,
        "identity_observations": 0,
        "state_source": "successful2800.after",
    }


def verify(failed_job: Path, image: Path) -> tuple[bytes, dict, dict]:
    directory = failed_job.resolve()
    inputs = {name: previous.pinned(directory / name, digest) for name, digest in PINS.items()}
    job, plan, good, failed = [
        json.loads(inputs[name][0])
        for name in ("report.json", "job-plan.json", "2800/report.json", "2a00/report.json")
    ]
    if (
        job.get("profile") != W.PROFILE
        or job.get("ok") is not False
        or job.get("error") != ERROR
        or job.get("active_slot") != "2a00"
        or len(job["completed"]) != 1
        or "outputs" in job
        or job["plan"]["file"] != "job-plan.json"
        or job["completed"][0]["report"]["file"] != "2800/report.json"
        or any((directory / name).exists() for name in ("tail.bin", "fw1_boot.bin"))
    ):
        raise ValueError("Requires pinned failed status job with only successful2800 checkpoint")
    W.J.check_reference(directory, job["plan"])
    W.J.check_reference(directory, job["completed"][0]["report"])
    W.validate_plan(plan)
    saved = json.loads(inputs["checkpoint-2800.json"][0])
    if saved != {
        key: ("2800" if key == "active_slot" else value)
        for key, value in job.items()
        if key not in ("error", "ended_at")
    }:
        raise ValueError("Original completed2800 checkpoint differs from failed job")
    prefix, state, old = previous.verify(Path(plan["checkpoint_directory"]), image)
    if old != plan["checkpoint"] or state != old["latest_info"]:
        raise ValueError("Original status job checkpoint source changed")
    W.J.time_order(old["ended_at"], plan["planned_at"], job["started_at"], good["started_at"])
    W.J.require_success(good)
    if good.get("status_event_policy") != W.E.POLICY:
        raise ValueError("Successful2800 status policy changed")
    previous.bind_slot(good, plan["slots"][0], plan, {"after": state, "ended_at": old["ended_at"]})
    result = W.N.replay(directory / "2800", image)
    if result != job["completed"][0]["verification"]:
        raise ValueError("Successful2800 complete replay differs from retained checkpoint")
    W.J.time_order(good["ended_at"], failed["started_at"], failed["ended_at"], job["ended_at"])
    failure = discovery_failure(failed, inputs["2a00/session.btsnoop"][0], plan, good)
    for label in ("2c00", "2e00"):
        slot = directory / label
        if sorted(p.name for p in slot.iterdir()) != ["first", "second"] or any(
            list((slot / name).iterdir()) for name in ("first", "second")
        ):
            raise ValueError("Later unscheduled slots must remain empty")
    block, source = previous.sector(directory / "2800/first/sector.bin", 0x2800, result)
    data = prefix + block
    if len(prefix) != 2048 or W.S.audit.sha(prefix) != old["sha256"] or len(data) != 2560:
        raise ValueError("Requires complete independently replayed prefix2000..2a00")
    names = set(old["prior_names"]) | {name for slot in plan["slots"] for name in slot["names"]}
    summary = {
        "directory": str(directory),
        "verified_prefix": [0x2000, 0x2A00],
        "bytes": len(data),
        "sha256": W.S.audit.sha(data),
        "ended_at": job["ended_at"],
        "latest_info": good["after"],
        "parent": plan["parent"],
        "window_parent": plan["window_parent"],
        "old_checkpoint": old,
        "references": {name: value[1] for name, value in inputs.items()},
        "coverage2800": source,
        "failed_discovery": failure,
        "prior_names": sorted(names),
        "original_job_ok": False,
        "original_failed_pair_verified": False,
    }
    return data, good["after"], summary
