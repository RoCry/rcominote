"""Four fixed status-aware boot sectors, with a separate failed-session state anchor.

A failed old job proves latest state, never NOR coverage. Only four complete
new pair audits plus the independently replayed 2048-byte prefix can assemble.
"""

import asyncio
import json
import re
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import dual_unknown_pair as U
from rcominote.experiments import fixed_window_job as fixed
from rcominote.experiments import status_event as E
from rcominote.experiments import window_nor_contract as C
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments import window_state_checkpoint as checkpoint
from rcominote.experiments.hci_interval_io import authorize

PROFILE = "fixed-fw1-boot-status-window-job"
OFFSETS = (0x2800, 0x2A00, 0x2C00, 0x2E00)
POLICY = "One pair per fixed sector; first failure stops; no retry/resume"


def coverage_basis() -> dict:
    return {"verified_prefix": [0x2000, 0x2800], "remaining_range": [0x2800, 0x3000], "remaining_bytes": 2048}


def validate_plan(plan: dict) -> None:
    J.time_order(plan["planned_at"])
    summary = plan.get("checkpoint", {})
    if (
        plan.get("profile") != PROFILE
        or plan.get("serial") != OWNED_SERIAL
        or plan.get("source_image_sha256") != U.probe.IMAGE_SHA
        or plan.get("coverage_basis") != coverage_basis()
        or plan.get("new_range") != [0x2800, 0x3000]
        or plan.get("status_event_policy") != E.POLICY
        or plan.get("policy") != POLICY
        or any(
            type(plan.get(key)) is not int or plan[key] != value
            for key, value in (
                ("max_connections", 4),
                ("max_producer_executions", 8),
                ("max_sd_test_files", 8),
            )
        )
        or not isinstance(summary, dict)
        or summary.get("verified_prefix") != [0x2000, 0x2800]
        or type(summary.get("bytes")) is not int
        or summary["bytes"] != 2048
        or not isinstance(summary.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", summary["sha256"]) is None
        or not isinstance(plan.get("checkpoint_directory"), str)
        or not plan["checkpoint_directory"]
        or summary.get("directory") != plan["checkpoint_directory"]
        or any(summary.get(key) != plan.get(key) for key in ("parent", "window_parent"))
    ):
        raise ValueError("Job differs from fixed four-sector status plan or checkpoint basis")
    C._pin(plan.get("parent"), C.C.PARENT_SHA, C.C.PARENT_HCI_SHA)
    C._pin(plan.get("window_parent"), C.WINDOW_PARENT_SHA, C.WINDOW_HCI_SHA)
    J.time_order(summary["ended_at"], plan["planned_at"])
    prior = summary["prior_names"]
    if (
        not isinstance(prior, list)
        or len(prior) != len(set(prior))
        or any(not isinstance(name, str) or re.fullmatch(r"rc[0-9a-f]{10}", name) is None for name in prior)
    ):
        raise ValueError("Checkpoint scratch nonce history is invalid")
    slots = plan["slots"]
    if (
        not isinstance(slots, list)
        or len(slots) != 4
        or any(type(slot.get("nor_offset")) is not int for slot in slots)
        or [slot["nor_offset"] for slot in slots] != list(OFFSETS)
    ):
        raise ValueError("Requires four fixed sectors once each, without gaps or overlap")
    names = []
    for offset, slot in zip(OFFSETS, slots, strict=True):
        if slot.get("directory") != f"{offset:04x}" or not isinstance(slot.get("names"), list):
            raise ValueError("Fixed slot path/names changed")
        if len(slot["names"]) != 2 or any(
            not isinstance(name, str) or re.fullmatch(r"rc[0-9a-f]{10}", name) is None
            for name in slot["names"]
        ):
            raise ValueError("Invalid planned scratch nonce")
        names.extend(slot["names"])
    if len(set(names)) != 8 or set(names) & set(prior):
        raise ValueError("Eight fresh distinct pre-I/O nonces required; no regeneration")


def prepare(image: Path, failed_job: Path) -> tuple[dict, list[dict]]:
    prefix, state, summary = checkpoint.verify(failed_job, image)
    if len(prefix) != 2048 or S.audit.sha(prefix) != summary["sha256"] or state != summary["latest_info"]:
        raise ValueError("Checkpoint bytes/latest state disagree with its retained proof")
    reports = [
        C.prepare(
            image, Path(summary["parent"]["directory"]), Path(summary["window_parent"]["directory"]), offset
        )
        for offset in OFFSETS
    ]
    for report in reports:
        report["status_event_policy"] = E.POLICY
        if any(report[key] != summary[key] for key in ("parent", "window_parent")):
            raise ValueError("Preparations disagree with actual checkpoint parent chains")
    plan = {
        "profile": PROFILE,
        "serial": OWNED_SERIAL,
        "planned_at": S.now(),
        "source_image_sha256": U.probe.IMAGE_SHA,
        "checkpoint_directory": str(failed_job.resolve()),
        "checkpoint": summary,
        "parent": summary["parent"],
        "window_parent": summary["window_parent"],
        "coverage_basis": coverage_basis(),
        "status_event_policy": E.POLICY,
        "new_range": [0x2800, 0x3000],
        "max_connections": 4,
        "max_producer_executions": 8,
        "max_sd_test_files": 8,
        "policy": POLICY,
        "slots": [
            {
                "nor_offset": r["nor_offset"],
                "directory": f"{r['nor_offset']:04x}",
                "names": [op["name"] for op in r["operations"]],
            }
            for r in reports
        ],
    }
    validate_plan(plan)
    return plan, reports


def run_pair(report: dict, directory: Path, image: Path) -> None:
    report["prepared_at"], report["started_at"] = report["started_at"], S.now()
    report.update(ok=False, pair_verified=False, final_audit_complete=False)
    try:
        C.recipe(report)
        if report.get("status_event_policy") != E.POLICY:
            raise ValueError("Fixed status policy required before capture")
        asyncio.run(N.capture(report, directory, image))
        if report.get("final_audit_complete") is not True or any(
            op.get("ok") is not True for op in report["operations"]
        ):
            raise ValueError("Full capture audit must pass before pairing")
        report["pair_verification"] = U.compare_pair(report, directory, validate=C.recipe, parse=C.payload)
        report["pair_verified"] = report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(directory / "report.json", report)


def join_sectors(sectors: list[tuple[int, bytes]], prefix: bytes) -> tuple[bytes, bytes]:
    if [offset for offset, _ in sectors] != list(OFFSETS) or any(len(data) != 512 for _, data in sectors):
        raise ValueError("Assembly requires four complete ordered sectors; no gaps/overlap/filling")
    if len(prefix) != 2048:
        raise ValueError("Assembly requires the actual independently verified 2048-byte prefix")
    tail = b"".join(data for _, data in sectors)
    return tail, prefix + tail


def audit_job(report: dict, directory: Path, image: Path) -> tuple[bytes, bytes, dict]:
    if report.get("profile") != PROFILE or any(
        value for key, value in report.items() if key.endswith("error")
    ):
        raise ValueError("Failed/unrelated job cannot assemble a partition")
    if report["plan"]["file"] != "job-plan.json":
        raise ValueError("Unexpected immutable plan path")
    plan = json.loads(J.check_reference(directory, report["plan"]).read_bytes())
    validate_plan(plan)
    prefix, state, summary = fixed.checkpoint_gate(plan, image, prefix_bytes=2048, verify=checkpoint.verify)
    previous_end = summary["ended_at"]
    J.time_order(previous_end, plan["planned_at"], report["started_at"], report["ended_at"])
    if len(report["completed"]) != 4:
        raise ValueError("Four independently successful pairs required; no partial assembly")
    sectors = fixed.replay_slots(report, plan, directory, image, state=state, previous_end=previous_end)
    tail, full = join_sectors(sectors, prefix)
    result = {
        "pair_verified": True,
        "independent_oracle": False,
        "new_verified_range": [0x2800, 0x3000],
        "new_verified_bytes": len(tail),
        "tail_sha256": S.audit.sha(tail),
        "partition": "fw1_boot",
        "partition_range": [0x2000, 0x3000],
        "partition_bytes": len(full),
        "partition_sha256": S.audit.sha(full),
        "connections": 4,
        "independent_producer_executions": 8,
    }
    return tail, full, result


def replay(directory: Path, image: Path) -> dict:
    report = json.loads((directory / "report.json").read_bytes())
    if report.get("ok") is not True:
        raise ValueError("Original status job failed; preserve checkpoints without promotion")
    if "ended_at" not in report:
        raise ValueError("Archived successful job requires its original end timestamp")
    J.time_order(report["started_at"], report["ended_at"])
    tail, full, result = audit_job(report, directory, image)
    if report["verification"] != result:
        raise ValueError("Saved aggregate status-job proof changed")
    for name, data in (("tail.bin", tail), ("fw1_boot.bin", full)):
        expected = report["outputs"][name]
        if expected["file"] != name or J.check_reference(directory, expected).read_bytes() != data:
            raise ValueError("Aggregate output differs from its independently replayed sectors")
    return result


def main(image: Path, failed_job: Path, newout: Path, sudo_password_stdin: bool = False):
    plan, reports = prepare(image, failed_job)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    S.save(newout / "job-plan.json", plan)
    for slot in plan["slots"]:
        for operation_id in ("first", "second"):
            (newout / slot["directory"] / operation_id).mkdir(parents=True, mode=0o700)
    job = {
        "profile": PROFILE,
        "started_at": S.now(),
        "plan": J.reference(newout, newout / "job-plan.json"),
        "completed": [],
        "ok": False,
    }
    try:
        fixed.plan_gate(job, plan, reports, newout)
        fixed.checkpoint_gate(plan, image, prefix_bytes=2048, verify=checkpoint.verify)
        authorize(password_stdin=sudo_password_stdin)
        fixed.acquire_slots(job, plan, reports, newout, image, run_pair=run_pair)
        job["ended_at"] = S.now()
        tail, full, job["verification"] = audit_job(job, newout, image)
        job["outputs"] = {}
        for name, data in (("tail.bin", tail), ("fw1_boot.bin", full)):
            with (newout / name).open("xb") as handle:
                handle.write(data)
            job["outputs"][name] = J.reference(newout, newout / name)
        job["ok"] = True
    except BaseException as error:
        job["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        job["ended_at"] = S.now()
        S.save(newout / "report.json", job)
    print(json.dumps({"ok": True, "new_verified_bytes": len(tail), "partition_bytes": len(full)}))


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
