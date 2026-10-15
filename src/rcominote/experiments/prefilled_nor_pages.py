"""Bounded unknown NOR pairs with independently verified RAM prefill per read.

Shared complete communication audit also preserves historical known controls.
Only contiguous file-prefix freshness is claimed; no SD atomicity assumption.
"""

import json
from datetime import datetime
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_startup as startup_control

PROFILE = "bounded-physical-nor-ram-prefilled-pairs-v1"
PAGE_PROFILE = "immutable-physical-nor-ram-prefilled-pair-v1"
STAGES = ("baseline", "prefill-first", "first", "prefill-second", "second")
ACTIONS_POLICY = "prefill-four-nor-six-acks-f1-empty-pending-all-f0-retained"
STAGE_SCOPE = "five-post-startup-transfers18-each-under-single-active60"
BUDGET = {k: v for k, v in P.BUDGET.items() if k != "new_raw_nor_coverage_bytes"} | {
    "max_verified_bytes": 512
}
EXTRA_FIELDS = ("ram_oracle", "gap_policy", "content_policy")


def nonces(plan):
    return plan["future_nonces"] if plan["profile"] == PAGE_PROFILE else P.nonces(plan)


def remaining(plan, op, *, after=False):
    # A prefill is not a new nonce; preserve all future page names throughout.
    index = 0 if op["operation_id"] in ("prefill-first", "first") else 1
    return nonces(plan)[index + (after and op["kind"] == "nor") :]


def page_budget(plan):
    return startup_control.budget(BUDGET, plan["startup_policy"])


def budgets(count, *, startup_policy=C.startup.LEGACY_POLICY):
    result = {
        k: count * BUDGET[k]
        for k in (
            "connections",
            "downloads",
            "producers",
            "ram_exports",
            "sd_writes",
            "new_files",
            "nor_writes",
            "ram_writes",
            "deletes",
            "parameter_transactions",
            "max_verified_bytes",
        )
    }
    if startup_policy != C.startup.LEGACY_POLICY:
        startup_control.budget(BUDGET, startup_policy)
        del result["parameter_transactions"]
        result.update(
            max_parameter_transactions=16 * count, max_startup_pulses=count, max_startup_commands=3 * count
        )
    return result


def policy_gate(plan):
    if (
        plan.get("content_policy") != C.F.STRICT_POLICY
        or plan.get("gap_policy")
        not in (C.F.PREFILL_GAP_POLICY, C.F.PREFILL_WAKE_GAP_POLICY, C.F.PREFILL_VSYNC_GAP_POLICY)
        or "prefix_policy" in plan
        or "oracles" in plan
        or plan.get("ram_oracle", {}).get("sha256") != P.RAM_SHA
        or plan["ram_oracle"].get("bytes") != 4096
        or plan["ram_oracle"].get("last_byte") != "48"
        or plan["ram_oracle"].get("cpu_address") != P.RAM.ADDRESS
        or plan["ram_oracle"].get("image_slice") != list(P.RAM_SLICE)
        or plan["ram_oracle"].get("permanent_ram_stability_assumed") is not False
    ):
        raise ValueError(
            "Prefilled unknown pair requires strict fullprefix, explicit closed layouts and no NOR oracle"
        )


def prepare(
    image, parent, offsets, *, gap_policy=C.F.PREFILL_GAP_POLICY, startup_policy=C.startup.LEGACY_POLICY
):
    if gap_policy not in (C.F.PREFILL_GAP_POLICY, C.F.PREFILL_WAKE_GAP_POLICY, C.F.PREFILL_VSYNC_GAP_POLICY):
        raise ValueError("Unknown explicit prefilled gap policy before parent admission")
    startup_control.budget(BUDGET, startup_policy)
    plan, baseline = C._prepare(image, parent, offsets)
    _ram, oracle = P.ram_source(image)
    for slot in plan["pages"]:
        operations = []
        for op in slot["operations"]:
            operations += [
                {
                    "operation_id": "prefill-" + op["operation_id"],
                    "kind": "prefill",
                    "name": C.F.NAME,
                    "dump_command": P.RAM_DUMP,
                },
                op | {"kind": "nor"},
            ]
        slot["operations"] = operations
    plan.update(
        profile=PROFILE,
        budget=budgets(len(offsets), startup_policy=startup_policy),
        page_budget=startup_control.budget(BUDGET, startup_policy),
        startup_policy=startup_policy,
        ram_oracle=oracle,
        gap_policy=gap_policy,
        content_policy=C.F.STRICT_POLICY,
        actions_policy=ACTIONS_POLICY,
    )
    C.validate_plan(plan)
    C.F.absent(baseline, C.nonces(plan))
    return plan, baseline


def source_ram(plan, image):
    ram, oracle = P.ram_source(image)
    if oracle != plan["ram_oracle"]:
        raise ValueError("Prefilled plan's independent complete RAM source changed")
    return ram


def page_plan(plan, index, state, ended_at):
    slot = plan["pages"][index]
    return {
        "profile": PAGE_PROFILE,
        "page_index": index,
        "nor_offset": slot["nor_offset"],
        "expected_before": state,
        "predecessor_ended_at": ended_at,
        "planned_at": plan["planned_at"],
        "budget": page_budget(plan),
        "actions_policy": ACTIONS_POLICY,
        "stage_timeout_scope": STAGE_SCOPE,
        "startup_policy": plan["startup_policy"],
        "status_event_policy": plan["status_event_policy"],
        "operations": slot["operations"],
        "future_nonces": C.nonces(plan, index),
        **{k: plan[k] for k in EXTRA_FIELDS},
    }


def validate_page(plan):
    if plan.get("profile") != PAGE_PROFILE:
        raise ValueError("Requires explicit immutable prefilled page profile")
    policy_gate(plan)
    C.offsets_gate([plan["nor_offset"]])
    if (
        plan.get("budget") != page_budget(plan)
        or any(type(v) is not int for v in plan["budget"].values())
        or plan.get("actions_policy") != ACTIONS_POLICY
        or plan.get("stage_timeout_scope") != STAGE_SCOPE
        or plan.get("startup_policy") not in (C.startup.LEGACY_POLICY, startup_control.POLICY)
        or plan.get("status_event_policy") != C.E.POLICY
        or len(plan["operations"]) != 4
        or [(op.get("operation_id"), op.get("kind")) for op in plan["operations"]]
        != [("prefill-first", "prefill"), ("first", "nor"), ("prefill-second", "prefill"), ("second", "nor")]
        or plan["future_nonces"][:2] != [op["nonce"] for op in plan["operations"] if op["kind"] == "nor"]
    ):
        raise ValueError("Immutable prefilled page stages/budgets/future nonces differ")
    for op in plan["operations"]:
        P.recipe(op)
        if op["kind"] == "nor" and op["nor_offset"] != plan["nor_offset"]:
            raise ValueError("Prefilled producer differs from immutable page target")
    A.verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    C.J.time_order(plan["predecessor_ended_at"])


def plan_gate(actual, plan, out):
    if plan["profile"] in P.PROFILES:
        return P.plan_gate(actual, plan, out)
    validate_page(plan)
    job = json.loads(C.J.check_reference(out.parent, actual["plan"]).read_bytes())
    C.validate_plan(job)
    if (
        actual["plan"]["file"] != "plan.json"
        or job["profile"] != PROFILE
        or out.name != job["pages"][plan["page_index"]]["directory"]
        or C.page_plan(job, plan["page_index"], plan["expected_before"], plan["predecessor_ended_at"]) != plan
        or any(actual.get(k) != plan[k] for k in C.fields(plan))
        or len(actual["operations"]) != 4
        or any(
            any(op.get(k) != v for k, v in slot.items())
            for slot, op in zip(plan["operations"], actual["operations"], strict=True)
        )
        or actual["baseline"].get("operation_id") != "baseline"
        or actual["baseline"].get("name") != C.F.NAME
    ):
        raise ValueError("Actual prefilled page differs from immutable original job slot")


def content(op, current, previous, ram, plan, marker_history):
    if plan["profile"] in P.PROFILES:
        return P.content(op, current, previous, ram, plan, marker_history)
    validate_page(plan)
    if op not in plan["operations"]:
        # Reports contain evidence in addition to their immutable slot.
        slot = next((s for s in plan["operations"] if s["operation_id"] == op["operation_id"]), None)
        if slot is None or any(op.get(k) != v for k, v in slot.items()):
            raise ValueError("Content target differs from immutable prefilled page slot")
    if op["kind"] == "prefill":
        return P.content(op, current, previous, ram, plan, marker_history)
    if (
        any(not isinstance(v, bytes) or len(v) != 4096 for v in (current, previous, ram))
        or previous != ram
        or A.A.sha(ram) != plan["ram_oracle"]["sha256"]
        or ram[-1] != 0x48
        or current[-1] == 0x48
    ):
        raise ValueError("Unknown NOR requires just-verified full RAM prefill and changed final byte")
    sector, proof = C.F._parse_ring(
        current,
        previous,
        nonce=op["nonce"],
        nor_offset=plan["nor_offset"],
        marker_previous=marker_history,
        gap_policy=plan["gap_policy"],
    )
    if proof["difference_proven_written_prefix_bytes"] != 4096:
        raise ValueError("Unknown page requires strict complete4096 difference prefix")
    return {
        "freshness": proof | {"target_profile": PAGE_PROFILE},
        "sector_hex": sector.hex(),
        "independent_oracle": False,
    }


def communication(actual, out, plan, baseline, ram, *, operation_count=4):
    """Audit original complete transfers, without asserting producer content/success.

    N2 retains all four original slots; callers must independently bind the
    original content-only failure and untouched remaining slots.
    """
    if type(operation_count) is not int or operation_count not in (2, 4):
        raise ValueError("Communication requires exactly two or four original write stages")
    plan_gate(actual, plan, out)
    if len(ram) != 4096 or A.A.sha(ram) != plan["ram_oracle"]["sha256"] or ram[-1] != 0x48:
        raise ValueError("Audit RAM argument differs from pinned complete independent oracle")
    A.common.no_errors(actual)
    stages = [actual["baseline"], *actual["operations"][:operation_count]]
    C.J.time_order(
        plan["predecessor_ended_at"] if plan["profile"] == PAGE_PROFILE else plan["parent"]["ended_at"],
        actual["started_at"],
        actual["ended_at"],
    )
    C.J.time_order(plan["planned_at"], actual["started_at"])
    for stage in stages:
        C.J.time_order(actual["started_at"], stage["started_at"], stage["ended_at"], actual["ended_at"])
        if (
            datetime.fromisoformat(stage["ended_at"]) - datetime.fromisoformat(stage["started_at"])
        ).total_seconds() > 18:
            raise ValueError("Original stage exceeds18-second bounded deadline")
    extra = startup_control.extra(actual, plan)
    transactions = 3 + extra + 3 * operation_count
    observed, wire, events = A.envelope(actual, out, transactions)
    if actual["predecessor_state_verification"] != A.verify_state(
        plan["expected_before"], actual["before"], sd_write=False
    ):
        raise ValueError("Initial actual identity differs from admitted latest state")
    A.E.bridge(actual, actual["before_span"][1], actual["file_list_span"][0])
    if A.common.file_list(actual) != actual["listed_count"]:
        raise ValueError("Original inventory changed")
    for row in A.E.rows(actual, *actual["file_list_span"])[1:]:
        _, data = A.Boyi.parse(bytes.fromhex(row["hex"])[3:])
        if data[:1] == b"\0" and A.Boyi.parse_file_entry(data).name in {C.F.NAME, *nonces(plan)}:
            raise ValueError("Visible inventory collides with dedicated file or fresh nonces")
    startup, startup_boundary, startup_proof = startup_control.audit(actual, plan, observed, wire)
    warm = actual["baseline"]
    if warm["before"] != actual["before"] or any(
        k in warm for k in ("actions_start", "sd_write_attempted", "producer")
    ):
        raise ValueError("Initial baseline must remain readonly")
    A.E.bridge(actual, startup_boundary, warm["download_start"])
    A.shared.baseline_window(actual, warm, wire, startup, *observed["transactions"][1 + extra : 3 + extra])
    previous = A.shared.download(actual, warm, out)
    if previous != baseline:
        raise ValueError("Initial full owned file differs from admitted predecessor")
    C.F.absent(previous, nonces(plan))
    A.shared.barrier(actual, warm, actual["before"], writing=False)
    state, boundary, settled, cursor, ended = (
        warm["after"],
        warm["verified_end"],
        warm["slow_settlement"],
        3 + extra,
        warm["ended_at"],
    )
    transfers = []
    for op in actual["operations"][:operation_count]:
        if op["before"] != state or op.get("sd_write_attempted") is not True:
            raise ValueError("Stage lacks actual immediate state/predecessor or SD attempt")
        attempted = "ram_export_attempted" if op["kind"] == "prefill" else "producer_attempted"
        if op.get(attempted) is not True:
            raise ValueError("Exact RAM/NOR operation was not attempted")
        if op["kind"] == "prefill" and op.get("producer_attempted"):
            raise ValueError("RAM export cannot be reported as a NOR producer")
        C.J.time_order(ended, op["started_at"])
        A.E.bridge(actual, boundary, op["actions_start"])
        A.E.bridge(actual, op["actions_end"], op["download_start"])
        if P.actions(actual, op) != op["actions_verification"]:
            raise ValueError("Original exact4/6ACK Actions evidence changed")
        normal, slow, cursor = A.W.parameter_stage(
            observed["transactions"], cursor, op, settled, first_fast_required=True
        )
        if op["activity_fast_verification"] != A.W.default_activity_fast(
            actual, op, settled, op["pre_download_fast"][0], wire
        ):
            raise ValueError("Stage FAST request is stale or precedes current Actions")
        A.W.download_window(wire, op, normal, slow, report=actual)
        data = A.shared.download(actual, op, out)
        A.shared.barrier(actual, op, state, writing=True)
        transfers.append(data)
        C.F.absent(
            data,
            remaining(plan, op, after=True),
        )
        previous, state, boundary, settled, ended = (
            data,
            op["after"],
            op["verified_end"],
            slow,
            op["ended_at"],
        )
    context = {"state": state, "boundary": boundary, "cursor": cursor}
    if startup_control.enabled(plan):
        context["startup_control"] = startup_proof
    A.final_identity(actual, wire, context, transactions)
    return transfers, context, events


def validate(actual, out, plan, baseline):
    C.validate_page(plan)
    stages = [actual["baseline"], *actual["operations"]]
    if any(s.get("ok") is not True or s.get("live_complete") is not True for s in stages):
        raise ValueError("All five original stages must complete before unknown pair acceptance")
    ram = source_ram(plan, Path(plan["ram_oracle"]["image"]["file"]))
    transfers, context, events = communication(actual, out, plan, baseline, ram)
    previous, history, sectors, observations = baseline, baseline, [], []
    for op, data in zip(actual["operations"], transfers, strict=True):
        proof = content(op, data, previous, ram, plan, history)
        if proof != op["verification"]:
            raise ValueError("Prefilled stage's original strict content proof changed")
        if op["kind"] == "nor":
            sector = bytes.fromhex(proof["sector_hex"])
            if (out / op["operation_id"] / "sector.bin").read_bytes() != sector:
                raise ValueError("Prefilled sector differs from own full retained current file")
            sectors.append(sector)
            observations.append(
                {
                    "operation": op["operation_id"],
                    "nonce": op["nonce"],
                    "ring_sha256": A.A.sha(data),
                    "sector_sha256": A.A.sha(sector),
                }
            )
            history = data
        previous = data
    if len(sectors) != 2 or any(len(s) != 512 for s in sectors) or sectors[0] != sectors[1]:
        raise ValueError("Two complete independent unknown NOR sectors differ; no oracle filling")
    result = {
        "verified": True,
        "pair_verified": True,
        "connections": 1,
        "downloads": 5,
        "producers": 2,
        "ram_exports": 2,
        "sd_writes": 4,
        "new_files": 0,
        "parameter_transactions": context["cursor"],
        "raw_range": [plan["nor_offset"], plan["nor_offset"] + 512],
        "bytes": 512,
        "paired_bytes": 512,
        "sha256": A.A.sha(sectors[0]),
        "observations": observations,
        "independent_oracle": False,
        "content_policy": C.F.STRICT_POLICY,
        "gap_policy": plan["gap_policy"],
        "status_events": events,
    }
    if startup_control.enabled(plan):
        result.update(startup_policy=plan["startup_policy"], startup_control=context["startup_control"])
    return result
