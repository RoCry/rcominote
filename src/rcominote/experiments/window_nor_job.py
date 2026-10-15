"""Five remaining fw1_boot sectors; immutable ten-nonce plan, no retry/resume.

Every scheduled pair needs its complete original window audit before advancing.
Assembly uses actual independently checked sectors, never FF filling or partials.
"""

import asyncio
import json
import re
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import boot_prefix_evidence as prefix_source
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import dual_unknown_pair as U
from rcominote.experiments import window_nor_contract as C
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments.hci_interval_io import authorize
from rcominote.experiments.sd_bootstrap import verify_state

PROFILE = "fixed-fw1-boot-tail-window-job"
OFFSETS = C.OFFSETS[1:]
PROGRESS_SHA = "7b0b2e8366df265499be45eae8061db7fe98609447089d49073eba129f47e852"
PROGRESS_HCI_SHA = "8b97473dc252637a5d63715791e0ab20a91dd2fba24361740c2b22c785fdb214"


def coverage_basis() -> dict:
    return {
        "acpt_early_basis": C.C.coverage_basis(),
        "verified_prefix": [0x2000, 0x2600],
        "remaining_range": [0x2600, 0x3000],
        "remaining_bytes": 2560,
        "progress_report_sha256": PROGRESS_SHA,
    }


def progress_gate(directory: Path, image: Path) -> tuple[dict, dict]:
    raw = (directory / "report.json").read_bytes()
    capture = (directory / "session.btsnoop").read_bytes()
    if S.audit.sha(raw) != PROGRESS_SHA or S.audit.sha(capture) != PROGRESS_HCI_SHA:
        raise ValueError("Requires exact successful raw0x2400 window progress parent")
    original = json.loads(raw)
    J.require_success(original)
    result = N.replay(directory, image)
    if result["nor_range"] != [0x2400, 0x2600] or result["bytes"] != 512:
        raise ValueError("Progress parent must prove exactly raw0x2400..0x2600")
    return {
        "directory": str(directory.resolve()),
        "report_sha256": PROGRESS_SHA,
        "hci_sha256": PROGRESS_HCI_SHA,
        "verification": result,
    }, original


def parent_names(original: dict) -> set[str]:
    names = {op["name"] for op in original["operations"]}
    for key in ("parent", "window_parent"):
        parent = json.loads((Path(original[key]["directory"]) / "report.json").read_bytes())
        names.update(op["name"] for op in parent["operations"])
    return names


def validate_plan(plan: dict) -> None:
    J.time_order(plan["planned_at"])
    progress = plan.get("progress_parent", {})
    if (
        plan.get("profile") != PROFILE
        or plan.get("serial") != OWNED_SERIAL
        or plan.get("source_image_sha256") != U.probe.IMAGE_SHA
        or plan.get("coverage_basis") != coverage_basis()
        or plan.get("new_range") != [0x2600, 0x3000]
        or any(
            type(plan.get(k)) is not int or plan[k] != v
            for k, v in (("max_connections", 5), ("max_producer_executions", 10), ("max_sd_test_files", 10))
        )
        or progress.get("report_sha256") != PROGRESS_SHA
        or progress.get("hci_sha256") != PROGRESS_HCI_SHA
        or not isinstance(plan.get("prefix_evidence"), dict)
        or plan["prefix_evidence"].get("sha256") != prefix_source.PREFIX_SHA
        or plan["prefix_evidence"].get("nor_range") != [0x2000, 0x2200]
    ):
        raise ValueError("Job differs from fixed five-sector window plan or progress pins")
    C._pin(plan.get("parent"), C.C.PARENT_SHA, C.C.PARENT_HCI_SHA)
    C._pin(plan.get("window_parent"), C.WINDOW_PARENT_SHA, C.WINDOW_HCI_SHA)
    slots = plan["slots"]
    if (
        len(slots) != 5
        or any(type(s["nor_offset"]) is not int for s in slots)
        or [slot["nor_offset"] for slot in slots] != list(OFFSETS)
    ):
        raise ValueError("Requires each remaining fixed sector once, without gaps or overlap")
    names = []
    for offset, slot in zip(OFFSETS, slots, strict=True):
        if (
            slot["directory"] != f"{offset:04x}"
            or not isinstance(slot["names"], list)
            or len(slot["names"]) != 2
        ):
            raise ValueError("Fixed slot path/names changed")
        if any(
            not isinstance(name, str) or re.fullmatch(r"rc[0-9a-f]{10}", name) is None
            for name in slot["names"]
        ):
            raise ValueError("Invalid planned scratch nonce")
        names.extend(slot["names"])
    if len(set(names)) != 10:
        raise ValueError("All ten pre-I/O scratch nonces must differ; no regeneration")


def prepare(image: Path, successful2400parent: Path) -> tuple[dict, list[dict]]:
    progress, original = progress_gate(successful2400parent, image)
    _, prefix_proof = prefix_source.verify()
    reports = [
        C.prepare(
            image, Path(original["parent"]["directory"]), Path(original["window_parent"]["directory"]), offset
        )
        for offset in OFFSETS
    ]
    if any(report[key] != original[key] for report in reports for key in ("parent", "window_parent")):
        raise ValueError("Preparations disagree with actual successful progress parent chains")
    plan = {
        "profile": PROFILE,
        "serial": OWNED_SERIAL,
        "planned_at": S.now(),
        "source_image_sha256": U.probe.IMAGE_SHA,
        "progress_parent": progress,
        "parent": original["parent"],
        "window_parent": original["window_parent"],
        "coverage_basis": coverage_basis(),
        "prefix_evidence": prefix_proof,
        "new_range": [0x2600, 0x3000],
        "max_connections": 5,
        "max_producer_executions": 10,
        "max_sd_test_files": 10,
        "policy": "One pair per remaining fixed sector; first failure stops, no retry/resume",
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
    J.time_order(original["ended_at"], plan["planned_at"])
    if parent_names(original) & {name for slot in plan["slots"] for name in slot["names"]}:
        raise ValueError("Planned scratch nonce collides with a proven parent; no regeneration")
    return plan, reports


def run_pair(report: dict, directory: Path, image: Path) -> None:
    report["prepared_at"], report["started_at"] = report["started_at"], S.now()
    report["final_audit_complete"] = False
    try:
        C.recipe(report)
        asyncio.run(N.capture(report, directory, image))
        report["pair_verification"] = U.compare_pair(report, directory, validate=C.recipe, parse=C.payload)
        report["pair_verified"] = report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(directory / "report.json", report)


def join_sectors(
    sectors: list[tuple[int, bytes]], prefix: bytes, block2200: bytes, block2400: bytes
) -> tuple[bytes, bytes]:
    if [offset for offset, _ in sectors] != list(OFFSETS) or any(len(data) != 512 for _, data in sectors):
        raise ValueError("Assembly requires five complete ordered sectors; no gaps/overlap/filling")
    if any(len(data) != 512 for data in (prefix, block2200, block2400)):
        raise ValueError("Assembly requires all three actual previously verified prefix sectors")
    tail = b"".join(data for _, data in sectors)
    full = prefix + block2200 + block2400 + tail
    if len(tail) != 2560 or len(full) != 4096:
        raise ValueError("Fixed fw1_boot assembly length changed")
    return tail, full


def audit_job(report: dict, directory: Path, image: Path) -> tuple[bytes, bytes, dict]:
    if report.get("profile") != PROFILE or any(
        value for key, value in report.items() if key.endswith("error")
    ):
        raise ValueError("Failed/unrelated job cannot assemble a partition")
    if report["plan"]["file"] != "job-plan.json":
        raise ValueError("Unexpected immutable plan path")
    plan = json.loads(J.check_reference(directory, report["plan"]).read_bytes())
    validate_plan(plan)
    prefix, prefix_proof = prefix_source.verify()
    if prefix_proof != plan["prefix_evidence"]:
        raise ValueError("Historical prefix provenance differs from the immutable plan")
    progress, previous = progress_gate(Path(plan["progress_parent"]["directory"]), image)
    if progress != plan["progress_parent"] or any(
        previous[key] != plan[key] for key in ("parent", "window_parent")
    ):
        raise ValueError("Actual progress/early/window parent wrappers differ from immutable plan")
    J.time_order(previous["ended_at"], plan["planned_at"], report["started_at"])
    if parent_names(previous) & {name for slot in plan["slots"] for name in slot["names"]}:
        raise ValueError("Plan reused a proven parent scratch nonce")
    if len(report["completed"]) != 5:
        raise ValueError("Five independently successful pairs required; no partial assembly")
    sectors = []
    for slot, completed in zip(plan["slots"], report["completed"], strict=True):
        label, offset = slot["directory"], slot["nor_offset"]
        if completed["report"]["file"] != f"{label}/report.json":
            raise ValueError("Completed report path differs from fixed slot")
        original = json.loads(J.check_reference(directory, completed["report"]).read_bytes())
        J.require_success(original)
        if (
            original["nor_offset"] != offset
            or any(original[key] != plan[key] for key in ("parent", "window_parent"))
            or [op["name"] for op in original["operations"]] != slot["names"]
        ):
            raise ValueError("Original pair target, nonce or parent provenance changed")
        J.time_order(report["started_at"], original["started_at"], original["ended_at"])
        J.time_order(previous["ended_at"], original["started_at"])
        state = verify_state(previous["after"], original["before"], sd_write=False)
        if (
            original["expected_before"] != previous["after"]
            or original["predecessor_state_verification"] != state
        ):
            raise ValueError("Pair prestate does not match its actual completed predecessor")
        result = N.replay(directory / label, image)
        if (
            result != completed["verification"]
            or result["nor_range"] != [offset, offset + 512]
            or result["bytes"] != 512
        ):
            raise ValueError("Original fixed-sector complete replay result changed")
        sector = (directory / label / "first/sector.bin").read_bytes()
        if len(sector) != 512 or S.audit.sha(sector) != result["sha256"]:
            raise ValueError("Replayed first sector changed before assembly")
        sectors.append((offset, sector))
        previous = original
    if "ended_at" in report:
        J.time_order(previous["ended_at"], report["ended_at"])
    block2200 = (Path(plan["parent"]["directory"]) / "first/sector.bin").read_bytes()
    block2400 = (Path(progress["directory"]) / "first/sector.bin").read_bytes()
    if (
        S.audit.sha(prefix) != U.unknown.PREFIX_SHA
        or S.audit.sha(block2200) != plan["parent"]["verification"]["sha256"]
        or S.audit.sha(block2400) != progress["verification"]["sha256"]
    ):
        raise ValueError("Previously verified actual prefix bytes changed")
    tail, full = join_sectors(sectors, prefix, block2200, block2400)
    result = {
        "pair_verified": True,
        "independent_oracle": False,
        "new_verified_range": [0x2600, 0x3000],
        "new_verified_bytes": len(tail),
        "tail_sha256": S.audit.sha(tail),
        "partition": "fw1_boot",
        "partition_range": [0x2000, 0x3000],
        "partition_bytes": len(full),
        "partition_sha256": S.audit.sha(full),
        "connections": 5,
        "independent_producer_executions": 10,
    }
    return tail, full, result


def replay(directory: Path, image: Path) -> dict:
    report = json.loads((directory / "report.json").read_bytes())
    if report.get("ok") is not True:
        raise ValueError("Original window job failed; preserve checkpoints without promotion")
    if "ended_at" not in report:
        raise ValueError("Archived successful job requires its original end timestamp")
    J.time_order(report["started_at"], report["ended_at"])
    tail, full, result = audit_job(report, directory, image)
    if report["verification"] != result:
        raise ValueError("Saved aggregate window-job proof changed")
    for name, data in (("tail.bin", tail), ("fw1_boot.bin", full)):
        expected = report["outputs"][name]
        if expected["file"] != name or J.check_reference(directory, expected).read_bytes() != data:
            raise ValueError("Aggregate output differs from its independently replayed sectors")
    return result


def main(image: Path, successful2400parent: Path, newout: Path, sudo_password_stdin: bool = False):
    plan, reports = prepare(image, successful2400parent)
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
    previous = json.loads((successful2400parent / "report.json").read_bytes())
    try:
        authorize(password_stdin=sudo_password_stdin)
        for report, slot in zip(reports, plan["slots"], strict=True):
            report["expected_before"] = previous["after"]
            directory = newout / slot["directory"]
            job["active_slot"] = slot["directory"]
            run_pair(report, directory, image)
            J.require_success(report)
            verified = N.replay(directory, image)
            job["completed"].append(
                {"report": J.reference(newout, directory / "report.json"), "verification": verified}
            )
            previous = report
            S.save(newout / f"checkpoint-{slot['directory']}.json", job)
            print(
                json.dumps({"completed_pairs": len(job["completed"]), "nor_offset": report["nor_offset"]}),
                flush=True,
            )
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
