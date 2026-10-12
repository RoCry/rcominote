"""Bounded raw realtime export; notification windows never imply complete recordings."""

import asyncio
import hashlib
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Annotated

import typer

from . import protocol as P
from .ble_target import OWNED_SERIAL, find_device
from .connection import Connection, RealtimeCapture
from .device_commands import ScanSeconds, change_recording, parse_record_reply, read_info
from .output import emit


def validate_output(out: Path, duration: float) -> None:
    if not math.isfinite(duration) or not 0.1 <= duration <= 300:
        raise ValueError("Realtime duration must be finite and in 0.1..300 seconds")
    if out.suffix != ".bin":
        raise ValueError("Realtime output must end in .bin; recording completeness is unverified")
    if out.exists() or out.is_symlink():
        raise FileExistsError(f"Realtime output already exists: {out}")


async def _stop_owned(conn: Connection) -> dict | None:
    state = (await conn.device_info())["recording_state"]
    if state == "idle":
        return None
    if state not in {"recording", "paused"}:
        raise RuntimeError(f"Cannot clean up owned recording in state {state!r}")
    return await change_recording(conn, "stop")


async def _record_interval(conn: Connection, capture: RealtimeCapture, duration: float) -> dict:
    # Check immediately before sending START: never stop an existing recording.
    state = (await conn.device_info())["recording_state"]
    if state != "idle":
        raise ValueError(f"Cannot start realtime test while {state}; no command sent")
    try:
        # A lost START reply may still leave a running recorder. Cleanup is owed
        # once the request is attempted, even when parsing/readback later fails.
        start = parse_record_reply("start", await conn.command(P.START_RECORDING))
        deadline = asyncio.get_running_loop().time() + 3
        while (state := (await conn.device_info())["recording_state"]) != "recording":
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(f"Realtime start acknowledged but readback state is {state}")
            await asyncio.sleep(0.1)
        await capture.wait(duration)
        stop = await _stop_owned(conn)
        if stop is None:
            raise RuntimeError("Owned realtime recording ended before explicit stop")
        if stop["name"] != start["name"]:
            raise RuntimeError("Stopped recording name differs from realtime start reply")
    except BaseException as error:
        try:
            await _stop_owned(conn)
        except BaseException as cleanup_error:  # noqa: BLE001 - retain cleanup failure on cancellation
            raise RuntimeError(
                f"Realtime recording failed: {error}; recording cleanup also failed: {cleanup_error}"
            ) from error
        raise
    # The first observed recording had two final notifications during STOP.
    # A bounded tail retains delayed delivery; it is not a loss-free barrier.
    await capture.wait(1)
    if capture.bytes == 0:
        raise RuntimeError("Owned recording produced no realtime audio bytes")
    return {"start": start, "stop": stop, "tail_seconds": 1}


async def capture_audio(conn: Connection, out: Path, duration: float, *, record: bool = False) -> dict:
    """Save a successful bounded window atomically; stop only our explicit test."""
    out = Path(out)
    validate_output(out, duration)
    out.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{out.name}.", suffix=".part", dir=out.parent)
    part = Path(temporary)
    digest = hashlib.sha256()
    recording = None
    started = time.monotonic()
    try:
        with os.fdopen(descriptor, "wb") as handle:

            def write(data: bytes) -> int:
                count = handle.write(data)
                digest.update(data[:count])
                return count

            async with conn.realtime_capture(write) as capture:
                if record:
                    recording = await _record_interval(conn, capture, duration)
                else:
                    await capture.wait(duration)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(part, out)
        return {
            "path": str(out),
            "bytes": capture.bytes,
            "packets": capture.packets,
            "sha256": digest.hexdigest(),
            "requested_seconds": duration,
            "capture_seconds": time.monotonic() - started,
            "scope": "realtime_notification_window",
            "completeness": "unverified; no offline recording comparison",
            "recording": recording,
        }
    finally:
        part.unlink(missing_ok=True)


def main(
    out: Annotated[Path, typer.Option(help="New .bin file for raw notification bytes.")],
    duration: Annotated[float, typer.Option(min=0.1, max=300)] = 30,
    record: Annotated[
        bool, typer.Option(help="Create and stop a recording; requires an idle device.")
    ] = False,
    serial: str = OWNED_SERIAL,
    seconds: ScanSeconds = 12,
):
    """Capture e5e3 bytes; passive by default, --record creates a bounded test recording."""
    validate_output(out, duration)

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            identity = await read_info(conn, serial)
            return {"serial": identity["serial"]} | await capture_audio(conn, out, duration, record=record)

    emit(asyncio.run(run()))
