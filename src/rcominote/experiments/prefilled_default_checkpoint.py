"""One pinned DEFAULT rejection before any stage: old SD ownership plus new state.

No fresh file download occurred. The object comes from the admitted notice node;
the new identity/time and two reserved names come from this zero-write capture.
"""

import copy
import json
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_checkpoint as K
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_link_checkpoint as times
from rcominote.experiments import prefilled_nor_pages as N

PROFILE = C.PREFILLED_STARTUP_CP
ERROR = "ValueError: Startup tuple is outside its explicit FAST/DEFAULT policy"
PAGE = "page0-1ecc00"
PINS = {
    "report.json": "cd342e8f91b1efcedb4fa8322553ff5070f8dbbb3d4b9798c43e1af6b2f56ae3",
    "plan.json": "31aa34bcfa141d258f36366cb27735bffd5bfc4e372c253c1a3e9f6ed66e00b9",
    f"{PAGE}/report.json": "cd42f081c4b208c8c860856f89cd28d917a0df05b8a8e394a3b357919f557d23",
    f"{PAGE}/session.btsnoop": "0430812dfff8e9a52da0546e5194d20728e82b384a3403926da7a82728118076",
}
PARENT_SHA = "5eb25bddf858cc4453e692470114048da81c7811153d2fab36f2d16ea894f21b"
MANIFEST_SHA = "dd58df82ee91e6f4807df2f372b1609eff8b86d5e13bd744aa0125e108966669"
SOURCE_COUNTS = (151, 138)
WIRE_SHAPE = (34, [34, 40], [40, 55], [55, 61])
HCI_COUNT = 123
CODE = {
    "prefilled_nor_pages.py": "c7940c91eac5b306e9a057191639830dd342f6a2717cb029790c8a7110538507",
    "prefilled_nor_runtime.py": "b2b86213cbc370f9a02f337c0241706683f71dac7ddcc27375e6dc30014dcae7",
    "paired_nor_plan.py": "261f0a862a7e59826c3f1e0324099e12518bf35ede5cf3cdb789b4c9e194b2ec",
    "paired_nor_sources.py": "a8659815ae8dcdc69a0e0caa0a14fc79762345ff9208ec82532bea681fba6320",
    "paired_nor_audit.py": "a30b6a4ad593fcbad2c84a8065b3e081c67a16d7e7fd347f04f9588cef6bc918",
    "paired_nor_runtime.py": "47b27c4506d7d690c65751c312a3c77da37f157822fe64eb2c25c82c8893ad70",
    "startup_policy.py": "68a920ecfbcbf5cc848ebf9abe60b1ecdf0ed7c1db34615fe6e14277116a909c",
    "prefilled_notice_checkpoint.py": "965c79344e5c20d0ae2be559ad0cdccd20c2319bc054246f2580e4937ffed09a",
}


def failed_startup(failed, source, baseline):
    refs = {name: C.pins.pinned(failed / name, digest)[1] for name, digest in PINS.items()}
    C.pins.pinned(Path(source["directory"]) / "checkpoint.json", PARENT_SHA)
    job = json.loads((failed / "report.json").read_bytes())
    plan = json.loads(C.J.check_reference(failed, job["plan"]).read_bytes())
    if (
        source["profile"] != C.PREFILLED_NOTICE_CP
        or len(source["prior_names"]) != 70
        or plan["parent"] != source
        or plan["profile"] != N.PROFILE
        or plan["offsets"] != [0x1ECC00]
        or plan["startup_policy"] != C.startup.LEGACY_POLICY
        or plan["gap_policy"] != C.F.PREFILL_WAKE_GAP_POLICY
        or job.get("ok") is not False
        or job.get("error") != ERROR
        or job.get("completed") != []
        or set(job) != {"profile", "budget", "started_at", "plan", "completed", "ok", "ended_at", "error"}
        or len(baseline) != 4096
        or A.A.sha(baseline) != source["baseline_sha256"]
    ):
        raise ValueError("Only pinned zero-stage DEFAULT failure after exact notice ownership admitted")
    A.job_gate(job, plan, failed)
    C.F.absent(baseline, C.nonces(plan))
    C.pins.pinned(failed / "source-snapshot/manifest.json", MANIFEST_SHA)
    snapshot = K.snapshot(failed, code=CODE)
    manifest = json.loads((failed / "source-snapshot/manifest.json").read_bytes())
    if (len(manifest["source_files"]), len(manifest["test_files"])) != SOURCE_COUNTS:
        raise ValueError("Original startup source/test snapshot changed")
    C.J.time_order(manifest["created_at"], source["created_at"], plan["planned_at"], job["started_at"])
    path = failed / PAGE
    report = json.loads((path / "report.json").read_bytes())
    page = C.page_plan(plan, 0, source["latest_info"], source["ended_at"])
    N.plan_gate(report, page, path)
    if (
        report.get("ok") is not False
        or report.get("error") != ERROR
        or report.get("capture_error") != ERROR
        or any(
            k in report
            for k in ("verification", "startup_settlement", "startup_classification", "startup_pulse")
        )
        or report["baseline"]
        != {"operation_id": "baseline", "name": C.F.NAME, "live_complete": False, "ok": False}
        or any(
            op != slot | {"ok": False, "live_complete": False}
            for op, slot in zip(report["operations"], page["operations"], strict=True)
        )
        or any(p.is_file() for stage in N.STAGES for p in (path / stage).rglob("*"))
    ):
        raise ValueError("Original DEFAULT rejection must retain all untouched slots, no baseline/Actions")
    view = copy.deepcopy(report)
    del view["error"], view["capture_error"]
    A.common.no_errors(view)
    observed, wire, events = A.envelope(view, path, 1)
    startup = observed["transactions"][0]
    classification = C.startup.classify(startup, policy=C.startup.POLICY)
    if classification["mode"] != "default":
        raise ValueError("Pinned startup must be actual fully settled DEFAULT")
    try:
        C.startup.classify(startup, policy=report["startup_policy"])
    except ValueError as error:
        if f"ValueError: {error}" != ERROR:
            raise ValueError("Original legacy rejection changed") from error
    else:
        raise ValueError("Original rejected startup unexpectedly passed")
    state = source["latest_info"]
    if (
        report["before"] != state
        or report["after"] != state
        or report["predecessor_state_verification"] != A.verify_state(state, state, sd_write=False)
    ):
        raise ValueError("Complete original readonly before/after identity changed")
    if any(report[f"{key}_verification"] != A.A.identity(report, report, key) for key in ("before", "after")):
        raise ValueError("Original full identity wire verification changed")
    A.E.bridge(report, report["before_span"][1], report["file_list_span"][0])
    if A.inventory(report, page) != report["listed_count"]:
        raise ValueError("Original inventory changed")
    A.final_identity(report, wire, {"state": state, "boundary": report["file_list_span"][1], "cursor": 1}, 1)
    if (
        (report["setup_end"], report["before_span"], report["file_list_span"], report["after_span"])
        != WIRE_SHAPE
        or observed["records"] != HCI_COUNT
        or events["events"] != 0
    ):
        raise ValueError("Pinned full61ATT/123HCI identity/inventory-only transcript changed")
    C.J.time_order(job["started_at"], report["started_at"], report["ended_at"], job["ended_at"])
    identity_at = times.iso(wire[report["after_span"][1] - 1][2])
    names = sorted(set(source["prior_names"]) | set(C.nonces(plan)))
    if len(names) != 72:
        raise ValueError("All72 historical/planned names, including unsent two, required")
    return (
        baseline,
        state,
        {
            "directory": str(failed.resolve()),
            "references": refs | {"snapshot": snapshot},
            "latest_identity_response_at": identity_at,
            "observed_ended_at": report["ended_at"],
            "failed_ended_at": job["ended_at"],
            "owned_file_observed_ended_at": source["ended_at"],
            "latest_info": state,
            "baseline_sha256": A.A.sha(baseline),
            "prior_names": names,
            "verification": {
                "verified": True,
                "parameter_transactions": 1,
                "startup": classification,
                "downloads": 0,
                "actions": 0,
                "sd_writes": 0,
                "original_error_reproduced": ERROR,
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
        or checkpoint.get("original_failed_page_ok") is not False
        or "ok" in checkpoint
        or type(checkpoint.get("new_raw_nor_coverage_bytes")) is not int
        or checkpoint["new_raw_nor_coverage_bytes"] != 0
        or checkpoint["parent"]["profile"] != C.PREFILLED_NOTICE_CP
    ):
        raise ValueError("Requires pinned zero-write DEFAULT ownership node, zero new coverage")
    C.J.time_order(checkpoint["failed"]["failed_ended_at"], checkpoint["created_at"])


def verify_admitted(checkpoint, directory, source, baseline):
    header(checkpoint)
    failed = Path(checkpoint["failed"]["directory"]).resolve()
    if checkpoint["parent"] != source or failed in (directory.resolve(), Path(source["directory"]).resolve()):
        raise ValueError("DEFAULT checkpoint source changed or has a failed-edge cycle")
    current, state, result = failed_startup(failed, source, baseline)
    if (
        checkpoint["failed"] != result
        or checkpoint["baseline"]["file"] != "baseline.bin"
        or C.J.check_reference(directory, checkpoint["baseline"]).read_bytes() != current
    ):
        raise ValueError("Original zero-write ownership evidence/object changed")
    return (
        current,
        state,
        {
            "directory": str(directory.resolve()),
            "profile": PROFILE,
            "created_at": checkpoint["created_at"],
            "ended_at": result["observed_ended_at"],
            "latest_identity_response_at": result["latest_identity_response_at"],
            "owned_file_observed_ended_at": result["owned_file_observed_ended_at"],
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
                "startup": result["verification"],
            },
            "current_object_live_download_required_before_overwrite": True,
        },
    )


def create(image, failed, newout):
    from rcominote.experiments.paired_nor_runtime import private_output

    private_output(newout)
    plan = json.loads(C.pins.pinned(failed / "plan.json", PINS["plan.json"])[0])
    baseline, _state, source = C.parent_gate(Path(plan["parent"]["directory"]), image)
    current, _state, result = failed_startup(failed, source, baseline)
    checkpoint = {
        "profile": PROFILE,
        "created_at": C.S.now(),
        "parent": source,
        "failed": result,
        "offline_ownership_verified": True,
        "live_capture_performed": False,
        "original_job_ok": False,
        "original_failed_page_ok": False,
        "new_raw_nor_coverage_bytes": 0,
    }
    header(checkpoint)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    (newout / "baseline.bin").write_bytes(current)
    checkpoint["baseline"] = C.J.reference(newout, newout / "baseline.bin")
    C.S.save(newout / "checkpoint.json", checkpoint)
    return verify_admitted(checkpoint, newout, source, baseline)
