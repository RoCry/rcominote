"""Pinned startup-rejected fixed-three job: full latest identity, zero NOR coverage.

Original FAST-only failure remains failed. DEFAULT is classified here solely
to audit the state-only session; this helper authorizes no producer or policy.
The successful2800 coverage anchor is independently replayed without extension.
"""

import json
from pathlib import Path

from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import fixed_window_job as fixed
from rcominote.experiments import param_window as parameters
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as events
from rcominote.experiments import status_remaining_checkpoint as coverage
from rcominote.experiments import window_nor_audit as nor
from rcominote.experiments import window_nor_contract as C
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.experiments.window_state_checkpoint import pinned

PROFILE = "fixed-fw1-boot-status-remaining-three-job"
OFFSETS = (0x2A00, 0x2C00, 0x2E00)
ERROR = "ValueError: Observed parameter transaction differs from the next fixed experiment stage"
PINS = {
    "report.json": "3f98ac2ba0ffa9edad7e0f02a29fec24d7623fac9b20a116454e9be8ad74eedf",
    "job-plan.json": "bea49b62e1aa3b547d8f4720532e2ec680c56d9419a1ba9a627ca55413b03976",
    "2a00/report.json": "03165ecada9f4d8bf178eec4b8e94352b0f5f34d0b4e8fdc3d34b3711cc08be6",
    "2a00/session.btsnoop": "bc8a88ab18853c551bbe34c9330cd4975370493e449ee6bfcb007721729401fe",
}
OPERATION_KEYS = {
    "operation_id",
    "phase",
    "name",
    "device_path",
    "source_address",
    "source_bytes",
    "dump_command",
    "producer",
    "transport_profile",
    "independent_oracle",
    "pair_verified",
    "sd_write_attempted",
    "ok",
}


def failed_state(report: dict, raw: bytes, plan: dict, state: dict) -> dict:
    C.recipe(report)
    slot = plan["slots"][0]
    if (
        any(report.get(key) is not False for key in ("ok", "pair_verified", "final_audit_complete"))
        or report.get("error") != ERROR
        or report.get("capture_error") != ERROR
        or any(key in report for key in ("startup_settlement", "pair_verification", "final_evidence_error"))
        or report.get("status_event_policy") != events.POLICY
        or report.get("status_events") != []
        or report["nor_offset"] != slot["nor_offset"]
        or [op["name"] for op in report["operations"]] != slot["names"]
        or any(report[key] != plan[key] for key in ("parent", "window_parent"))
        or report["expected_before"] != state
        or report["before"] != state
        or report["after"] != state
        or report["transport"].get("update_attempted") is not False
        or report.get("monitor_exit") != 0
        or report.get("monitor_stop") != {"signal": "SIGINT", "requested": True, "delivery": "sent"}
    ):
        raise ValueError("Requires original startup rejection and unchanged complete before/after identity")
    for operation in report["operations"]:
        if set(operation) != OPERATION_KEYS or any(
            operation.get(key) is not False for key in ("ok", "pair_verified", "sd_write_attempted")
        ):
            raise ValueError(
                "Preproducer checkpoint requires no Actions, producer, SD write or download execution"
            )
    _, status_proof = events.verify(report)
    observed = parameters.inspect(raw, link=report["transport"]["link"], final=True)
    if (
        observed["pending"]
        or observed["disconnects"]
        or len(observed["transactions"]) != 1
        or report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
        or len(report["att_packets"]) != 61
        or report["setup_end"] != 34
        or A.setup(report) != report["gatt_proof"]
        or dual_hci.bind(report, raw) != report["att_hci_binding"]
    ):
        raise ValueError(
            "Preproducer state requires complete61ATT GATT/HCI and exactly one settled transaction"
        )
    warm = observed["transactions"][0]
    classification = startup.classify(warm, policy=startup.POLICY)
    connection = observed["connection"]
    if (
        classification["mode"] != "default"
        or warm["update"]["interval"] != 36
        or [connection[key] for key in ("interval", "latency", "timeout")] != [12, 0, 500]
    ):
        raise ValueError("Requires actual initial12/0/500 and complete DEFAULT startup applied36")
    if (
        common.span(report, report["before_span"]) != [34, 40]
        or common.span(report, report["file_list_span"]) != [40, 55]
        or common.span(report, report["after_span"]) != [55, 61]
    ):
        raise ValueError("Read-only setup/before/file-list/after must consume every original ATT row")
    A.identity(report, report, "before")
    A.identity(report, report, "after")
    predecessor = verify_state(state, report["before"], sd_write=False)
    final = verify_state(report["before"], report["after"], sd_write=False)
    if (
        report["predecessor_state_verification"] != predecessor
        or report["state_verification"] != final
        or nor.listed_nonce_gate(report) != 13
    ):
        raise ValueError("Actual identity/state or complete file-list nonce proof changed")
    wire = common.wire_positions(report, raw)
    if not (wire[54][1] < warm["remote_request"]["records"][0] < warm["update"]["record"] < wire[55][0]):
        raise ValueError("Actual DEFAULT negotiation must lie between complete file-list and final identity")
    return {
        "identity_verified": True,
        "sd_write_attempts": 0,
        "producer_executions": 0,
        "actions_commands": 0,
        "new_raw_nor_coverage_bytes": 0,
        "parameter_transactions": 1,
        "pending_transactions": 0,
        "host_origin_normalizations": 0,
        "startup_state_audit": classification,
        "startup_transaction": warm,
        "att_binding": report["att_hci_binding"],
        "status_events": status_proof,
        "predecessor_state": predecessor,
        "final_readonly_state": final,
        "original_job_policy_rejection_preserved": True,
    }


def verify(failed_job: Path, image: Path) -> tuple[bytes, dict, dict]:
    directory = failed_job.resolve()
    inputs = {name: pinned(directory / name, digest) for name, digest in PINS.items()}
    job, plan, failed = [
        json.loads(inputs[name][0]) for name in ("report.json", "job-plan.json", "2a00/report.json")
    ]
    if (
        job.get("profile") != PROFILE
        or job.get("ok") is not False
        or job.get("error") != ERROR
        or job.get("active_slot") != "2a00"
        or job.get("completed") != []
        or "outputs" in job
        or job["plan"]["file"] != "job-plan.json"
        or any((directory / name).exists() for name in ("tail.bin", "fw1_boot.bin"))
    ):
        raise ValueError("Requires pinned failed three-slot job with no completed NOR pair or outputs")
    J.check_reference(directory, job["plan"])
    # Hash-pinned old plan is checked independently of the evolving current job profile.
    if (
        plan.get("profile") != PROFILE
        or plan.get("source_image_sha256") != C.C.probe.IMAGE_SHA
        or plan.get("verified_prefix") != [0x2000, 0x2A00]
        or plan.get("new_range") != [0x2A00, 0x3000]
        or plan.get("status_event_policy") != events.POLICY
        or len(plan["slots"]) != 3
        or [s["nor_offset"] for s in plan["slots"]] != list(OFFSETS)
        or any(
            type(plan.get(k)) is not int or plan[k] != v
            for k, v in (("max_connections", 3), ("max_producer_executions", 6), ("max_sd_test_files", 6))
        )
    ):
        raise ValueError("Pinned historical three-slot plan scope/budget changed")
    prefix, state, anchor = fixed.checkpoint_gate(plan, image, prefix_bytes=2560, verify=coverage.verify)
    if any(plan[key] != anchor[key] for key in ("parent", "window_parent")):
        raise ValueError("Historical plan differs from independently replayed coverage parents")
    J.time_order(
        anchor["ended_at"],
        failed["prepared_at"],
        plan["planned_at"],
        job["started_at"],
        failed["started_at"],
        failed["ended_at"],
        job["ended_at"],
    )
    proof = failed_state(failed, inputs["2a00/session.btsnoop"][0], plan, state)
    for slot in plan["slots"]:
        if slot["directory"] != f"{slot['nor_offset']:04x}" or any(
            list((directory / slot["directory"] / name).iterdir()) for name in ("first", "second")
        ):
            raise ValueError("Every failed/unscheduled payload directory must remain empty")
    names = set(anchor["prior_names"]) | {name for slot in plan["slots"] for name in slot["names"]}
    summary = {
        "directory": str(directory),
        "verified_prefix": [0x2000, 0x2A00],
        "bytes": len(prefix),
        "sha256": A.sha(prefix),
        "ended_at": job["ended_at"],
        "latest_info": failed["after"],
        "parent": anchor["parent"],
        "window_parent": anchor["window_parent"],
        "coverage_anchor": anchor,
        "references": {name: value[1] for name, value in inputs.items()},
        "state_verification": proof,
        "prior_names": sorted(names),
        "original_job_ok": False,
        "original_failed_pair_verified": False,
        "new_raw_nor_coverage_bytes": 0,
    }
    return prefix, failed["after"], summary
