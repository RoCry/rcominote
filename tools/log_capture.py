#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["bleak>=1.1,<2", "typer>=0.16,<1"]
# ///
"""Bounded Actions logs and fixed diagnostic queries; no arbitrary shell, writes, or reboot."""

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from ble_target import OWNED_SERIAL, find_device
from bleak import BleakClient
from log_probe import ACK, NOTIFY, PREPARE, SERVICE, WRITE

START = bytes.fromhex("1d108105000002002000")
STOP = bytes.fromhex("1d108105000002002100")


class Stream:
    """GATT notifications are fragments of the SDK byte stream, not message boundaries."""

    def __init__(self):
        self.pending = bytearray()
        self.frames: list[dict] = []
        self.acks = 0
        self.ended = False

    def feed(self, data: bytes):
        self.pending.extend(data)
        while len(self.pending) >= 5:
            if self.pending[0] != 0x1D or self.pending[2] != 0x81:
                raise ValueError(f"Unexpected Actions log header: {self.pending[:5].hex()}")
            length = int.from_bytes(self.pending[3:5], "little")
            if length > 4096:
                raise ValueError(f"Unexpected Actions log payload size {length}")
            if len(self.pending) < 5 + length:
                return
            frame = bytes(self.pending[: 5 + length])
            del self.pending[: 5 + length]
            command, payload = frame[1], frame[5:]
            row = {"command": command, "hex": frame.hex()}
            if command == 0x10:
                if frame != ACK:
                    raise ValueError(f"Unexpected ACK: {frame.hex()}")
                self.acks += 1
            elif command == 0xF1:
                if payload:
                    raise ValueError("Nonempty log end frame")
                self.ended = True
            elif command == 0xF0:
                if len(payload) < 3 or int.from_bytes(payload[1:3], "little") != len(payload) - 3:
                    raise ValueError("Invalid log TLV length")
                row |= {"log_type": payload[0], "text": payload[3:].decode("utf-8", errors="replace")}
            else:
                raise ValueError(f"Unexpected log command {command:#x}")
            self.frames.append(row)


async def capture(
    *,
    serial: str,
    duration: float,
    device_info: bool = False,
    commands: bool = False,
    flash_header: bool = False,
    platform_info: bool = False,
) -> dict:
    queue = asyncio.Queue()
    stream = Stream()
    origin = time.monotonic()
    result = {
        "captured_at": datetime.now(UTC).isoformat(),
        "serial": serial,
        "duration_seconds": duration,
        "scope": "PREPARE/DEFAULT_START/STOP; fixed queries only; optional 512-byte NOR header read",
        "fixed_text_commands": (
            (["kernel version", "device levels", "device levels"] if device_info else [])
            + (["help", "dbg"] if commands else [])
            + (["dbg fread spi_flash 0", "help"] if flash_header else [])
            + (["app", "system", "dbg nvram FW_VERION", "dbg nvram BT_LE_NAME", "help"] if platform_info else [])
        ),
        "notifications": [],
        "writes": [],
        "frames": stream.frames,
        "ok": False,
    }

    def receive(_char, data):
        queue.put_nowait(bytes(data))

    async def pump(timeout: float):
        packet = await asyncio.wait_for(queue.get(), timeout=timeout)
        if packet is None:
            raise ConnectionError("CoMi disconnected during log capture")
        result["notifications"].append({"seconds": round(time.monotonic() - origin, 3), "hex": packet.hex()})
        if len(result["notifications"]) > 8192:
            raise RuntimeError("Log notification limit exceeded")
        stream.feed(packet)

    async def wait_for_ack(count: int):
        async with asyncio.timeout(5):
            while stream.acks < count:
                await pump(timeout=5)

    device = await find_device(serial=serial, seconds=12)
    async with BleakClient(device, timeout=20, disconnected_callback=lambda _: queue.put_nowait(None)) as client:
        if client.services.get_service(SERVICE) is None:
            raise ValueError("Selected device has no Actions log service")
        await client.start_notify(NOTIFY, receive)

        async def send(packet):
            result["writes"].append(packet.hex())
            await client.write_gatt_char(WRITE, packet, response=True)

        start_attempted = False
        expected_acks = 0

        async def request(packet):
            nonlocal expected_acks
            expected_acks += 1
            await send(packet)
            await wait_for_ack(expected_acks)

        try:
            await request(PREPARE)
            start_attempted = True
            await request(START)
            for command in result["fixed_text_commands"]:
                # Fixed source-audited queries only. Help/duplicate table output may
                # fill the SDK's 504-byte initial buffer; never infer failure from silence.
                encoded = command.encode("ascii")
                tlv = b"\x01" + len(encoded).to_bytes(2, "little") + encoded
                await request(b"\x1d\x10\x81" + len(tlv).to_bytes(2, "little") + tlv)
            deadline = time.monotonic() + duration
            while (remaining := deadline - time.monotonic()) > 0:
                try:
                    await pump(timeout=remaining)
                except TimeoutError:
                    break
        except Exception as error:
            result["error"] = str(error) or type(error).__name__
        finally:
            if start_attempted and client.is_connected:
                try:
                    await request(STOP)
                    async with asyncio.timeout(5):
                        while not stream.ended:
                            await pump(timeout=5)
                except Exception as error:
                    result["stop_error"] = str(error) or type(error).__name__
            if client.is_connected:
                await client.stop_notify(NOTIFY)
    result |= {
        "ack_count": stream.acks,
        "end_received": stream.ended,
        "pending_hex": stream.pending.hex(),
        "text_bytes": sum(len(bytes.fromhex(row["hex"])) - 8 for row in stream.frames if row["command"] == 0xF0),
    }
    result["ok"] = (
        "error" not in result
        and "stop_error" not in result
        and stream.acks == expected_acks
        and stream.ended
        and not stream.pending
    )
    return result


def main(
    out: Annotated[Path, typer.Option(help="New evidence JSON; keep raw logs in ignored artifacts/")],
    serial: str = OWNED_SERIAL,
    duration: Annotated[float, typer.Option(min=1, max=30)] = 15,
    device_info: Annotated[
        bool, typer.Option(help="Also request fixed kernel version and device levels (twice)")
    ] = False,
    commands: Annotated[bool, typer.Option(help="Also request fixed help and bare dbg command listings")] = False,
    flash_header: Annotated[bool, typer.Option(help="Read only NOR offset 0, fixed 512 bytes; not a backup")] = False,
    platform_info: Annotated[bool, typer.Option(help="Fixed app/system help and two bounded NVRAM getters")] = False,
):
    if out.exists():
        raise FileExistsError(f"Output already exists: {out}")
    result = asyncio.run(
        capture(
            serial=serial,
            duration=duration,
            device_info=device_info,
            commands=commands,
            flash_header=flash_header,
            platform_info=platform_info,
        )
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in result.items() if key not in ("frames", "notifications")},
            ensure_ascii=False,
            indent=2,
        )
    )
    if not result["ok"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
