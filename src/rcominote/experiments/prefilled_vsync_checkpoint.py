"""Closed SECOND gap-failure communication case for the existing notice node.

Adopts only the actual SECOND owned SD object and final identity. The original
wake-policy content error must reproduce; the new vsync policy is never used.
"""

import copy
import json
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_checkpoint as snapshot
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_link_checkpoint as times
from rcominote.experiments import prefilled_nor_pages as N
from rcominote.experiments import prefilled_notice_checkpoint as owner

PAGE = "page1-1eda00"
OFFSETS = [0x1ED800, 0x1EDA00, 0x1EDC00, 0x1EDE00]
PINS = {
    "report.json": "2a064280820e80ae35c3857e688685f6e1f1b7e1f66b302b65b96e79dc38132f",
    "plan.json": "9a1f0d503bbd0178bb6e57e1f69149a498bc316d71d64ec21f1924925351dfdd",
    f"{PAGE}/report.json": "83767139c12886b40b21d1afef2b8b45ba39f57eeab9c0a9989ddb60b12ff78d",
    f"{PAGE}/session.btsnoop": "0493f6b03ff5f030808c463368f9084c6fadfd7d9e5c13ae05bdf381ea094426",
}
MANIFEST_SHA = "743d851a991940c3be31297955b6e7855c17544ea5b58eb9f504c78a54361b59"
SOURCE_COUNTS = (153, 141)
CODE = {
    "prefilled_nor_pages.py": "d3ddb9a2e3b3ee5627e6f7f7cb3a7c091d7f76540095e0576f11fa548a4d27f8",
    "prefilled_nor_runtime.py": "20ba7bcea1eebb64f3abdf605f5ba9560c74dd3e188e737004d5eec268db7d1f",
    "paired_nor_plan.py": "cf715c10b5346451de59ceaf61078b1d847a9d7ea9efc5e0442ec0c55d426010",
    "paired_nor_audit.py": "a30b6a4ad593fcbad2c84a8065b3e081c67a16d7e7fd347f04f9588cef6bc918",
    "paired_nor_runtime.py": "47b27c4506d7d690c65751c312a3c77da37f157822fe64eb2c25c82c8893ad70",
    "paired_nor_sources.py": "fdc38b68bb5fd53e1cadab3074881922f024d3399cf206cfc4211bec19504c54",
    "scratch_reuse_parser.py": "449359eeb72d4705304b503dd864a5dab843cfa1e3c24f7235f67f970b0c1383",
}


def verify(failed, source, baseline):
    refs = {name: C.pins.pinned(failed / name, digest)[1] for name, digest in PINS.items()}
    job = json.loads((failed / "report.json").read_bytes())
    plan = json.loads(C.J.check_reference(failed, job["plan"]).read_bytes())
    if (
        set(job) != {"profile", "budget", "started_at", "plan", "completed", "ok", "ended_at", "error"}
        or job.get("ok") is not False
        or job["error"] != owner.ERROR
        or job["profile"] != C.PREFILLED_PROFILE
        or plan["profile"] != C.PREFILLED_PROFILE
        or plan["parent"] != source
        or source["profile"] != C.PREFILLED_LINK_CP
        or plan["offsets"] != OFFSETS
        or len(job["completed"]) != 1
        or plan["gap_policy"] != C.F.PREFILL_WAKE_GAP_POLICY
        or plan["startup_policy"] != C.startup.POLICY
    ):
        raise ValueError("Only pinned remaining-four SECOND-content failure with exact LinkCP admitted")
    C.pins.pinned(failed / "source-snapshot/manifest.json", MANIFEST_SHA)
    frozen = snapshot.snapshot(failed, code=CODE)
    manifest = json.loads((failed / "source-snapshot/manifest.json").read_bytes())
    if (len(manifest["source_files"]), len(manifest["test_files"])) != SOURCE_COUNTS:
        raise ValueError("Original complete remaining-four source/test snapshot changed")
    C.J.time_order(manifest["created_at"], source["created_at"], plan["planned_at"], job["started_at"])
    proofs, previous, state = A.completed_prefix(job, plan, failed, baseline)
    path = failed / PAGE
    report = json.loads((path / "report.json").read_bytes())
    page = C.page_plan(plan, 1, state, job["completed"][0]["ended_at"])
    N.plan_gate(report, page, path)
    second = report["operations"][3]
    if (
        report.get("ok") is not False
        or report.get("error") != owner.ERROR
        or report.get("capture_error") != owner.ERROR
        or report.get("plan") != job["plan"]
        or "verification" in report
        or any(
            s.get("ok") is not True or s.get("live_complete") is not True
            for s in [report["baseline"], *report["operations"][:3]]
        )
        or second.get("ok") is not False
        or second.get("live_complete") is not False
        or second.get("error") != owner.ERROR
        or second.get("barrier_complete") is not True
        or any(k in second for k in ("verification", "oracle_verification", "sector_hex"))
        or (path / "second/sector.bin").exists()
        or any(p.is_file() for slot in plan["pages"][2:] for p in (failed / slot["directory"]).rglob("*"))
    ):
        raise ValueError("SECOND alone must fail content after full transfer/barrier, later pages untouched")
    C.J.time_order(
        job["started_at"],
        page["predecessor_ended_at"],
        report["started_at"],
        report["ended_at"],
        job["ended_at"],
    )
    view = copy.deepcopy(report)
    del view["error"], view["capture_error"], view["operations"][3]["error"]
    ram = N.source_ram(plan, Path(plan["ram_oracle"]["image"]["file"]))
    transfers, context, events = N.communication(view, path, page, previous, ram, operation_count=4)
    predecessor, history = previous, previous
    for op, data in zip(report["operations"][:3], transfers[:3], strict=True):
        if N.content(op, data, predecessor, ram, page, history) != op["verification"]:
            raise ValueError("Originally accepted stage content/proof changed")
        if op["kind"] == "nor":
            if (path / "first/sector.bin").read_bytes() != bytes.fromhex(op["verification"]["sector_hex"]):
                raise ValueError("Original first sector differs from its own accepted content")
            history = data
        elif data != ram:
            raise ValueError("Both independently completed RAM prefills must match full pinned oracle")
        predecessor = data
    current = transfers[3]
    prefix = max(
        (i + 1 for i, (a, b) in enumerate(zip(current, predecessor, strict=True)) if a != b), default=0
    )
    if predecessor != ram or len(current) != 4096 or prefix != 4096:
        raise ValueError("Original SECOND must follow its own full RAM prefill with complete4096 prefix")
    try:
        N.content(second, current, predecessor, ram, page, history)  # Original wake policy, no v4.
    except ValueError as error:
        if f"ValueError: {error}" != owner.ERROR:
            raise ValueError("Original SECOND content failure does not replay exactly") from error
    else:
        raise ValueError("Original rejected SECOND unexpectedly passed; no retrospective promotion")
    wire = A.common.wire_positions(report, (path / "session.btsnoop").read_bytes())
    identity_at = times.iso(wire[report["after_span"][1] - 1][2])
    C.J.time_order(identity_at, report["ended_at"], job["ended_at"])
    names = sorted(set(source["prior_names"]) | set(C.nonces(plan)))
    if len(names) != 98:
        raise ValueError("All98 historical/planned names must remain reserved")
    return (
        current,
        context["state"],
        {
            "directory": str(failed.resolve()),
            "references": refs
            | {"snapshot": frozen, "current_file": C.J.reference(failed, path / "second/download.bin")},
            "original_completed_prefix": proofs,
            "latest_identity_response_at": identity_at,
            "observed_ended_at": report["ended_at"],
            "failed_ended_at": job["ended_at"],
            "latest_info": context["state"],
            "current_ring_sha256": A.A.sha(current),
            "prior_names": names,
            "communication": {
                "verified": True,
                "parameter_transactions": context["cursor"],
                "downloads": 5,
                "att_packets": len(report["att_packets"]),
                "hci_capture": report["hci_capture"],
                "status_events": events,
                "ram_prefill_oracle_verified": True,
                "difference_proven_written_prefix_bytes": prefix,
                "content_error_reproduced": owner.ERROR,
                "failed_content_accepted": False,
            },
        },
    )
