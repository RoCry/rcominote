"""Live readonly ownership recovery after a narrowly admitted WAIT_FAST failure.

This node proves only the present dedicated file/state, never failed NOR content.
"""

import asyncio
import copy
import json
from datetime import datetime
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_checkpoint as K
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import scratch_postmortem_probe as readonly
from rcominote.experiments import scratch_reuse_probe as shared
from rcominote.experiments import window_ram_probe as R
from rcominote.experiments.sd_bootstrap import verify_state

PROFILE = "readonly-owned-current-after-wait-fast-timeout-v1"
OMITTED = "Final identity omitted after timeout/cancellation; no new read command"
PINS = {
    "report.json": "ff24dee4e05c0a17e9ab29fd60aa2e89feb2dbd937562baf11c510085c68917b",
    "plan.json": "1be029f508a9f037a962af0d49c74fa3fa6f73cf64465f426094bf7cd690e016",
    "session.btsnoop": "f60ee8f383f3f9ec4d38b4c05481c41cd30c4b3f13725b29a07e2a2f15fa9b06",
    "source-snapshot/manifest.json": "92e2ec882e0ff5cdfcd11e18c6045b24b4d052aecb67666c96fdb3a256845051",
}
CODE = {
    "paired_nor_plan.py": "a05b84c34a6630a272011f759fce21e4ebe713678b63fea20bae7f50a9d48317",
    "paired_nor_audit.py": "1f47d4f8d4d9702372db04caa2111b4af9c912ae993a7b15f4b031db9c6ae67d",
    "paired_nor_runtime.py": "019d2535694a7738ef1396c29f31bc8189b78b4749f43ad57d1965d8b193f472",
    "scratch_reuse_parser.py": "471c517b5ad6e62cd3698a7018a47befec2f51e6b62607b05b62670a05c7915f",
}
BUDGET = {
    "connections": 1,
    "downloads": 1,
    "parameter_transactions": 3,
    "actions": 0,
    "producers": 0,
    "sd_writes": 0,
    "new_files": 0,
    "new_raw_nor_coverage_bytes": 0,
    "prior_unverified_sd_write_attempts": 1,
    "active_seconds": 42,
    "monitor_seconds": 55,
    "stage_seconds": 18,
    "download_seconds": 8,
    "identity_seconds": 3,
    "disconnect_observation_seconds": 8,
    "scan_seconds": 12,
}
FIELDS = ("profile", "expected_before", "budget", "startup_policy", "status_event_policy")


def stage_time(owner, stage):
    C.J.time_order(owner["started_at"], stage["started_at"], stage["ended_at"], owner["ended_at"])
    if (
        datetime.fromisoformat(stage["ended_at"]) - datetime.fromisoformat(stage["started_at"])
    ).total_seconds() > 18:
        raise ValueError("Post-startup readonly/producer stage exceeds18 seconds")


def receive_guard(conn, pdu):
    readonly.no_actions(pdu)
    if pdu[:3] == b"\x1b\x2a\0" and not conn.offline_allowed:
        raise ValueError("Readonly offline bytes outside sole active download")


def failed_source(failed, source, baseline):
    references = {name: C.pins.pinned(failed / name, digest)[1] for name, digest in PINS.items()}
    report = json.loads((failed / "report.json").read_bytes())
    plan = json.loads(C.J.check_reference(failed, report["plan"]).read_bytes())
    C.validate_plan(plan)
    if (
        plan["profile"] != C.KNOWN_CONTROL
        or report["plan"]["file"] != "plan.json"
        or plan["parent"] != source
        or report.get("ok") is not False
        or report.get("error") != "TimeoutError: "
        or report.get("capture_error") != "TimeoutError: "
        or report.get("after_error") != OMITTED
        or any(k in report for k in ("after", "after_span", "state_verification", "verification"))
        or any(report.get(k) != plan[k] for k in C.CONTROL_FIELDS)
        or len(report["groups"]) != 2
    ):
        raise ValueError("Requires original failed known control with sole WAIT_FAST timeout")
    view = copy.deepcopy(report)
    for key in ("error", "capture_error", "after_error"):
        del view[key]
    first_group, last_group = report["groups"]
    attempted, untouched = last_group["operations"]
    if (
        first_group.get("candidate") is not True
        or first_group.get("live_complete") is not True
        or last_group.get("candidate") is not False
        or last_group.get("live_complete") is not False
        or attempted.get("error") != "TimeoutError: "
        or attempted.get("ok") is not False
        or attempted.get("live_complete") is not False
        or attempted.get("producer_attempted") is not True
        or attempted.get("sd_write_attempted") is not True
        or any(
            k in attempted
            for k in (
                "normalization",
                "normalization_requested_us",
                "download_start",
                "download_verification",
                "pre_download_fast",
                "barrier_complete",
                "verification",
                "after",
            )
        )
        or untouched != plan["pages"][1]["operations"][1] | {"live_complete": False, "ok": False}
    ):
        raise ValueError(
            "Failure must follow last six ACKs before FAST/normalization/download; later slot untouched"
        )
    del view["groups"][1]["operations"][0]["error"]
    A.common.no_errors(view)
    snapshot = K.snapshot(failed, code=CODE)
    C.J.time_order(
        json.loads((failed / "source-snapshot/manifest.json").read_bytes())["created_at"],
        report["started_at"],
    )
    observed, wire, events = A.envelope(report, failed, 11)
    if report["predecessor_state_verification"] != verify_state(
        plan["expected_before"], report["before"], sd_write=False
    ):
        raise ValueError("Failed source initial state differs from admitted successful ancestor")
    A.E.bridge(report, report["before_span"][1], report["file_list_span"][0])
    if A.inventory(report, plan) != report["listed_count"]:
        raise ValueError("Failed source visible inventory changed")
    startup = observed["transactions"][0]
    if report["startup_settlement"] != startup or report["startup_classification"] != C.startup.classify(
        startup
    ):
        raise ValueError("Failed source startup must remain exact FAST")
    context = {
        "state": report["before"],
        "boundary": report["file_list_span"][1],
        "previous_tx": startup,
        "cursor": 1,
        "previous": baseline,
    }
    previous = baseline
    for index, group in enumerate(report["groups"]):
        if (
            group.get("group_index") != index
            or group.get("nor_offset") != plan["offsets"][index]
            or len(group["operations"]) != 2
            or any(key in group for key in ("ok", "disconnect", "disconnect_observation"))
        ):
            raise ValueError("Failed source fixed group/slot order changed")
        path = failed / plan["pages"][index]["directory"]
        page = C.page_plan(plan, index, context["state"], context.get("ended_at", source["ended_at"]))
        C.J.time_order(context.get("ended_at", source["ended_at"]), group["baseline"]["started_at"])
        stages = [group["baseline"], *(group["operations"] if index == 0 else [])]
        warm = group["baseline"]
        if (
            warm.get("operation_id") != "baseline"
            or warm.get("name") != C.F.NAME
            or any(key in warm for key in ("actions_start", "producer", "sd_write_attempted"))
        ):
            raise ValueError("Original baseline must remain fixed readonly download")
        for stage in stages:
            if stage.get("ok") is not True or stage.get("live_complete") is not True:
                raise ValueError("All four prior download/barrier stages must originally complete")
            stage_time(report, stage)
        transfers, context = A.transfer_group(
            report, group, page, path, observed, wire, context, operation_count=2 if index == 0 else 0
        )
        for op, data in zip(group["operations"][: len(transfers)], transfers, strict=True):
            decoded = C.payload(op, data, previous)
            sector = bytes.fromhex(decoded["sector_hex"])
            if (
                decoded != op["verification"]
                or (path / op["operation_id"] / "sector.bin").read_bytes() != sector
                or A.oracle_proof(plan, index, sector) != op["oracle_verification"]
            ):
                raise ValueError("Originally complete known group content/oracle changed")
            previous = data
        if index == 1 and any(
            p.is_file() for label in ("first", "second") for p in (path / label).rglob("*")
        ):
            raise ValueError(
                "Failed WAIT_FAST producer or untouched later slot has unexpected download/files"
            )
    if (
        any(attempted.get(k) != v for k, v in plan["pages"][1]["operations"][0].items())
        or attempted["before"] != context["state"]
        or C.actions(report, attempted) != attempted["actions_verification"]
    ):
        raise ValueError("Last attempted Actions recipe/state/six-ACK receipt changed")
    A.E.bridge(report, context["boundary"], attempted["actions_start"])
    A.E.bridge(report, attempted["actions_end"], len(report["att_packets"]))
    C.J.time_order(context["ended_at"], attempted["started_at"], attempted["ended_at"], report["ended_at"])
    stage_time(report, attempted)
    ended_us = A.P.H.EPOCH_US + int(datetime.fromisoformat(attempted["ended_at"]).timestamp() * 1_000_000)
    if context["cursor"] != 11 or ended_us - wire[attempted["actions_end"] - 1][2] < 8_000_000:
        raise ValueError("WAIT_FAST failure lacks full eight-second no-negotiation evidence")
    C.J.time_order(source["ended_at"], plan["planned_at"], report["started_at"], report["ended_at"])
    return {
        "directory": str(failed.resolve()),
        "references": references,
        "source_snapshot": snapshot,
        "ended_at": report["ended_at"],
        "last_verified_state": context["state"],
        "historical_ring_sha256": A.A.sha(context["previous"]),
        "prior_names": sorted(set(source["prior_names"]) | set(C.nonces(plan))),
        "current_file_unknown": True,
        "original_failed_retained": True,
        "parameter_transactions": 11,
        "complete_downloads": 4,
        "last_actions": attempted["actions_verification"],
        "status_events": events,
        "pending_prior_writes": 1,
    }


def validate_plan(plan):
    if (
        plan.get("profile") != PROFILE
        or plan.get("name") != C.F.NAME
        or plan.get("budget") != BUDGET
        or any(type(plan["budget"][k]) is not int for k in BUDGET)
        or plan.get("startup_policy") != C.startup.LEGACY_POLICY
        or plan.get("status_event_policy") != C.E.POLICY
        or plan.get("expected_before") != plan["failed"]["last_verified_state"]
        or plan["failed"].get("current_file_unknown") is not True
        or plan["failed"].get("original_failed_retained") is not True
        or plan["failed"].get("pending_prior_writes") != 1
        or type(plan["failed"]["pending_prior_writes"]) is not int
        or any(k in plan for k in ("operations", "pages", "nonce", "nor_offset", "offsets"))
    ):
        raise ValueError(
            "Requires fixed zero-write ownership recovery with exactly one pending prior overwrite"
        )
    verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    C.J.time_order(plan["parent"]["ended_at"], plan["failed"]["ended_at"], plan["planned_at"])


def prepare(image, failed):
    original = json.loads((failed / "report.json").read_bytes())
    old_plan = json.loads(C.J.check_reference(failed, original["plan"]).read_bytes())
    baseline, _state, parent = C.parent_gate(Path(old_plan["parent"]["directory"]), image)
    evidence = failed_source(failed, parent, baseline)
    plan = {
        "profile": PROFILE,
        "name": C.F.NAME,
        "parent": parent,
        "failed": evidence,
        "expected_before": evidence["last_verified_state"],
        "budget": BUDGET.copy(),
        "startup_policy": C.startup.LEGACY_POLICY,
        "status_event_policy": C.E.POLICY,
        "planned_at": C.S.now(),
    }
    validate_plan(plan)
    return plan


def source_gate(plan, image):
    validate_plan(plan)
    baseline, _state, parent = C.parent_gate(Path(plan["parent"]["directory"]), image)
    if (
        parent != plan["parent"]
        or failed_source(Path(plan["failed"]["directory"]), parent, baseline) != plan["failed"]
    ):
        raise ValueError("Original successful ancestor/failed communication evidence changed")
    return baseline


def report(plan):
    validate_plan(plan)
    return {k: plan[k] for k in FIELDS} | {
        "started_at": C.S.now(),
        "transport": {},
        "ok": False,
        "sd_write_attempted": False,
        "producer_attempted": False,
        "operation": {"operation_id": "retained", "name": C.F.NAME, "live_complete": False, "ok": False},
    }


def plan_gate(actual, plan, out):
    validate_plan(plan)
    if (
        actual["plan"]["file"] != "plan.json"
        or json.loads(C.J.check_reference(out, actual["plan"]).read_bytes()) != plan
        or any(actual.get(k) != plan[k] for k in FIELDS)
        or actual.get("sd_write_attempted") is not False
        or actual.get("producer_attempted") is not False
        or actual["operation"].get("name") != C.F.NAME
        or actual["operation"].get("operation_id") != "retained"
        or any(k in actual for k in ("operations", "groups"))
    ):
        raise ValueError("Readonly report differs from immutable zero-write plan")


async def connected(conn, monitor, actual, plan, out):
    failure, op = None, actual["operation"]
    try:
        await shared.identity(conn, actual, "before", plan["expected_before"], writing=True)
        start = len(actual["att_packets"])
        try:
            actual["listed_count"] = len(await conn.file_list())
        finally:
            actual["file_list_span"] = [start, len(actual["att_packets"])]
        tx, classification = await C.startup.wait_startup(
            monitor, conn, actual["transport"]["link"], seconds=12
        )
        actual.update(startup_settlement=tx, startup_classification=classification)
        plan_gate(actual, plan, out)
        op.update(before=actual["before"], started_at=C.S.now())
        async with asyncio.timeout(18):
            await R.normalize(monitor, conn, actual, op, 1)
            await shared.download(conn, actual, op, out / "retained")
            await shared.finish_stage(conn, monitor, actual, op, 2, actual["before"], writing=False)
        op.update(ended_at=C.S.now(), live_complete=True)
    except BaseException as error:
        failure = error
        if "started_at" in op:
            op.update(ended_at=C.S.now(), error=f"{type(error).__name__}: {error}")
        raise
    finally:
        if isinstance(failure, (TimeoutError, asyncio.CancelledError)):
            actual["after_error"] = OMITTED
        else:
            try:
                await shared.identity(conn, actual, "after", actual["before"])
                R.observe(monitor, conn, actual["transport"]["link"])
            except BaseException as error:
                actual["after_error"] = f"{type(error).__name__}: {error}"
                if failure is None:
                    raise


def validate_readonly(actual, out, plan):
    plan_gate(actual, plan, out)
    A.common.no_errors(actual)
    op = actual["operation"]
    if op.get("live_complete") is not True or any(
        k in op for k in ("producer", "writes", "frames", "actions_start", "sd_write_attempted", "nonce")
    ):
        raise ValueError("Only original complete readonly fixed4096 transfer permitted")
    stage_time(actual, op)
    C.J.time_order(plan["failed"]["ended_at"], plan["planned_at"], actual["started_at"], op["started_at"])
    observed, wire, events = A.envelope(actual, out, 3)
    initial = verify_state(plan["expected_before"], actual["before"], sd_write=True)
    if actual["predecessor_state_verification"] != initial:
        raise ValueError("Initial state exceeds exactly one prior unverified overwrite allowance")
    A.E.bridge(actual, actual["before_span"][1], actual["file_list_span"][0])
    if A.common.file_list(actual) != actual["listed_count"]:
        raise ValueError("Readonly inventory changed")
    startup, normal, slow = observed["transactions"]
    if (
        actual["startup_settlement"] != startup
        or actual["startup_classification"] != C.startup.classify(startup)
        or op["before"] != actual["before"]
    ):
        raise ValueError("Readonly startup must remain exactly FAST before download")
    A.E.bridge(actual, actual["file_list_span"][1], op["download_start"])
    A.shared.baseline_window(actual, op, wire, startup, normal, slow)
    data = A.shared.download(actual, op, out)
    A.shared.barrier(actual, op, actual["before"], writing=False)
    A.final_identity(actual, wire, {"state": op["after"], "boundary": op["verified_end"], "cursor": 3}, 3)
    return {
        "verified": True,
        "ownership_only": True,
        "connections": 1,
        "downloads": 1,
        "bytes": 4096,
        "sha256": A.A.sha(data),
        "parameter_transactions": 3,
        "actions": 0,
        "producers": 0,
        "sd_writes": 0,
        "new_files": 0,
        "new_raw_nor_coverage_bytes": 0,
        "initial_state_verification": initial,
        "status_events": events,
        "original_failed_retained": True,
    }


def replay_admitted(actual, plan, directory, source, baseline):
    if actual.get("ok") is not True or actual["operation"].get("ok") is not True:
        raise ValueError("Original failed readonly recovery cannot be adopted")
    if (
        plan["parent"] != source
        or failed_source(Path(plan["failed"]["directory"]), source, baseline) != plan["failed"]
    ):
        raise ValueError("Recovery source differs from fully admitted successful ancestor/failure edge")
    proof = validate_readonly(actual, directory, plan)
    if proof != actual["verification"]:
        raise ValueError("Original readonly ownership proof changed")
    path = directory / "retained/download.bin"
    current, state = path.read_bytes(), actual["after"]
    summary = {
        "directory": str(directory.resolve()),
        "profile": PROFILE,
        "ended_at": actual["ended_at"],
        "latest_info": state,
        "baseline_sha256": A.A.sha(current),
        "prior_names": plan["failed"]["prior_names"],
        "references": {
            "report": C.J.reference(directory, directory / "report.json"),
            "plan": actual["plan"],
            "baseline": C.J.reference(directory, path),
        },
        "verification": proof,
        "original_failed_retained": True,
    }
    return current, state, summary


def main(image, plan, plan_raw, newout, *, sudo_password_stdin=False):
    from rcominote.experiments import paired_nor_runtime as runtime

    baseline = source_gate(plan, image)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    (newout / "plan.json").write_bytes(plan_raw)
    (newout / "retained").mkdir(mode=0o700)
    actual = report(plan) | {"plan": C.J.reference(newout, newout / "plan.json")}
    try:
        plan_gate(actual, plan, newout)
        if source_gate(plan, image) != baseline:
            raise ValueError("Recovery source changed before authorization")
        runtime.authorize(password_stdin=sudo_password_stdin)
        plan_gate(actual, plan, newout)
        if source_gate(plan, image) != baseline:
            raise ValueError("Recovery source changed before connection")
        asyncio.run(runtime.capture(actual, plan, baseline, newout))
        actual["ended_at"] = C.S.now()
        actual["verification"] = validate_readonly(actual, newout, plan)
        actual["operation"]["ok"], actual["ok"] = True, True
    except BaseException as error:
        actual["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        actual["ended_at"] = C.S.now()
        C.S.save(newout / "report.json", actual)


def replay(directory: Path, image: Path):
    original = json.loads((directory / "report.json").read_bytes())
    if original.get("profile") != PROFILE or original.get("ok") is not True:
        raise ValueError("Original failed/non-recovery cannot be promoted")
    return C.parent_gate(directory, image)[2]["verification"]
