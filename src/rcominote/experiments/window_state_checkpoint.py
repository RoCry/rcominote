"""Offline coverage/state split for one pinned failed fixed-window job.

Only the successful2600 pair extends coverage. The failed2800 capture supplies
an independently verified final identity/state checkpoint, never NOR coverage.
Original flags remain untouched; no device I/O or filesystem writes.
"""

import json
import re
from pathlib import Path

from rcominote import protocol as P
from rcominote.experiments import boot_prefix_evidence as prefix_source
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import param_window as parameters
from rcominote.experiments import window_nor_contract as C
from rcominote.experiments import window_nor_job as W
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state

JOB_SHA = "981603275a1468731dead831556e38a0000be3becc8246ada2bf6cad22555c34"
REPORT2600_SHA = "8d2a053191b36ee55a9520f4a323be8cb68f6e55f4e5521f310ca7dc1d6b4918"
HCI2600_SHA = "926b044c1bbc5b091f8b31d3b77ea05c36c04c4b2fa624efc25f7081db39bb23"
REPORT2800_SHA = "cfbfd1c563d546140cea1ccb0a8d4c9d90b1945f961f53794781562bea25e062"
HCI2800_SHA = "bda51998e95d604e0ecf3122e563d9a701439986e72d6bd3d62f7ef4fb99be12"
GAP_ERROR = "ValueError: Incomplete operation or a gap/reused boundary in actual Actions/download trace"


def pinned(path: Path, expected_sha: str) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    if A.sha(raw) != expected_sha:
        raise ValueError(f"Pinned failed-window checkpoint changed: {path}")
    return raw, J.reference(path.parent, path) | {"file": str(path.resolve())}


def bind_slot(report: dict, slot: dict, plan: dict, previous: dict) -> dict:
    C.recipe(report)
    if (
        report["nor_offset"] != slot["nor_offset"]
        or [op["name"] for op in report["operations"]] != slot["names"]
        or any(report[key] != plan[key] for key in ("parent", "window_parent"))
        or report["expected_before"] != previous["after"]
    ):
        raise ValueError("Checkpoint slot target, nonce, parents or predecessor changed")
    J.time_order(previous["ended_at"], report["started_at"], report["ended_at"])
    state = verify_state(previous["after"], report["before"], sd_write=False)
    if report["predecessor_state_verification"] != state:
        raise ValueError("Checkpoint predecessor-state proof changed")
    return state


def failed_state(report: dict, raw: bytes) -> dict:
    """Audit identity/state and attempted writes; deliberately omit NOR pairing."""
    C.recipe(report)
    if (
        any(report.get(key) is not False for key in ("ok", "pair_verified", "final_audit_complete"))
        or report.get("error") != GAP_ERROR
        or report.get("final_evidence_error") != GAP_ERROR
        or any(
            op.get("ok") is not False or op.get("sd_write_attempted") is not True
            for op in report["operations"]
        )
        or report.get("monitor_exit") != 0
        or report.get("monitor_stop") != {"signal": "SIGINT", "requested": True, "delivery": "sent"}
    ):
        raise ValueError("Requires original failed2800 flags, exact gap error and two attempted SD writes")
    observed = parameters.inspect(raw, link=report["transport"]["link"], final=True)
    if (
        len(observed["transactions"]) != 6
        or observed["pending"]
        or report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
        or A.setup(report) != report["gatt_proof"]
        or dual_hci.bind(report, raw) != report["att_hci_binding"]
    ):
        raise ValueError("Failed2800 state lacks complete HCI/ATT/GATT/parameter evidence")
    if common.span(report, report["before_span"])[0] != report["setup_end"]:
        raise ValueError("Initial actual identity does not immediately follow setup")
    A.identity(report, report, "before")
    verify_state(report["before"], report["before"], sd_write=False)
    common.file_list(report)
    boundary = report["file_list_span"][1]
    state = report["before"]
    steps = []
    for index, operation in enumerate(report["operations"]):
        if (
            operation["before"] != state
            or operation["actions_start"] != boundary
            or operation.get("live_complete") is not True
            or operation.get("barrier_complete") is not True
            or operation["download_start"] - operation["actions_end"] != index
            or common.span(report, operation["after_span"])
            != [operation["download_end"], operation["verified_end"]]
        ):
            raise ValueError("Failed2800 actual operation/state boundary changed")
        if A.actions(report, operation) != operation["actions_verification"]:
            raise ValueError("Failed2800 fixed SD-write Actions proof changed")
        A.identity(report, operation, "after")
        step = verify_state(state, operation["after"], sd_write=True)
        if operation["state_verification"] != step:
            raise ValueError("Failed2800 per-write state proof changed")
        steps.append(step)
        state, boundary = operation["after"], operation["verified_end"]
    gap_index = report["operations"][1]["actions_end"]
    row = report["att_packets"][gap_index]
    packet = bytes.fromhex(row["hex"])
    if row["direction"] != "rx" or packet[:3] != b"\x1b\x24\0":
        raise ValueError("Known gap must be one actual command notification")
    command, payload = P.parse(packet[3:])
    if command != 0x0F or len(payload) != 20:
        raise ValueError("Known gap must be the fixed20-byte status notification")
    event = P.parse_event(command, payload)
    shared = [key for key in event if key != "raw" and key in state["device"]]
    if len(shared) != 9 or any(event[key] != state["device"][key] for key in shared):
        raise ValueError("Known gap status differs from final operation state")
    if common.span(report, report["after_span"]) != [boundary, len(report["att_packets"])]:
        raise ValueError("Final actual identity must consume the remaining ATT tail")
    A.identity(report, report, "after")
    final = verify_state(state, report["after"], sd_write=False)
    if report["state_verification"] != final:
        raise ValueError("Failed2800 final read-only state proof changed")
    return {
        "identity_verified": True,
        "attempted_fixed_sd_writes": 2,
        "parameter_transactions": 6,
        "pending_transactions": 0,
        "att_binding": report["att_hci_binding"],
        "per_write_state": steps,
        "final_readonly_state": final,
        "original_nor_pair_verified": False,
        "coverage_bytes": 0,
    }


def sector(path: Path, offset: int, proof: dict) -> tuple[bytes, dict]:
    data = path.read_bytes()
    if len(data) != 512 or proof["nor_range"] != [offset, offset + 512] or A.sha(data) != proof["sha256"]:
        raise ValueError("Actual checkpoint coverage sector differs from its full source proof")
    return data, {
        "nor_range": [offset, offset + 512],
        "source": J.reference(path.parent, path) | {"file": str(path.resolve())},
        "proof": proof,
    }


def prior_names(plan: dict) -> list[str]:
    names = {name for slot in plan["slots"] for name in slot["names"]}
    visited = set()

    def walk(wrapper: dict) -> None:
        path = Path(wrapper["directory"]) / "report.json"
        if path.resolve() in visited:
            return
        visited.add(path.resolve())
        raw, _ = pinned(path, wrapper["report_sha256"])
        report = json.loads(raw)
        candidates = [report.get("name")] + [op.get("name") for op in report.get("operations", [])]
        names.update(
            name for name in candidates if isinstance(name, str) and re.fullmatch(r"rc[0-9a-f]{10}", name)
        )
        for key in ("parent", "window_parent", "progress_parent"):
            if key in report:
                walk(report[key])

    for key in ("parent", "window_parent", "progress_parent"):
        walk(plan[key])
    return sorted(names)


def verify(failed_job: Path, image: Path) -> tuple[bytes, dict, dict]:
    directory = failed_job.resolve()
    specs = {
        "job": ("report.json", JOB_SHA),
        "report2600": ("2600/report.json", REPORT2600_SHA),
        "capture2600": ("2600/session.btsnoop", HCI2600_SHA),
        "report2800": ("2800/report.json", REPORT2800_SHA),
        "capture2800": ("2800/session.btsnoop", HCI2800_SHA),
    }
    pinned_inputs = {key: pinned(directory / name, digest) for key, (name, digest) in specs.items()}
    job, good, failed = [json.loads(pinned_inputs[key][0]) for key in ("job", "report2600", "report2800")]
    if (
        job.get("profile") != W.PROFILE
        or job.get("ok") is not False
        or job.get("error") != GAP_ERROR
        or job.get("active_slot") != "2800"
        or len(job["completed"]) != 1
        or "outputs" in job
        or any((directory / name).exists() for name in ("tail.bin", "fw1_boot.bin"))
        or job["plan"]["file"] != "job-plan.json"
        or job["completed"][0]["report"]["file"] != "2600/report.json"
    ):
        raise ValueError("Requires exact failed five-slot job with only successful2600 checkpoint")
    plan_path = J.check_reference(directory, job["plan"])
    plan = json.loads(plan_path.read_bytes())
    W.validate_plan(plan)
    J.check_reference(directory, job["completed"][0]["report"])
    checkpoint = json.loads((directory / "checkpoint-2600.json").read_bytes())
    if checkpoint != {
        key: ("2600" if key == "active_slot" else value)
        for key, value in job.items()
        if key not in ("error", "ended_at")
    }:
        raise ValueError("Original completed2600 checkpoint differs from the failed job")
    prefix, historical = prefix_source.verify()
    progress, original2400 = W.progress_gate(Path(plan["progress_parent"]["directory"]), image)
    if (
        progress != plan["progress_parent"]
        or historical != plan["prefix_evidence"]
        or any(original2400[key] != plan[key] for key in ("parent", "window_parent"))
    ):
        raise ValueError("Checkpoint actual prefix/parent provenance differs from immutable plan")
    J.time_order(original2400["ended_at"], plan["planned_at"], job["started_at"], good["started_at"])
    bind_slot(good, plan["slots"][0], plan, original2400)
    verified2600 = N.replay(directory / "2600", image)
    if verified2600 != job["completed"][0]["verification"]:
        raise ValueError("Original successful2600 replay differs from the completed checkpoint")
    bind_slot(failed, plan["slots"][1], plan, good)
    J.time_order(failed["ended_at"], job["ended_at"])
    state_proof = failed_state(failed, pinned_inputs["capture2800"][0])
    blocks = [prefix]
    coverage = [
        {"nor_range": [0x2000, 0x2200], "source": historical["sources"]["prefix"], "proof": historical}
    ]
    for offset, wrapper in ((0x2200, plan["parent"]), (0x2400, progress)):
        block, proof = sector(
            Path(wrapper["directory"]) / "first/sector.bin", offset, wrapper["verification"]
        )
        blocks.append(block)
        coverage.append(proof)
    block, proof = sector(directory / "2600/first/sector.bin", 0x2600, verified2600)
    blocks.append(block)
    coverage.append(proof)
    data = b"".join(blocks)
    if len(prefix) != 512 or len(data) != 2048:
        raise ValueError("Checkpoint requires four actual512-byte sectors in address order")
    refs = {key: value[1] for key, value in pinned_inputs.items()}
    refs.update(
        plan=J.reference(directory, plan_path),
        checkpoint2600=J.reference(directory, directory / "checkpoint-2600.json"),
    )
    summary = {
        "directory": str(directory),
        "verified_prefix": [0x2000, 0x2800],
        "bytes": len(data),
        "sha256": A.sha(data),
        "ended_at": failed["ended_at"],
        "state_checkpoint_file": refs["report2800"]["file"],
        "state_checkpoint_sha256": REPORT2800_SHA,
        "latest_info": failed["after"],
        "original_job_ok": False,
        "original_failed_pair_verified": False,
        "original_error": GAP_ERROR,
        "references": refs,
        "historical_prefix": historical,
        "coverage_sources": coverage,
        "parent": plan["parent"],
        "window_parent": plan["window_parent"],
        "progress_parent": progress,
        "plan": plan,
        "state_verification": state_proof,
        "prior_names": prior_names(plan),
    }
    return data, failed["after"], summary
