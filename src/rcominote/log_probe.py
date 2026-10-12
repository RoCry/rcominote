"""One fixed Actions log PREPARE handshake. No shell, logging mode, dump or reset commands."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from bleak import BleakClient

from .ble_target import OWNED_SERIAL, find_device

SERVICE = "e49a3001-f69a-11e8-8eb2-f2801f1b9fd1"
WRITE = "e49a3002-f69a-11e8-8eb2-f2801f1b9fd1"
NOTIFY = "e49a3003-f69a-11e8-8eb2-f2801f1b9fd1"
# Hand-encoded from pinned log_service.c: svc 1d, cmd 10, param type 81,
# 5-byte params: TLV code 00, len 0002 LE, PREPARE 0001 LE.
PREPARE = bytes.fromhex("1d108105000002000100")
# SDK _svc_prot_send_ack: 7-byte params, TLV 7f, len 4, value 100000 LE.
ACK = bytes.fromhex("1d108107007f0400a0860100")


async def probe(*, serial: str, seconds: float) -> dict:
    notifications = []
    queue = asyncio.Queue()

    def receive(_char, data):
        packet = bytes(data)
        notifications.append(packet.hex())
        queue.put_nowait(packet)

    def disconnected(_client):
        queue.put_nowait(None)

    result = {
        "captured_at": datetime.now(UTC).isoformat(),
        "advertised_serial": serial,
        "request_hex": PREPARE.hex(),
        "expected_ack_hex": ACK.hex(),
        "notifications_hex": notifications,
        "scope": "PREPARE only; no console text, log mode, dump, reset, or storage command",
        "ok": False,
    }
    device = await find_device(serial=serial, seconds=seconds)
    async with BleakClient(device, timeout=20, disconnected_callback=disconnected) as client:
        if client.services.get_service(SERVICE) is None:
            raise ValueError("Selected device has no Actions log service")
        await client.start_notify(NOTIFY, receive)
        await client.write_gatt_char(WRITE, PREPARE, response=True)
        received = bytearray()
        try:
            async with asyncio.timeout(5):
                while len(received) < len(ACK):
                    packet = await queue.get()
                    if packet is None:
                        raise ConnectionError("Device disconnected before ACK")
                    received.extend(packet)
                    if not ACK.startswith(received):
                        raise ValueError(f"Unexpected PREPARE response: {received.hex()}")
            result["ok"] = True
        except (TimeoutError, ConnectionError, ValueError) as error:
            result["error"] = str(error) or "PREPARE acknowledgement timed out after 5 seconds"
        finally:
            if client.is_connected:
                await client.stop_notify(NOTIFY)
    return result


def main(
    out: Annotated[Path, typer.Option(help="New evidence JSON path; refuses overwrite")],
    serial: str = OWNED_SERIAL,
    seconds: float = 12.0,
):
    if out.exists():
        raise FileExistsError(f"Output already exists: {out}")
    result = asyncio.run(probe(serial=serial, seconds=seconds))
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        handle.write(encoded)
    print(encoded, end="")
    if not result["ok"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
