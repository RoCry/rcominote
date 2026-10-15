"""Pinned partial controlled job: two complete sectors, feature-failed final slot.

Only successful2a00/2c00 extend coverage. Failed2e00 has no ACL, ATT, identity,
Actions or SD execution. Latest identity stays actual successful2c00.after;
the original successful RAM control retains its earlier state-parent source.
"""

import json
import re
import struct
from pathlib import Path

from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import param_window as parameters
from rcominote.experiments import preproducer_state_checkpoint as state_source
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_control_parent as control_source
from rcominote.experiments import status_event as events
from rcominote.experiments import window_nor_contract as C
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments import window_state_checkpoint as previous
from rcominote.experiments.hci_monitor import Snoop
from rcominote.experiments.sd_bootstrap import verify_state

PROFILE = "fixed-fw1-boot-status-startup-controlled-three-job"
OFFSETS = (0x2A00, 0x2C00, 0x2E00)
ERROR = "OSError: [Errno 38] LE ATT connect failed"
PINS = {
    "report.json": "f4ce4eb4523d353d15375ed16f358ef1467cf3de5b6e9c3cce5102e6f012f46e",
    "job-plan.json": "d947f4d3ab6b91ead5aeddfd57e826476fe9dcac4b484e8ccf7d54f77dd1b79d",
    "checkpoint-2a00.json": "199280ecd978d092a7cc4710897dbab4d2aa28473c9b1d976e6353056afaa7cb",
    "checkpoint-2c00.json": "87dcea34259a7a2151b29d067e8a58c058edc534bd325c2bf8f6b439cfb31623",
    "2a00/report.json": "9e7c334b722f7370b66f05c523584f1f4fca487bc203bdc6a193f7833ff5b441",
    "2a00/session.btsnoop": "853521a9964f99a4b51613e9572badf761d68ffacd81762f84c9f838fe666c2a",
    "2c00/report.json": "33a08b30bb8eba47d00888f8e70b584001244cab36a7db6adb1491d8f5ab8ebd",
    "2c00/session.btsnoop": "5154b8a6e75431cd7ab4a6dfbe3e8a4c184ae37301d5169b24d211be50b50b57",
    "2e00/report.json": "588bc0a2d304e97af1754d9e79ed4dc96a795285783953672df7d5e4365898a6",
    "2e00/session.btsnoop": "e029bbe3a153db7c183e9555e5fbc05afbbd122d21ef83c527a941b9f32ab060",
}


def bind(report: dict, slot: dict, plan: dict, state: dict) -> None:
    C.recipe(report)
    if (
        report["nor_offset"] != slot["nor_offset"]
        or [op["name"] for op in report["operations"]] != slot["names"]
        or any(
            report[key] != plan[key]
            for key in ("parent", "window_parent", "status_event_policy", "startup_policy", "control_parent")
        )
        or report["expected_before"] != state
    ):
        raise ValueError("Actual controlled slot differs from immutable target/nonces/source/prestate")


def feature_failure(report: dict, raw: bytes) -> dict:
    C.recipe(report)
    if (
        any(report.get(key) is not False for key in ("ok", "pair_verified", "final_audit_complete"))
        or report.get("error") != ERROR
        or report.get("capture_error") != ERROR
        or report.get("att_packets") != []
        or report.get("status_events") != []
        or any(
            key in report
            for key in (
                "before",
                "after",
                "setup_end",
                "gatt_proof",
                "pair_verification",
                "startup_settlement",
            )
        )
        or report["transport"] != {"update_attempted": False, "policy": C.POLICY}
        or report.get("monitor_exit") != 0
        or report.get("monitor_stop") != {"signal": "SIGINT", "requested": True, "delivery": "sent"}
        or any(
            set(op) != state_source.OPERATION_KEYS
            or any(op.get(key) is not False for key in ("ok", "pair_verified", "sd_write_attempted"))
            for op in report["operations"]
        )
    ):
        raise ValueError(
            "Feature-failed slot must retain original failure and zero ATT/identity/Actions/SD execution"
        )
    parser = Snoop()
    parser.feed(raw, final=True)
    rows = list(parameters.records(raw, parser.records))
    if (
        parser.records != 23
        or len(raw) != 950
        or report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": parser.records}
        or any(opcode & 0xFFFF in (4, 5) for _, opcode, _, _ in rows)
        or [item["kind"] for item in parser.events] != ["controller", "connect"]
    ):
        raise ValueError("Requires complete23-record zero-ACL feature-exchange failure capture")
    controller, connection = parser.events
    handle = connection["handle"]
    if (
        controller["address"] != "AC:19:8E:26:2B:F8"
        or connection["record"] != 18
        or rows[17][1] != 3
        or rows[17][3][:3] != b"\x3e\x1f\x0a"
        or (connection["status"], connection["role"], connection["address_type"], connection["address"])
        != (0, 0, 0, parameters.H.PEER)
        or [connection[key] for key in ("interval", "latency", "timeout")] != [48, 4, 600]
        or [(number, opcode) for number, opcode, _, _ in rows[-3:]] != [(21, 2), (22, 3), (23, 3)]
        or rows[20][3] != b"\x16\x20\x02" + struct.pack("<H", handle)
        or rows[21][3] != bytes.fromhex("0f0400011620")
        or rows[22][3] != b"\x3e\x0c\x04\x3e" + struct.pack("<H", handle) + bytes(8)
        or not connection["timestamp_us"] <= rows[20][2] <= rows[21][2] <= rows[22][2]
    ):
        raise ValueError("Requires actual successful owned connect then READ_REMOTE_FEATURES status3e")
    return {
        "connect": connection,
        "feature_request_record": 21,
        "command_status_record": 22,
        "feature_complete_record": 23,
        "feature_complete_status": 0x3E,
        "reported_errno": 38,
        "acl_packets": 0,
        "att_packets": 0,
        "identity_observations": 0,
        "actions_commands": 0,
        "producer_executions": 0,
        "sd_write_attempts": 0,
        "new_raw_nor_coverage_bytes": 0,
    }


def verify(failed_job: Path, image: Path) -> tuple[bytes, dict, dict]:
    directory = failed_job.resolve()
    inputs = {name: previous.pinned(directory / name, digest) for name, digest in PINS.items()}
    job, plan = [json.loads(inputs[name][0]) for name in ("report.json", "job-plan.json")]
    if (
        job.get("profile") != PROFILE
        or job.get("ok") is not False
        or job.get("error") != ERROR
        or job.get("active_slot") != "2e00"
        or len(job["completed"]) != 2
        or "outputs" in job
        or job["plan"]["file"] != "job-plan.json"
        or any((directory / name).exists() for name in ("tail.bin", "fw1_boot.bin"))
        or plan.get("profile") != PROFILE
        or plan.get("source_image_sha256") != C.C.probe.IMAGE_SHA
        or plan.get("verified_prefix") != [0x2000, 0x2A00]
        or plan.get("new_range") != [0x2A00, 0x3000]
        or plan.get("status_event_policy") != events.POLICY
        or plan.get("startup_policy") != startup.POLICY
        or len(plan["slots"]) != 3
        or [slot["nor_offset"] for slot in plan["slots"]] != list(OFFSETS)
        or any(
            type(plan.get(key)) is not int or plan[key] != value
            for key, value in (
                ("max_connections", 3),
                ("max_producer_executions", 6),
                ("max_sd_test_files", 6),
            )
        )
    ):
        raise ValueError(
            "Requires pinned failed controlled-three job with exactly two successful checkpoints"
        )
    J.check_reference(directory, job["plan"])
    prefix, state, basis = state_source.verify(Path(plan["checkpoint_directory"]), image)
    if (
        basis != plan["checkpoint"]
        or state != basis["latest_info"]
        or len(prefix) != 2560
        or A.sha(prefix) != basis["sha256"]
    ):
        raise ValueError("Original2560-byte coverage/control state-parent provenance changed")
    control = control_source.verify(Path(plan["control_parent"]["directory"]), image, basis)
    if control != plan["control_parent"] or control["latest_info"] != state:
        raise ValueError("Original exact RAM control source/state wrapper changed")
    J.time_order(basis["ended_at"], control["ended_at"], plan["planned_at"], job["started_at"])
    blocks, proofs, previous_end = [prefix], [], job["started_at"]
    for index, offset in enumerate(OFFSETS[:2]):
        label = f"{offset:04x}"
        completed, slot = job["completed"][index], plan["slots"][index]
        if completed["report"]["file"] != f"{label}/report.json":
            raise ValueError("Original completed controlled pair path changed")
        path = J.check_reference(directory, completed["report"])
        report = json.loads(path.read_bytes())
        J.require_success(report)
        bind(report, slot, plan, state)
        J.time_order(previous_end, report["started_at"], report["ended_at"])
        if report["predecessor_state_verification"] != verify_state(state, report["before"], sd_write=False):
            raise ValueError("Controlled pair original predecessor proof changed")
        result = N.replay(directory / label, image)
        if result != completed["verification"] or result.get("bytes") != 512:
            raise ValueError("Complete controlled pair replay differs from checkpoint")
        block, proof = previous.sector(directory / label / "first/sector.bin", offset, result)
        snapshot = json.loads(inputs[f"checkpoint-{label}.json"][0])
        expected = {
            key: (
                label
                if key == "active_slot"
                else job["completed"][: index + 1]
                if key == "completed"
                else value
            )
            for key, value in job.items()
            if key not in ("error", "ended_at")
        }
        if snapshot != expected:
            raise ValueError("Original successful controlled checkpoint differs from retained partial job")
        blocks.append(block)
        proofs.append(proof)
        state, previous_end = report["after"], report["ended_at"]
    failed = json.loads(inputs["2e00/report.json"][0])
    bind(failed, plan["slots"][2], plan, state)
    J.time_order(previous_end, failed["started_at"], failed["ended_at"], job["ended_at"])
    failure = feature_failure(failed, inputs["2e00/session.btsnoop"][0])
    if any(list((directory / "2e00" / name).iterdir()) for name in ("first", "second")):
        raise ValueError("Failed feature-exchange payload directories must remain empty")
    names = {name for slot in plan["slots"] for name in slot["names"]}
    if (
        len(names) != 6
        or len(basis["prior_names"]) != 31
        or names & set(basis["prior_names"])
        or any(re.fullmatch(r"rc[0-9a-f]{10}", name) is None for name in names)
    ):
        raise ValueError("Original controlled plan must retain six fresh names beyond all31 ancestors")
    names.update(basis["prior_names"])
    data = b"".join(blocks)
    if len(data) != 3584 or state != control["latest_info"]:
        raise ValueError(
            "Requires actual3584-byte ordered prefix and latest unchanged successful2c00 identity"
        )
    summary = {
        "directory": str(directory),
        "verified_prefix": [0x2000, 0x2E00],
        "bytes": len(data),
        "sha256": A.sha(data),
        "ended_at": job["ended_at"],
        "latest_info": state,
        "parent": plan["parent"],
        "window_parent": plan["window_parent"],
        "control_state_parent": basis,
        "control_parent": control,
        "coverage_sources": proofs,
        "references": {name: value[1] for name, value in inputs.items()},
        "failed_feature_exchange": failure,
        "prior_names": sorted(names),
        "original_job_ok": False,
        "original_failed_pair_verified": False,
        "latest_info_source": "successful2c00.after",
    }
    return data, state, summary
