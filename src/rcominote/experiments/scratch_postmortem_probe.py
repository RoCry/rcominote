"""Exactly one readonly download of the fixed failed trial's dedicated file."""

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
from rcominote.experiments import scratch_postmortem_contract as C
from rcominote.experiments import scratch_reuse_probe as shared
from rcominote.experiments import startup_ram_probe as closing
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments import window_ram_probe as R
from rcominote.experiments.dual_client import DualConnection
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize
from rcominote.experiments.hci_monitor import Snoop
from rcominote.log_probe import NOTIFY


def no_actions(pdu):
    if pdu[:3] == b"\x1b\x18\0":
        raise ValueError("Actions notification forbidden in readonly retained-file postmortem")


def forbidden_notification(_characteristic, _data):
    raise ValueError("Actions notification forbidden in readonly retained-file postmortem")


def plan_gate(report, plan, out):
    if (
        report["plan"]["file"] != "plan.json"
        or json.loads(J.check_reference(out, report["plan"]).read_bytes()) != plan
    ):
        raise ValueError("Readonly in-memory plan differs from immutable original")
    C.validate_plan(plan)
    if (
        any(
            report.get(key) != plan[key]
            for key in (
                "profile",
                "expected_before",
                "budget",
                "stage_timeout_scope",
                "startup_policy",
                "status_event_policy",
            )
        )
        or report.get("sd_write_attempted") is not False
        or report["operation"].get("name") != C.F.NAME
        or report["operation"].get("operation_id") != "retained"
        or "operations" in report
    ):
        raise ValueError("Actual readonly report differs from fixed plan before I/O")


async def connected(conn, monitor, report, plan, out):
    failure = None
    op = report["operation"]
    link = report["transport"]["link"]
    try:
        await shared.identity(conn, report, "before", plan["expected_before"])
        start = len(report["att_packets"])
        try:
            report["listed_count"] = len(await conn.file_list())
        finally:
            report["file_list_span"] = [start, len(report["att_packets"])]
        tx, classification = await C.startup.wait_startup(monitor, conn, link, seconds=12)
        report.update(startup_settlement=tx, startup_classification=classification)
        plan_gate(report, plan, out)
        op.update(before=report["before"], started_at=S.now())
        async with asyncio.timeout(18):
            await R.normalize(monitor, conn, report, op, 1)
            await shared.download(conn, report, op, out / "retained")
            await shared.finish_stage(conn, monitor, report, op, 2, report["before"], writing=False)
        op.update(ended_at=S.now(), live_complete=True)
    except BaseException as error:
        failure = error
        if "started_at" in op:
            op.update(ended_at=S.now(), error=f"{type(error).__name__}: {error}")
        raise
    finally:
        if isinstance(failure, (TimeoutError, asyncio.CancelledError)):
            report["after_error"] = "Final identity omitted after timeout/cancellation; no new read command"
        else:
            try:
                await shared.identity(conn, report, "after", report["before"])
                R.observe(monitor, conn, link)
            except BaseException as error:
                report["after_error"] = f"{type(error).__name__}: {error}"
                if failure is None:
                    raise


async def capture(report, plan, out):
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != H.PEER:
        raise ValueError("Scanned peer differs from fixed owned peer")
    monitor = Monitor(out, snoop=Snoop())
    failure = None
    try:
        # Includes monitor readiness and GATT. Post-cancel close observation is
        # bounded8; monitor55 + kill-after2 independently bounds capture cleanup.
        async with asyncio.timeout(42):
            await monitor.start()
            conn = DualConnection(device, report)
            N.attach_status_observer(conn, report)
            conn.client.receive_guard = no_actions
            connection_failure = None
            try:
                async with conn:
                    try:
                        await conn.client.start_notify(NOTIFY, forbidden_notification)
                        report["setup_end"] = len(report["att_packets"])
                        report["gatt_proof"] = A.setup(report)
                        report["transport"]["link"] = active_link(conn)
                        await connected(conn, monitor, report, plan, out)
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
    if (
        report.get("ok") is not True
        or report["operation"].get("ok") is not True
        or report.get("content_error")
    ):
        raise ValueError("Original failed postmortem cannot be promoted by replay")
    plan = json.loads(J.check_reference(directory, report["plan"]).read_bytes())
    plan_gate(report, plan, directory)
    previous = C.source_gate(plan, image)
    proof = C.readonly(report, directory, plan)
    if proof != report["readonly_proof"]:
        raise ValueError("Saved complete readonly proof changed")
    data = (directory / "retained" / "download.bin").read_bytes()
    content = C.content(data, previous, plan)
    if content != report["content_verification"] or (
        directory / "retained" / "sector.bin"
    ).read_bytes() != bytes.fromhex(content["sector_hex"]):
        raise ValueError("Saved retained known-content proof changed")
    return {"readonly": proof, "content": content}


def main(image: Path, failed_trial: Path, newout: Path, sudo_password_stdin: bool = False):
    plan, previous = C.prepare(failed_trial, image)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    S.save(newout / "plan.json", plan)
    (newout / "retained").mkdir(mode=0o700)
    report = C.report(plan)
    report["plan"] = J.reference(newout, newout / "plan.json")
    try:
        plan_gate(report, plan, newout)
        if C.source_gate(plan, image) != previous:
            raise ValueError("Original failed baseline changed before authorization")
        authorize(password_stdin=sudo_password_stdin)
        plan_gate(report, plan, newout)
        if C.source_gate(plan, image) != previous:
            raise ValueError("Original failed baseline changed before connection")
        asyncio.run(capture(report, plan, newout))
        report["ended_at"] = S.now()
        report["readonly_proof"] = C.readonly(report, newout, plan)
        report["operation"]["ok"] = True
        S.save(newout / "readonly-checkpoint.json", report)
        try:
            data = (newout / "retained" / "download.bin").read_bytes()
            report["content_verification"] = C.content(data, previous, plan)
        except BaseException as error:
            report["content_error"] = f"{type(error).__name__}: {error}"
            raise
        with (newout / "retained" / "sector.bin").open("xb") as handle:
            handle.write(bytes.fromhex(report["content_verification"]["sector_hex"]))
        report["ok"] = True
    except BaseException as error:
        if "content_error" not in report:
            report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(newout / "report.json", report)
    print(
        json.dumps(
            {
                "ok": True,
                "readonly_postmortem": True,
                "original_trial_ok": False,
                "reuse_pair_complete": False,
                "sd_writes": 0,
            },
            ensure_ascii=False,
        )
    )


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)
if __name__ == "__main__":
    app()
