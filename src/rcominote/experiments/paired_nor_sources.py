"""Iterative closed current-file parent admission, independent of live producers."""

import json
import re
from pathlib import Path

from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import scratch_system_pair_probe as old
from rcominote.experiments.sd_bootstrap import verify_state


def checkpoint_module(profile):
    from rcominote.experiments import (
        paired_nor_checkpoint,
        prefilled_default_checkpoint,
        prefilled_link_checkpoint,
        prefilled_notice_checkpoint,
    )

    return {
        C.PREFILLED_LINK_CP: prefilled_link_checkpoint,
        C.PREFILLED_NOTICE_CP: prefilled_notice_checkpoint,
        C.PREFILLED_STARTUP_CP: prefilled_default_checkpoint,
    }.get(profile, paired_nor_checkpoint)


def parent_gate(parent: Path, image: Path):
    from rcominote.experiments import owned_file_recovery as recovery
    from rcominote.experiments import paired_nor_audit as audit
    from rcominote.experiments import prefilled_nor_control as prefill

    stack, seen = ([], set())
    current = parent.resolve()
    while True:
        if current in seen:
            raise ValueError("Cycle in original successful NOR parent chain")
        seen.add(current)
        if (current / "checkpoint.json").exists():
            original = json.loads((current / "checkpoint.json").read_bytes())
            checkpoint_module(original.get("profile")).header(original)
            stack.append((current, original, None))
            current = Path(original["parent"]["directory"]).resolve()
            continue
        original = json.loads((current / "report.json").read_bytes())
        if original.get("ok") is not True:
            raise ValueError("Original failed parent cannot be adopted; current file may have changed")
        if original.get("profile") == C.legacy.PROFILE:
            break
        if original.get("profile") not in (
            C.PROFILE,
            C.PROFILE_V3,
            C.KNOWN_CONTROL,
            C.CONTINUOUS_CONTROL,
            C.STATUS_CONTROL,
            C.FORMAT_CONTROL,
            C.RECOVERY_PROFILE,
            *C.PREFILL_PROFILES,
            C.PREFILLED_PROFILE,
        ):
            raise ValueError("Parent admission accepts only pinned legacy24200 or fully successful v2")
        plan = json.loads(C.J.check_reference(current, original["plan"]).read_bytes())
        validators = {
            C.RECOVERY_PROFILE: recovery.validate_plan,
            **dict.fromkeys(C.PREFILL_PROFILES, prefill.validate_plan),
        }
        validators.get(original["profile"], C.validate_plan)(plan)
        stack.append((current, original, plan))
        current = Path(plan["parent"]["directory"]).resolve()
    references = {name: C.pins.pinned(current / name, digest)[1] for name, digest in C.LEGACY_PINS.items()}
    proof = old.replay(current, image)
    ring = (current / "second/download.bin").read_bytes()
    plan = json.loads((current / "plan.json").read_bytes())
    state = original["after"]
    if state["device"]["free_capacity"] != 59589:
        raise ValueError("Pinned legacy24200 latest state differs from59589")
    source = C.source_summary(current, original, plan, proof, ring, state, references)
    for directory, original, plan in reversed(stack):
        if plan is None:
            verifier = checkpoint_module(original["profile"])
            ring, state, source = verifier.verify_admitted(original, directory, source, ring)
            continue
        if plan["profile"] in C.PREFILL_PROFILES:
            ring, state, source = prefill.replay_admitted(original, plan, directory, source, ring, image)
            continue
        if plan["profile"] == C.RECOVERY_PROFILE:
            ring, state, source = recovery.replay_admitted(original, plan, directory, source, ring)
            continue
        if plan["parent"] != source or plan["expected_before"] != state:
            raise ValueError("Original child parent summary/state differs from fully admitted predecessor")
        C.F.absent(ring, C.nonces(plan))
        if C.is_control(plan):
            proof = audit.validate_control(original, directory, plan, ring, archived=True)
            last = original
        else:
            proof = audit._replay_admitted(original, plan, directory, ring)
            last = json.loads(
                C.J.check_reference(directory, original["completed"][-1]["report"]).read_bytes()
            )
        ring_path = directory / plan["pages"][-1]["directory"] / "second/download.bin"
        ring, state = (ring_path.read_bytes(), last["after"])
        references = {
            "report": C.J.reference(directory, directory / "report.json"),
            "plan": original["plan"],
            "baseline": C.J.reference(directory, ring_path),
        }
        source = C.source_summary(directory, original, plan, proof, ring, state, references)
    return (ring, state, source)


def source_summary(parent, original, plan, proof, ring, state, references):
    if len(ring) != 4096:
        raise ValueError("Successful parent requires actual complete current4096 ring")
    verify_state(state, state, sd_write=False)
    names = sorted(set(re.findall("rc[0-9a-f]{10}", json.dumps(plan))))
    return {
        "directory": str(parent.resolve()),
        "profile": original["profile"],
        "ended_at": original["ended_at"],
        "latest_info": state,
        "baseline_sha256": C.legacy.A.sha(ring),
        "prior_names": names,
        "references": references,
        "verification": proof,
    }


def job_proof(plan, proofs):
    if len(proofs) != len(plan["pages"]) or any(
        proof.get("pair_verified") is not True or proof.get("raw_range") != [offset, offset + 512]
        for offset, proof in zip(plan["offsets"], proofs, strict=True)
    ):
        raise ValueError("Whole job proof requires all declared full independent page audits")
    return {
        "verified": True,
        "verified_physical_ranges": [proof["raw_range"] for proof in proofs],
        "paired_bytes": len(proofs) * 512,
        "pages": proofs,
        "independent_oracle": False,
        "unique_global_coverage_not_evaluated": True,
    }
