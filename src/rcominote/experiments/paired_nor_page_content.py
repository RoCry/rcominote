"""Original v3 second-transfer communication; rejected NOR content stays rejected."""

import copy
import json
from datetime import datetime
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_checkpoint as K
from rcominote.experiments import paired_nor_plan as C

ROLE = K.PAGE_CONTENT_ROLE
SOURCE_MANIFEST_SHA = "9af7580903246d32070e9e59933b126b79cb72c335216ecf9a365d6563e7ff24"
CAPTURE_CODE = K.STATUS_CAPTURE_CODE.copy()


def verify(failed: Path, source: dict, baseline: bytes) -> tuple[bytes, dict, dict]:
    job = json.loads((failed / "report.json").read_bytes())
    plan = json.loads(C.J.check_reference(failed, job["plan"]).read_bytes())
    if (
        job.get("profile") != C.PROFILE_V3
        or plan.get("profile") != C.PROFILE_V3
        or plan.get("parent") != source
        or job.get("ok") is not False
        or job.get("error") != K.CONTENT_ERROR
        or job["plan"]["file"] != "plan.json"
        or "verification" in job
    ):
        raise ValueError("Requires original v3 second-content failure with exact admitted ancestor")
    job_view = copy.deepcopy(job)
    del job_view["error"]
    A.common.no_errors(job_view)
    C.pins.pinned(failed / "source-snapshot/manifest.json", SOURCE_MANIFEST_SHA)
    snapshot = K.snapshot(failed, code=CAPTURE_CODE)
    manifest = json.loads((failed / "source-snapshot/manifest.json").read_bytes())
    C.J.time_order(manifest["created_at"], job["started_at"])
    # Independently accepted prefix stays separate from this zero-coverage node.
    proofs, previous, state = A.completed_prefix(job, plan, failed, baseline)
    index = len(job["completed"])
    if index >= len(plan["pages"]):
        raise ValueError("Failed second transfer must immediately follow the accepted prefix")
    slot = plan["pages"][index]
    directory = failed / slot["directory"]
    report = json.loads((directory / "report.json").read_bytes())
    warm, first, second = report["baseline"], *report["operations"]
    if (
        report.get("ok") is not False
        or report.get("error") != K.CONTENT_ERROR
        or report.get("capture_error") != K.CONTENT_ERROR
        or report.get("plan") != job["plan"]
        or "verification" in report
        or any(
            stage.get("ok") is not True or stage.get("live_complete") is not True for stage in (warm, first)
        )
        or second.get("ok") is not False
        or second.get("live_complete") is not False
        or second.get("error") != K.CONTENT_ERROR
        or second.get("barrier_complete") is not True
        or any(key in second for key in ("verification", "oracle_verification"))
        or (directory / "second/sector.bin").exists()
        or warm.get("operation_id") != "baseline"
        or warm.get("name") != C.F.NAME
        or any(key in warm for key in ("actions_start", "producer", "sd_write_attempted"))
    ):
        raise ValueError("Requires complete baseline/first and failed second content after its real barrier")
    for later in plan["pages"][index + 1 :]:
        if any(path.is_file() for path in (failed / later["directory"]).rglob("*")):
            raise ValueError("Later page has artifacts after the original second-content failure")
    ended = job["completed"][-1]["ended_at"] if index else source["ended_at"]
    page = C.page_plan(plan, index, state, ended)
    C.J.time_order(source["ended_at"], plan["planned_at"], job["started_at"])
    C.J.time_order(job["started_at"], report["started_at"], report["ended_at"], job["ended_at"])
    C.J.time_order(ended, report["started_at"])
    for stage in (warm, first, second):
        C.J.time_order(report["started_at"], stage["started_at"], stage["ended_at"], report["ended_at"])
        if (
            datetime.fromisoformat(stage["ended_at"]) - datetime.fromisoformat(stage["started_at"])
        ).total_seconds() > 18:
            raise ValueError("Original completed communication stage exceeds18 seconds")
    view = copy.deepcopy(report)
    # Remove only the three exact recorded exceptions, preserving all false flags.
    del view["error"], view["capture_error"], view["operations"][1]["error"]
    transfers, events = A.communication(view, directory, page, previous, operation_count=2)
    decoded = C.payload(first, transfers[0], previous)
    if decoded != first["verification"] or (directory / "first/sector.bin").read_bytes() != bytes.fromhex(
        decoded["sector_hex"]
    ):
        raise ValueError("Originally complete first observation differs from its own retained bytes")
    try:
        C.payload(second, transfers[1], transfers[0])  # Original v3 only; no later policy or oracle.
    except ValueError as error:
        if f"ValueError: {error}" != K.CONTENT_ERROR:
            raise ValueError("Original second-content failure does not replay exactly") from error
    else:
        raise ValueError("Rejected original second content unexpectedly passed; no relabeling")
    result = {
        "directory": str(failed.resolve()),
        "references": {
            "failed_report": C.J.reference(failed, failed / "report.json"),
            "failed_plan": job["plan"],
            "failed_page": C.J.reference(failed, directory / "report.json"),
            "capture": C.J.reference(failed, directory / "session.btsnoop"),
            "baseline": C.J.reference(failed, directory / "baseline/download.bin"),
            "current_file": C.J.reference(failed, directory / "second/download.bin"),
            "completed_prefix": job["completed"],
            "source_snapshot": snapshot,
        },
        "observed_ended_at": job["ended_at"],
        "latest_info": report["after"],
        "current_ring_sha256": A.A.sha(transfers[1]),
        "prior_names": sorted(set(source["prior_names"]) | set(C.nonces(plan))),
        "original_capture_profile": plan["profile"],
        "original_completed_prefix": proofs,
        "communication": {
            "complete": True,
            "parameter_transactions": 9,
            "downloads": 3,
            "att_packets": len(report["att_packets"]),
            "hci_capture": report["hci_capture"],
            "status_events": events,
            "content_error_reproduced": K.CONTENT_ERROR,
            "failed_content_accepted": False,
            "new_raw_nor_coverage_bytes": 0,
        },
    }
    return transfers[1], report["after"], result
