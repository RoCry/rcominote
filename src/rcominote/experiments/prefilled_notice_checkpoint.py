"""Pinned NEXT3 first-NOR content failure: communication-only current ownership.

The original three-gap parser must still reject. No sector is returned, no new
policy is applied, and the whole failed capture never becomes a successful job.
Only the observed owned SD object is adopted, not the current live printk RAM.
"""

import copy
import json
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_checkpoint as K
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_link_checkpoint as times
from rcominote.experiments import prefilled_nor_pages as N

PROFILE = C.PREFILLED_NOTICE_CP
ERROR = "ValueError: Unexpected text after current producer before dump"
PAGE = "page1-1ecc00"
OFFSETS = [0x1ECA00, 0x1ECC00, 0x1ECE00]
MANIFEST_SHA = "32c990c53544e8f2eb33d4681f7cadf5fade6a952e93be68b93859d0df1a1cfd"
SOURCE_COUNTS = (147, 133)
PINS = {
    "report.json": "ebf89fc59e7d675151797e15acf7d5abd3cecdb8efa1ba0994dfdad5c5f45c44",
    "plan.json": "ce57a141d0ab9fe5c4cb2d19479b3c2b385027d56d1031325841e6d528d57685",
    f"{PAGE}/report.json": "db8c3426ad15729b0c4127837d6b955a0c7633e68a3a89bf1e0a8c620a1fec99",
    f"{PAGE}/session.btsnoop": "80d9e6197b978631ef49db486a44db5690301471e489d0238b66a089d87617d1",
}
CODE = {
    "prefilled_nor_pages.py": "584e3afbf84f7c67bb7c282d8b072934202004af27ce322bf30b596747ccd0c9",
    "prefilled_nor_control.py": "3ee6207a782609bb087593d989c1c03ff6d0557e4d9652eb5fae4b8bfcccc93c",
    "prefilled_nor_runtime.py": "b2b86213cbc370f9a02f337c0241706683f71dac7ddcc27375e6dc30014dcae7",
    "paired_nor_plan.py": "28a71a534c1ebc5062bcbe88b6c42e174d74651befff498cf8c6a3f37afbf06b",
    "paired_nor_audit.py": "a30b6a4ad593fcbad2c84a8065b3e081c67a16d7e7fd347f04f9588cef6bc918",
    "paired_nor_runtime.py": "47b27c4506d7d690c65751c312a3c77da37f157822fe64eb2c25c82c8893ad70",
    "paired_nor_sources.py": "56f2fdc838784907be153fab0e0ca99b762d5e35b6deacb15fe5ca6e9186a980",
    "scratch_reuse_parser.py": "a69a8bdd243a0c786d9602806412986712c11dae21bfff00c41054ace63177fb",
}


def capture_module(failed):
    from rcominote.experiments import prefilled_vsync_checkpoint

    if A.A.sha((failed / "report.json").read_bytes()) == prefilled_vsync_checkpoint.PINS["report.json"]:
        return prefilled_vsync_checkpoint
    return None


def failed_prefix(failed, source, baseline):
    if module := capture_module(failed):
        return module.verify(failed, source, baseline)
    refs = {name: C.pins.pinned(failed / name, digest)[1] for name, digest in PINS.items()}
    job = json.loads((failed / "report.json").read_bytes())
    plan = json.loads(C.J.check_reference(failed, job["plan"]).read_bytes())
    if (
        set(job) != {"profile", "budget", "started_at", "plan", "completed", "ok", "ended_at", "error"}
        or job.get("ok") is not False
        or job["error"] != ERROR
        or plan["profile"] != C.PREFILLED_PROFILE
        or job["profile"] != plan["profile"]
        or plan["parent"] != source
        or source["profile"] != C.PREFILLED_PROFILE
        or plan["gap_policy"] != C.F.PREFILL_GAP_POLICY
        or plan["offsets"] != OFFSETS
        or len(job["completed"]) != 1
    ):
        raise ValueError("Requires pinned NEXT3 with one complete pair and original first-NOR gap failure")
    C.pins.pinned(failed / "source-snapshot/manifest.json", MANIFEST_SHA)
    snapshot = K.snapshot(failed, code=CODE)
    manifest = json.loads((failed / "source-snapshot/manifest.json").read_bytes())
    if (len(manifest["source_files"]), len(manifest["test_files"])) != SOURCE_COUNTS:
        raise ValueError("Original complete NEXT3 source/test snapshot changed")
    C.J.time_order(manifest["created_at"], source["ended_at"], plan["planned_at"], job["started_at"])
    proofs, previous, state = A.completed_prefix(job, plan, failed, baseline)
    path = failed / PAGE
    report = json.loads((path / "report.json").read_bytes())
    page = C.page_plan(plan, 1, state, job["completed"][0]["ended_at"])
    N.plan_gate(report, page, path)
    warm, prefill, first = report["baseline"], *report["operations"][:2]
    if (
        report.get("ok") is not False
        or report.get("error") != ERROR
        or report.get("capture_error") != ERROR
        or report.get("plan") != job["plan"]
        or "verification" in report
        or any(s.get("ok") is not True or s.get("live_complete") is not True for s in (warm, prefill))
        or first.get("ok") is not False
        or first.get("live_complete") is not False
        or first.get("error") != ERROR
        or first.get("barrier_complete") is not True
        or any(k in first for k in ("verification", "oracle_verification", "sector_hex"))
        or (path / "first/sector.bin").exists()
    ):
        raise ValueError("Only original failed content after complete RAM/NOR communication permitted")
    for op, slot in zip(report["operations"][2:], page["operations"][2:], strict=True):
        if op != slot | {"ok": False, "live_complete": False} or any(
            p.is_file() for p in (path / slot["operation_id"]).rglob("*")
        ):
            raise ValueError("Later failed-page stages must remain untouched")
    if any(p.is_file() for p in (failed / plan["pages"][2]["directory"]).rglob("*")):
        raise ValueError("Last NEXT3 page must remain empty")
    C.J.time_order(
        job["started_at"],
        page["predecessor_ended_at"],
        report["started_at"],
        report["ended_at"],
        job["ended_at"],
    )
    view = copy.deepcopy(report)
    del view["error"], view["capture_error"], view["operations"][1]["error"]
    ram = N.source_ram(plan, Path(plan["ram_oracle"]["image"]["file"]))
    transfers, context, events = N.communication(view, path, page, previous, ram, operation_count=2)
    if (
        transfers[0] != ram
        or N.content(prefill, ram, previous, ram, page, previous) != prefill["verification"]
    ):
        raise ValueError("Original accepted RAM prefill full oracle/proof changed")
    try:
        N.content(first, transfers[1], ram, ram, page, previous)  # Original three-gap policy only.
    except ValueError as error:
        if f"ValueError: {error}" != ERROR:
            raise ValueError("Original first-NOR gap failure no longer replays exactly") from error
    else:
        raise ValueError("Original rejected content unexpectedly passed; no promotion")
    wire = A.common.wire_positions(report, (path / "session.btsnoop").read_bytes())
    identity_at = times.iso(wire[report["after_span"][1] - 1][2])
    C.J.time_order(identity_at, report["ended_at"], job["ended_at"])
    names = sorted(set(source["prior_names"]) | set(C.nonces(plan)))
    if len(names) != 70:
        raise ValueError("All70 historical/planned nonces must remain reserved")
    return (
        transfers[1],
        context["state"],
        {
            "directory": str(failed.resolve()),
            "references": refs
            | {"snapshot": snapshot, "current_file": C.J.reference(failed, path / "first/download.bin")},
            "original_completed_prefix": proofs,
            "latest_identity_response_at": identity_at,
            "observed_ended_at": report["ended_at"],
            "failed_ended_at": job["ended_at"],
            "latest_info": context["state"],
            "current_ring_sha256": A.A.sha(transfers[1]),
            "prior_names": names,
            "communication": {
                "verified": True,
                "parameter_transactions": 9,
                "downloads": 3,
                "att_packets": len(report["att_packets"]),
                "hci_capture": report["hci_capture"],
                "status_events": events,
                "ram_prefill_oracle_verified": True,
                "content_error_reproduced": ERROR,
                "failed_content_accepted": False,
            },
        },
    )


def header(checkpoint):
    A.common.no_errors(checkpoint)
    if (
        checkpoint.get("profile") != PROFILE
        or checkpoint.get("offline_ownership_verified") is not True
        or checkpoint.get("live_capture_performed") is not False
        or checkpoint.get("original_job_ok") is not False
        or checkpoint.get("original_failed_content_ok") is not False
        or "ok" in checkpoint
        or type(checkpoint.get("new_raw_nor_coverage_bytes")) is not int
        or checkpoint["new_raw_nor_coverage_bytes"] != 0
        or checkpoint["parent"]["profile"] not in (C.PREFILLED_PROFILE, C.PREFILLED_LINK_CP)
    ):
        raise ValueError("Requires distinct pinned NEXT3 offline ownership node, zero coverage")
    C.J.time_order(checkpoint["failed"]["failed_ended_at"], checkpoint["created_at"])


def verify_admitted(checkpoint, directory, source, baseline):
    header(checkpoint)
    failed = Path(checkpoint["failed"]["directory"]).resolve()
    if checkpoint["parent"] != source or failed in (directory.resolve(), Path(source["directory"]).resolve()):
        raise ValueError("Checkpoint source differs from admitted ancestor or has a failed-edge cycle")
    current, state, result = failed_prefix(failed, source, baseline)
    if (
        checkpoint["failed"] != result
        or checkpoint["baseline"]["file"] != "baseline.bin"
        or C.J.check_reference(directory, checkpoint["baseline"]).read_bytes() != current
    ):
        raise ValueError("Original NEXT3 communication/current baseline changed")
    return (
        current,
        state,
        {
            "directory": str(directory.resolve()),
            "profile": PROFILE,
            "ended_at": result["observed_ended_at"],
            "created_at": checkpoint["created_at"],
            "latest_identity_response_at": result["latest_identity_response_at"],
            "failed_ended_at": result["failed_ended_at"],
            "latest_info": state,
            "baseline_sha256": A.A.sha(current),
            "prior_names": result["prior_names"],
            "references": {
                "checkpoint": C.J.reference(directory, directory / "checkpoint.json"),
                "baseline": checkpoint["baseline"],
            },
            "verification": {
                "verified": True,
                "device_io": 0,
                "new_raw_nor_coverage_bytes": 0,
                "original_failed_retained": True,
                "communication": result["communication"],
            },
            "current_object_live_download_required_before_overwrite": True,
        },
    )


def create(image, failed, newout):
    from rcominote.experiments.paired_nor_runtime import private_output

    private_output(newout)
    pins = module.PINS if (module := capture_module(failed)) else PINS
    plan = json.loads(C.pins.pinned(failed / "plan.json", pins["plan.json"])[0])
    baseline, _state, source = C.parent_gate(Path(plan["parent"]["directory"]), image)
    current, _state, result = failed_prefix(failed, source, baseline)
    checkpoint = {
        "profile": PROFILE,
        "created_at": C.S.now(),
        "parent": source,
        "failed": result,
        "offline_ownership_verified": True,
        "live_capture_performed": False,
        "original_job_ok": False,
        "original_failed_content_ok": False,
        "new_raw_nor_coverage_bytes": 0,
    }
    header(checkpoint)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    (newout / "baseline.bin").write_bytes(current)
    checkpoint["baseline"] = C.J.reference(newout, newout / "baseline.bin")
    C.S.save(newout / "checkpoint.json", checkpoint)
    return verify_admitted(checkpoint, newout, source, baseline)
