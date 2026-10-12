"""Explicit single-recording deletion; matching replies do not prove deletion."""

import asyncio
from dataclasses import asdict
from typing import Annotated

import typer

from . import protocol as P
from .ble_target import find_device
from .connection import Connection, validate_filename
from .output import emit


class DeletionUnverified(RuntimeError):
    def __init__(self, outcome: dict):
        super().__init__(outcome["error"])
        self.outcome = outcome


class DeletionCancelled(asyncio.CancelledError):
    def __init__(self, outcome: dict):
        super().__init__(outcome["error"])
        self.outcome = outcome


async def delete_recording(conn: Connection, name: str) -> dict:
    """Send once, then require absence from a complete new file list."""
    payload = validate_filename(name)
    state = await conn.device_info()
    if state["recording_state"] != "idle":
        raise ValueError("Deletion requires an idle recorder; no delete command sent")
    before = await conn.file_list()
    if not any(entry.name == name for entry in before):
        raise ValueError(f"Recording not listed: {name}; no delete command sent")
    # Buffered reads need not suspend. Honor pending cancellation before mutation.
    await asyncio.sleep(0)
    outcome = {
        "ok": False,
        "operation": "delete_recording",
        "name": name,
        "status": "unknown",
        "response_received": False,
        "reply_hex": None,
        "before": [asdict(entry) for entry in before],
        "after": None,
        "verification": None,
        "scope": "listed_recording_absence",
        "secure_erasure_verified": False,
        "retry_attempted": False,
        "error": None,
    }
    try:
        reply = await conn.command(P.DELETE_FILE, payload)
        outcome["response_received"] = True
        outcome["reply_hex"] = reply.hex()
        # A buffered ACK must not hide SIGINT until asyncio.run has already exited.
        await asyncio.sleep(0)
        after = await conn.file_list()
        outcome["after"] = [asdict(entry) for entry in after]
        await asyncio.sleep(0)
        if any(entry.name == name for entry in after):
            outcome["status"] = "target_still_listed"
            raise RuntimeError("Delete received a reply but the recording remains listed")
    except asyncio.CancelledError as error:
        outcome["cancelled"] = True
        outcome["error"] = "Canceled after delete attempt; device outcome unknown; not retried"
        raise DeletionCancelled(outcome) from error
    except Exception as error:
        outcome["error"] = f"{type(error).__name__}: {error}"
        raise DeletionUnverified(outcome) from error
    outcome.update(ok=True, status="target_absent", verification="absent_from_complete_file_list")
    return outcome


def main(
    name: str,
    serial: Annotated[str, typer.Option(help="Exact recorder serial; required for deletion.")],
    confirm_delete: Annotated[str, typer.Option(help="Repeat NAME to confirm deletion of this recording.")],
    seconds: Annotated[float, typer.Option(min=0.1, max=60)] = 12,
):
    """Delete one listed recording. This changes device storage; it does not erase local exports."""
    validate_filename(name)
    if confirm_delete != name:
        raise ValueError("--confirm-delete must exactly match NAME; no connection attempted")
    if (
        not serial
        or len(serial) > 10
        or not serial.isascii()
        or any(ord(char) <= 32 or ord(char) == 127 for char in serial)
    ):
        raise ValueError("--serial must contain 1..10 printable ASCII characters without spaces")

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            actual = await conn.serial()
            if actual != serial:
                raise ValueError(f"Connected serial {actual!r} differs from selected {serial!r}")
            try:
                result = await delete_recording(conn, name)
            except (DeletionUnverified, DeletionCancelled) as error:
                result = error.outcome
            return result | {"serial": actual}

    result = asyncio.run(run())
    emit(result)
    if not result["ok"]:
        raise typer.Exit(code=130 if result.get("cancelled") else 1)
