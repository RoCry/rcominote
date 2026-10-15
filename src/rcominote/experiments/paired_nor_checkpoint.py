"""Offline adoption of complete failed-page communication, never its NOR content.

No live capture, Actions, SD write or content promotion occurs here. A future
producer must first download and byte-compare this actual4096 current object.
"""

import copy
import json
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C

PROFILE = C.CHECKPOINT_PROFILE
CONTENT_PROFILE = C.CONTENT_CHECKPOINT_PROFILE
PAGE_CONTENT_ROLE = "complete-page-second-transfer-content-proof-only"
PREFILL_CONTENT_ROLE = "complete-prefill-first-nor-content-proof-only"
PREFILL_CAPTURE_PROFILE = "verified-ram-prefill-strict-known-nor-control-v1"
CAPTURE_ROLES = {C.PROFILE_V3: PAGE_CONTENT_ROLE, PREFILL_CAPTURE_PROFILE: PREFILL_CONTENT_ROLE}
CONTENT_ERROR = "ValueError: Current chain depends on tail outside difference-proven written prefix"
STRICT_CAPTURE_CODE = {
    "paired_nor_audit.py": "917eba0f883fa210d8a695ba5f09cff400ad00561e80dab60ad8cc3bc621600e",
    "paired_nor_plan.py": "14aa4e6fbe2ebf8a9ea8bc9ef5edd2de65020bde408e591719dddeebae7f9fa9",
    "paired_nor_runtime.py": "f7ce20ab8c06fa46b6125726a5ac06057de4862c3b37582e0db8b83028cc5c72",
    "scratch_reuse_parser.py": "3f8bf86e95b73bc70b1cb068a41e735eb621ac42a247cac3768fdc6163d16bbc",
}


def snapshot(failed, *, code=None):
    path = failed / "source-snapshot/manifest.json"
    manifest = json.loads(path.read_bytes())
    entries = [*manifest["source_files"], *manifest["test_files"]]
    if len({entry["path"] for entry in entries}) != len(entries):
        raise ValueError("Original source snapshot contains duplicate paths")
    for entry in entries:
        target = path.parent / entry["path"]
        if not target.resolve().is_relative_to(path.parent.resolve()):
            raise ValueError("Original source snapshot escapes its frozen directory")
        expected = {"file": entry["path"], "bytes": entry["bytes"], "sha256": entry["sha256"]}
        C.J.check_reference(path.parent, expected)
    by_name = {entry["path"]: entry["sha256"] for entry in manifest["source_files"]}
    if any(
        by_name.get(f"src/rcominote/experiments/{name}") != sha
        for name, sha in (STRICT_CAPTURE_CODE if code is None else code).items()
    ):
        raise ValueError("Failed capture must retain its original strict-v2 audit/parser source")
    return {"manifest": C.J.reference(failed, path), "files": len(entries)}


def header(checkpoint):
    if checkpoint.get("profile") == CONTENT_PROFILE:
        if (
            checkpoint.get("failure_role")
            not in ("complete-second-transfer-content-proof-only", *CAPTURE_ROLES.values())
            or (
                checkpoint.get("failure_role") in CAPTURE_ROLES.values()
                and CAPTURE_ROLES.get(checkpoint.get("original_capture_profile"))
                != checkpoint["failure_role"]
            )
            or checkpoint.get("communication_verified") is not True
            or checkpoint.get("live_capture_performed") is not False
            or checkpoint.get("original_job_ok") is not False
            or checkpoint.get("original_operation_ok") is not False
            or any(k in checkpoint for k in ("original_page_ok", "original_first_ok"))
            or type(checkpoint.get("new_raw_nor_coverage_bytes")) is not int
            or checkpoint["new_raw_nor_coverage_bytes"] != 0
            or "ok" in checkpoint
        ):
            raise ValueError("Requires distinct zero-coverage complete-content-failure communication role")
        C.J.time_order(checkpoint["observed_ended_at"], checkpoint["created_at"])
        return
    if (
        checkpoint.get("profile") != PROFILE
        or checkpoint.get("communication_verified") is not True
        or checkpoint.get("live_capture_performed") is not False
        or checkpoint.get("original_job_ok") is not False
        or checkpoint.get("original_page_ok") is not False
        or checkpoint.get("original_first_ok") is not False
        or type(checkpoint.get("new_raw_nor_coverage_bytes")) is not int
        or checkpoint["new_raw_nor_coverage_bytes"] != 0
        or "ok" in checkpoint
        or any(k in checkpoint for k in ("failure_role", "original_operation_ok"))
    ):
        raise ValueError("Requires distinct offline zero-coverage failed-communication checkpoint")
    C.J.time_order(checkpoint["observed_ended_at"], checkpoint["created_at"])


def failed_communication(failed, source, baseline):
    job = json.loads((failed / "report.json").read_bytes())
    if job.get("profile") == PREFILL_CAPTURE_PROFILE:
        from rcominote.experiments.prefilled_nor_checkpoint import verify

        return verify(failed, source, baseline)
    if job.get("profile") == C.PROFILE_V3:
        from rcominote.experiments.paired_nor_page_content import verify

        return verify(failed, source, baseline)
    if job.get("profile") in (C.CONTINUOUS_CONTROL, C.STATUS_CONTROL):
        return control_content_communication(failed, source, baseline)
    plan = json.loads(C.J.check_reference(failed, job["plan"]).read_bytes())
    if job.get("ok") is not False or job.get("error") != CONTENT_ERROR or plan["parent"] != source:
        raise ValueError("Only original failed content-stage job with exact admitted parent permitted")
    if plan["profile"] != C.PROFILE:
        raise ValueError("Communication checkpoint currently requires original strict-v2 capture")
    job_view = copy.deepcopy(job)
    del job_view["error"]
    A.common.no_errors(job_view)
    frozen_source = snapshot(failed)
    manifest = json.loads((failed / "source-snapshot/manifest.json").read_bytes())
    C.J.time_order(manifest["created_at"], job["started_at"])
    proofs, previous, state = A.completed_prefix(job, plan, failed, baseline)
    index = len(job["completed"])
    if index >= len(plan["pages"]):
        raise ValueError("Failed page must immediately follow independently complete prefix")
    slot = plan["pages"][index]
    directory = failed / slot["directory"]
    page = json.loads((directory / "report.json").read_bytes())
    warm, first, second = page["baseline"], *page["operations"]
    if (
        page.get("ok") is not False
        or page.get("error") != CONTENT_ERROR
        or page.get("capture_error") != CONTENT_ERROR
        or page.get("plan") != job["plan"]
        or warm.get("ok") is not True
        or warm.get("live_complete") is not True
        or first.get("ok") is not False
        or first.get("live_complete") is not False
        or first.get("error") != CONTENT_ERROR
        or first.get("barrier_complete") is not True
        or "verification" in first
        or (directory / "first/sector.bin").exists()
        or second != slot["operations"][1] | {"live_complete": False, "ok": False}
        or any((directory / "second").iterdir())
    ):
        raise ValueError("Failure must occur only in first content proof after complete barrier")
    for later in plan["pages"][index + 1 :]:
        if any(path.is_file() for path in (failed / later["directory"]).rglob("*")):
            raise ValueError("Later page performed I/O after first failure")
    ended = job["completed"][-1]["ended_at"] if index else source["ended_at"]
    page_plan = C.page_plan(plan, index, state, ended)
    C.J.time_order(job["started_at"], page["started_at"], page["ended_at"], job["ended_at"])
    # Only the exact recorded content exception is removed in this local view.
    # Original flags remain false; every other error and original byte is audited.
    communication_view = copy.deepcopy(page)
    del communication_view["error"]
    del communication_view["capture_error"]
    del communication_view["operations"][0]["error"]
    transfers, events = A.communication(communication_view, directory, page_plan, previous, operation_count=1)
    current = transfers[0]
    try:
        C.payload(first, current, previous)  # Reproduce ORIGINAL policy failure; no new-policy promotion.
    except ValueError as error:
        if f"ValueError: {error}" != CONTENT_ERROR:
            raise ValueError("Original content failure classification does not replay exactly") from error
    else:
        raise ValueError("Original failed content unexpectedly passed; cannot adopt by relabeling")
    references = {
        "failed_report": C.J.reference(failed, failed / "report.json"),
        "failed_plan": job["plan"],
        "failed_page": C.J.reference(failed, directory / "report.json"),
        "capture": C.J.reference(failed, directory / "session.btsnoop"),
        "baseline": C.J.reference(failed, directory / "baseline/download.bin"),
        "current_file": C.J.reference(failed, directory / "first/download.bin"),
        "completed_prefix": job["completed"],
        "source_snapshot": frozen_source,
    }
    result = {
        "directory": str(failed.resolve()),
        "references": references,
        "observed_ended_at": job["ended_at"],
        "latest_info": page["after"],
        "current_ring_sha256": A.A.sha(current),
        "prior_names": sorted(set(C.nonces(plan)) | set(source["prior_names"])),
        "original_completed_prefix": proofs,
        "communication": {
            "complete": True,
            "parameter_transactions": 6,
            "downloads": 2,
            "att_packets": len(page["att_packets"]),
            "hci_capture": page["hci_capture"],
            "status_events": events,
            "content_error_reproduced": CONTENT_ERROR,
            "failed_content_accepted": False,
            "new_raw_nor_coverage_bytes": 0,
        },
    }
    return current, page["after"], result


def verify_admitted(checkpoint, directory, source, baseline):
    header(checkpoint)
    if checkpoint["parent"] != source:
        raise ValueError("Checkpoint successful ancestor differs from admitted source")
    failed = Path(checkpoint["failed"]["directory"])
    original_profile = json.loads((failed / "report.json").read_bytes())["profile"]
    expected_profile = (
        CONTENT_PROFILE
        if original_profile in (C.CONTINUOUS_CONTROL, C.STATUS_CONTROL, *CAPTURE_ROLES)
        else PROFILE
    )
    if checkpoint["profile"] != expected_profile:
        raise ValueError("Checkpoint role differs from original failed communication profile")
    if original_profile in CAPTURE_ROLES:
        if (
            checkpoint.get("original_capture_profile") != original_profile
            or checkpoint.get("failure_role") != CAPTURE_ROLES[original_profile]
        ):
            raise ValueError("Checkpoint role differs from original complete content-failure capture")
    elif checkpoint.get("failure_role") in CAPTURE_ROLES.values():
        raise ValueError("Content checkpoint cannot adopt another original capture profile")
    elif original_profile == C.STATUS_CONTROL:
        if checkpoint.get("original_capture_profile") != original_profile:
            raise ValueError("Checkpoint underlying frozen STATUS capture profile differs")
    elif "original_capture_profile" in checkpoint:
        raise ValueError("Legacy checkpoint must retain its original capture role")
    current, state, result = failed_communication(failed, source, baseline)
    if result != checkpoint["failed"] or checkpoint["observed_ended_at"] != result["observed_ended_at"]:
        raise ValueError("Offline checkpoint original communication source changed")
    if (
        checkpoint["baseline"]["file"] != "baseline.bin"
        or C.J.check_reference(directory, checkpoint["baseline"]).read_bytes() != current
    ):
        raise ValueError("Checkpoint current object is not exact original complete download")
    summary = {
        "directory": str(directory.resolve()),
        "profile": checkpoint["profile"],
        "ended_at": checkpoint["observed_ended_at"],
        "created_at": checkpoint["created_at"],
        "latest_info": state,
        "baseline_sha256": A.A.sha(current),
        "prior_names": result["prior_names"],
        "references": {
            "checkpoint": C.J.reference(directory, directory / "checkpoint.json"),
            "baseline": checkpoint["baseline"],
        },
        "verification": result["communication"],
        "original_failed_retained": True,
        "current_object_live_download_required_before_overwrite": True,
    }
    return current, state, summary


def create(image: Path, failed: Path, newout: Path):
    from rcominote.experiments.paired_nor_runtime import private_output

    private_output(newout)
    original = json.loads((failed / "report.json").read_bytes())
    plan = json.loads(C.J.check_reference(failed, original["plan"]).read_bytes())
    baseline, _state, source = C.parent_gate(Path(plan["parent"]["directory"]), image)
    current, _state, result = failed_communication(failed, source, baseline)
    checkpoint = {
        "profile": PROFILE,
        "created_at": C.S.now(),
        "observed_ended_at": result["observed_ended_at"],
        "parent": source,
        "failed": result,
        "communication_verified": True,
        "live_capture_performed": False,
        "original_job_ok": False,
        "original_page_ok": False,
        "original_first_ok": False,
        "new_raw_nor_coverage_bytes": 0,
    }
    if plan["profile"] in (C.CONTINUOUS_CONTROL, C.STATUS_CONTROL, *CAPTURE_ROLES):
        checkpoint.update(
            profile=CONTENT_PROFILE,
            failure_role=CAPTURE_ROLES.get(plan["profile"], "complete-second-transfer-content-proof-only"),
            original_operation_ok=False,
        )
        del checkpoint["original_page_ok"], checkpoint["original_first_ok"]
        if plan["profile"] in (C.STATUS_CONTROL, *CAPTURE_ROLES):
            checkpoint["original_capture_profile"] = plan["profile"]
    header(checkpoint)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    (newout / "baseline.bin").write_bytes(current)
    checkpoint["baseline"] = C.J.reference(newout, newout / "baseline.bin")
    C.S.save(newout / "checkpoint.json", checkpoint)
    return verify_admitted(checkpoint, newout, source, baseline)


CONTROL_CAPTURE_CODE = {
    "paired_nor_plan.py": "e8ba6ceb31ecf937e2e72537fdf3fce86c27040303c7efda8ea543b6e2d440ba",
    "paired_nor_audit.py": "f8a54a789330cdac4ee4bbc244031ebc9756c71fcb2cfd83e6db2c29175a4472",
    "paired_nor_runtime.py": "3919be6dc3205ac3374c672f3cfa317fcf346b6d296457b13497d25c77352aa6",
    "scratch_reuse_parser.py": "471c517b5ad6e62cd3698a7018a47befec2f51e6b62607b05b62670a05c7915f",
}


STATUS_CAPTURE_CODE = {
    "paired_nor_plan.py": "25a00bfd0daa5a6bfa98495d997eef5afa8b864df9d17d10d86dd1e9a1aff712",
    "paired_nor_audit.py": "2954cbcbb45cd46cd2f284b920de8095daac585ec77f0c2171b5038b2bab89e6",
    "paired_nor_runtime.py": "86d2b0b6cd66b2f66395cfea6e2141f43c230480ae4f21c297bec46529b8da59",
    "paired_nor_recipe.py": "2bfdf1b29e27ab594665b85b3b7478d224d8e5c309c0b45072e758d4dcd0cba1",
    "scratch_reuse_parser.py": "821b1c7395ecc3fe1a6c4a8dbb6e2d5ab3b819c10346281540a6a7b6faac98a4",
}


def control_content_communication(failed, source, baseline):
    """Admit full original communication, preserving rejected second content."""
    report = json.loads((failed / "report.json").read_bytes())
    plan = json.loads(C.J.check_reference(failed, report["plan"]).read_bytes())
    C.validate_plan(plan)
    if (
        plan["profile"] not in (C.CONTINUOUS_CONTROL, C.STATUS_CONTROL)
        or plan["parent"] != source
        or report.get("ok") is not False
        or report.get("error") != CONTENT_ERROR
        or report.get("capture_error") != CONTENT_ERROR
        or "verification" in report
        or report["plan"]["file"] != "plan.json"
        or any(report.get(k) != plan[k] for k in C.CONTROL_FIELDS)
        or len(report["groups"]) != 2
    ):
        raise ValueError(
            "Requires original continuous control content failure with exact successful ancestor"
        )
    group, later = report["groups"]
    warm, first, second = group["baseline"], *group["operations"]
    if (
        group.get("candidate") is not False
        or group.get("live_complete") is not False
        or group.get("group_index") != 0
        or group.get("nor_offset") != 0
        or any(key in group for key in ("ok", "disconnect", "disconnect_observation"))
        or any(
            stage.get("ok") is not True or stage.get("live_complete") is not True for stage in (warm, first)
        )
        or second.get("ok") is not False
        or second.get("live_complete") is not False
        or second.get("error") != CONTENT_ERROR
        or second.get("barrier_complete") is not True
        or "verification" in second
        or "oracle_verification" in second
        or (failed / plan["pages"][0]["directory"] / "second/sector.bin").exists()
        or later != C.control_report(plan)["groups"][1]
        or any(p.is_file() for p in (failed / plan["pages"][1]["directory"]).rglob("*"))
        or warm.get("operation_id") != "baseline"
        or warm.get("name") != C.F.NAME
        or any(k in warm for k in ("actions_start", "producer", "sd_write_attempted"))
    ):
        raise ValueError("Only second content failure after full barrier; later group must remain untouched")
    view = copy.deepcopy(report)
    del view["error"], view["capture_error"], view["groups"][0]["operations"][1]["error"]
    A.common.no_errors(view)
    frozen_source = snapshot(
        failed, code=STATUS_CAPTURE_CODE if plan["profile"] == C.STATUS_CONTROL else CONTROL_CAPTURE_CODE
    )
    C.J.time_order(
        json.loads((failed / "source-snapshot/manifest.json").read_bytes())["created_at"],
        report["started_at"],
    )
    C.J.time_order(source["ended_at"], plan["planned_at"], report["started_at"], report["ended_at"])
    for stage in (warm, first, second):
        C.J.time_order(report["started_at"], stage["started_at"], stage["ended_at"], report["ended_at"])
        if (
            A.datetime.fromisoformat(stage["ended_at"]) - A.datetime.fromisoformat(stage["started_at"])
        ).total_seconds() > 18:
            raise ValueError("Original completed communication stage exceeds18 seconds")
    observed, wire, events = A.envelope(report, failed, 9)
    if report["predecessor_state_verification"] != A.verify_state(
        plan["expected_before"], report["before"], sd_write=False
    ):
        raise ValueError("Original initial state differs from successful ancestor")
    A.E.bridge(report, report["before_span"][1], report["file_list_span"][0])
    if A.inventory(report, plan) != report["listed_count"]:
        raise ValueError("Original visible inventory changed")
    startup = observed["transactions"][0]
    if report["startup_settlement"] != startup or report["startup_classification"] != C.startup.classify(
        startup
    ):
        raise ValueError("Original startup is not strict FAST")
    context = {
        "state": report["before"],
        "boundary": report["file_list_span"][1],
        "previous_tx": startup,
        "cursor": 1,
        "previous": baseline,
    }
    page = C.page_plan(plan, 0, source["latest_info"], source["ended_at"])
    directory = failed / plan["pages"][0]["directory"]
    transfers, context = A.transfer_group(report, group, page, directory, observed, wire, context)
    A.final_identity(report, wire, context, 9)
    original_first = C.payload(first, transfers[0], baseline)
    sector = bytes.fromhex(original_first["sector_hex"])
    if (
        original_first != first["verification"]
        or A.oracle_proof(plan, 0, sector) != first["oracle_verification"]
        or (directory / "first/sector.bin").read_bytes() != sector
    ):
        raise ValueError("Originally complete first observation changed")
    try:
        C.payload(
            second, transfers[1], transfers[0]
        )  # ORIGINAL captured policy; never substitute a later formatter policy.
    except ValueError as error:
        if f"ValueError: {error}" != CONTENT_ERROR:
            raise ValueError("Original content failure does not replay exactly") from error
    else:
        raise ValueError("Rejected original content unexpectedly passed; no relabeling")
    result = {
        "directory": str(failed.resolve()),
        "references": {
            "failed_report": C.J.reference(failed, failed / "report.json"),
            "failed_plan": report["plan"],
            "capture": C.J.reference(failed, failed / "session.btsnoop"),
            "current_file": C.J.reference(failed, directory / "second/download.bin"),
            "source_snapshot": frozen_source,
        },
        "observed_ended_at": report["ended_at"],
        "latest_info": report["after"],
        "current_ring_sha256": A.A.sha(transfers[1]),
        "prior_names": sorted(set(source["prior_names"]) | set(C.nonces(plan))),
        "communication": {
            "complete": True,
            "parameter_transactions": 9,
            "downloads": 3,
            "att_packets": len(report["att_packets"]),
            "hci_capture": report["hci_capture"],
            "status_events": events,
            "content_error_reproduced": CONTENT_ERROR,
            "failed_content_accepted": False,
            "new_raw_nor_coverage_bytes": 0,
        },
    }
    if plan["profile"] == C.STATUS_CONTROL:
        result["original_capture_profile"] = plan["profile"]
    return transfers[1], report["after"], result
