"""Immutable physical NOR plans and iterative closed parent admission."""

import secrets
from pathlib import Path

from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import paired_nor_recipe as fixed_recipe
from rcominote.experiments import paired_nor_sources as sources
from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import scratch_reuse_sources as pins
from rcominote.experiments import scratch_system_pair_contract as legacy
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as E
from rcominote.experiments.sd_bootstrap import verify_state

# Preserve the public evidence API while sharing its exact recipe implementation.
recipe, actions, payload = fixed_recipe.recipe, fixed_recipe.actions, fixed_recipe.payload
parent_gate, source_summary, old = sources.parent_gate, sources.source_summary, sources.old

PROFILE = "bounded-physical-nor-paired-pages-v2"
PAGE_PROFILE = "immutable-physical-nor-pair-page-v2"
PROFILE_V3 = "bounded-physical-nor-paired-pages-v3"
PAGE_PROFILE_V3 = "immutable-physical-nor-pair-page-v3"
PAGE_PROFILE_V4 = "immutable-physical-nor-pair-page-v4"
PAGE_PROFILE_V5 = "immutable-physical-nor-pair-page-v5"
CHECKPOINT_PROFILE = "verified-failed-page-communication-checkpoint-v1"
KNOWN_CONTROL = "single-connection-two-known-pairs-v1"
CONTINUOUS_CONTROL = "single-connection-continuous-two-known-pairs-v1"
STATUS_CONTROL = "single-connection-known-pairs-status-literals-v2"
FORMAT_CONTROL = "single-connection-known-pairs-formatter-constants-v3"
CONTENT_CHECKPOINT_PROFILE = "verified-content-failure-communication-checkpoint-v2"
RECOVERY_PROFILE = "readonly-owned-current-after-wait-fast-timeout-v1"
PREFILL_PROFILE = "verified-ram-prefill-strict-known-nor-control-v1"
PREFILL_PROFILE_V2 = "verified-ram-prefill-strict-known-nor-control-v2"
PREFILL_PROFILES = (PREFILL_PROFILE, PREFILL_PROFILE_V2)
PREFILLED_PROFILE = "bounded-physical-nor-ram-prefilled-pairs-v1"
PREFILLED_PAGE = "immutable-physical-nor-ram-prefilled-pair-v1"
PREFILLED_LINK_CP = "pinned-prefilled-preproducer-link-failure-prefix-checkpoint-v1"
PREFILLED_NOTICE_CP = "pinned-prefilled-os-notice-content-ownership-checkpoint-v1"
PREFILLED_STARTUP_CP = "pinned-prefilled-default-preproducer-ownership-checkpoint-v1"
LEGACY_PINS = {
    "report.json": "6795c06151b1c0d4a902e07ac1e43a52b52dd188ae9a7fce2debcad12e736911",
    "plan.json": "c2a3027b1d03ed6c889b8cc7b8cc76329be392d09f42ca8c5707ed9850fd0b55",
    "session.btsnoop": "4bba453a3654e5d60e725d78e77aea0cce74861506503911b175a57206ddb7d3",
    "second/download.bin": "96a615b8f0e4d8e115fed262e2b4afa1684839194a7a0417394295342e49ef9c",
}
BUDGET = legacy.BUDGET.copy()
BUDGET["max_verified_bytes"] = BUDGET.pop("new_raw_nor_coverage_bytes")
ACTIONS_POLICY = legacy.ACTIONS_POLICY
STAGES = legacy.STAGES
FIELDS = (*legacy.FIELDS, "nor_offset", "page_index", "future_nonces", "predecessor_ended_at")
CONTROL_FIELDS = (*legacy.FIELDS, "prefix_policy")
CONTROL_BUDGET = {
    "connections": 1,
    "downloads": 6,
    "producers": 4,
    "sd_writes": 4,
    "new_files": 0,
    "parameter_transactions": 17,
    "max_verified_bytes": 1024,
    "new_raw_nor_coverage_bytes": 0,
}


CONTINUOUS_BUDGET = CONTROL_BUDGET | {"downloads": 5, "parameter_transactions": 15}


def is_control(plan):
    return plan["profile"] in (KNOWN_CONTROL, CONTINUOUS_CONTROL, STATUS_CONTROL, FORMAT_CONTROL)


def is_continuous(plan):
    return plan["profile"] in (CONTINUOUS_CONTROL, STATUS_CONTROL, FORMAT_CONTROL)


def control_budget(plan):
    return CONTINUOUS_BUDGET if is_continuous(plan) else CONTROL_BUDGET


def stages(plan):
    from rcominote.experiments import prefilled_nor_pages as prefilled

    return prefilled.STAGES if plan["profile"] in (PREFILLED_PROFILE, PREFILLED_PAGE) else STAGES


def fields(plan):
    if plan["profile"] == PREFILLED_PAGE:
        return (*FIELDS, "ram_oracle", "gap_policy", "content_policy")
    return (*FIELDS, "prefix_policy") if "prefix_policy" in plan else FIELDS


def policy_gate(plan, *, page=False):
    if plan.get("profile") == (PREFILLED_PAGE if page else PREFILLED_PROFILE):
        from rcominote.experiments import prefilled_nor_pages

        return prefilled_nor_pages.policy_gate(plan)
    exact = {
        PAGE_PROFILE_V4 if page else STATUS_CONTROL: F.STATUS_POLICY,
        PAGE_PROFILE_V5 if page else FORMAT_CONTROL: F.FORMAT_POLICY,
    }
    if plan.get("profile") in exact:
        if plan.get("prefix_policy") != exact[plan["profile"]]:
            raise ValueError("Requires exact explicit formatter policy for this profile")
        return
    old_profile, new_profile = (PAGE_PROFILE, PAGE_PROFILE_V3) if page else (PROFILE, PROFILE_V3)
    if plan.get("profile") == old_profile:
        if "prefix_policy" in plan:
            raise ValueError("Legacy v2 must retain strict default prefix proof")
    elif (
        plan.get("profile")
        not in ((new_profile,) if page else (new_profile, KNOWN_CONTROL, CONTINUOUS_CONTROL))
        or plan.get("prefix_policy") != F.PADDING_POLICY
    ):
        raise ValueError("Requires exact explicit v3 canonical address-padding policy")


def offsets_gate(offsets):
    if (
        not isinstance(offsets, list)
        or not 1 <= len(offsets) <= 4
        or any(type(n) is not int or n % 512 or not 0 <= n <= 0x400000 - 512 for n in offsets)
        or len(set(offsets)) != len(offsets)
    ):
        raise ValueError("Requires explicit finite1..4 unique aligned physical NOR512 offsets")


def budgets(count):
    return {
        "connections": count,
        "downloads": count * 3,
        "producers": count * 2,
        "sd_writes": count * 2,
        "new_files": 0,
        "parameter_transactions": count * 9,
        "max_verified_bytes": count * 512,
    }


def validate_plan(plan):
    from rcominote.experiments import prefilled_nor_control as prefill
    from rcominote.experiments import prefilled_nor_pages

    policy_gate(plan)
    seeded = plan["profile"] == PREFILLED_PROFILE
    offsets_gate(plan["offsets"])
    count = len(plan["offsets"])
    if (
        plan.get("name") != F.NAME
        or plan.get("address_space") != "physical-4MiB-NOR"
        or plan.get("budget")
        != (
            prefilled_nor_pages.budgets(count, startup_policy=plan.get("startup_policy"))
            if seeded
            else control_budget(plan)
            if is_control(plan)
            else budgets(count)
        )
        or any(type(plan["budget"][k]) is not int for k in plan["budget"])
        or plan.get("page_budget") != (prefilled_nor_pages.page_budget(plan) if seeded else BUDGET)
        or any(type(value) is not int for value in plan["page_budget"].values())
        or plan.get("startup_policy")
        not in ((startup.LEGACY_POLICY, startup.POLICY) if seeded else (startup.LEGACY_POLICY,))
        or plan.get("status_event_policy") != E.POLICY
        or plan.get("actions_policy") != (prefilled_nor_pages.ACTIONS_POLICY if seeded else ACTIONS_POLICY)
        or plan.get("independent_oracle") is not is_control(plan)
        or plan.get("expected_before") != plan["parent"]["latest_info"]
        or plan.get("parent", {}).get("profile")
        not in (
            legacy.PROFILE,
            PROFILE,
            PROFILE_V3,
            CHECKPOINT_PROFILE,
            KNOWN_CONTROL,
            CONTINUOUS_CONTROL,
            STATUS_CONTROL,
            FORMAT_CONTROL,
            CONTENT_CHECKPOINT_PROFILE,
            RECOVERY_PROFILE,
            *PREFILL_PROFILES,
            PREFILLED_PROFILE,
            PREFILLED_LINK_CP,
            PREFILLED_NOTICE_CP,
            PREFILLED_STARTUP_CP,
        )
        or len(plan["pages"]) != count
    ):
        raise ValueError("Immutable bounded NOR job profile/budget/policy/parent differs")
    if is_control(plan) and (
        plan["offsets"] != [0, 0x4200]
        or plan.get("oracles") != pins.oracles()
        or plan.get("stage_timeout_scope")
        != ("five" if is_continuous(plan) else "six") + "-post-startup-stages18-each-under-single-active60"
    ):
        raise ValueError("Known control requires fixed boot0/4200 and independent pinned raw oracles")
    if not seeded and plan["parent"]["profile"] in (
        PREFILLED_LINK_CP,
        PREFILLED_NOTICE_CP,
        PREFILLED_STARTUP_CP,
    ):
        raise ValueError("Pinned preproducer link checkpoint seeds only prefilled unknown jobs")
    if seeded and plan["parent"]["profile"] not in (
        PREFILL_PROFILE_V2,
        PREFILLED_PROFILE,
        PREFILLED_LINK_CP,
        PREFILLED_NOTICE_CP,
        PREFILLED_STARTUP_CP,
    ):
        raise ValueError("Prefilled unknown admission requires successful knownV2 or prefilled-pair parent")
    names = []
    for index, (offset, slot) in enumerate(zip(plan["offsets"], plan["pages"], strict=True)):
        if (
            slot.get("page_index") != index
            or type(slot["page_index"]) is not int
            or slot.get("nor_offset") != offset
            or type(slot["nor_offset"]) is not int
            or slot.get("directory") != f"page{index}-{offset:06x}"
            or len(slot["operations"]) != (4 if seeded else 2)
            or [op.get("operation_id") for op in slot["operations"]]
            != list(prefilled_nor_pages.STAGES[1:] if seeded else ("first", "second"))
            or seeded
            and [op.get("kind") for op in slot["operations"]] != ["prefill", "nor", "prefill", "nor"]
        ):
            raise ValueError("Page address/order/directory/two producer slots changed")
        for op in slot["operations"]:
            (prefill.recipe if seeded else recipe)(op)
            if seeded and op["kind"] == "prefill":
                continue
            if op.get("prefix_policy") != plan.get("prefix_policy"):
                raise ValueError("Producer policy differs from frozen whole-job policy")
            if op["nor_offset"] != offset:
                raise ValueError("Producer address differs from declared page")
            names.append(op["nonce"])
    if len(set(names)) != 2 * count or set(names).intersection(plan["parent"]["prior_names"]):
        raise ValueError("All2N predeclared nonces must be distinct and fresh across parent chain")
    verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    J.time_order(plan["parent"]["ended_at"], plan["planned_at"])
    if "created_at" in plan["parent"]:
        J.time_order(plan["parent"]["created_at"], plan["planned_at"])


def _prepare(image: Path, parent: Path, offsets: list[int], *, prefix_policy=F.STRICT_POLICY):
    if type(prefix_policy) is not str or prefix_policy not in (F.STRICT_POLICY, F.PADDING_POLICY):
        raise ValueError("Unknown explicit prefix policy before parent admission")
    offsets_gate(offsets)
    baseline, state, source = parent_gate(parent, image)
    pages = []
    for index, offset in enumerate(offsets):
        ops = []
        for label in ("first", "second"):
            nonce = "rc" + secrets.token_hex(5)
            ops.append(
                {
                    "operation_id": label,
                    "name": F.NAME,
                    "nonce": nonce,
                    "nor_offset": offset,
                    "uptime_command": f"kernel uptime {nonce}",
                    "producer": f"dbg fread spi_flash {'0' if offset == 0 else hex(offset)}",
                    "dump_command": F.DUMP,
                }
            )
        pages.append(
            {
                "page_index": index,
                "nor_offset": offset,
                "directory": f"page{index}-{offset:06x}",
                "operations": ops,
            }
        )
    plan = {
        "profile": PROFILE,
        "name": F.NAME,
        "address_space": "physical-4MiB-NOR",
        "offsets": offsets.copy(),
        "pages": pages,
        "planned_at": S.now(),
        "parent": source,
        "expected_before": state,
        "budget": budgets(len(pages)),
        "page_budget": BUDGET.copy(),
        "startup_policy": startup.LEGACY_POLICY,
        "status_event_policy": E.POLICY,
        "actions_policy": ACTIONS_POLICY,
        "independent_oracle": False,
    }
    if prefix_policy == F.PADDING_POLICY:
        plan.update(profile=PROFILE_V3, prefix_policy=prefix_policy)
        for slot in pages:
            for op in slot["operations"]:
                op["prefix_policy"] = prefix_policy
    return plan, baseline


def prepare(image: Path, parent: Path, offsets: list[int], *, prefix_policy=F.STRICT_POLICY):
    plan, baseline = _prepare(image, parent, offsets, prefix_policy=prefix_policy)
    validate_plan(plan)
    F.absent(baseline, nonces(plan))
    return plan, baseline


def nonces(plan, start=0):
    return [
        op["nonce"]
        for page in plan["pages"][start:]
        for op in page["operations"]
        if op.get("kind", "nor") == "nor"
    ]


def source_gate(plan, image):
    validate_plan(plan)
    baseline, state, source = parent_gate(Path(plan["parent"]["directory"]), image)
    if source != plan["parent"] or state != plan["expected_before"]:
        raise ValueError("Original successful parent/current object differs from frozen plan")
    F.absent(baseline, nonces(plan))
    if plan["profile"] == PREFILLED_PROFILE:
        from rcominote.experiments import prefilled_nor_pages

        prefilled_nor_pages.source_ram(plan, image)
    return baseline


def page_plan(plan, index, state, ended_at):
    validate_plan(plan)
    if plan["profile"] == PREFILLED_PROFILE:
        from rcominote.experiments import prefilled_nor_pages

        return prefilled_nor_pages.page_plan(plan, index, state, ended_at)
    slot = plan["pages"][index]
    result = {
        "profile": PAGE_PROFILE,
        "page_index": index,
        "nor_offset": slot["nor_offset"],
        "expected_before": state,
        "predecessor_ended_at": ended_at,
        "planned_at": plan["planned_at"],
        "budget": BUDGET.copy(),
        "actions_policy": ACTIONS_POLICY,
        "stage_timeout_scope": legacy.STAGE_SCOPE,
        "startup_policy": startup.LEGACY_POLICY,
        "status_event_policy": E.POLICY,
        "operations": slot["operations"],
        "future_nonces": nonces(plan, index),
    }
    if "prefix_policy" in plan:
        result.update(
            profile={STATUS_CONTROL: PAGE_PROFILE_V4, FORMAT_CONTROL: PAGE_PROFILE_V5}.get(
                plan["profile"], PAGE_PROFILE_V3
            ),
            prefix_policy=plan["prefix_policy"],
        )
    return result


def validate_page(plan):
    if plan["profile"] == PREFILLED_PAGE:
        from rcominote.experiments import prefilled_nor_pages

        return prefilled_nor_pages.validate_page(plan)
    policy_gate(plan, page=True)
    offsets_gate([plan["nor_offset"]])
    if (
        plan.get("budget") != BUDGET
        or any(type(plan["budget"][k]) is not int for k in BUDGET)
        or plan.get("actions_policy") != ACTIONS_POLICY
        or plan.get("stage_timeout_scope") != legacy.STAGE_SCOPE
        or plan.get("startup_policy") != startup.LEGACY_POLICY
        or plan.get("status_event_policy") != E.POLICY
        or len(plan["operations"]) != 2
        or [op["operation_id"] for op in plan["operations"]] != ["first", "second"]
        or plan["future_nonces"][:2] != [op["nonce"] for op in plan["operations"]]
    ):
        raise ValueError("Page policy/slots/future nonces differ")
    for op in plan["operations"]:
        recipe(op)
        if op.get("prefix_policy") != plan.get("prefix_policy"):
            raise ValueError("Page producer prefix policy differs")
        if op["nor_offset"] != plan["nor_offset"]:
            raise ValueError("Page operation target differs")
    verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    J.time_order(plan["planned_at"])
    J.time_order(plan["predecessor_ended_at"])


def report(plan):
    validate_page(plan)
    return {key: plan[key] for key in fields(plan)} | {
        "started_at": S.now(),
        "transport": {},
        "ok": False,
        "baseline": {"operation_id": "baseline", "name": F.NAME, "live_complete": False, "ok": False},
        "operations": [op | {"live_complete": False, "ok": False} for op in plan["operations"]],
    }


def prepare_known_control(image: Path, parent: Path):
    plan, baseline = prepare(image, parent, [0, 0x4200], prefix_policy=F.PADDING_POLICY)
    plan.update(
        profile=KNOWN_CONTROL,
        budget=CONTROL_BUDGET.copy(),
        oracles=pins.oracles(),
        independent_oracle=True,
        stage_timeout_scope="six-post-startup-stages18-each-under-single-active60",
    )
    validate_plan(plan)
    return plan, baseline


def control_report(plan):
    validate_plan(plan)
    if not is_control(plan):
        raise ValueError("Requires fixed two-known-group control plan")
    groups = []
    for index in range(2):
        group = report(page_plan(plan, index, plan["expected_before"], plan["parent"]["ended_at"]))
        groups.append(
            {
                "group_index": index,
                "nor_offset": plan["offsets"][index],
                "baseline": group["baseline"],
                "operations": group["operations"],
                "live_complete": False,
                "candidate": False,
            }
        )
    if is_continuous(plan):
        del groups[1]["baseline"]
        groups[1]["continuation"] = None
    return {key: plan[key] for key in CONTROL_FIELDS} | {
        "started_at": S.now(),
        "transport": {},
        "groups": groups,
        "ok": False,
    }


def prepare_continuous_control(image: Path, parent: Path):
    plan, baseline = prepare_known_control(image, parent)
    plan.update(
        profile=CONTINUOUS_CONTROL,
        budget=CONTINUOUS_BUDGET.copy(),
        stage_timeout_scope="five-post-startup-stages18-each-under-single-active60",
    )
    validate_plan(plan)
    return plan, baseline


def _prepare_formatter_control(image, parent, profile, policy):
    plan, baseline = prepare_continuous_control(image, parent)
    plan.update(profile=profile, prefix_policy=policy)
    for slot in plan["pages"]:
        for op in slot["operations"]:
            op["prefix_policy"] = policy
    validate_plan(plan)
    return plan, baseline


def prepare_status_control(image: Path, parent: Path):
    return _prepare_formatter_control(image, parent, STATUS_CONTROL, F.STATUS_POLICY)


def prepare_formatter_control(image: Path, parent: Path):
    return _prepare_formatter_control(image, parent, FORMAT_CONTROL, F.FORMAT_POLICY)


def continuation(op):
    return {
        "group_index": 0,
        "operation_id": "second",
        "download_sha256": op["download_sha256"],
        "download_span": [op["download_start"], op["download_end"]],
        "verified_end": op["verified_end"],
        "after": op["after"],
        "slow_settlement": op["slow_settlement"],
    }


def oracle(plan, index):
    item = plan["oracles"]["boot0" if index == 0 else "4200"]
    raw = Path(item["source"]["file"]).read_bytes()
    if pins.sha(raw) != item["source"]["sha256"] or len(raw) != item["source"]["bytes"]:
        raise ValueError("Known control independent whole raw oracle source changed")
    data = raw[slice(*item["slice"])]
    if len(data) != 512 or pins.sha(data) != item["sha256"]:
        raise ValueError("Known control independent512 oracle slice changed")
    return data
