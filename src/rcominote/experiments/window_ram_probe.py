"""Two read-only oracle4096 downloads with observed per-download parameter epochs."""

import asyncio
import json
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import hci_interval as H
from rcominote.experiments import param_window as P
from rcominote.experiments import sd_warm_download as W
from rcominote.experiments import window_ram_audit as evidence
from rcominote.experiments.dual_client import Actions, DualConnection
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize, request_once
from rcominote.experiments.hci_monitor import Snoop
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.log_probe import NOTIFY

PROFILE = "per-download-window-known-ram4096"
FAST = (6, 12, 0, 500)
SLOW = (32, 48, 4, 600)


def prepare(image: Path, parent_ram: Path) -> tuple[dict, bytes]:
    oracle, parent = W.validate_inputs(image, parent_ram)
    return {
        "profile": PROFILE,
        "started_at": S.now(),
        "serial": OWNED_SERIAL,
        "name": W.NAME,
        "source_image_sha256": W.IMAGE_SHA,
        "expected_sha256": W.ORACLE_SHA,
        "parent": parent,
        "sd_write_attempted": False,
        "scope": "Two existing RAM-file downloads; no Actions commands, new files or NOR operations",
        "transport": {},
        "operations": [
            {"operation_id": label, "name": W.NAME, "ok": False, "live_complete": False}
            for label in ("first", "second")
        ],
        "ok": False,
    }, oracle


def observe(monitor, conn, link):
    conn._check_failure()
    if monitor.process is None or monitor.process.returncode is not None:
        raise RuntimeError(
            "Capture exited during parameter experiment; stale observations cannot settle a stage"
        )
    if active_link(conn) != link:
        raise ValueError("Owned live link changed; no reconnect permitted")
    monitor.poll()
    result = P.inspect(monitor.path.read_bytes(), link=link)
    if result["disconnects"]:
        raise ConnectionError("Owned link disconnected during parameter experiment")
    return result


def expected(transaction, origin, parameters):
    if transaction["origin"] != origin or P.parameters(transaction["request"]) != parameters:
        raise ValueError("Observed parameter transaction differs from the next fixed experiment stage")
    if origin == "remote" and (
        transaction["remote_request"] is None
        or P.parameters(transaction["remote_request"]) != parameters
        or transaction["remote_accept"] is None
    ):
        raise ValueError("Remote settlement lacks exact peripheral request and host acceptance")


def logical_pending(snapshot):
    return [
        value for value in snapshot["pending"] if value.get("kind") not in ("acl-fragment", "capture-tail")
    ]


async def wait_transaction(monitor, conn, link, *, index, origin, parameters, seconds):
    async with asyncio.timeout(seconds):
        while True:
            snapshot = observe(monitor, conn, link)
            if len(snapshot["transactions"]) > index:
                if len(snapshot["transactions"]) != index + 1 or logical_pending(snapshot):
                    raise ValueError("Unexpected extra/pending parameter traffic at the fixed stage boundary")
                if not snapshot["pending"]:
                    transaction = snapshot["transactions"][index]
                    expected(transaction, origin, parameters)
                    return transaction
            await asyncio.sleep(0.05)


async def normalize(monitor, conn, report, operation, index):
    link = report["transport"]["link"]
    async with asyncio.timeout(3):
        while True:
            snapshot = observe(monitor, conn, link)
            if logical_pending(snapshot) or len(snapshot["transactions"]) != index:
                raise ValueError(
                    "Prior observed parameter negotiation has not settled; no host update attempted"
                )
            if not snapshot["pending"]:
                break
            await asyncio.sleep(0.05)
    operation["normalization_requested_us"] = H.timestamp_us()
    operation["normalization_attempted"] = True
    await request_once(link["handle"], 500)
    operation["normalization"] = await wait_transaction(
        monitor, conn, link, index=index, origin="host", parameters=(6, 6, 0, 500), seconds=8
    )


async def download(conn, report, operation, directory, oracle):
    data = bytearray()

    def sink(chunk):
        if len(data) + len(chunk) > 4096:
            raise ValueError("Fixed oracle4096 download overflow")
        data.extend(chunk)
        return len(chunk)

    operation["download_start"] = len(report["att_packets"])
    operation["download_started_us"] = H.timestamp_us()
    conn.offline_allowed = True
    try:
        operation["download_bytes"] = await conn.download(W.NAME, sink, offset=0, timeout=8)
        if operation["download_bytes"] != 4096 or bytes(data) != oracle:
            raise ValueError("Existing file differs from complete independent4096-byte oracle")
    finally:
        conn.offline_allowed = False
        operation.update(
            received_bytes=len(data),
            download_sha256=A.sha(data),
            download_end=len(report["att_packets"]),
            download_ended_us=H.timestamp_us(),
        )
        with (directory / "download.bin").open("xb") as handle:
            handle.write(data)
    operation["download_trace_verification"] = A.download(
        report, operation, bytes(data), minimum_start=report["setup_end"]
    )


async def connected(conn, monitor, report, out, oracle):
    actions = Actions(conn, report)  # Guard rejects unsolicited Actions; no run/write call here.
    await conn.client.start_notify(NOTIFY, actions.receive)
    report["setup_end"] = len(report["att_packets"])
    report["gatt_proof"] = A.setup(report)
    report["transport"]["link"] = active_link(conn)
    failure = None
    try:
        await S.read_identity(conn, report, "before")
        verify_state(report["before"], report["before"], sd_write=False)
        start = len(report["att_packets"])
        try:
            report["listed_count"] = len(await conn.file_list())
        finally:
            report["file_list_span"] = [start, len(report["att_packets"])]
        report["startup_settlement"] = await wait_transaction(
            monitor, conn, report["transport"]["link"], index=0, origin="remote", parameters=FAST, seconds=12
        )
        state = report["before"]
        for index, operation in enumerate(report["operations"]):
            operation.update(before=state, started_at=S.now())
            await normalize(monitor, conn, report, operation, 1 + index * 2)
            await download(conn, report, operation, out / operation["operation_id"], oracle)
            operation["slow_settlement"] = await wait_transaction(
                monitor,
                conn,
                report["transport"]["link"],
                index=2 + index * 2,
                origin="remote",
                parameters=SLOW,
                seconds=8,
            )
            await S.read_identity(conn, operation, "after")
            operation["state_verification"] = verify_state(state, operation["after"], sd_write=False)
            conn._check_failure()
            observe(monitor, conn, report["transport"]["link"])
            operation.update(verified_end=len(report["att_packets"]), live_complete=True, ended_at=S.now())
            S.save(out / operation["operation_id"] / "checkpoint.json", report)
            state = operation["after"]
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            await S.read_identity(conn, report, "after")
            report["state_verification"] = verify_state(report["before"], report["after"], sd_write=False)
            observe(monitor, conn, report["transport"]["link"])
        except BaseException as error:
            report["after_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


async def capture(report, out, image, oracle):
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != H.PEER:
        raise ValueError("Scanned peer differs from owned public address")
    monitor = Monitor(out, snoop=Snoop())
    failure = None
    try:
        await monitor.start()
        async with asyncio.timeout(45):
            async with DualConnection(device, report) as conn:
                await connected(conn, monitor, report, out, oracle)
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
            if failure is None:
                report["verification"] = evidence.validate(report, out, image)
                for operation in report["operations"]:
                    operation["ok"] = True
        except BaseException as error:
            report["final_evidence_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


def replay(directory: Path, image: Path) -> dict:
    report = json.loads((directory / "report.json").read_bytes())
    if report.get("ok") is not True or not all(op.get("ok") is True for op in report["operations"]):
        raise ValueError("Original read-only window trial failed; retain it without promotion")
    result = evidence.validate(report, directory, image)
    if result != report["verification"]:
        raise ValueError("Retained window verification differs from complete original evidence")
    return result


def main(image: Path, parent_ram: Path, new_out: Path, sudo_password_stdin: bool = False):
    report, oracle = prepare(image, parent_ram)
    new_out.mkdir(parents=True, exist_ok=False, mode=0o700)
    for operation in report["operations"]:
        (new_out / operation["operation_id"]).mkdir(mode=0o700)
    try:
        authorize(password_stdin=sudo_password_stdin)
        asyncio.run(capture(report, new_out, image, oracle))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(new_out / "report.json", report)
    print(json.dumps({"ok": True, "downloads": 2, "exact_bytes_each": 4096, "new_sd_files": 0}))


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
