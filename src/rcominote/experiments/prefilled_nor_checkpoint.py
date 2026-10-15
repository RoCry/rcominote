"""Adopt original prefill-v1 communication; rejected NOR content stays rejected.

Retained files and their digests are private: RAM SD prefill does not clear the
resident ring. This helper performs no capture, writes, or new-policy parsing.
"""

import copy
import json
from pathlib import Path

from rcominote.experiments import paired_nor_checkpoint as K
from rcominote.experiments import prefilled_nor_control as P

ROLE = K.PREFILL_CONTENT_ROLE
CONTENT_ERROR = "ValueError: Unexpected text after current producer before dump"
SOURCE_MANIFEST_SHA = "9139f449cc69785dfbde1c86c5bb007f076dacfa0c2479c587797d608fb47fe5"
SOURCE_COUNTS = (144, 127)
CAPTURE_CODE = {
    "prefilled_nor_control.py": "412e35a15e88013c83eebf640e4359787d38128d3bec3a82e9cb1c18204c456e",
    "prefilled_nor_runtime.py": "b1e293723dcf26e393883929bce43e7d19ee854ed1c498ec65b727ccf4b8c6de",
    "paired_nor_plan.py": "1a83dd8669df5cece64955e9027b12b534a08e7c587d964685d835a5ee260b0f",
    "paired_nor_audit.py": "2954cbcbb45cd46cd2f284b920de8095daac585ec77f0c2171b5038b2bab89e6",
    "paired_nor_runtime.py": "1a9762e10723862f15e482d030ed139f3e0586fcebb063f2dff1e5e710e43246",
    "paired_nor_recipe.py": "093b2fc2ec17f1061945fd8764e61ae036b6a3ebe77254a846469f870a3a91a2",
    "scratch_reuse_parser.py": "5cd1eef9f9d72466548314bab8f680bd7fcd273c534324f96d9faa825e8e1f39",
}


def verify(failed: Path, source: dict, baseline: bytes) -> tuple[bytes, dict, dict]:
    report = json.loads((failed / "report.json").read_bytes())
    plan = json.loads(P.C.J.check_reference(failed, report["plan"]).read_bytes())
    if (
        plan.get("profile") != K.PREFILL_CAPTURE_PROFILE
        or report.get("profile") != K.PREFILL_CAPTURE_PROFILE
        or plan.get("parent") != source
        or report.get("ok") is not False
        or report.get("error") != CONTENT_ERROR
        or report.get("capture_error") != CONTENT_ERROR
        or "verification" in report
        or report["plan"]["file"] != "plan.json"
    ):
        raise ValueError("Requires original prefill-v1 first-NOR content failure with exact ancestor")
    P.plan_gate(report, plan, failed)
    warm, prefill, first = report["baseline"], *report["operations"][:2]
    if (
        any(
            stage.get("ok") is not True or stage.get("live_complete") is not True for stage in (warm, prefill)
        )
        or first.get("ok") is not False
        or first.get("live_complete") is not False
        or first.get("error") != CONTENT_ERROR
        or first.get("barrier_complete") is not True
        or any(key in first for key in ("verification", "oracle_verification", "sector_hex"))
        or (failed / "first/sector.bin").exists()
    ):
        raise ValueError("Only first NOR content failure after full verified RAM prefill/barrier permitted")
    for op, slot in zip(report["operations"][2:], plan["operations"][2:], strict=True):
        if op != slot | {"ok": False, "live_complete": False} or any(
            path.is_file() for path in (failed / slot["operation_id"]).rglob("*")
        ):
            raise ValueError("Later prefill/NOR slots must remain untouched without files")
    manifest_path = failed / "source-snapshot/manifest.json"
    P.C.pins.pinned(manifest_path, SOURCE_MANIFEST_SHA)
    frozen_source = K.snapshot(failed, code=CAPTURE_CODE)
    manifest = json.loads(manifest_path.read_bytes())
    if (len(manifest["source_files"]), len(manifest["test_files"])) != SOURCE_COUNTS:
        raise ValueError("Original prefill-v1 complete source/test snapshot counts changed")
    P.C.J.time_order(manifest["created_at"], plan["planned_at"], report["started_at"])
    ram, oracle = P.ram_source(Path(plan["ram_oracle"]["image"]["file"]))
    if oracle != plan["ram_oracle"]:
        raise ValueError("Original independent full RAM oracle source changed")
    view = copy.deepcopy(report)
    # Only these exact recorded exceptions are removed; all false flags persist.
    del view["error"], view["capture_error"], view["operations"][1]["error"]
    transfers, context, events = P.communication(view, failed, plan, baseline, ram, operation_count=2)
    if transfers[0] != ram or P.content(prefill, transfers[0], baseline, ram, plan, baseline) != prefill.get(
        "verification"
    ):
        raise ValueError("Originally accepted RAM prefill differs from its independent full oracle/proof")
    # Require original strict grammar failure before P.content could reach its
    # oracle branch on coherently substituted passing bytes. No later gap policy.
    # SD predecessor is RAM; marker predecessor is the retained baseline.
    for original in (
        lambda: P.C.F.parse_prefilled_ring(
            transfers[1], transfers[0], baseline, nonce=first["nonce"], nor_offset=first["nor_offset"]
        ),
        lambda: P.content(first, transfers[1], transfers[0], ram, plan, baseline),
    ):
        try:
            original()
        except ValueError as error:
            if f"ValueError: {error}" != CONTENT_ERROR:
                raise ValueError("Original first-NOR content failure does not replay exactly") from error
        else:
            raise ValueError("Original rejected first NOR unexpectedly passed; no relabeling")
    result = {
        "directory": str(failed.resolve()),
        "references": {
            "failed_report": P.C.J.reference(failed, failed / "report.json"),
            "failed_plan": report["plan"],
            "capture": P.C.J.reference(failed, failed / "session.btsnoop"),
            "baseline": P.C.J.reference(failed, failed / "baseline/download.bin"),
            "ram_prefill": P.C.J.reference(failed, failed / "prefill-first/download.bin"),
            "current_file": P.C.J.reference(failed, failed / "first/download.bin"),
            "source_snapshot": frozen_source,
        },
        "observed_ended_at": report["ended_at"],
        "latest_info": context["state"],
        "current_ring_sha256": P.A.A.sha(transfers[1]),
        "prior_names": sorted(set(source["prior_names"]) | set(P.nonces(plan))),
        "original_capture_profile": plan["profile"],
        "communication": {
            "complete": True,
            "parameter_transactions": 9,
            "downloads": 3,
            "att_packets": len(report["att_packets"]),
            "hci_capture": report["hci_capture"],
            "status_events": events,
            "ram_prefill_oracle_verified": True,
            "content_error_reproduced": CONTENT_ERROR,
            "failed_content_accepted": False,
            "new_raw_nor_coverage_bytes": 0,
        },
    }
    return transfers[1], context["state"], result
