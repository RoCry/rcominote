"""Boyi recorder commands. Device mutations are explicit; results include readback."""

import asyncio
import struct
import time
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from bleak import BleakScanner

from . import protocol as P
from .ble_target import OWNED_SERIAL, advertised_serial, find_device
from .connection import Connection, recording_output_name, validate_filename
from .download_cancel import DownloadCancelled
from .download_progress import export_with_progress
from .output import emit, new_output

app = typer.Typer(no_args_is_help=True)
DEFAULT_OUT = Path.home() / ".local/share/comi-research"
ScanSeconds = Annotated[float, typer.Option(min=0.1, max=60)]


async def read_info(conn: Connection, serial: str) -> dict:
    actual = await conn.serial()
    if actual != serial:
        raise ValueError(f"Connected serial {actual!r} differs from selected {serial!r}")
    return {"serial": actual, "bound": await conn.bound(), "device": await conn.device_info()}


@app.command()
def scan(seconds: ScanSeconds = 12):
    """Discover CoMi advertisements without connecting."""

    async def run():
        found = await BleakScanner.discover(timeout=seconds, return_adv=True)
        return [
            {
                "address": dev.address,
                "name": adv.local_name,
                "rssi": adv.rssi,
                "serial": advertised_serial(raw),
                "mac": ":".join(f"{b:02X}" for b in raw[:6]),
            }
            for dev, adv in found.values()
            if (raw := adv.manufacturer_data.get(P.COMPANY_ID)) is not None
        ]

    emit(asyncio.run(run()))


@app.command()
def info(serial: str = OWNED_SERIAL, seconds: ScanSeconds = 12, out: Path | None = None):
    """Read identity, firmware, capacity, battery, recording state and settings."""
    new_output(out)

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            return await read_info(conn, serial)

    emit(asyncio.run(run()), out)


@app.command()
def files(serial: str = OWNED_SERIAL, seconds: ScanSeconds = 12, out: Path | None = None):
    """List recordings; never delete or mark them synced."""
    new_output(out)

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            await read_info(conn, serial)
            return [asdict(entry) for entry in await conn.file_list()]

    emit(asyncio.run(run()), out)


@app.command()
def watch(
    duration: Annotated[float, typer.Option(min=0.1, max=300)] = 30,
    serial: str = OWNED_SERIAL,
    seconds: ScanSeconds = 12,
    out: Path | None = None,
):
    """Observe device/voice events for a bounded time; never change device settings."""
    new_output(out)

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            identity = await read_info(conn, serial)
            return {
                "serial": identity["serial"],
                "watch_seconds": duration,
                "event_scope": "notifications since connection setup, including identity queries",
                "events": await conn.watch(duration),
                "parser_source": "CoMi 1.1.2 Y8/Z8 layout; mode labels corrected on FW010004 hardware",
            }

    emit(asyncio.run(run()), out)


@app.command()
def download(
    name: str,
    out: Path = DEFAULT_OUT,
    serial: str = OWNED_SERIAL,
    seconds: ScanSeconds = 12,
    offset: Annotated[int, typer.Option(min=0, max=0xFFFFFFFF)] = 0,
):
    """Export a listed recording; Ctrl-C stops transfer and preserves a labeled partial prefix."""
    validate_filename(name)
    target = out / recording_output_name(name, offset)
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Recording output already exists: {target}")

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            await read_info(conn, serial)
            entries = await conn.file_list()
            entry = next((entry for entry in entries if entry.name == name), None)
            if entry is None:
                raise ValueError(f"Recording not listed: {name}")
            try:
                return await export_with_progress(conn, name, out, expected_size=entry.size, offset=offset)
            except DownloadCancelled as error:
                if error.export_result is None:
                    raise RuntimeError("Canceled export did not supply an outcome") from error
                return error.export_result

    result = asyncio.run(run())
    emit(result)
    if result.get("status") == "cancelled":
        raise typer.Exit(code=130)


@app.command()
def sync(out: Path = DEFAULT_OUT, serial: str = OWNED_SERIAL, seconds: ScanSeconds = 12):
    """Export missing recordings; Ctrl-C preserves the partial file and ends sync."""

    async def run():
        results = []
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            await read_info(conn, serial)
            for entry in await conn.file_list():
                target = out / f"{entry.name}.mp3"
                if target.is_symlink():
                    raise FileExistsError(f"Refusing symlink in export directory: {target}")
                if target.exists():
                    if not target.is_file() or target.stat().st_size != entry.size:
                        raise FileExistsError(f"Existing destination does not match listed size: {target}")
                    result = {
                        "name": entry.name,
                        "status": "skip",
                        "verification": "size_only",
                        "path": str(target),
                    }
                else:
                    try:
                        result = await export_with_progress(conn, entry.name, out, expected_size=entry.size)
                    except DownloadCancelled as error:
                        if error.export_result is None:
                            raise RuntimeError("Canceled export did not supply an outcome") from error
                        results.append(error.export_result)
                        break
                results.append(result)
        return results

    results = asyncio.run(run())
    emit(results)
    if any(result.get("status") == "cancelled" for result in results):
        raise typer.Exit(code=130)


class RecordAction(StrEnum):
    start = "start"
    pause = "pause"
    resume = "resume"
    stop = "stop"


RECORD_COMMANDS = {
    "start": P.START_RECORDING,
    "pause": P.PAUSE_RECORDING,
    "resume": P.RESUME_RECORDING,
    "stop": P.STOP_RECORDING,
}
ALLOWED_STATES = {
    "start": {"idle"},
    "pause": {"recording"},
    "resume": {"paused"},
    "stop": {"recording", "paused"},
}
EXPECTED_STATES = {"start": "recording", "pause": "paused", "resume": "recording", "stop": "idle"}


def parse_record_reply(action: str, data: bytes) -> dict:
    required = 21 if action == "stop" else 16
    if len(data) < required or data[0] != 0:
        raise ValueError(f"Recording {action} failed/malformed: {data.hex()}")
    result = {"action": action, "name": P.text(data[1:15]), "reply_hex": data.hex()}
    if action == "stop":
        result |= {"size": struct.unpack_from(">I", data, 15)[0], "need_sync": data[20] == 1}
    return result


async def change_recording(conn: Connection, action: str) -> dict:
    before = await conn.device_info()
    if before["recording_state"] not in ALLOWED_STATES[action]:
        raise ValueError(f"Cannot {action} while {before['recording_state']}; no command sent")
    result = parse_record_reply(action, await conn.command(RECORD_COMMANDS[action]))
    deadline = asyncio.get_running_loop().time() + 3
    while True:
        after = await conn.device_info()
        if after["recording_state"] == EXPECTED_STATES[action]:
            return result | {
                "ok": True,
                "state_before": before["recording_state"],
                "state_after": after["recording_state"],
            }
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(f"{action} acknowledged but readback state is {after['recording_state']}")
        await asyncio.sleep(0.2)


@app.command()
def record(action: RecordAction, serial: str = OWNED_SERIAL, seconds: ScanSeconds = 12):
    """Start/pause/resume/stop recording; verify resulting state."""

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            await read_info(conn, serial)
            return await change_recording(conn, action.value)

    emit(asyncio.run(run()))


@app.command("recording-info")
def recording_info(serial: str = OWNED_SERIAL, seconds: ScanSeconds = 12):
    """Query current recording name, byte count and state."""

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            await read_info(conn, serial)
            data = await conn.command(P.GET_RECORDING_INFO)
            if data == b"\x01":
                return {"recording_state": "idle", "raw": data.hex()}
            if len(data) < 20 or data[0] not in (0, 2):
                raise ValueError(f"Invalid recording-info response: {data.hex()}")
            return {
                "recording_state": "recording" if data[0] == 0 else "paused",
                "name": P.text(data[1:15]),
                "size": struct.unpack_from(">I", data, 15)[0],
                "kind": "call" if data[19] == 0 else "note",
                "raw": data.hex(),
            }

    emit(asyncio.run(run()))


@app.command("set-time")
def set_time(serial: str = OWNED_SERIAL, seconds: ScanSeconds = 12):
    """Set device clock to host local time; no clock readback exists in known protocol."""

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            await read_info(conn, serial)
            now = time.localtime()
            payload = bytes(
                (now.tm_year - 2000, now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec)
            )
            reply = await conn.command(P.SET_TIME, payload)
        return {
            "requested_time": time.strftime("%Y-%m-%d %H:%M:%S", now),
            "reply_hex": reply.hex(),
            "verification": "matching_response_only; no known clock getter",
        }

    emit(asyncio.run(run()))
