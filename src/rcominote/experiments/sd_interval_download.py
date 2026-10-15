"""One interval6/latency0 existing-RAM4096 download; never Actions or SD writes."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.connection import Connection
from rcominote.device_commands import read_info
from rcominote.experiments import hci_interval as H
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize, request_once
from rcominote.experiments.sd_bootstrap import IMAGE_SHA, ORACLE_SHA, verify_state
from rcominote.experiments.sd_warm_download import NAME, sha, transfer, validate_inputs


async def baseline(monitor: Monitor, link: dict) -> dict:
    async with asyncio.timeout(12):
        while True:
            events = monitor.poll()
            if any(e["kind"] == "connect" and e["handle"] == link["handle"] for e in events):
                value = H.current(events, link["handle"], link["local"])
                if value["latency"] == 0:
                    if not 6 < value["interval"] <= 3200 or not 10 <= value["timeout"] <= 3200:
                        raise ValueError("Already interval6 or invalid current parameters")
                    return value
            await asyncio.sleep(0.05)


def gate(monitor: Monitor, report: dict, *, through: int | None = None) -> dict | None:
    events = monitor.poll()
    if through is not None:
        events = [e for e in events if e["timestamp_us"] <= through]
    link = report["link"]
    return H.applied(events, link["handle"], link["local"], report["baseline"], report["update_requested_us"])


async def watch(monitor: Monitor, report: dict) -> None:
    while True:
        if gate(monitor, report) != report["applied"]:
            raise ValueError("Applied HCI condition disappeared/changed")
        await asyncio.sleep(0.05)


async def guarded_download(
    conn: Connection, monitor: Monitor, report: dict, oracle: bytes, out: Path, *, operation=None
) -> None:
    report["download_start_us"] = H.timestamp_us()
    download = asyncio.create_task(
        transfer(conn, out, report, "full", oracle) if operation is None else operation(conn, out, report)
    )
    observer = asyncio.create_task(watch(monitor, report))
    try:
        done, _ = await asyncio.wait((download, observer), return_when=asyncio.FIRST_COMPLETED)
        if observer in done:
            await observer  # Its error wins; cancelled download still retains partial bytes.
        await download
    finally:
        report["download_end_us"] = H.timestamp_us()
        for task in (observer, download):
            if not task.done():
                task.cancel()
        await asyncio.gather(observer, download, return_exceptions=True)


async def connected(
    conn: Connection, monitor: Monitor, report: dict, oracle: bytes, out: Path, *, operation=None
) -> None:
    failure: BaseException | None = None
    try:
        report["before"] = await read_info(conn, OWNED_SERIAL)
        verify_state(report["before"], report["before"], sd_write=False)
        report["link"] = active_link(conn)
        report["baseline"] = await baseline(monitor, report["link"])
        prior = [
            e for e in monitor.poll() if e["kind"] == "request" and e["handle"] == report["link"]["handle"]
        ]
        report["prior_hci_request"] = prior[-1] if prior else None
        if active_link(conn) != report["link"]:
            raise ValueError("Active socket changed before per-link update")
        report["update_requested_us"] = H.timestamp_us()
        report["update_attempted"] = True
        await request_once(report["link"]["handle"], report["baseline"]["timeout"])
        async with asyncio.timeout(8):
            while (result := gate(monitor, report)) is None:
                await asyncio.sleep(0.05)
        report["applied"] = result
        report["actual_hci_request"] = next(
            e
            for e in monitor.poll()
            if e["kind"] == "request"
            and e["handle"] == report["link"]["handle"]
            and e["timestamp_us"] >= report["update_requested_us"]
        )
        report["condition"] = "applied-before-download"
        if active_link(conn) != report["link"]:
            raise ValueError("Active socket changed after per-link update")
        if operation is None:
            await guarded_download(conn, monitor, report, oracle, out)
        else:
            await guarded_download(conn, monitor, report, oracle, out, operation=operation)
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            report["after"] = await read_info(conn, OWNED_SERIAL)
            report["state_verification"] = verify_state(report["before"], report["after"], sd_write=False)
        except BaseException as error:
            report["after_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


async def capture(report: dict, oracle: bytes, out: Path, *, operation=None) -> None:
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != H.PEER:
        raise ValueError("Advertised owned serial is not the fixed public peer")
    monitor = Monitor(out)
    failure: BaseException | None = None
    try:
        await monitor.start()  # Capture ready before the sole connection is created.
        async with asyncio.timeout(45):
            async with Connection(device) as conn:
                await connected(conn, monitor, report, oracle, out, operation=operation)
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            report["monitor_stop"] = monitor.stop
            report["monitor_exit"] = await monitor.close()
            raw = monitor.path.read_bytes()
            report["hci_capture"] = {"bytes": len(raw), "sha256": sha(raw), "records": monitor.snoop.records}
            if "download_end_us" in report:
                # Final flushed capture, limited to the transfer interval: intentional
                # disconnect during cleanup must not be mistaken for data-phase loss.
                final = gate(monitor, report, through=report["download_end_us"])
                if final != report.get("applied"):
                    raise ValueError("Final HCI evidence does not preserve applied condition")
                report["condition"] = "verified-through-download"
        except BaseException as error:
            report["condition"] = "unverified-or-changed"
            report["hci_final_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


def main(image: Path, parent_ram_dir: Path, new_out: Path, sudo_password_stdin: bool = False) -> None:
    oracle, parent = validate_inputs(image, parent_ram_dir)
    new_out.mkdir(parents=True, exist_ok=False, mode=0o700)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "serial": OWNED_SERIAL,
        "name": NAME,
        "profile": "single-link-hcitool-interval6-ce1-ram4096",
        "policy": "interval6/latency0/current timeout; hcitool fixes both CE length hints at1; not a pure interval-only comparison",
        "parent": parent,
        "source_image_sha256": IMAGE_SHA,
        "expected_sha256": ORACLE_SHA,
        "scope": "One existing-file download; one per-link interval update; no Actions, SD write or reconnect",
        "sd_write_attempted": False,
        "update_attempted": False,
        "condition": "not-applied",
        "ok": False,
    }
    try:
        authorize(password_stdin=sudo_password_stdin)
        asyncio.run(capture(report, oracle, new_out))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = datetime.now(UTC).isoformat()
        with (new_out / "report.json").open("x") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {"ok": True, "received_bytes": report["full"]["received_bytes"], "condition": report["condition"]}
        )
    )


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
