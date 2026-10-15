"""One final fixed sector after the pinned partial controlled job; never resume.

Reuse status_window_job's complete capture/pair runner. The prefix provenance
helper independently replays successful2800 and every historical source.
"""

import json
import re
from pathlib import Path

import typer

from rcominote.experiments import controlled_tail_checkpoint as checkpoint
from rcominote.experiments import fixed_window_job as fixed
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_control_parent as control_source
from rcominote.experiments import status_window_job as W

PROFILE = "fixed-fw1-boot-status-startup-controlled-final-sector-job"
OFFSETS = (0x2E00,)
POLICY = "New final-sector job after partial controlled coverage; first failure stops; no retry/resume"


def validate_plan(plan: dict) -> None:
    summary = plan["checkpoint"]
    if (
        plan.get("profile") != PROFILE
        or plan.get("serial") != W.OWNED_SERIAL
        or plan.get("source_image_sha256") != W.U.probe.IMAGE_SHA
        or plan.get("status_event_policy") != W.E.POLICY
        or plan.get("startup_policy") != startup.POLICY
        or plan.get("policy") != POLICY
        or plan.get("new_range") != [0x2E00, 0x3000]
        or plan.get("verified_prefix") != [0x2000, 0x2E00]
        or any(
            type(plan.get(k)) is not int or plan[k] != v
            for k, v in (("max_connections", 1), ("max_producer_executions", 2), ("max_sd_test_files", 2))
        )
        or summary.get("directory") != plan.get("checkpoint_directory")
        or not isinstance(plan.get("checkpoint_directory"), str)
        or not plan["checkpoint_directory"]
        or summary.get("verified_prefix") != plan["verified_prefix"]
        or type(summary.get("bytes")) is not int
        or summary["bytes"] != 3584
        or not isinstance(summary.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", summary["sha256"]) is None
        or summary.get("original_job_ok") is not False
        or summary.get("original_failed_pair_verified") is not False
        or any(summary.get(key) != plan.get(key) for key in ("parent", "window_parent"))
    ):
        raise ValueError("Requires fixed new final-sector plan and actual3584-byte prefix source")
    W.C._pin(plan["parent"], W.C.C.PARENT_SHA, W.C.C.PARENT_HCI_SHA)
    W.C._pin(plan["window_parent"], W.C.WINDOW_PARENT_SHA, W.C.WINDOW_HCI_SHA)
    W.J.time_order(summary["ended_at"], plan["planned_at"])
    if (
        plan["control_parent"] != summary["control_parent"]
        or plan["control_parent"]["latest_info"] != summary["latest_info"]
    ):
        raise ValueError("Final-sector control source/latest successful2c00 state changed")
    control_source.validate_wrapper(
        plan["control_parent"], summary["control_state_parent"], planned_at=plan["planned_at"]
    )
    slots = plan["slots"]
    if (
        len(slots) != 1
        or any(type(slot["nor_offset"]) is not int for slot in slots)
        or [slot["nor_offset"] for slot in slots] != list(OFFSETS)
        or any(slot["directory"] != f"{offset:04x}" for slot, offset in zip(slots, OFFSETS, strict=True))
    ):
        raise ValueError("Requires the single fixed2e00 sector/directory")
    names = []
    for slot in slots:
        if not isinstance(slot["names"], list) or len(slot["names"]) != 2:
            raise ValueError("Requires two preplanned scratch nonces per slot")
        names.extend(slot["names"])
    prior = summary["prior_names"]
    if (
        not isinstance(prior, list)
        or any(
            not isinstance(name, str) or re.fullmatch(r"rc[0-9a-f]{10}", name) is None
            for name in names + prior
        )
        or len(prior) != 37
        or len(set(prior)) != len(prior)
        or len(set(names)) != 2
        or set(names) & set(prior)
    ):
        raise ValueError("Two fresh unique nonces must exclude every prior planned/parental name")


def prepare(image: Path, failed_job: Path, control_parent: Path) -> tuple[dict, list[dict]]:
    prefix, state, summary = checkpoint.verify(failed_job, image)
    if len(prefix) != 3584 or W.S.audit.sha(prefix) != summary["sha256"] or state != summary["latest_info"]:
        raise ValueError("Actual prefix/latest verified state disagrees with checkpoint source")
    control = control_source.verify(control_parent, image, summary["control_state_parent"])
    if control != summary["control_parent"] or control["latest_info"] != state:
        raise ValueError("Final-sector control source/state differs from actual successful2c00")
    reports = [
        W.C.prepare(
            image, Path(summary["parent"]["directory"]), Path(summary["window_parent"]["directory"]), offset
        )
        for offset in OFFSETS
    ]
    for report in reports:
        report["status_event_policy"] = W.E.POLICY
        report["startup_policy"] = startup.POLICY
        report["control_parent"] = control
        if any(report[key] != summary[key] for key in ("parent", "window_parent")):
            raise ValueError("Prepared parent provenance differs from actual checkpoint")
    plan = {
        "profile": PROFILE,
        "serial": W.OWNED_SERIAL,
        "planned_at": W.S.now(),
        "source_image_sha256": W.U.probe.IMAGE_SHA,
        "checkpoint_directory": str(failed_job.resolve()),
        "checkpoint": summary,
        "parent": summary["parent"],
        "window_parent": summary["window_parent"],
        "verified_prefix": [0x2000, 0x2E00],
        "new_range": [0x2E00, 0x3000],
        "status_event_policy": W.E.POLICY,
        "startup_policy": startup.POLICY,
        "control_parent": control,
        "policy": POLICY,
        "max_connections": 1,
        "max_producer_executions": 2,
        "max_sd_test_files": 2,
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


def admission(plan: dict, image: Path) -> tuple[bytes, dict, dict]:
    prefix, state, summary = fixed.checkpoint_gate(plan, image, prefix_bytes=3584, verify=checkpoint.verify)
    control = control_source.verify(
        Path(plan["control_parent"]["directory"]), image, summary["control_state_parent"]
    )
    if control != plan["control_parent"] or control["latest_info"] != state:
        raise ValueError("Actual successful control admission differs from immutable plan/latest state")
    control_source.validate_wrapper(control, summary["control_state_parent"], planned_at=plan["planned_at"])
    return prefix, state, summary


def join_sectors(sectors: list[tuple[int, bytes]], prefix: bytes) -> tuple[bytes, bytes]:
    if (
        [offset for offset, _ in sectors] != list(OFFSETS)
        or len(prefix) != 3584
        or any(len(data) != 512 for _, data in sectors)
    ):
        raise ValueError("Assembly requires verified3584-byte prefix and one complete final sector")
    tail = b"".join(data for _, data in sectors)
    return tail, prefix + tail


def audit_job(report: dict, directory: Path, image: Path) -> tuple[bytes, bytes, dict]:
    if report.get("profile") != PROFILE or any(v for k, v in report.items() if k.endswith("error")):
        raise ValueError("Failed/unrelated job cannot assemble a partition")
    if report["plan"]["file"] != "job-plan.json":
        raise ValueError("Unexpected immutable plan path")
    plan = json.loads(W.J.check_reference(directory, report["plan"]).read_bytes())
    validate_plan(plan)
    prefix, state, _ = admission(plan, image)
    previous_end = plan["checkpoint"]["ended_at"]
    W.J.time_order(previous_end, plan["planned_at"], report["started_at"], report["ended_at"])
    if len(report["completed"]) != 1:
        raise ValueError("One independently successful final pair required; no partial assembly")
    sectors = fixed.replay_slots(report, plan, directory, image, state=state, previous_end=previous_end)
    tail, full = join_sectors(sectors, prefix)
    return (
        tail,
        full,
        {
            "pair_verified": True,
            "independent_oracle": False,
            "new_verified_range": [0x2E00, 0x3000],
            "new_verified_bytes": len(tail),
            "tail_sha256": W.S.audit.sha(tail),
            "partition": "fw1_boot",
            "partition_range": [0x2000, 0x3000],
            "partition_bytes": len(full),
            "partition_sha256": W.S.audit.sha(full),
            "connections": 1,
            "independent_producer_executions": 2,
        },
    )


def replay(directory: Path, image: Path) -> dict:
    report = json.loads((directory / "report.json").read_bytes())
    if report.get("ok") is not True or "ended_at" not in report:
        raise ValueError("Archived job requires original success and original end timestamp")
    tail, full, result = audit_job(report, directory, image)
    if report["verification"] != result:
        raise ValueError("Saved aggregate verification changed")
    for name, data in (("tail.bin", tail), ("fw1_boot.bin", full)):
        ref = report["outputs"][name]
        if ref["file"] != name or W.J.check_reference(directory, ref).read_bytes() != data:
            raise ValueError("Actual aggregate output differs from independently replayed sectors")
    return result


def main(
    image: Path, failed_job: Path, control_parent: Path, newout: Path, sudo_password_stdin: bool = False
):
    plan, reports = prepare(image, failed_job, control_parent)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    W.S.save(newout / "job-plan.json", plan)
    for slot in plan["slots"]:
        for name in ("first", "second"):
            (newout / slot["directory"] / name).mkdir(parents=True, mode=0o700)
    job = {
        "profile": PROFILE,
        "started_at": W.S.now(),
        "plan": W.J.reference(newout, newout / "job-plan.json"),
        "completed": [],
        "ok": False,
    }
    try:
        fixed.plan_gate(job, plan, reports, newout)
        admission(plan, image)
        W.authorize(password_stdin=sudo_password_stdin)
        fixed.acquire_slots(
            job, plan, reports, newout, image, run_pair=W.run_pair, before_pair=lambda: admission(plan, image)
        )
        job["ended_at"] = W.S.now()
        tail, full, job["verification"] = audit_job(job, newout, image)
        job["outputs"] = {}
        for name, data in (("tail.bin", tail), ("fw1_boot.bin", full)):
            with (newout / name).open("xb") as handle:
                handle.write(data)
            job["outputs"][name] = W.J.reference(newout, newout / name)
        job["ok"] = True
    except BaseException as error:
        job["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        job["ended_at"] = W.S.now()
        W.S.save(newout / "report.json", job)
    print(json.dumps({"ok": True, "new_verified_bytes": len(tail), "partition_bytes": len(full)}))


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
