"""Fixed one4200 overwrite; primitives shared, old capture/contracts unchanged."""

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
from rcominote.experiments import scratch_4200_contract as C
from rcominote.experiments import scratch_reuse_probe as shared
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
        raise ValueError("In-memory known4200 plan differs from immutable original")
    C.validate_plan(plan)
    if (
        any(
            report.get(key) != plan[key]
            for key in (
                "profile",
                "expected_before",
                "budget",
                "actions_policy",
                "stage_timeout_scope",
                "startup_policy",
                "status_event_policy",
            )
        )
        or report["baseline"].get("name") != C.F.NAME
        or report["baseline"].get("operation_id") != "baseline"
        or "operations" in report
        or any(report["operation"].get(key) != value for key, value in plan["operation"].items())
    ):
        raise ValueError("Actual known4200 report differs from fixed plan before I/O")


def final_state(report):
    """Content failure does not discard an already verified actual state barrier."""
    for owner, writing in ((report["operation"], True), (report["baseline"], False)):
        if owner.get("barrier_complete") is True:
            C.shared.barrier(report, owner, owner["before"], writing=writing)
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
            if names.intersection((C.F.NAME, plan["operation"]["nonce"])):
                raise ValueError("Visible inventory collides with dedicated scratch/fresh nonce")
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
                raise ValueError("Live baseline differs from complete successful postmortem file")
            C.F.absent(previous, [plan["operation"]["nonce"]])
            current, observed, wire = await C.startup.live_wire(monitor, conn, report)
            if len(observed["transactions"]) != 3 or observed["pending"]:
                raise ValueError("Baseline requires exactly three completed negotiations")
            C.shared.baseline_window(
                current, warm, wire, tx, observed["transactions"][1], observed["transactions"][2]
            )
            C.shared.barrier(current, warm, warm["before"], writing=False)
        warm.update(live_complete=True, ok=True, ended_at=S.now())
        S.save(out / "baseline/checkpoint.json", report)
        op = active = report["operation"]
        plan_gate(report, plan, out)
        snapshot = R.observe(monitor, conn, link)
        if len(snapshot["transactions"]) != 3 or snapshot["pending"]:
            raise ValueError("Extra/pending negotiation before overwrite; no Actions attempted")
        op.update(before=warm["after"], started_at=S.now(), producer_attempted=False)
        async with asyncio.timeout(18):
            try:
                await actions.run_commands(op, C.recipe(op)[2:-1], sd_write_command_index=2)
            finally:
                op["producer_attempted"] = len(op.get("writes", [])) >= 4
            op["actions_verification"] = C.actions(report, op)
            op["pre_download_fast"] = await N.pre_download_fast(monitor, conn, link, cursor=3, required=True)
            current, observed, wire = await C.startup.live_wire(monitor, conn, report)
            if len(observed["transactions"]) != 4 or observed["pending"]:
                raise ValueError("Overwrite requires exactly one new completed remote FAST")
            op["activity_fast_verification"] = W.default_activity_fast(
                current, op, warm["slow_settlement"], op["pre_download_fast"][0], wire
            )
            await R.normalize(monitor, conn, report, op, 4)
            data = await shared.download(conn, report, op, out / "overwrite")
            await shared.finish_stage(conn, monitor, report, op, 5, warm["after"], writing=True)
            current, observed, wire = await C.startup.live_wire(monitor, conn, report)
            if len(observed["transactions"]) != 6 or observed["pending"]:
                raise ValueError("Overwrite download has extra/pending negotiation")
            W.download_window(wire, op, op["normalization"], op["slow_settlement"], report=current)
            C.shared.barrier(current, op, warm["after"], writing=True)
            op["verification"] = C.payload(op, data, previous, plan)
            with (out / "overwrite/sector.bin").open("xb") as handle:
                handle.write(bytes.fromhex(op["verification"]["sector_hex"]))
        op.update(live_complete=True, ok=True, ended_at=S.now())
        S.save(out / "overwrite/checkpoint.json", report)
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
                state = final_state(report)
                await shared.identity(conn, report, "after", state)
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
        report[key].get("ok") is not True for key in ("baseline", "operation")
    ):
        raise ValueError("Original failed known4200 control cannot be promoted by replay")
    plan = json.loads(J.check_reference(directory, report["plan"]).read_bytes())
    plan_gate(report, plan, directory)
    baseline = C.source_gate(plan, image)
    proof = C.validate(report, directory, plan, baseline)
    if proof != report["verification"]:
        raise ValueError("Original complete known4200 verification changed")
    return proof


def main(image: Path, parent_postmortem: Path, newout: Path, sudo_password_stdin: bool = False):
    plan, baseline = C.prepare(image, parent_postmortem)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    S.save(newout / "plan.json", plan)
    for label in ("baseline", "overwrite"):
        (newout / label).mkdir(mode=0o700)
    report = C.report(plan)
    report["plan"] = J.reference(newout, newout / "plan.json")
    try:
        plan_gate(report, plan, newout)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Retained-file parent changed before authorization")
        authorize(password_stdin=sudo_password_stdin)
        plan_gate(report, plan, newout)
        if C.source_gate(plan, image) != baseline:
            raise ValueError("Retained-file parent changed before connection")
        asyncio.run(capture(report, plan, baseline, newout))
        report["ended_at"] = S.now()
        report["verification"] = C.validate(report, newout, plan, baseline)
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(newout / "report.json", report)
    print(
        json.dumps(
            {"ok": True, "known_offset": 0x4200, "sd_writes": 1, "new_files": 0, "original_trial_ok": False},
            ensure_ascii=False,
        )
    )


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)
if __name__ == "__main__":
    app()
