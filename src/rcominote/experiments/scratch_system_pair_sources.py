"""Pinned latest known4200 control/current object; no unknown raw oracle."""

import json
import re
from pathlib import Path

from rcominote.experiments import dual_audit as A
from rcominote.experiments import scratch_4200_probe as Q
from rcominote.experiments import scratch_reuse_sources as pins
from rcominote.experiments.sd_bootstrap import verify_state

REPORT_SHA = "1aeaec193999c0443e14f85ab95d31a2ce9fcd164e9ce11be17afbc0b41914ef"
PLAN_SHA = "bcf21844af658985e624f29ecd99632e84dfd412f36487c1dcbf04b7fd3815bd"
HCI_SHA = "7b3b8448971b1f3c405b7fbe2100bf25c0ba572cf2c34b469f8506a1329d2510"
BASELINE_SHA = "10bd351c52d1d8560ad28929b9d8b34002ebe8398586bdf988595dc0d3f433e1"


def verify(parent: Path, image: Path) -> tuple[bytes, dict, dict]:
    report_raw, report_ref = pins.pinned(parent / "report.json", REPORT_SHA)
    plan_raw, plan_ref = pins.pinned(parent / "plan.json", PLAN_SHA)
    _, capture_ref = pins.pinned(parent / "session.btsnoop", HCI_SHA)
    baseline, baseline_ref = pins.pinned(parent / "overwrite/download.bin", BASELINE_SHA)
    report, plan = json.loads(report_raw), json.loads(plan_raw)
    if report.get("ok") is not True or any(
        report[key].get("ok") is not True for key in ("baseline", "operation")
    ):
        raise ValueError("Requires original successful latest known4200 control")
    proof = Q.replay(parent, image)
    if (
        proof != report["verification"]
        or proof.get("known_offset") != 0x4200
        or proof.get("original_trial_ok") is not False
        or proof.get("new_raw_nor_coverage_bytes") != 0
        or len(baseline) != 4096
        or report["operation"]["download_sha256"] != A.sha(baseline)
    ):
        raise ValueError(
            "Known parent must preserve original failed contract and exact complete current file"
        )
    verify_state(report["after"], report["after"], sd_write=False)
    if report["after"]["device"]["free_capacity"] != 59589:
        raise ValueError("Latest pinned known4200 final identity must remain59589")
    names = sorted(set(re.findall(r"rc[0-9a-f]{10}", json.dumps(plan))))
    if pins.NAME not in names or report["operation"]["nonce"] not in names:
        raise ValueError("Pinned latest plan must retain owned name and every planned producer nonce")
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
            "verification": proof,
            "original_failed_retained": True,
            "current_object_live_download_required_before_overwrite": True,
            "unknown_raw_oracle": False,
            "new_raw_nor_coverage_bytes": 0,
        },
    )
