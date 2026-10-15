"""Bounded immutable-plan NOR pages; no runtime address selection or retry."""

import asyncio
import json
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import hci_interval as H
from rcominote.experiments import paired_nor_audit as audit
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import scratch_reuse_probe as shared
from rcominote.experiments import startup_ram_probe as closing
from rcominote.experiments import window_nor_audit as W
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments import window_ram_probe as R
from rcominote.experiments.dual_client import Actions, DualConnection
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize
from rcominote.experiments.hci_monitor import Snoop
from rcominote.log_probe import NOTIFY


def private_output(out):
    private_root = Path(__file__).resolve().parents[3] / "artifacts"
    if out.resolve() == private_root.resolve() or not out.resolve().is_relative_to(private_root.resolve()):
        raise ValueError("All physical NOR captures must stay in a new private repo artifacts directory")


def save_job(out, job):
    # Only the active job journal is replaced. Plans and original page evidence
    # use exclusive creation and become immutable once appended to the ledger.
    temporary = out / "report.pending.json"
    temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(out / "report.json")


def plan_gate(report, plan, out):
    from rcominote.experiments import owned_file_recovery as recovery
    from rcominote.experiments import prefilled_nor_control as prefill

    if plan["profile"] in prefill.PROFILES:
        return prefill.plan_gate(report, plan, out)
    if plan["profile"] == recovery.PROFILE:
        return recovery.plan_gate(report, plan, out)
    if C.is_control(plan):
        C.validate_plan(plan)
        if (
            report["plan"]["file"] != "plan.json"
            or json.loads(J.check_reference(out, report["plan"]).read_bytes()) != plan
            or any(report.get(k) != plan[k] for k in C.CONTROL_FIELDS)
            or len(report["groups"]) != 2
        ):
            raise ValueError("Known control differs from immutable plan before I/O")
        for index, group in enumerate(report["groups"]):
            if (
                group.get("group_index") != index
                or group.get("nor_offset") != plan["offsets"][index]
                or len(group["operations"]) != 2
            ):
                raise ValueError("Known control group/baseline/producer slots differ")
            if C.is_continuous(plan) and index == 1:
                if "baseline" in group or (
                    report["groups"][0]["candidate"]
                    and group.get("continuation") != C.continuation(report["groups"][0]["operations"][-1])
                ):
                    raise ValueError("Continuous group requires real prior second, never fabricated baseline")
            elif (
                group["baseline"].get("name") != C.F.NAME
                or group["baseline"].get("operation_id") != "baseline"
            ):
                raise ValueError("Fixed readonly baseline changed")
            for slot, op in zip(plan["pages"][index]["operations"], group["operations"], strict=True):
                if any(op.get(k) != v for k, v in slot.items()):
                    raise ValueError("Known control producer differs before I/O")
        return
    C.policy_gate(report, page=True)
    job = json.loads(J.check_reference(out.parent, report["plan"]).read_bytes())
    C.validate_plan(job)
    index = plan["page_index"]
    saved = json.loads((out.parent / "report.json").read_bytes())
    audit.job_gate(saved, job, out.parent)
    if report["plan"] != saved["plan"]:
        raise ValueError("Page plan reference differs from original job")
    if len(saved["completed"]) != index or out.name != job["pages"][index]["directory"]:
        raise ValueError("Page must follow exactly the saved completed prefix")
    state, ended = job["expected_before"], job["parent"]["ended_at"]
    if index:
        receipt = saved["completed"][-1]
        previous = json.loads(J.check_reference(out.parent, receipt["report"]).read_bytes())
        audit.original_success(previous)
        state, ended = previous["after"], previous["ended_at"]
        if state != receipt["after"] or ended != receipt["ended_at"]:
            raise ValueError("Saved predecessor state differs from original completed receipt")
    expected = C.page_plan(job, index, state, ended)
    if expected != plan or any(report.get(key) != plan[key] for key in C.fields(plan)):
        raise ValueError("Page differs from immutable job slot before I/O")
    if (
        len(report.get("operations", [])) != len(plan["operations"])
        or any(
            any(op.get(key) != value for key, value in slot.items())
            for slot, op in zip(plan["operations"], report["operations"], strict=True)
        )
        or report["baseline"].get("name") != C.F.NAME
        or report["baseline"].get("operation_id") != "baseline"
    ):
        raise ValueError("Actual page producer/baseline slots differ before I/O")


def final_state(report):
    groups = report.get("groups", [report])
    owners = [
        stage
        for group in groups
        for stage in [*([group["baseline"]] if "baseline" in group else []), *group["operations"]]
    ]
    for owner in reversed(owners):
        if owner.get("barrier_complete") is True:
            audit.shared.barrier(report, owner, owner["before"], writing=owner["operation_id"] != "baseline")
            return owner["after"]
    return report["before"]


async def baseline_transfer(conn, monitor, report, warm, context, target, future):
    warm.update(before=context["state"], started_at=S.now())
    cursor, previous_tx, boundary = context["cursor"], context["previous_tx"], context["boundary"]
    async with asyncio.timeout(18):
        snapshot = R.observe(monitor, conn, report["transport"]["link"])
        if len(snapshot["transactions"]) != cursor or snapshot["pending"]:
            raise ValueError("Extra/pending negotiation before readonly baseline")
        await R.normalize(monitor, conn, report, warm, cursor)
        data = await shared.download(conn, report, warm, target)
        await shared.finish_stage(conn, monitor, report, warm, cursor + 1, context["state"], writing=False)
        if data != context["previous"]:
            raise ValueError("Live readonly baseline differs from actual complete predecessor file")
        C.F.absent(data, future)
        current, observed, wire = await C.startup.live_wire(monitor, conn, report)
        if len(observed["transactions"]) != cursor + 2 or observed["pending"]:
            raise ValueError("Readonly baseline requires exactly host6 and EOF SLOW")
        normal, slow = observed["transactions"][cursor : cursor + 2]
        if cursor != 1 and not (
            wire[boundary - 1][1] < normal["request"]["record"]
            and wire[boundary - 1][2] < normal["request"]["timestamp_us"]
        ):
            raise ValueError("Continuation host normalization precedes prior final identity response")
        audit.shared.baseline_window(current, warm, wire, previous_tx, normal, slow)
        audit.shared.barrier(current, warm, context["state"], writing=False)
    warm.update(live_complete=True, ok=True, ended_at=S.now())
    S.save(target / "checkpoint.json", report)
    context.update(
        state=warm["after"], previous=data, previous_tx=slow, cursor=cursor + 2, boundary=warm["verified_end"]
    )


async def producer_transfer(
    conn, actions, monitor, report, op, context, target, future, *, control_plan=None, group_index=0
):
    cursor, state, previous_tx = context["cursor"], context["state"], context["previous_tx"]
    snapshot = R.observe(monitor, conn, report["transport"]["link"])
    if len(snapshot["transactions"]) != cursor or snapshot["pending"]:
        raise ValueError("Extra/pending negotiation before producer; no Actions attempted")
    op.update(before=state, started_at=S.now(), producer_attempted=False)
    async with asyncio.timeout(18):
        try:
            await actions.run_commands(op, C.recipe(op)[2:-1], sd_write_command_index=2)
        finally:
            op["producer_attempted"] = len(op.get("writes", [])) >= 4
        op["actions_verification"] = C.actions(report, op)
        op["pre_download_fast"] = await N.pre_download_fast(
            monitor, conn, report["transport"]["link"], cursor=cursor, required=True
        )
        current, observed, wire = await C.startup.live_wire(monitor, conn, report)
        if len(observed["transactions"]) != cursor + 1 or observed["pending"]:
            raise ValueError("Each producer requires exactly one new completed FAST")
        op["activity_fast_verification"] = W.default_activity_fast(
            current, op, previous_tx, op["pre_download_fast"][0], wire
        )
        await R.normalize(monitor, conn, report, op, cursor + 1)
        data = await shared.download(conn, report, op, target)
        await shared.finish_stage(conn, monitor, report, op, cursor + 2, state, writing=True)
        current, observed, wire = await C.startup.live_wire(monitor, conn, report)
        if len(observed["transactions"]) != cursor + 3 or observed["pending"]:
            raise ValueError("Producer download has extra/pending negotiation")
        W.download_window(wire, op, op["normalization"], op["slow_settlement"], report=current)
        audit.shared.barrier(current, op, state, writing=True)
        op["verification"] = C.payload(op, data, context["previous"])
        C.F.absent(data, future)
        sector = bytes.fromhex(op["verification"]["sector_hex"])
        if control_plan is not None:
            op["oracle_verification"] = audit.oracle_proof(control_plan, group_index, sector)
        with (target / "sector.bin").open("xb") as handle:
            handle.write(sector)
    op.update(live_complete=True, ok=True, ended_at=S.now())
    S.save(target / "checkpoint.json", report)
    context.update(
        state=op["after"],
        previous=data,
        previous_tx=op["slow_settlement"],
        cursor=cursor + 3,
        boundary=op["verified_end"],
    )


async def connected(conn, actions, monitor, report, plan, baseline, out):
    failure, active = None, None
    link, control = report["transport"]["link"], C.is_control(plan)
    future = C.nonces(plan) if control else plan["future_nonces"]
    try:
        await shared.identity(conn, report, "before", plan["expected_before"])
        start = len(report["att_packets"])
        try:
            names = {entry.name for entry in await conn.file_list()}
            report["listed_count"] = len(names)
            if names.intersection({C.F.NAME, *future}):
                raise ValueError("Visible inventory collides with dedicated scratch/fresh nonces")
        finally:
            report["file_list_span"] = [start, len(report["att_packets"])]
        tx, classification = await C.startup.wait_startup(monitor, conn, link, seconds=12)
        report.update(startup_settlement=tx, startup_classification=classification)
        context = {
            "state": report["before"],
            "previous": baseline,
            "previous_tx": tx,
            "cursor": 1,
            "boundary": report["file_list_span"][1],
        }
        for index, group in enumerate(report["groups"] if control else [report]):
            directory = out / plan["pages"][index]["directory"] if control else out
            remaining = C.nonces(plan, index) if control else future
            if C.is_continuous(plan) and index == 1:
                group["continuation"] = C.continuation(report["groups"][0]["operations"][-1])
                C.F.absent(context["previous"], remaining)
            else:
                active = group["baseline"]
                plan_gate(report, plan, out)
                await baseline_transfer(
                    conn, monitor, report, active, context, directory / "baseline", remaining
                )
            for number, op in enumerate(group["operations"]):
                active = op
                plan_gate(report, plan, out)
                await producer_transfer(
                    conn,
                    actions,
                    monitor,
                    report,
                    op,
                    context,
                    directory / op["operation_id"],
                    remaining[number + 1 :],
                    control_plan=plan if control else None,
                    group_index=index,
                )
            if control:
                group.update(live_complete=True, candidate=True)
                S.save(directory / "candidate.json", report)
    except BaseException as error:
        failure = error
        if active is not None and "started_at" in active:
            active.update(ended_at=S.now(), error=f"{type(error).__name__}: {error}")
        raise
    finally:
        if isinstance(failure, (TimeoutError, asyncio.CancelledError)):
            report["after_error"] = "Final identity omitted after timeout/cancellation; no new read command"
        else:
            try:
                await shared.identity(conn, report, "after", final_state(report))
                R.observe(monitor, conn, link)
            except BaseException as error:
                report["after_error"] = f"{type(error).__name__}: {error}"
                if failure is None:
                    raise


async def capture(report, plan, baseline, out):
    from rcominote.experiments import owned_file_recovery as recovery
    from rcominote.experiments import prefilled_nor_runtime as prefill_runtime

    recovering = plan["profile"] == recovery.PROFILE
    plan_gate(report, plan, out)
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != H.PEER:
        raise ValueError("Scanned peer differs from fixed owned peer")
    monitor = Monitor(out, snoop=Snoop(), seconds=55 if recovering else 70)
    failure = None
    try:
        # Readiness/GATT included60; cancellation adds bounded STOP2/close8.
        async with asyncio.timeout(42 if recovering else 60):
            await monitor.start()
            conn = DualConnection(device, report)
            N.attach_status_observer(conn, report)
            actions = None if recovering else Actions(conn, report)
            if recovering:
                conn.client.receive_guard = lambda pdu: recovery.receive_guard(conn, pdu)
            connection_failure = None
            try:
                async with conn:
                    try:
                        await conn.client.start_notify(
                            NOTIFY,
                            recovery.readonly.forbidden_notification if recovering else actions.receive,
                        )
                        report["setup_end"] = len(report["att_packets"])
                        report["gatt_proof"] = A.setup(report)
                        report["transport"]["link"] = active_link(conn)
                        if plan["profile"] in (*C.PREFILL_PROFILES, C.PREFILLED_PAGE):
                            await prefill_runtime.connected(
                                conn, actions, monitor, report, plan, baseline, out
                            )
                        elif recovering:
                            await recovery.connected(conn, monitor, report, plan, out)
                        else:
                            await connected(conn, actions, monitor, report, plan, baseline, out)
                    finally:
                        report["close_requested_us"] = H.timestamp_us()
            except BaseException as error:
                connection_failure = error
                raise
            finally:
                report["close_completed_us"] = H.timestamp_us()
                if report["transport"].get("link"):
                    try:
                        await closing.observe_disconnect(monitor, report)
                    except BaseException as error:
                        report["disconnect_error"] = f"{type(error).__name__}: {error}"
                        if connection_failure is None:
                            raise
    except BaseException as error:
        failure = error
        report["capture_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        try:
            report["monitor_stop"] = monitor.stop
            report["monitor_exit"] = await monitor.close()
            raw = monitor.path.read_bytes()
            report["hci_capture"] = {
                "bytes": len(raw),
                "sha256": A.sha(raw),
                "records": monitor.snoop.records,
            }
            if report.get("att_packets") and report["transport"].get("link"):
                report["att_hci_binding"] = dual_hci.bind(report, raw)
        except BaseException as error:
            report["final_evidence_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


def main(image: Path, planpath: Path, newout: Path, sudo_password_stdin: bool = False):
    # Prepare is a separate host-only operation; runtime has no address argument.
    private_output(newout)
    plan_raw = planpath.read_bytes()
    plan = json.loads(plan_raw)
    from rcominote.experiments import owned_file_recovery as recovery

    if plan.get("profile") == recovery.PROFILE:
        return recovery.main(image, plan, plan_raw, newout, sudo_password_stdin=sudo_password_stdin)
    if plan.get("profile") in C.PREFILL_PROFILES:
        from rcominote.experiments import prefilled_nor_runtime

        return prefilled_nor_runtime.main(
            image, plan, plan_raw, newout, sudo_password_stdin=sudo_password_stdin
        )
    C.validate_plan(plan)
    baseline = C.source_gate(plan, image)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    (newout / "plan.json").write_bytes(plan_raw)
    for slot in plan["pages"]:
        for label in C.stages(plan):
            if C.is_continuous(plan) and slot["page_index"] == 1 and label == "baseline":
                continue
            (newout / slot["directory"] / label).mkdir(parents=True, mode=0o700)
    if C.is_control(plan):
        return control_main(image, plan, baseline, newout, sudo_password_stdin=sudo_password_stdin)
    job = {
        "profile": plan["profile"],
        "budget": plan["budget"],
        "started_at": S.now(),
        "plan": J.reference(newout, newout / "plan.json"),
        "completed": [],
        "ok": False,
    }
    try:
        job["ended_at"] = S.now()
        save_job(newout, job)
        audit.job_gate(job, plan, newout)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Successful parent changed before authorization")
        authorize(password_stdin=sudo_password_stdin)
        for index, slot in enumerate(plan["pages"]):
            # Independently replay every completed predecessor before next I/O.
            if C.source_gate(plan, image) != baseline:
                raise ValueError("Original parent changed before page connection")
            _proofs, previous, state = audit.completed_prefix(job, plan, newout, baseline)
            C.F.absent(previous, C.nonces(plan, index))
            ended = job["completed"][-1]["ended_at"] if index else plan["parent"]["ended_at"]
            page_plan = C.page_plan(plan, index, state, ended)
            page = C.report(page_plan) | {"plan": job["plan"]}
            directory = newout / slot["directory"]
            try:
                plan_gate(page, page_plan, directory)
                asyncio.run(capture(page, page_plan, previous, directory))
                page["ended_at"] = S.now()
                page["verification"] = audit.validate_page(page, directory, page_plan, previous)
                page["ok"] = True
            except BaseException as error:
                page["error"] = f"{type(error).__name__}: {error}"
                raise
            finally:
                page["ended_at"] = S.now()
                S.save(directory / "report.json", page)
            audit.original_success(page)
            job["completed"].append(audit.ledger_entry(newout, slot, page, page["verification"]))
            job["ended_at"] = S.now()
            save_job(newout, job)
            proofs, _ring, _state = audit.completed_prefix(job, plan, newout, baseline)
            print(
                json.dumps(
                    {
                        "completed_pages": len(proofs),
                        "paired_bytes": len(proofs) * 512,
                        "raw_range": proofs[-1]["raw_range"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        job["verification"] = audit.job_proof(plan, proofs)
        job["ok"] = True
    except BaseException as error:
        job["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        job["ended_at"] = S.now()
        save_job(newout, job)


def control_main(image, plan, baseline, out, *, sudo_password_stdin):
    report = C.control_report(plan) | {"plan": J.reference(out, out / "plan.json")}
    try:
        plan_gate(report, plan, out)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Known control parent changed before authorization")
        authorize(password_stdin=sudo_password_stdin)
        plan_gate(report, plan, out)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Known control parent changed before connection")
        asyncio.run(capture(report, plan, baseline, out))
        report["ended_at"] = S.now()
        report["verification"] = audit.validate_control(report, out, plan, baseline)
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(out / "report.json", report)


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)
if __name__ == "__main__":
    app()
