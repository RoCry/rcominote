"""Seed FAST, then actual DEFAULT/activity FAST with an existing RAM oracle file.

Two connections only. PREPARE/START/STOP pulses change temporary Actions/log
RAM state; no console body, producer, SD write, new file or NOR operation.
"""

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
from rcominote.experiments import startup_ram_audit as evidence
from rcominote.experiments import startup_ram_contract as C
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments import window_ram_probe as R
from rcominote.experiments.dual_client import Actions, DualConnection
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize
from rcominote.experiments.hci_monitor import Snoop
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.log_probe import NOTIFY


async def readonly_identity(conn, owner, key, expected):
    async with asyncio.timeout(3):
        await S.read_identity(conn, owner, key)
    proof = verify_state(expected, owner[key], sd_write=False)
    owner["predecessor_state_verification" if key == "before" else "state_verification"] = proof


async def seed_connected(conn, monitor, report):
    failure = None
    try:
        await readonly_identity(conn, report, "before", report["expected_before"])
        transaction, classification = await C.startup.wait_startup(
            monitor, conn, report["transport"]["link"], seconds=12
        )
        report.update(startup_settlement=transaction, startup_classification=classification)
    except BaseException as error:
        failure = error
        raise
    finally:
        if isinstance(failure, (asyncio.CancelledError, TimeoutError)):
            report["after_error"] = "Final identity omitted after timeout/cancellation; no new read command"
        else:
            try:
                await readonly_identity(conn, report, "after", report["expected_before"])
                R.observe(monitor, conn, report["transport"]["link"])
            except BaseException as error:
                report["after_error"] = f"{type(error).__name__}: {error}"
                if failure is None:
                    raise


async def live_fast_proof(monitor, conn, report, op, previous):
    current, _, wire = await C.startup.live_wire(monitor, conn, report)
    return evidence.activity_fast(current, op, previous, op["activity_fast"], wire)


async def data_connected(conn, actions, monitor, report, out, oracle):
    failure = None
    link = report["transport"]["link"]
    try:
        await readonly_identity(conn, report, "before", report["expected_before"])
        start = len(report["att_packets"])
        try:
            report["listed_count"] = len(await conn.file_list())
        finally:
            report["file_list_span"] = [start, len(report["att_packets"])]
        transaction, classification = await C.startup.wait_startup(
            monitor, conn, link, policy=C.startup.POLICY, seconds=12
        )
        report.update(startup_settlement=transaction, startup_classification=classification)
        if classification["mode"] != "default":
            raise ValueError("Data control requires actual DEFAULT; observed FAST is not DEFAULT tested")
        state, previous, cursor = report["before"], transaction, 1
        for op in report["operations"]:
            snapshot = R.observe(monitor, conn, link)
            if len(snapshot["transactions"]) != cursor or snapshot["pending"]:
                raise ValueError(
                    "Extra/pending negotiation before pulse; no pulse or normalization attempted"
                )
            op.update(before=state, started_at=S.now())
            await actions.run_commands(op, [], sd_write_command_index=None)
            op["actions_verification"] = evidence.pulse(report, op)
            op["activity_fast"] = await R.wait_transaction(
                monitor, conn, link, index=cursor, origin="remote", parameters=R.FAST, seconds=8
            )
            op["activity_fast_verification"] = await live_fast_proof(monitor, conn, report, op, previous)
            cursor += 1
            await R.normalize(monitor, conn, report, op, cursor)
            cursor += 1
            await R.download(conn, report, op, out / op["operation_id"], oracle)
            op["slow_settlement"] = await R.wait_transaction(
                monitor, conn, link, index=cursor, origin="remote", parameters=R.SLOW, seconds=8
            )
            cursor += 1
            await readonly_identity(conn, op, "after", state)
            R.observe(monitor, conn, link)
            op.update(verified_end=len(report["att_packets"]), live_complete=True, ended_at=S.now())
            S.save(out / op["operation_id"] / "checkpoint.json", report)
            state, previous = op["after"], op["slow_settlement"]
    except BaseException as error:
        failure = error
        raise
    finally:
        if isinstance(failure, (asyncio.CancelledError, TimeoutError)):
            report["after_error"] = "Final identity omitted after timeout/cancellation; no new read command"
        else:
            try:
                await readonly_identity(conn, report, "after", report["expected_before"])
                R.observe(monitor, conn, link)
            except BaseException as error:
                report["after_error"] = f"{type(error).__name__}: {error}"
                if failure is None:
                    raise


async def observe_disconnect(monitor, report):
    """Observe after close; never reconnect or issue a controller command."""
    report["disconnect_observation"] = {"observed": False, "max_wait_seconds": 8}
    async with asyncio.timeout(8):
        while True:
            if monitor.process is None or monitor.process.returncode is not None:
                raise RuntimeError("Monitor stopped before post-close disconnect observation")
            monitor.poll()
            matches = [
                event
                for event in monitor.snoop.events
                if event["kind"] == "disconnect" and event["handle"] == report["transport"]["link"]["handle"]
            ]
            if matches:
                if len(matches) != 1 or matches[0]["status"] != 0 or matches[0]["reason"] != 0x16:
                    raise ValueError("Post-close disconnect is not the sole normal local disconnect")
                report["disconnect_observation"].update(observed=True, event=matches[0])
                report["disconnect_observed_us"] = H.timestamp_us()
                return
            await asyncio.sleep(0.05)


async def capture_phase(report, out, kind, oracle):
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != H.PEER:
        raise ValueError("Scanned peer differs from fixed owned identity")
    monitor = Monitor(out, snoop=Snoop())
    failure = None
    try:
        # Includes monitor readiness. Cancellation can add bounded STOP2/close observation8;
        # no fresh identity is sent after a timeout. All activity stays below monitor's55-second cap.
        async with asyncio.timeout(42):
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
                        if kind == "seed":
                            await seed_connected(conn, monitor, report)
                        else:
                            await data_connected(conn, actions, monitor, report, out, oracle)
                    finally:
                        report["close_requested_us"] = H.timestamp_us()
            except BaseException as error:
                connection_failure = error
                raise
            finally:
                report["close_completed_us"] = H.timestamp_us()
                if report["transport"].get("link"):
                    try:
                        await observe_disconnect(monitor, report)
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


async def run_phase(plan, kind, out, oracle):
    report = C.phase(plan, kind)
    try:
        await capture_phase(report, out, kind, oracle)
        report["ended_at"] = S.now()
        report["verification"] = (
            evidence.seed(report, out) if kind == "seed" else evidence.data(report, out, oracle)
        )
        for op in report["operations"]:
            op["ok"] = True
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(out / "report.json", report)


async def run_control(job, plan, out, image, oracle):
    for kind in C.PHASES:
        plan_gate(job, plan, out)
        if C.source_gate(plan, image) != oracle:
            raise ValueError("Control oracle source changed before connection")
        job["active_phase"] = kind
        try:
            await run_phase(plan, kind, out / kind, oracle)
        finally:
            path = out / kind / "report.json"
            if path.exists():
                job["phases"][kind] = J.reference(out, path)


def plan_gate(job, plan, out):
    original = json.loads(J.check_reference(out, job["plan"]).read_bytes())
    if original != plan:
        raise ValueError("In-memory control plan differs from its immutable original")
    C.validate_plan(plan)


def replay(directory: Path, image: Path) -> dict:
    job = json.loads((directory / "report.json").read_bytes())
    if job.get("ok") is not True:
        raise ValueError("Original activity/RAM control failed; retain partials without promotion")
    proof = evidence.validate(job, directory, image)
    if proof != job["verification"]:
        raise ValueError("Saved activity/RAM verification changed")
    return proof


def main(image: Path, parent_ram: Path, state_parent: Path, newout: Path, sudo_password_stdin: bool = False):
    plan, oracle = C.prepare(image, parent_ram, state_parent)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    S.save(newout / "plan.json", plan)
    for kind in C.PHASES:
        (newout / kind).mkdir(mode=0o700)
    for label in ("first", "second"):
        (newout / "data" / label).mkdir(mode=0o700)
    job = {
        "profile": C.PROFILE,
        "started_at": S.now(),
        "plan": J.reference(newout, newout / "plan.json"),
        "phases": {},
        "ok": False,
    }
    try:
        plan_gate(job, plan, newout)
        if C.source_gate(plan, image) != oracle:
            raise ValueError("Actual state/oracle changed before authorization")
        authorize(password_stdin=sudo_password_stdin)
        asyncio.run(run_control(job, plan, newout, image, oracle))
        job["ended_at"] = S.now()
        job["verification"] = evidence.validate(job, newout, image)
        job["ok"] = True
    except BaseException as error:
        job["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        job["ended_at"] = S.now()
        S.save(newout / "report.json", job)
    print(json.dumps({"ok": True, "actual_default_tested": True, "downloads": 2, "new_sd_files": 0}))


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
