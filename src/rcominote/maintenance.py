"""Fixed official-client requests with explicitly unverified device effects."""

import asyncio
from enum import StrEnum
from typing import Annotated

import typer

from . import protocol as P
from .ble_target import find_device
from .connection import Connection
from .device_commands import ScanSeconds
from .output import emit

app = typer.Typer(
    no_args_is_help=True,
    help="Explicit management requests. Exit3: submitted, effect unverified; error1, cancel130. No effect-success0.",
)
Serial = Annotated[str, typer.Option(help="Exact device serial; read back before the request.")]
Confirm = Annotated[str, typer.Option(help="Repeat the operation name to confirm this device mutation.")]


class Operation(StrEnum):
    bind = "bind"
    unbind = "unbind"
    format = "format"
    factory_reset = "factory-reset"
    phone_type = "phone-type"


class PhoneType(StrEnum):
    android = "android"
    ios = "ios"


# ACK timeouts follow official JS. Write-only5s is a host deadline, not device behavior.
REQUESTS = {
    Operation.bind: (P.BIND, True, 5.0),
    Operation.unbind: (P.BIND, False, 5.0),
    Operation.format: (0x10, True, 10.0),
    Operation.factory_reset: (0x12, False, 5.0),
    Operation.phone_type: (0x18, True, 5.0),
}


class MaintenanceUnverified(RuntimeError):
    def __init__(self, outcome: dict):
        super().__init__(outcome["error"])
        self.outcome = outcome


class MaintenanceCancelled(asyncio.CancelledError):
    def __init__(self, outcome: dict):
        super().__init__(outcome["error"])
        self.outcome = outcome


def encode_user_id(user_id: str) -> bytes:
    if (
        not 1 <= len(user_id) <= 16
        or not user_id.isascii()
        or any(not 0x20 <= ord(char) <= 0x7E for char in user_id)
    ):
        raise ValueError("User ID requires 1..16 printable ASCII bytes; never truncated")
    return user_id.encode("ascii").ljust(16, b"\0") + b"\0"


async def submit(conn: Connection, operation: Operation, payload: bytes = b"") -> dict:
    """Submit one named request; never promote ACK/write completion to device success."""
    if (await conn.device_info())["recording_state"] != "idle":
        raise ValueError("Management requests require an idle recorder; no mutation sent")
    await asyncio.sleep(0)  # Honor pending cancellation before a destructive write.
    opcode, expects_reply, timeout = REQUESTS[operation]
    outcome = {
        "ok": False,
        "operation": operation.value,
        "status": "unknown",
        "request_attempted": True,
        "request_sent": None,
        "response_expected": expects_reply,
        "response_received": False,
        "reply_hex": None,
        "device_effect_verified": False,
        "scope": "request_submission_only",
        "retry_attempted": False,
        "error": None,
    }
    try:
        async with asyncio.timeout(timeout):
            if expects_reply:
                reply = await conn.command(opcode, payload, timeout=timeout)
                outcome["response_received"] = True
                outcome["reply_hex"] = reply.hex()
            else:
                await conn.send_only(opcode, payload, timeout=timeout)
            outcome["request_sent"] = True
            await asyncio.sleep(0)  # Buffered ACKs can otherwise hide pending SIGINT.
    except asyncio.CancelledError as error:
        outcome["cancelled"] = True
        outcome["error"] = "Canceled after management request attempt; device outcome unknown; not retried"
        raise MaintenanceCancelled(outcome) from error
    except Exception as error:
        outcome["error"] = f"{type(error).__name__}: {error}"
        raise MaintenanceUnverified(outcome) from error
    outcome["status"] = "submitted_unverified"
    return outcome


def execute(operation: Operation, serial: str, confirm: str | None, seconds: float, payload: bytes = b""):
    if (
        not serial
        or len(serial) > 10
        or not serial.isascii()
        or any(ord(char) <= 32 or ord(char) == 127 for char in serial)
    ):
        raise ValueError("--serial requires 1..10 printable ASCII characters without spaces")
    if operation != Operation.phone_type and confirm != operation.value:
        raise ValueError(f"--confirm must exactly match {operation.value}; no connection attempted")

    async def run():
        result: dict | None = None
        try:
            async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
                actual = await conn.serial()
                if actual != serial:
                    raise ValueError(f"Connected serial {actual!r} differs from selected {serial!r}")
                try:
                    result = await submit(conn, operation, payload)
                except (MaintenanceUnverified, MaintenanceCancelled) as error:
                    result = error.outcome
        except asyncio.CancelledError:
            if result is None:
                raise
            result.update(
                status="unknown", cancelled=True, error="Canceled during disconnect; device outcome unknown"
            )
        except Exception as error:
            if result is None:
                raise
            result.update(status="unknown", error=f"Disconnect failed: {type(error).__name__}: {error}")
        return result | {"serial": serial}

    result = asyncio.run(run())
    emit(result)
    raise typer.Exit(
        code=130 if result.get("cancelled") else 3 if result["status"] == "submitted_unverified" else 1
    )


@app.command("bind")
def bind(user_id: str, serial: Serial, confirm: Confirm, seconds: ScanSeconds = 12):
    """Request binding to a literal ID; does not verify cloud identity. Exit3 if submitted."""
    execute(Operation.bind, serial, confirm, seconds, encode_user_id(user_id))


@app.command("unbind")
def unbind(
    serial: Serial,
    confirm: Confirm,
    seconds: ScanSeconds = 12,
    delete_recordings: bool = False,
    confirm_delete_all: Annotated[
        str | None, typer.Option(help="Repeat SERIAL when --delete-recordings is set.")
    ] = None,
):
    """Request unbinding, then disconnect. Optional deletion needs a separate serial confirmation."""
    if delete_recordings:
        if confirm_delete_all != serial:
            raise ValueError("--delete-recordings requires --confirm-delete-all matching SERIAL")
    elif confirm_delete_all is not None:
        raise ValueError("--confirm-delete-all requires --delete-recordings")
    execute(Operation.unbind, serial, confirm, seconds, bytes(16) + bytes([int(delete_recordings)]))


@app.command("format")
def format_device(serial: Serial, confirm: Confirm, seconds: ScanSeconds = 12):
    """Request device formatting. Data can be lost; ACK does not prove formatting. Exit3 if submitted."""
    execute(Operation.format, serial, confirm, seconds)


@app.command("factory-reset")
def factory_reset(serial: Serial, confirm: Confirm, seconds: ScanSeconds = 12):
    """Request factory reset, not reboot; write once and disconnect. Exit3 if submitted."""
    execute(Operation.factory_reset, serial, confirm, seconds)


@app.command("phone-type")
def phone_type(value: PhoneType, serial: Serial, seconds: ScanSeconds = 12):
    """Explicit Android0/iOS1 request; no known getter. Never selected automatically. Exit3 if submitted."""
    execute(Operation.phone_type, serial, None, seconds, bytes([0 if value == PhoneType.android else 1]))
