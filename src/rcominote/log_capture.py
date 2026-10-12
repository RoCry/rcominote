"""Bounded Actions logs and fixed diagnostic queries; no arbitrary shell, storage writes, or reboot."""

import asyncio
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from bleak import BleakClient
from bleak.exc import BleakError

from .ble_target import OWNED_SERIAL, find_device
from .code_references import BLOCKS, VENDOR_BLOCKS, read_block
from .log_probe import ACK, NOTIFY, PREPARE, SERVICE, WRITE

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


def observed_logsrv_entry(frames: list[dict]) -> bool:
    text = "".join(frame.get("text", "") for frame in frames)
    match = re.search(r"(?m)^\*0x[0-9a-f]+ logsrv[ \t]*\r?\n[^\n]*\n[^\n]*entry: (0x[0-9a-f]+)", text)
    if match and match[1] != "0x1000bf21":
        raise ValueError(f"Live logsrv entry changed: {match[1]}; fixed sample is not applicable")
    return match is not None


def observed_vendor_entries(frames: list[dict]) -> bool:
    """Both exact live thread names/entries must precede fixed vendor code reads."""
    text = "".join(frame.get("text", "") for frame in frames)
    complete = True
    for name, expected in (("vendor_read", "0x1000a01d"), ("vendor", "0x10009e9d")):
        entries = re.findall(
            rf"(?m)^[ *]0x[0-9a-f]+ {name}[ \t]*\r?\n[^\n]*\n[^\n]*entry: (0x[0-9a-f]+)",
            text,
        )
        if entries and entries != [expected]:
            raise ValueError(f"Live {name} entry changed or repeated: {entries}")
        complete = complete and bool(entries)
    return complete


def observed_vendor_code(frames: list[dict]) -> bool:
    text = "".join(frame.get("text", "") for frame in frames)
    if not re.search(r"(?m)^1000a01c:[^\r\n]*\r?\n", text):
        return False
    # Entry captured independently twice before deriving these six literal addresses.
    capture = {
        "serial": OWNED_SERIAL,
        "ok": True,
        "fixed_text_commands": ["dbg mdb 1000a01c 10"],
        "frames": frames,
    }
    if read_block(capture, 0x1000A01C, 16).hex() != "8fb5544c544b55485549564fdff88081":
        raise ValueError("Live vendor_read code changed; fixed literals are not applicable")
    return True


def observed_logsrv_code(frames: list[dict]) -> bool:
    text = "".join(frame.get("text", "") for frame in frames)
    rows = re.findall(r"(?m)^1000bf20: ((?:[0-9a-f]{2} ){15}[0-9a-f]{2}) {2,}", text)
    if rows and rows != ["2d e9 f0 47 61 49 62 4e 86 b0 50 20 a1 f0 ab fa"]:
        raise ValueError("Live logsrv code changed or repeated; literal addresses are not applicable")
    return bool(rows)


def observed_logsrv_literals(frames: list[dict]) -> bool:
    text = "".join(frame.get("text", "") for frame in frames)
    rows = re.findall(r"(?m)^1000c0ac: ((?:[0-9a-f]{2} ){7}[0-9a-f]{2}) {2,}", text)
    if rows and rows != ["ba 26 0c 10 1c a5 0b 10"]:
        raise ValueError("Live logsrv literals changed or repeated; references are not applicable")
    return bool(rows)


def verify_readback(result: dict) -> None:
    """Transport completion does not prove shell output survived firmware buffering."""
    result["transport_ok"] = result["ok"]
    reads = [
        block
        for block in (*BLOCKS, *VENDOR_BLOCKS)
        if f"dbg mdb {block[0]:x} {block[1]:x}" in result["fixed_text_commands"]
    ]
    if not reads:
        return
    result["readback_complete"] = False
    if not result["transport_ok"]:
        return
    try:
        for address, length, *_ in reads:
            read_block(result, address, length)
    except ValueError as error:
        result["error"] = str(error)
        result["ok"] = False
    else:
        result["readback_complete"] = True


async def capture(
    *,
    serial: str,
    duration: float,
    device_info: bool = False,
    commands: bool = False,
    flash_header: bool = False,
    platform_info: bool = False,
    kernel_info: bool = False,
    threads: bool = False,
    stacks: bool = False,
    code_sample: bool = False,
    code_literals: bool = False,
    code_references: bool = False,
    vendor_code: bool = False,
) -> dict:
    if (code_sample or code_literals or code_references or vendor_code) and serial != OWNED_SERIAL:
        raise ValueError("Code sample address is evidenced only for owned C261CF0430 FW 1.0.4")
    code_literals = code_literals or code_references
    queue = asyncio.Queue()
    stream = Stream()
    origin = time.monotonic()
    result = {
        "captured_at": datetime.now(UTC).isoformat(),
        "serial": serial,
        "duration_seconds": duration,
        "scope": "PREPARE/DEFAULT_START/STOP; fixed diagnostics and optional bounded reads; no storage writes/reboot",
        "fixed_text_commands": (
            (["kernel version", "device levels", "device levels"] if device_info else [])
            + (["help", "dbg"] if commands else [])
            + (["dbg fread spi_flash 0", "help"] if flash_header else [])
            + (
                ["app", "system", "dbg nvram FW_VERION", "dbg nvram BT_LE_NAME", "help"]
                if platform_info
                else []
            )
            + (
                [
                    "kernel threads",
                    "dbg mdb 1000a01c 10",
                    "dbg mdb 10009e9c 10",
                    "help",
                    *(f"dbg mdb {block[0]:x} {block[1]:x}" for block in VENDOR_BLOCKS[2:]),
                    "help",
                ]
                if vendor_code
                else []
            )
            + (["kernel", "kernel uptime", "help"] if kernel_info else [])
            + (["kernel uptime", "kernel threads", "kernel uptime", "help"] if threads else [])
            + (["kernel stacks", "help"] if stacks else [])
            + (["kernel threads", "dbg mdb 1000bf20 10", "help"] if code_sample or code_literals else [])
            + (["dbg mdb 1000c0ac 8", "help"] if code_literals else [])
            + (
                ["dbg mdb 100c26ba d", "dbg mdb 100ad486 10", "dbg mdb 1000bf30 10", "help"]
                if code_references
                else []
            )
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
    async with BleakClient(
        device, timeout=20, disconnected_callback=lambda _: queue.put_nowait(None)
    ) as client:
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
                if command == "dbg mdb 1000bf20 10":
                    # Revalidate the live entry in this session before any memory read.
                    async with asyncio.timeout(5):
                        while not observed_logsrv_entry(stream.frames):
                            await pump(timeout=5)
                if command in {"dbg mdb 1000a01c 10", "dbg mdb 10009e9c 10"}:
                    async with asyncio.timeout(5):
                        while not observed_vendor_entries(stream.frames):
                            await pump(timeout=5)
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in VENDOR_BLOCKS[2:]}:
                    async with asyncio.timeout(5):
                        while not observed_vendor_code(stream.frames):
                            await pump(timeout=5)
                if command == "dbg mdb 1000c0ac 8":
                    # Both literal loads are evidenced in the live entry bytes:
                    # Align(PC, 4) + imm = 0x1000bf28 + 0x184 / 0x188.
                    async with asyncio.timeout(5):
                        while not observed_logsrv_code(stream.frames):
                            await pump(timeout=5)
                if command in {"dbg mdb 100c26ba d", "dbg mdb 100ad486 10", "dbg mdb 1000bf30 10"}:
                    # Pinned r1 literal, BL target, and BL return address. Do not
                    # follow arbitrary pointer values or infer physical offsets.
                    async with asyncio.timeout(5):
                        while not observed_logsrv_literals(stream.frames):
                            await pump(timeout=5)
                encoded = command.encode("ascii")
                tlv = b"\x01" + len(encoded).to_bytes(2, "little") + encoded
                await request(b"\x1d\x10\x81" + len(tlv).to_bytes(2, "little") + tlv)
            deadline = time.monotonic() + duration
            while (remaining := deadline - time.monotonic()) > 0:
                try:
                    await pump(timeout=remaining)
                except TimeoutError:
                    break
        except (ValueError, RuntimeError, OSError, BleakError) as error:
            result["error"] = str(error) or type(error).__name__
        finally:
            if start_attempted and client.is_connected:
                try:
                    await request(STOP)
                    async with asyncio.timeout(5):
                        while not stream.ended:
                            await pump(timeout=5)
                except (ValueError, RuntimeError, OSError, BleakError) as error:
                    result["stop_error"] = str(error) or type(error).__name__
            if client.is_connected:
                await client.stop_notify(NOTIFY)
    result |= {
        "ack_count": stream.acks,
        "end_received": stream.ended,
        "pending_hex": stream.pending.hex(),
        "text_bytes": sum(
            len(bytes.fromhex(row["hex"])) - 8 for row in stream.frames if row["command"] == 0xF0
        ),
    }
    result["ok"] = (
        "error" not in result
        and "stop_error" not in result
        and stream.acks == expected_acks
        and stream.ended
        and not stream.pending
    )
    verify_readback(result)
    return result


def main(
    out: Annotated[Path, typer.Option(help="New evidence JSON; keep raw logs in ignored artifacts/")],
    serial: str = OWNED_SERIAL,
    duration: Annotated[float, typer.Option(min=1, max=30)] = 15,
    device_info: Annotated[
        bool, typer.Option(help="Also request fixed kernel version and device levels (twice)")
    ] = False,
    commands: Annotated[
        bool, typer.Option(help="Also request fixed help and bare dbg command listings")
    ] = False,
    flash_header: Annotated[
        bool, typer.Option(help="Read only NOR offset 0, fixed 512 bytes; not a backup")
    ] = False,
    platform_info: Annotated[
        bool, typer.Option(help="Fixed app/system help and two bounded NVRAM getters")
    ] = False,
    kernel_info: Annotated[bool, typer.Option(help="Fixed kernel help and uptime queries")] = False,
    threads: Annotated[
        bool, typer.Option(help="Fixed thread listing bracketed by uptime; verify help first")
    ] = False,
    stacks: Annotated[bool, typer.Option(help="Compact thread stack-usage table; no stack contents")] = False,
    code_sample: Annotated[
        bool, typer.Option(help="Owned FW1.0.4 only: 16 bytes at observed logsrv code entry")
    ] = False,
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
            kernel_info=kernel_info,
            threads=threads,
            stacks=stacks,
            code_sample=code_sample,
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
