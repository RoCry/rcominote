"""Pinned successful retained-file observation, without promoting its failed trial."""

import json
from pathlib import Path

from rcominote.experiments import dual_audit as A
from rcominote.experiments import scratch_postmortem_probe as P
from rcominote.experiments import scratch_postmortem_sources as failed
from rcominote.experiments import scratch_reuse_sources as pins
from rcominote.experiments.sd_bootstrap import verify_state

REPORT_SHA = "aef13eb53fad9c25584e0a4dd23c9eb4b041316b02b06ef9587c98f796a03e54"
PLAN_SHA = "d0493d3241e56af45cf0f5a730b361ef1748824c35d2f386cd16c6aec171409a"
HCI_SHA = "02e600215d0b2259a3604c86b4dd104abaac7703beb8c35325dd6563507d85b4"
BASELINE_SHA = "3621a69cc9215acf435ecab311088f53e8eb65d28f3d3a80cce6aca892560360"


def verify(parent: Path, image: Path) -> tuple[bytes, dict, dict]:
    report_raw, report_ref = pins.pinned(parent / "report.json", REPORT_SHA)
    plan_raw, plan_ref = pins.pinned(parent / "plan.json", PLAN_SHA)
    _, capture_ref = pins.pinned(parent / "session.btsnoop", HCI_SHA)
    baseline, baseline_ref = pins.pinned(parent / "retained/download.bin", BASELINE_SHA)
    report, plan = json.loads(report_raw), json.loads(plan_raw)
    if report.get("ok") is not True or report["operation"].get("ok") is not True:
        raise ValueError("Requires original successful readonly retained-file parent")
    proof = P.replay(parent, image)
    content = report["content_verification"]
    if (
        len(baseline) != 4096
        or proof != {"readonly": report["readonly_proof"], "content": content}
        or content.get("original_trial_ok") is not False
        or content.get("reuse_pair_complete") is not False
        or content["freshness"]["nor_offset"] != 0
        or content["freshness"]["ring_sha256"] != A.sha(baseline)
        or content["freshness"]["nonce"] != P.C.NONCE
    ):
        raise ValueError("Readonly parent must preserve failed original and exact retained boot0 observation")
    verify_state(report["after"], report["after"], sd_write=False)
    if report["after"]["device"]["free_capacity"] != 59589:
        raise ValueError("Pinned readonly latest state must remain59589")
    old_raw, _ = pins.pinned(Path(plan["parent"]["directory"]) / "plan.json", failed.PLAN_SHA)
    old_plan = json.loads(old_raw)
    names = [pins.NAME, *(op["nonce"] for op in old_plan["operations"])]
    return (
        baseline,
        report["after"],
        {
            "directory": str(parent.resolve()),
            "ended_at": report["ended_at"],
            "latest_info": report["after"],
            "references": {
                "report": report_ref,
                "plan": plan_ref,
                "capture": capture_ref,
                "baseline": baseline_ref,
            },
            "baseline_sha256": BASELINE_SHA,
            "prior_names": names,
            "sources": plan["parent"]["sources"],
            "verification": proof,
            "original_failed_retained": True,
            "reuse_pair_complete": False,
            "current_object_live_download_required_before_overwrite": True,
            "new_raw_nor_coverage_bytes": 0,
        },
    )
