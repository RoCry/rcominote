"""One connection, readonly baseline then two fixed same-scratch known writes."""

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
from rcominote.experiments import scratch_reuse_audit as evidence
from rcominote.experiments import scratch_reuse_contract as C
from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import startup_ram_probe as close_proof
from rcominote.experiments import window_nor_audit as W
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments import window_ram_probe as R
from rcominote.experiments.dual_client import Actions, DualConnection
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize
from rcominote.experiments.hci_monitor import Snoop
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.log_probe import NOTIFY


def plan_gate(job, plan, out):
    if (
        job["plan"]["file"] != "plan.json"
        or json.loads(J.check_reference(out, job["plan"]).read_bytes()) != plan
    ):
        raise ValueError("In-memory scratch plan differs from immutable original")
    C.validate_plan(plan)
    report_fields = (
        "profile",
        "expected_before",
        "startup_policy",
        "status_event_policy",
        "budget",
        "stage_timeout_scope",
    )
    if (
        any(job.get(key) != plan[key] for key in report_fields)
        or job.get("baseline", {}).get("name") != F.NAME
        or len(job.get("operations", [])) != len(plan["operations"])
        or any(
            any(op.get(key) != value for key, value in slot.items())
            for slot, op in zip(plan["operations"], job["operations"], strict=True)
        )
    ):
        raise ValueError("Actual scratch report/operations differ from immutable plan before I/O")


async def download(conn, report, op, directory):
    data = bytearray()

    def sink(chunk):
        if len(data) + len(chunk) > 4096:
            raise ValueError("Fixed4096 download overflow")
        data.extend(chunk)
        return len(chunk)

    op.update(download_start=len(report["att_packets"]), download_started_us=H.timestamp_us())
    conn.offline_allowed = True
    try:
        op["download_bytes"] = await conn.download(F.NAME, sink, offset=0, timeout=8)
        if op["download_bytes"] != 4096 or len(data) != 4096:
            raise ValueError("Incomplete fixed4096 scratch download")
    finally:
        conn.offline_allowed = False
        op.update(
            received_bytes=len(data),
            download_sha256=A.sha(data),
            download_end=len(report["att_packets"]),
            download_ended_us=H.timestamp_us(),
        )
        with (directory / "download.bin").open("xb") as handle:
            handle.write(data)
    op["download_verification"] = A.download(report, op, bytes(data), minimum_start=report["setup_end"])
    return bytes(data)


async def identity(conn, owner, key, before, *, writing=False):
    async with asyncio.timeout(3):
        await S.read_identity(conn, owner, key)
    owner["predecessor_state_verification" if key == "before" else "state_verification"] = verify_state(
        before, owner[key], sd_write=writing
    )


async def finish_stage(conn, monitor, report, op, cursor, before, *, writing):
    op["slow_settlement"] = await R.wait_transaction(
        monitor,
        conn,
        report["transport"]["link"],
        index=cursor,
        origin="remote",
        parameters=R.SLOW,
        seconds=8,
    )
    await identity(conn, op, "after", before, writing=writing)
    R.observe(monitor, conn, report["transport"]["link"])
    op.update(verified_end=len(report["att_packets"]), barrier_complete=True)


async def connected(conn, actions, monitor, report, plan, baseline, out):
    failure = None
    active = None
    link = report["transport"]["link"]
    try:
        await identity(conn, report, "before", plan["expected_before"])
        start = len(report["att_packets"])
        try:
            names = {entry.name for entry in await conn.file_list()}
            report["listed_count"] = len(names)
            if names.intersection([F.NAME, *(op["nonce"] for op in plan["operations"])]):
                raise ValueError("Visible inventory collides with dedicated scratch/nonce")
        finally:
            report["file_list_span"] = [start, len(report["att_packets"])]
        transaction, classification = await startup.wait_startup(monitor, conn, link, seconds=12)
        report.update(startup_settlement=transaction, startup_classification=classification)
        op = report["baseline"]
        active = op
        plan_gate(report, plan, out)
        op.update(before=report["before"], started_at=S.now())
        async with asyncio.timeout(18):
            await R.normalize(monitor, conn, report, op, 1)
            previous = await download(conn, report, op, out / "baseline")
            await finish_stage(conn, monitor, report, op, 2, op["before"], writing=False)
            if previous != baseline:
                raise ValueError("Readonly existing object differs from original complete baseline")
            F.absent(previous, [slot["nonce"] for slot in plan["operations"]])
            current, observed, wire = await startup.live_wire(monitor, conn, report)
            if len(observed["transactions"]) != 3 or observed["pending"]:
                raise ValueError("Baseline has extra/pending parameter negotiation")
            evidence.baseline_window(
                current, op, wire, transaction, observed["transactions"][1], observed["transactions"][2]
            )
            evidence.barrier(current, op, op["before"], writing=False)
        op.update(live_complete=True, ok=True, ended_at=S.now())
        S.save(out / "baseline" / "checkpoint.json", report)
        state, previous_tx, cursor = op["after"], op["slow_settlement"], 3
        for slot, op in zip(plan["operations"], report["operations"], strict=True):
            active = op
            plan_gate(report, plan, out)
            if any(op.get(key) != value for key, value in slot.items()):
                raise ValueError("Overwrite recipe differs from fixed plan before Actions")
            snapshot = R.observe(monitor, conn, link)
            if len(snapshot["transactions"]) != cursor or snapshot["pending"]:
                raise ValueError("Extra negotiation before overwrite; no Actions attempted")
            directory = out / op["operation_id"]
            op.update(before=state, started_at=S.now(), producer_attempted=False)
            async with asyncio.timeout(18):
                body = C.recipe(op)[2:-1]
                try:
                    await actions.run_commands(op, body, sd_write_command_index=2)
                finally:
                    op["producer_attempted"] = len(op.get("writes", [])) >= 4
                op["actions_verification"] = evidence.actions(report, op)
                op["pre_download_fast"] = await N.pre_download_fast(
                    monitor, conn, link, cursor=cursor, required=True
                )
                current, observed, wire = await startup.live_wire(monitor, conn, report)
                if len(observed["transactions"]) != cursor + 1 or observed["pending"]:
                    raise ValueError("Overwrite requires exactly one new completed FAST")
                op["activity_fast_verification"] = W.default_activity_fast(
                    current, op, previous_tx, op["pre_download_fast"][0], wire
                )
                cursor += 1
                await R.normalize(monitor, conn, report, op, cursor)
                cursor += 1
                raw = await download(conn, report, op, directory)
                await finish_stage(conn, monitor, report, op, cursor, state, writing=True)
                cursor += 1
                current, observed, wire = await startup.live_wire(monitor, conn, report)
                if len(observed["transactions"]) != cursor or observed["pending"]:
                    raise ValueError("Extra/pending transaction after overwrite download")
                W.download_window(wire, op, op["normalization"], op["slow_settlement"], report=current)
                evidence.barrier(current, op, state, writing=True)
                op["verification"] = C.payload(op, raw, previous, plan)
                if op["operation_id"] == "first":
                    F.absent(raw, [plan["operations"][1]["nonce"]])
                with (directory / "sector.bin").open("xb") as handle:
                    handle.write(bytes.fromhex(op["verification"]["sector_hex"]))
            op.update(live_complete=True, ok=True, ended_at=S.now())
            S.save(directory / "checkpoint.json", report)
            previous, state, previous_tx = raw, op["after"], op["slow_settlement"]
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
                state = next(
                    (
                        op["after"]
                        for op in reversed([report["baseline"], *report["operations"]])
                        if op.get("live_complete")
                    ),
                    report["before"],
                )
                await identity(conn, report, "after", state)
                R.observe(monitor, conn, link)
            except BaseException as error:
                report["after_error"] = f"{type(error).__name__}: {error}"
                if failure is None:
                    raise


async def capture(report, plan, baseline, out):
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != H.PEER:
        raise ValueError("Scanned peer differs from fixed owned peer")
    monitor = Monitor(out, snoop=Snoop(), seconds=70)
    failure = None
    try:
        async with asyncio.timeout(60):
            await monitor.start()
            conn = DualConnection(device, report)
            N.attach_status_observer(conn, report)
            actions = Actions(conn, report)
            connection_failure = None
            try:
                async with conn:
                    try:
                        await conn.client.start_notify(NOTIFY, actions.receive)
                        report["setup_end"] = len(report["att_packets"])
                        report["gatt_proof"] = A.setup(report)
                        report["transport"]["link"] = active_link(conn)
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
                        await close_proof.observe_disconnect(monitor, report)
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


def replay(directory: Path, image: Path):
    report = json.loads((directory / "report.json").read_bytes())
    if report.get("ok") is not True or any(
        op.get("ok") is not True for op in [report["baseline"], *report["operations"]]
    ):
        raise ValueError("Original failed scratch experiment cannot be promoted by replay")
    plan = json.loads(J.check_reference(directory, report["plan"]).read_bytes())
    plan_gate(report, plan, directory)
    baseline = C.source_gate(plan, image)
    J.time_order(
        plan["sources"]["state_parent"]["ended_at"],
        plan["planned_at"],
        report["started_at"],
        report["ended_at"],
    )
    proof = evidence.validate(report, directory, plan, baseline)
    if proof != report["verification"]:
        raise ValueError("Original scratch proof changed")
    return proof


def main(
    image: Path, known_parent: Path, state_parent: Path, newout: Path, sudo_password_stdin: bool = False
):
    plan, baseline = C.prepare(image, known_parent, state_parent)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    S.save(newout / "plan.json", plan)
    for label in C.STAGES:
        (newout / label).mkdir(mode=0o700)
    report = C.report(plan)
    report["plan"] = J.reference(newout, newout / "plan.json")
    try:
        plan_gate(report, plan, newout)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Source baseline changed before authorization")
        authorize(password_stdin=sudo_password_stdin)
        plan_gate(report, plan, newout)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Source baseline changed before connection")
        asyncio.run(capture(report, plan, baseline, newout))
        report["ended_at"] = S.now()
        report["verification"] = evidence.validate(report, newout, plan, baseline)
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(newout / "report.json", report)
    print(
        json.dumps(
            {"ok": True, "known_control_only": True, "sd_writes": 2, "new_files": 0}, ensure_ascii=False
        )
    )


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)
if __name__ == "__main__":
    app()
