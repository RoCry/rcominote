"""Fixed known NOR observations after independently verified same-file RAM prefill.

Only the contiguous logical file-prefix model is claimed; no SD atomicity proof.
"""

import json
import secrets
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import sd_bootstrap as RAM
from rcominote.experiments.sd_bridge import console_packet
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE

PROFILE = "verified-ram-prefill-strict-known-nor-control-v1"
PROFILE_V2 = "verified-ram-prefill-strict-known-nor-control-v2"
PROFILES = (PROFILE, PROFILE_V2)
RAM_SHA = RAM.ORACLE_SHA
RAM_SLICE = (0xDD500, 0xDE500)
RAM_DUMP = f"dbg dumpbuf {RAM.ADDRESS} 4096 /SD:/RECORDER/Call-{C.F.NAME}.mp3"
COPY_REGIONS = (
    (0x9C1DE, 0x9C1E8, "4cb5a8e7a3769819a1f2503ef0c1368c6241b41b1b3344c2af84d6b6d53f5c92"),
    (0x9C204, 0x9C210, "4a839be18cfe2f7e38cc98f04d16b0136328a95cfeab1bb5df4333e6e72d7ffc"),
)
BUDGET = {
    "connections": 1,
    "downloads": 5,
    "producers": 2,
    "ram_exports": 2,
    "sd_writes": 4,
    "new_files": 0,
    "nor_writes": 0,
    "ram_writes": 0,
    "deletes": 0,
    "parameter_transactions": 15,
    "active_seconds": 60,
    "monitor_seconds": 70,
    "stage_seconds": 18,
    "new_raw_nor_coverage_bytes": 0,
}
FIELDS = ("profile", "expected_before", "budget", "startup_policy", "status_event_policy", "content_policy")


def fields(plan):
    return (*FIELDS, "gap_policy") if plan.get("profile") == PROFILE_V2 else FIELDS


def ram_source(image):
    raw, image_ref = C.pins.pinned(image, C.pins.IMAGE_SHA)
    data = raw[slice(*RAM_SLICE)]
    regions = []
    for start, end, digest in COPY_REGIONS:
        code = raw[start:end]
        if A.A.sha(code) != digest:
            raise ValueError("Fixed RAM initialization instruction/literal source changed")
        regions.append(
            {"cpu_range": [0x10000000 + start, 0x10000000 + end], "hex": code.hex(), "sha256": digest}
        )
    if len(data) != 4096 or A.A.sha(data) != RAM_SHA or data[-1] != 0x48:
        raise ValueError("Requires complete independent RAM4096 oracle ending48")
    return data, {
        "image": image_ref,
        "image_slice": list(RAM_SLICE),
        "cpu_address": RAM.ADDRESS,
        "bytes": 4096,
        "sha256": RAM_SHA,
        "last_byte": "48",
        "static_initialization": regions,
        "permanent_ram_stability_assumed": False,
    }


def nonces(plan):
    return [op["nonce"] for op in plan["operations"] if op["kind"] == "nor"]


def recipe(op):
    if op.get("kind") == "prefill":
        if (
            op.get("operation_id") not in ("prefill-first", "prefill-second")
            or op.get("name") != C.F.NAME
            or op.get("dump_command") != RAM_DUMP
            or any(k in op for k in ("producer", "nonce", "nor_offset", "prefix_policy"))
        ):
            raise ValueError("Prefill must remain the sole fixed readonly RAM dump to owned file")
        return [PREPARE, START, console_packet(RAM_DUMP), STOP]
    if op.get("kind") != "nor" or "prefix_policy" in op:
        raise ValueError("Known NOR requires original strict parser without formatter policy")
    return C.recipe(op)


def actions(report, op):
    return A.A.action_frames(report, op, expected=recipe(op)) | {
        "f0_frames": sum(frame["command"] == 0xF0 for frame in op["frames"])
    }


def validate_plan(plan):
    if (
        plan.get("profile") not in PROFILES
        or plan.get("name") != C.F.NAME
        or plan.get("offsets") != [0, 0x4200]
        or any(type(offset) is not int for offset in plan["offsets"])
        or plan.get("budget") != BUDGET
        or any(type(plan["budget"][k]) is not int for k in BUDGET)
        or plan.get("expected_before") != plan["parent"]["latest_info"]
        or plan.get("startup_policy") != C.startup.LEGACY_POLICY
        or plan.get("status_event_policy") != C.E.POLICY
        or plan.get("content_policy") != C.F.STRICT_POLICY
        or plan.get("oracles") != C.pins.oracles()
        or plan.get("ram_oracle", {}).get("sha256") != RAM_SHA
        or plan["ram_oracle"].get("last_byte") != "48"
        or plan["ram_oracle"].get("bytes") != 4096
        or plan["ram_oracle"].get("cpu_address") != RAM.ADDRESS
        or plan["ram_oracle"].get("image_slice") != list(RAM_SLICE)
        or plan["ram_oracle"].get("permanent_ram_stability_assumed") is not False
        or len(plan["operations"]) != 4
        or [(op.get("operation_id"), op.get("kind")) for op in plan["operations"]]
        != [("prefill-first", "prefill"), ("first", "nor"), ("prefill-second", "prefill"), ("second", "nor")]
    ):
        raise ValueError("Requires explicit bounded known0/4200 prefill control with strict content")
    if (
        plan.get("gap_policy") != C.F.PREFILL_GAP_POLICY
        if plan["profile"] == PROFILE_V2
        else "gap_policy" in plan
    ):
        raise ValueError("Explicit profile must bind its exact producer/dump gap policy")
    if plan["parent"].get("profile") in (C.PREFILLED_LINK_CP, C.PREFILLED_NOTICE_CP, C.PREFILLED_STARTUP_CP):
        raise ValueError("Pinned link checkpoint is restricted to prefilled unknown acquisition")
    for index, op in enumerate(plan["operations"]):
        recipe(op)
        if op["kind"] == "nor" and op["nor_offset"] != plan["offsets"][index // 2]:
            raise ValueError("NOR stage differs from fixed known target")
    names = nonces(plan)
    if len(set(names)) != 2 or set(names).intersection(plan["parent"]["prior_names"]):
        raise ValueError("Both predeclared NOR nonces must be fresh across entire ancestor history")
    A.verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    C.J.time_order(plan["parent"]["ended_at"], plan["planned_at"])
    if "created_at" in plan["parent"]:
        C.J.time_order(plan["parent"]["created_at"], plan["planned_at"])


def _prepare(image, parent, *, profile):
    baseline, state, source = C.parent_gate(parent, image)
    _ram, oracle = ram_source(image)
    operations = []
    for label, offset in (("first", 0), ("second", 0x4200)):
        nonce = "rc" + secrets.token_hex(5)
        operations += [
            {
                "operation_id": f"prefill-{label}",
                "kind": "prefill",
                "name": C.F.NAME,
                "dump_command": RAM_DUMP,
            },
            {
                "operation_id": label,
                "kind": "nor",
                "name": C.F.NAME,
                "nonce": nonce,
                "nor_offset": offset,
                "uptime_command": f"kernel uptime {nonce}",
                "producer": f"dbg fread spi_flash {'0' if offset == 0 else hex(offset)}",
                "dump_command": C.F.DUMP,
            },
        ]
    plan = {
        "profile": profile,
        "name": C.F.NAME,
        "offsets": [0, 0x4200],
        "operations": operations,
        "parent": source,
        "expected_before": state,
        "ram_oracle": oracle,
        "oracles": C.pins.oracles(),
        "budget": BUDGET.copy(),
        "startup_policy": C.startup.LEGACY_POLICY,
        "status_event_policy": C.E.POLICY,
        "content_policy": C.F.STRICT_POLICY,
        "planned_at": C.S.now(),
    }
    if profile == PROFILE_V2:
        plan["gap_policy"] = C.F.PREFILL_GAP_POLICY
    validate_plan(plan)
    C.F.absent(baseline, nonces(plan))
    return plan, baseline


def prepare(image, parent):
    return _prepare(image, parent, profile=PROFILE)


def prepare_v2(image, parent):
    return _prepare(image, parent, profile=PROFILE_V2)


def source_gate(plan, image):
    validate_plan(plan)
    baseline, state, parent = C.parent_gate(Path(plan["parent"]["directory"]), image)
    _ram, oracle = ram_source(image)
    if parent != plan["parent"] or state != plan["expected_before"] or oracle != plan["ram_oracle"]:
        raise ValueError("Original admitted current file/state/RAM source changed")
    C.F.absent(baseline, nonces(plan))
    return baseline


def report(plan):
    validate_plan(plan)
    return {k: plan[k] for k in fields(plan)} | {
        "started_at": C.S.now(),
        "transport": {},
        "ok": False,
        "baseline": {"operation_id": "baseline", "name": C.F.NAME, "ok": False, "live_complete": False},
        "operations": [op | {"ok": False, "live_complete": False} for op in plan["operations"]],
    }


def plan_gate(actual, plan, out):
    validate_plan(plan)
    if (
        actual["plan"]["file"] != "plan.json"
        or json.loads(C.J.check_reference(out, actual["plan"]).read_bytes()) != plan
        or any(actual.get(k) != plan[k] for k in fields(plan))
        or len(actual["operations"]) != 4
        or actual["baseline"].get("name") != C.F.NAME
        or actual["baseline"].get("operation_id") != "baseline"
        or "groups" in actual
        or "operation" in actual
        or any(
            any(op.get(k) != v for k, v in slot.items())
            for slot, op in zip(plan["operations"], actual["operations"], strict=True)
        )
    ):
        raise ValueError("Actual prefill report differs from immutable fixed stages before I/O")


def content(op, current, previous, ram, plan, marker_history):
    if (
        any(not isinstance(value, bytes) or len(value) != 4096 for value in (current, previous, ram))
        or A.A.sha(ram) != RAM_SHA
        or ram[-1] != 0x48
    ):
        raise ValueError("Requires complete current/predecessor and independent RAM oracle")
    if op["kind"] == "prefill":
        if current != ram or len(current) != 4096 or current[-1] != 0x48:
            raise ValueError("Current full RAM prefill differs from independent4096 oracle")
        return {
            "verified": True,
            "ram_prefill": True,
            "bytes": 4096,
            "sha256": A.A.sha(current),
            "last_byte": "48",
            "permanent_ram_stability_assumed": False,
        }
    if previous != ram or current[-1] == 0x48:
        raise ValueError("NOR must immediately follow verified RAM prefill and change its final byte")
    sector, freshness = C.F.parse_prefilled_ring(
        current,
        previous,
        marker_history,
        nonce=op["nonce"],
        nor_offset=op["nor_offset"],
        **({"gap_policy": plan["gap_policy"]} if plan["profile"] == PROFILE_V2 else {}),
    )
    decoded = {"freshness": freshness, "sector_hex": sector.hex()}
    if (
        decoded["freshness"]["difference_proven_written_prefix_bytes"] != 4096
        or "prefix_policy" in decoded["freshness"]
    ):
        raise ValueError("Requires entire4096 difference-proven prefix with original strict parser")
    sector = bytes.fromhex(decoded["sector_hex"])
    return decoded | {"oracle": A.oracle_proof(plan, 0 if op["nor_offset"] == 0 else 1, sector)}


def communication(actual, out, plan, baseline, ram, *, operation_count=4):
    from rcominote.experiments import prefilled_nor_pages

    return prefilled_nor_pages.communication(
        actual, out, plan, baseline, ram, operation_count=operation_count
    )


def validate(actual, out, plan, baseline, ram, *, archived=False):
    if archived and actual.get("ok") is not True:
        raise ValueError("Original failed prefill control cannot be promoted")
    stages = [actual["baseline"], *actual["operations"]]
    if any(stage.get("live_complete") is not True or stage.get("ok") is not True for stage in stages):
        raise ValueError("All five original stages must complete before whole control succeeds")
    transfers, _context, events = communication(actual, out, plan, baseline, ram)
    observations, previous, marker_history = [], baseline, baseline
    for op, data in zip(actual["operations"], transfers, strict=True):
        proof = content(op, data, previous, ram, plan, marker_history)
        if proof != op["verification"]:
            raise ValueError("Stage current RAM/NOR strict proof changed")
        if op["kind"] == "nor":
            if (out / op["operation_id"] / "sector.bin").read_bytes() != bytes.fromhex(proof["sector_hex"]):
                raise ValueError("Known sector file differs from own current strict chain")
            marker_history = data
            observations.append(
                {"offset": op["nor_offset"], "nonce": op["nonce"], "sha256": proof["oracle"]["sha256"]}
            )
        previous = data
    proof = {
        "verified": True,
        "known_control": True,
        "connections": 1,
        "downloads": 5,
        "producers": 2,
        "ram_exports": 2,
        "sd_writes": 4,
        "new_files": 0,
        "parameter_transactions": 15,
        "content_policy": C.F.STRICT_POLICY,
        "known_observations": observations,
        "ram_oracle_sha256": A.A.sha(ram),
        "new_raw_nor_coverage_bytes": 0,
        "status_events": events,
    }
    if plan["profile"] == PROFILE_V2:
        proof["gap_policy"] = plan["gap_policy"]
    if archived and proof != actual["verification"]:
        raise ValueError("Original complete structural control proof changed")
    return proof


def replay_admitted(actual, plan, directory, source, baseline, image):
    if actual.get("ok") is not True or plan["parent"] != source:
        raise ValueError("Failed or changed-source structural control cannot be adopted")
    ram, oracle = ram_source(image)
    if oracle != plan["ram_oracle"]:
        raise ValueError("Structural RAM source changed")
    proof = validate(actual, directory, plan, baseline, ram, archived=True)
    path = directory / "second/download.bin"
    current, state = path.read_bytes(), actual["after"]
    refs = {
        "report": C.J.reference(directory, directory / "report.json"),
        "plan": actual["plan"],
        "baseline": C.J.reference(directory, path),
    }
    return current, state, C.source_summary(directory, actual, plan, proof, current, state, refs)


def replay(directory: Path, image: Path):
    original = json.loads((directory / "report.json").read_bytes())
    if original.get("profile") not in PROFILES or original.get("ok") is not True:
        raise ValueError("Original failed/non-structural control cannot be promoted")
    return C.parent_gate(directory, image)[2]["verification"]
