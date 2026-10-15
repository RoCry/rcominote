"""Six fixed backup-boot sectors, one independent two-read session each; fail stops job."""

import asyncio
import json
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

import typer

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import boot_tail_contract as C
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import dual_unknown_pair as U
from rcominote.experiments.hci_interval_io import authorize
from rcominote.experiments.hci_monitor import Snoop
from rcominote.experiments.sd_bootstrap import verify_state

PROFILE = "fixed-fw1-boot-tail-job"


def time_order(*values: str) -> None:
    stamps = [datetime.fromisoformat(value) for value in values]
    if any(value.tzinfo is None for value in stamps) or any(a > b for a, b in pairwise(stamps)):
        raise ValueError("Acquisition/plan timestamps must be timezone-aware and chronological")


def reference(root: Path, path: Path) -> dict:
    raw = path.read_bytes()
    return {"file": str(path.relative_to(root)), "bytes": len(raw), "sha256": S.audit.sha(raw)}


def check_reference(root: Path, expected: dict) -> Path:
    path = root / expected["file"]
    if reference(root, path) != expected:
        raise ValueError("Original file differs from its retained job reference")
    return path


def require_success(report: dict) -> None:
    if (
        report.get("ok") is not True
        or report.get("pair_verified") is not True
        or report.get("final_audit_complete") is not True
        or any(value for key, value in report.items() if key.endswith("error"))
        or not all(op.get("ok") is True for op in report["operations"])
    ):
        raise ValueError("Original pair failed or is incomplete; never reclassify it")


def compare(report: dict, directory: Path) -> dict:
    return U.compare_pair(report, directory, validate=C.recipe, parse=C.payload)


def pair_replay(directory: Path, image: Path) -> dict:
    report = json.loads((directory / "report.json").read_bytes())
    require_success(report)
    C.recipe(report)
    parent = C.parent_gate(Path(report["parent"]["directory"]), image)
    if parent != report["parent"] or report["source_image_sha256"] != U.probe.IMAGE_SHA:
        raise ValueError("Fixed successful early-parent/image chain changed")
    if report["predecessor_state_verification"] != verify_state(
        report["expected_before"], report["before"], sd_write=False
    ):
        raise ValueError("Pair pre-producer identity/state predecessor gate changed")
    original_parent = json.loads((Path(parent["directory"]) / "report.json").read_bytes())
    time_order(original_parent["ended_at"], report["started_at"], report["ended_at"])
    raw = (directory / "session.btsnoop").read_bytes()
    parser = Snoop()
    parser.feed(raw, final=True)
    if report["hci_capture"] != {"bytes": len(raw), "sha256": S.audit.sha(raw), "records": parser.records}:
        raise ValueError("Complete pair HCI capture changed")
    S.finalize(report, directory, SimpleNamespace(path=directory / "session.btsnoop", snoop=parser))
    result = compare(report, directory)
    if result != report["pair_verification"]:
        raise ValueError("Pair result differs from two fresh complete independent observations")
    return result


def validate_plan(plan: dict) -> None:
    time_order(plan["planned_at"])
    if (
        plan.get("profile") != PROFILE
        or plan.get("serial") != OWNED_SERIAL
        or plan.get("source_image_sha256") != U.probe.IMAGE_SHA
        or plan.get("coverage_basis") != C.coverage_basis()
        or plan.get("max_connections") != 6
        or plan.get("max_producer_executions") != 12
        or plan.get("max_sd_test_files") != 12
    ):
        raise ValueError("Job differs from the exact six-sector backup-boot plan")
    slots = plan["slots"]
    if len(slots) != 6 or [slot["nor_offset"] for slot in slots] != list(C.OFFSETS):
        raise ValueError("Job requires each fixed sector exactly once and in order")
    names = []
    for offset, slot in zip(C.OFFSETS, slots, strict=True):
        if slot["directory"] != f"{offset:04x}" or len(slot["names"]) != 2:
            raise ValueError("Fixed job slot/directory differs")
        names.extend(slot["names"])
    if len(set(names)) != 12:
        raise ValueError("All twelve planned producer/export nonces must differ")


def prepare(image: Path, parent_dir: Path) -> tuple[dict, list[dict]]:
    reports = [C.prepare(image, parent_dir, offset) for offset in C.OFFSETS]
    parent = reports[0]["parent"]
    if any(report["parent"] != parent for report in reports):
        raise ValueError("Fixed job preparations disagree on successful parent evidence")
    plan = {
        "profile": PROFILE,
        "serial": OWNED_SERIAL,
        "planned_at": S.now(),
        "source_image_sha256": U.probe.IMAGE_SHA,
        "parent": parent,
        "coverage_basis": C.coverage_basis(),
        "max_connections": 6,
        "max_producer_executions": 12,
        "max_sd_test_files": 12,
        "policy": "One scheduled pair per fixed offset; first failure stops remaining slots; no retries",
        "slots": [
            {
                "nor_offset": report["nor_offset"],
                "directory": f"{report['nor_offset']:04x}",
                "names": [op["name"] for op in report["operations"]],
            }
            for report in reports
        ],
    }
    validate_plan(plan)
    parent_original = json.loads((parent_dir / "report.json").read_bytes())
    old_names = {op["name"] for op in parent_original["operations"]}
    if old_names & {name for slot in plan["slots"] for name in slot["names"]}:
        raise ValueError("Planned scratch nonce collides with original parent; no regeneration")
    return plan, reports


def run_pair(report: dict, directory: Path) -> None:
    report["prepared_at"] = report["started_at"]
    report["started_at"] = S.now()
    try:
        C.recipe(report)
        asyncio.run(S.capture(report, directory))
        report["pair_verification"] = compare(report, directory)
        report["pair_verified"] = True
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(directory / "report.json", report)


def join_sectors(sectors: list[tuple[int, bytes]], prefix: bytes, block2200: bytes) -> tuple[bytes, bytes]:
    if [offset for offset, _ in sectors] != list(C.OFFSETS) or any(len(data) != 512 for _, data in sectors):
        raise ValueError("Assembly requires exactly six complete ordered sectors, no gaps/overlap")
    if len(prefix) != 512 or len(block2200) != 512:
        raise ValueError("Assembly requires both existing complete prefix sectors")
    tail = b"".join(data for _, data in sectors)
    return tail, prefix + block2200 + tail


def audit_job(report: dict, directory: Path, image: Path) -> tuple[bytes, bytes, dict]:
    if report.get("profile") != PROFILE or any(
        value for key, value in report.items() if key.endswith("error")
    ):
        raise ValueError("Failed or unrelated job cannot assemble a partition")
    if report["plan"]["file"] != "job-plan.json":
        raise ValueError("Unexpected immutable job-plan path")
    plan = json.loads(check_reference(directory, report["plan"]).read_bytes())
    validate_plan(plan)
    parent = C.parent_gate(Path(plan["parent"]["directory"]), image)
    if parent != plan["parent"]:
        raise ValueError("Job parent differs from the pinned complete early session")
    previous = json.loads((Path(parent["directory"]) / "report.json").read_bytes())
    time_order(previous["ended_at"], plan["planned_at"], report["started_at"])
    if len(report["completed"]) != 6:
        raise ValueError("Six independently successful pairs are required; no partial assembly")
    sectors = []
    for slot, completed in zip(plan["slots"], report["completed"], strict=True):
        label, offset = slot["directory"], slot["nor_offset"]
        if completed["report"]["file"] != f"{label}/report.json":
            raise ValueError("Completed pair path differs from its fixed job slot")
        original = json.loads(check_reference(directory, completed["report"]).read_bytes())
        if original["nor_offset"] != offset or original["parent"] != parent:
            raise ValueError("Pair belongs to a different target or parent job")
        if [op["name"] for op in original["operations"]] != slot["names"]:
            raise ValueError("Actual pair nonces differ from the pre-I/O fixed plan")
        time_order(report["started_at"], original["started_at"], original["ended_at"])
        time_order(previous["ended_at"], original["started_at"])
        if original["expected_before"] != previous["after"] or original[
            "predecessor_state_verification"
        ] != verify_state(previous["after"], original["before"], sd_write=False):
            raise ValueError("Actual identity/state continuity across fixed pair sessions changed")
        result = pair_replay(directory / label, image)
        if result != completed["verification"] or result["nor_range"] != [offset, offset + 512]:
            raise ValueError("Completed fixed-sector result changed")
        sectors.append((offset, (directory / label / "first/sector.bin").read_bytes()))
        previous = original
    if "ended_at" in report:
        time_order(previous["ended_at"], report["ended_at"])
    prefix = Path("docs/evidence/boot-recovery-prefixes-2026-10-12/backup-boot.bin").read_bytes()
    block2200 = (Path(parent["directory"]) / "first/sector.bin").read_bytes()
    if (
        S.audit.sha(prefix) != U.unknown.PREFIX_SHA
        or S.audit.sha(block2200) != parent["verification"]["sha256"]
    ):
        raise ValueError("Previously verified prefix bytes changed")
    tail, full = join_sectors(sectors, prefix, block2200)
    result = {
        "pair_verified": True,
        "independent_oracle": False,
        "new_verified_range": [0x2400, 0x3000],
        "new_verified_bytes": len(tail),
        "tail_sha256": S.audit.sha(tail),
        "partition": "fw1_boot",
        "partition_range": [0x2000, 0x3000],
        "partition_bytes": len(full),
        "partition_sha256": S.audit.sha(full),
        "connections": 6,
        "independent_producer_executions": 12,
    }
    return tail, full, result


def replay(directory: Path, image: Path) -> dict:
    report = json.loads((directory / "report.json").read_bytes())
    if report.get("ok") is not True:
        raise ValueError(
            "Original full job did not succeed; preserve completed checkpoints without promotion"
        )
    if "ended_at" not in report:
        raise ValueError("Successful archived job requires its original end timestamp")
    time_order(report["started_at"], report["ended_at"])
    tail, full, result = audit_job(report, directory, image)
    if report["verification"] != result:
        raise ValueError("Saved full job verification changed")
    for label, data in (("tail.bin", tail), ("fw1_boot.bin", full)):
        expected = report["outputs"][label]
        if expected["file"] != label or check_reference(directory, expected).read_bytes() != data:
            raise ValueError("Assembled output differs from separately verified original sectors")
    return result


def main(image: Path, successful_2200_parent: Path, new_out: Path, sudo_password_stdin: bool = False):
    plan, reports = prepare(image, successful_2200_parent)
    new_out.mkdir(parents=True, exist_ok=False, mode=0o700)
    S.save(new_out / "job-plan.json", plan)
    for slot in plan["slots"]:
        for operation_id in ("first", "second"):
            (new_out / slot["directory"] / operation_id).mkdir(parents=True, mode=0o700)
    job = {
        "profile": PROFILE,
        "started_at": S.now(),
        "plan": reference(new_out, new_out / "job-plan.json"),
        "completed": [],
        "ok": False,
    }
    previous = json.loads((successful_2200_parent / "report.json").read_bytes())
    try:
        authorize(password_stdin=sudo_password_stdin)
        for report, slot in zip(reports, plan["slots"], strict=True):
            report["expected_before"] = previous["after"]
            directory = new_out / slot["directory"]
            job["active_slot"] = slot["directory"]
            run_pair(report, directory)
            verified = pair_replay(directory, image)
            job["completed"].append(
                {"report": reference(new_out, directory / "report.json"), "verification": verified}
            )
            previous = report
            S.save(new_out / f"checkpoint-{slot['directory']}.json", job)
            print(
                json.dumps({"completed_pairs": len(job["completed"]), "nor_offset": report["nor_offset"]}),
                flush=True,
            )
        tail, full, job["verification"] = audit_job(job, new_out, image)
        job["outputs"] = {}
        for label, data in (("tail.bin", tail), ("fw1_boot.bin", full)):
            with (new_out / label).open("xb") as handle:
                handle.write(data)
            job["outputs"][label] = reference(new_out, new_out / label)
        job["ok"] = True
    except BaseException as error:
        job["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        job["ended_at"] = S.now()
        S.save(new_out / "report.json", job)
    print(json.dumps({"ok": True, "new_verified_bytes": len(tail), "partition_bytes": len(full)}))


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
