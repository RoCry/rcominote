"""One fixed RAM-prefill known NOR control; no runtime address or retry option."""

import asyncio
from pathlib import Path

from rcominote.experiments import paired_nor_audit as audit
from rcominote.experiments import paired_nor_plan as plan_contract
from rcominote.experiments import paired_nor_runtime as shared
from rcominote.experiments import prefilled_nor_control as C
from rcominote.experiments import prefilled_nor_pages as pages
from rcominote.experiments import prefilled_startup as startup_control
from rcominote.experiments import scratch_reuse_probe as transfer


async def write_stage(conn, actions, monitor, report, op, context, out, ram, plan):
    cursor, state, settled = context["cursor"], context["state"], context["previous_tx"]
    snapshot = shared.R.observe(monitor, conn, report["transport"]["link"])
    if len(snapshot["transactions"]) != cursor or snapshot["pending"]:
        raise ValueError("Extra/pending negotiation before prefill/NOR; no new command")
    if op["kind"] == "nor" and context["previous"] != ram:
        raise ValueError("NOR cannot start before actual full RAM prefill oracle passes")
    future = pages.remaining(plan, op)
    plan_contract.F.absent(context["previous"], future)
    plan_contract.F.absent(context["marker_history"], future)
    op.update(before=state, started_at=plan_contract.S.now())
    target = out / op["operation_id"]
    async with asyncio.timeout(18):
        try:
            await actions.run_commands(
                op, C.recipe(op)[2:-1], sd_write_command_index=0 if op["kind"] == "prefill" else 2
            )
        finally:
            attempted = "ram_export_attempted" if op["kind"] == "prefill" else "producer_attempted"
            op[attempted] = len(op.get("writes", [])) >= (3 if op["kind"] == "prefill" else 4)
        op["actions_verification"] = C.actions(report, op)
        op["pre_download_fast"] = await shared.N.pre_download_fast(
            monitor, conn, report["transport"]["link"], cursor=cursor, required=True
        )
        current, observed, wire = await plan_contract.startup.live_wire(monitor, conn, report)
        if len(observed["transactions"]) != cursor + 1 or observed["pending"]:
            raise ValueError("Each write requires exactly one completed fresh FAST")
        op["activity_fast_verification"] = shared.W.default_activity_fast(
            current, op, settled, op["pre_download_fast"][0], wire
        )
        await shared.R.normalize(monitor, conn, report, op, cursor + 1)
        data = await transfer.download(conn, report, op, target)
        await transfer.finish_stage(conn, monitor, report, op, cursor + 2, state, writing=True)
        current, observed, wire = await plan_contract.startup.live_wire(monitor, conn, report)
        if len(observed["transactions"]) != cursor + 3 or observed["pending"]:
            raise ValueError("Write download has extra/pending parameter activity")
        shared.W.download_window(wire, op, op["normalization"], op["slow_settlement"], report=current)
        audit.shared.barrier(current, op, state, writing=True)
        op["verification"] = pages.content(
            op, data, context["previous"], ram, plan, context["marker_history"]
        )
        plan_contract.F.absent(data, pages.remaining(plan, op, after=True))
        if op["kind"] == "nor":
            with (target / "sector.bin").open("xb") as handle:
                handle.write(bytes.fromhex(op["verification"]["sector_hex"]))
            context["marker_history"] = data
    op.update(ok=True, live_complete=True, ended_at=plan_contract.S.now())
    plan_contract.S.save(target / "checkpoint.json", report)
    context.update(
        state=op["after"],
        previous=data,
        previous_tx=op["slow_settlement"],
        cursor=cursor + 3,
        boundary=op["verified_end"],
    )


async def connected(conn, actions, monitor, report, plan, baseline, out):
    failure, active = None, None
    ram, oracle = C.ram_source(Path(plan["ram_oracle"]["image"]["file"]))
    if oracle != plan["ram_oracle"]:
        raise ValueError("Pinned RAM oracle changed before any actual connection command")
    try:
        await transfer.identity(conn, report, "before", plan["expected_before"])
        start = len(report["att_packets"])
        try:
            names = {entry.name for entry in await conn.file_list()}
            report["listed_count"] = len(names)
            if names.intersection({plan_contract.F.NAME, *pages.nonces(plan)}):
                raise ValueError("Visible inventory collides with owned scratch/fresh nonces")
        finally:
            report["file_list_span"] = [start, len(report["att_packets"])]
        startup, classification = await plan_contract.startup.wait_startup(
            monitor, conn, report["transport"]["link"], policy=plan["startup_policy"], seconds=12
        )
        report.update(startup_settlement=startup, startup_classification=classification)
        settled, cursor, boundary = await startup_control.settle(
            conn, actions, monitor, report, plan, startup, classification
        )
        context = {
            "state": report["before"],
            "previous": baseline,
            "marker_history": baseline,
            "previous_tx": settled,
            "cursor": cursor,
            "boundary": boundary,
        }
        active = report["baseline"]
        pages.plan_gate(report, plan, out)
        await shared.baseline_transfer(
            conn, monitor, report, active, context, out / "baseline", pages.nonces(plan)
        )
        for op in report["operations"]:
            active = op
            pages.plan_gate(report, plan, out)
            await write_stage(conn, actions, monitor, report, op, context, out, ram, plan)
    except BaseException as error:
        failure = error
        if active is not None and "started_at" in active:
            active.update(ended_at=plan_contract.S.now(), error=f"{type(error).__name__}: {error}")
        raise
    finally:
        if isinstance(failure, (TimeoutError, asyncio.CancelledError)):
            report["after_error"] = "Final identity omitted after timeout/cancellation; no new read command"
        else:
            try:
                await transfer.identity(conn, report, "after", shared.final_state(report))
                shared.R.observe(monitor, conn, report["transport"]["link"])
            except BaseException as error:
                report["after_error"] = f"{type(error).__name__}: {error}"
                if failure is None:
                    raise


def main(image, plan, raw, out, *, sudo_password_stdin=False):
    baseline = C.source_gate(plan, image)
    ram, _proof = C.ram_source(image)
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    (out / "plan.json").write_bytes(raw)
    for name in ("baseline", *(op["operation_id"] for op in plan["operations"])):
        (out / name).mkdir(mode=0o700)
    report = C.report(plan) | {"plan": plan_contract.J.reference(out, out / "plan.json")}
    try:
        pages.plan_gate(report, plan, out)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Structural control parent changed before authorization")
        shared.authorize(password_stdin=sudo_password_stdin)
        pages.plan_gate(report, plan, out)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Structural control parent changed before connection")
        asyncio.run(shared.capture(report, plan, baseline, out))
        report["ended_at"] = plan_contract.S.now()
        report["verification"] = C.validate(report, out, plan, baseline, ram)
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = plan_contract.S.now()
        plan_contract.S.save(out / "report.json", report)
