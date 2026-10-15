"""Fixed unknown24200 pair; no oracle and no arbitrary address entry."""

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
from rcominote.experiments import scratch_reuse_probe as shared
from rcominote.experiments import scratch_system_pair_contract as C
from rcominote.experiments import startup_ram_probe as closing
from rcominote.experiments import window_nor_audit as W
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments import window_ram_probe as R
from rcominote.experiments.dual_client import Actions, DualConnection
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize
from rcominote.experiments.hci_monitor import Snoop
from rcominote.log_probe import NOTIFY


def plan_gate(report, plan, out):
    if (
        report["plan"]["file"] != "plan.json"
        or json.loads(J.check_reference(out, report["plan"]).read_bytes()) != plan
    ):
        raise ValueError("In-memory system pair plan differs from immutable original")
    C.validate_plan(plan)
    if (
        any(report.get(key) != plan[key] for key in C.FIELDS)
        or report["baseline"].get("name") != C.F.NAME
        or report["baseline"].get("operation_id") != "baseline"
        or "operation" in report
        or len(report.get("operations", [])) != 2
        or any(
            any(op.get(key) != value for key, value in slot.items())
            for slot, op in zip(plan["operations"], report["operations"], strict=True)
        )
    ):
        raise ValueError("Actual system pair report differs from fixed slots before I/O")


def final_state(report):
    for owner in [*reversed(report["operations"]), report["baseline"]]:
        if owner.get("barrier_complete") is True:
            C.shared.barrier(report, owner, owner["before"], writing=owner is not report["baseline"])
            return owner["after"]
    return report["before"]


async def connected(conn, actions, monitor, report, plan, baseline, out):
    failure, active = None, None
    link = report["transport"]["link"]
    try:
        await shared.identity(conn, report, "before", plan["expected_before"])
        start = len(report["att_packets"])
        try:
            names = {entry.name for entry in await conn.file_list()}
            report["listed_count"] = len(names)
            if names.intersection({C.F.NAME, *(op["nonce"] for op in plan["operations"])}):
                raise ValueError("Visible inventory collides with dedicated scratch/fresh nonces")
        finally:
            report["file_list_span"] = [start, len(report["att_packets"])]
        tx, classification = await C.startup.wait_startup(monitor, conn, link, seconds=12)
        report.update(startup_settlement=tx, startup_classification=classification)
        warm = active = report["baseline"]
        plan_gate(report, plan, out)
        warm.update(before=report["before"], started_at=S.now())
        async with asyncio.timeout(18):
            await R.normalize(monitor, conn, report, warm, 1)
            previous = await shared.download(conn, report, warm, out / "baseline")
            await shared.finish_stage(conn, monitor, report, warm, 2, report["before"], writing=False)
            if previous != baseline:
                raise ValueError("Live baseline differs from complete latest known4200 file")
            C.F.absent(previous, [op["nonce"] for op in plan["operations"]])
            current, observed, wire = await C.startup.live_wire(monitor, conn, report)
            if len(observed["transactions"]) != 3 or observed["pending"]:
                raise ValueError("Baseline requires exactly three completed negotiations")
            C.shared.baseline_window(
                current, warm, wire, tx, observed["transactions"][1], observed["transactions"][2]
            )
            C.shared.barrier(current, warm, warm["before"], writing=False)
        warm.update(live_complete=True, ok=True, ended_at=S.now())
        S.save(out / "baseline/checkpoint.json", report)
        state, previous_tx, cursor = warm["after"], warm["slow_settlement"], 3
        for op in report["operations"]:
            active = op
            plan_gate(report, plan, out)
            snapshot = R.observe(monitor, conn, link)
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
                    monitor, conn, link, cursor=cursor, required=True
                )
                current, observed, wire = await C.startup.live_wire(monitor, conn, report)
                if len(observed["transactions"]) != cursor + 1 or observed["pending"]:
                    raise ValueError("Each producer requires exactly one new completed FAST")
                op["activity_fast_verification"] = W.default_activity_fast(
                    current, op, previous_tx, op["pre_download_fast"][0], wire
                )
                cursor += 1
                await R.normalize(monitor, conn, report, op, cursor)
                cursor += 1
                data = await shared.download(conn, report, op, out / op["operation_id"])
                await shared.finish_stage(conn, monitor, report, op, cursor, state, writing=True)
                cursor += 1
                current, observed, wire = await C.startup.live_wire(monitor, conn, report)
                if len(observed["transactions"]) != cursor or observed["pending"]:
                    raise ValueError("Producer download has extra/pending negotiation")
                W.download_window(wire, op, op["normalization"], op["slow_settlement"], report=current)
                C.shared.barrier(current, op, state, writing=True)
                op["verification"] = C.payload(op, data, previous)
                if op["operation_id"] == "first":
                    C.F.absent(data, [plan["operations"][1]["nonce"]])
                with (out / op["operation_id"] / "sector.bin").open("xb") as handle:
                    handle.write(bytes.fromhex(op["verification"]["sector_hex"]))
            op.update(live_complete=True, ok=True, ended_at=S.now())
            S.save(out / op["operation_id"] / "checkpoint.json", report)
            previous, state, previous_tx = data, op["after"], op["slow_settlement"]
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
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != H.PEER:
        raise ValueError("Scanned peer differs from fixed owned peer")
    monitor = Monitor(out, snoop=Snoop(), seconds=70)
    failure = None
    try:
        # Readiness/GATT included60; cancellation adds bounded STOP2/close8.
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


def replay(directory: Path, image: Path):
    report = json.loads((directory / "report.json").read_bytes())
    if report.get("ok") is not True or any(
        op.get("ok") is not True for op in [report["baseline"], *report["operations"]]
    ):
        raise ValueError("Original failed system pair cannot be promoted by replay")
    plan = json.loads(J.check_reference(directory, report["plan"]).read_bytes())
    plan_gate(report, plan, directory)
    baseline = C.source_gate(plan, image)
    proof = C.validate(report, directory, plan, baseline)
    if (
        proof != report["verification"]
        or set(report["outputs"]) != {C.OUTPUT}
        or report["outputs"][C.OUTPUT]["file"] != C.OUTPUT
    ):
        raise ValueError("Original complete system pair proof/output reference changed")
    sector = J.check_reference(directory, report["outputs"][C.OUTPUT]).read_bytes()
    if (
        len(sector) != 512
        or A.sha(sector) != proof["sha256"]
        or sector != (directory / "first/sector.bin").read_bytes()
    ):
        raise ValueError("Original assembled512 output differs from the fully verified raw pair")
    return proof


def main(image: Path, parent4200: Path, newout: Path, sudo_password_stdin: bool = False):
    plan, baseline = C.prepare(image, parent4200)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    S.save(newout / "plan.json", plan)
    for label in C.STAGES:
        (newout / label).mkdir(mode=0o700)
    report = C.report(plan)
    report["plan"] = J.reference(newout, newout / "plan.json")
    try:
        plan_gate(report, plan, newout)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Latest current-file parent changed before authorization")
        authorize(password_stdin=sudo_password_stdin)
        plan_gate(report, plan, newout)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Latest current-file parent changed before connection")
        asyncio.run(capture(report, plan, baseline, newout))
        report["ended_at"] = S.now()
        report["verification"] = C.validate(report, newout, plan, baseline)
        sector = (newout / "first/sector.bin").read_bytes()
        if len(sector) != 512 or A.sha(sector) != report["verification"]["sha256"]:
            raise ValueError("Aggregate raw output differs from its complete verified pair")
        with (newout / C.OUTPUT).open("xb") as handle:
            handle.write(sector)
        report["outputs"] = {C.OUTPUT: J.reference(newout, newout / C.OUTPUT)}
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(newout / "report.json", report)
    print(
        json.dumps(
            {
                "ok": True,
                "raw_range": [C.OFFSET, C.OFFSET + 512],
                "new_verified_bytes": 512,
                "independent_oracle": False,
                "new_files": 0,
            },
            ensure_ascii=False,
        )
    )


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)
if __name__ == "__main__":
    app()
