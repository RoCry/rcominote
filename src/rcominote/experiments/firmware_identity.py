"""Read only fixed FW010004 getter evidence and its cached parameter version block."""

import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import typer
from bleak import BleakClient

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.code_guards import observed_block
from rcominote.connection import Connection
from rcominote.device_commands import read_info
from rcominote.log_capture import START, STOP
from rcominote.log_probe import NOTIFY, PREPARE, SERVICE, WRITE
from rcominote.log_stream import Stream
from rcominote.range_readback import read_range


async def capture(
    report: dict,
    *,
    cpu: bool = False,
    rom_table: bool = False,
    rom_entry: bool = False,
    rom_flow: bool = False,
) -> None:
    async with Connection(await find_device(serial=OWNED_SERIAL, seconds=12)) as conn:
        identity = await read_info(conn, OWNED_SERIAL)
        report["identity"] = identity
        if identity["device"]["version"] != "010004" or identity["device"]["recording_state"] != "idle":
            raise RuntimeError("Fixed reads require idle owned FW010004")
    stream = Stream()
    queue = asyncio.Queue()
    report["frames"] = stream.frames
    report["fixed_text_commands"] = []
    report["range_frame_spans"] = {}
    expected = 0

    def receive(_sender, data):
        queue.put_nowait(bytes(data))

    async def pump():
        packet = await asyncio.wait_for(queue.get(), timeout=5)
        if packet is None:
            raise ConnectionError("Log connection lost")
        stream.feed(packet)
        if len(stream.frames) > 1024:
            raise RuntimeError("Fixed identity capture exceeded frame limit")

    async with BleakClient(
        await find_device(serial=OWNED_SERIAL, seconds=12),
        disconnected_callback=lambda _: queue.put_nowait(None),
    ) as client:
        if client.services.get_service(SERVICE) is None:
            raise RuntimeError("Missing Actions log service")
        await client.start_notify(NOTIFY, receive)

        async def request(packet):
            nonlocal expected
            expected += 1
            await client.write_gatt_char(WRITE, packet, response=True)
            async with asyncio.timeout(5):
                while stream.acks < expected:
                    await pump()

        async def text(command):
            report["fixed_text_commands"].append(command)
            encoded = command.encode() + b"\n"
            tlv = b"\x01" + len(encoded).to_bytes(2, "little") + encoded
            await request(b"\x1d\x10\x81" + len(tlv).to_bytes(2, "little") + tlv)

        async def read(address, length):
            command = f"dbg mdb {address:x} {length:x}"
            start = len(stream.frames)
            await text(command)
            await text("help")
            async with asyncio.timeout(5):
                while any(
                    observed_block(stream.frames[start:], address + offset, min(16, length - offset)) is None
                    for offset in range(0, length, 16)
                ):
                    await pump()
            report["range_frame_spans"][command] = [start, len(stream.frames)]
            return read_range(report | {"ok": True}, address, length)

        attempted = False
        try:
            await request(PREPARE)
            attempted = True
            await request(START)
            guard = await read(0x100A0B00, 16)
            if guard.hex() != "4ff08073586800f53a7070474ff08070":
                raise RuntimeError(f"Actual parameter getter changed: {guard.hex()}")
            if cpu:
                # Actual mdw width4 wrapper and the word-load branch in print_buffer.
                for address, expected_hex in (
                    (0x100A18E0, "fff7d0bf13460a460221fff7cbbf13460a460421fff7c6bf73b582f7d5fc0024"),
                    (0x100251A0, "c8440198a6eb0a06cbe7042d03aa0dd1dbf8003042f829301d4a019000217bf0"),
                ):
                    if (await read(address, len(bytes.fromhex(expected_hex)))).hex() != expected_hex:
                        raise RuntimeError("Actual word-read implementation changed")
                start = len(stream.frames)
                await text("dbg mdw e000ed00 1")
                await text("help")
                async with asyncio.timeout(5):
                    while not re.search(
                        r"(?m)^e000ed00: ([0-9a-fA-F]{8})[ \t]+[^\r\n]*\r?\n",
                        "".join(frame.get("text", "") for frame in stream.frames[start:]),
                    ):
                        await pump()
                report["cpuid_frame_span"] = [start, len(stream.frames)]
                words = re.findall(
                    r"(?m)^e000ed00: ([0-9a-fA-F]{8})[ \t]+[^\r\n]*\r?\n",
                    "".join(frame.get("text", "") for frame in stream.frames[start:]),
                )
                if len(words) != 1:
                    raise RuntimeError("Expected exactly one CPUID row")
                value = int(words[0], 16)
                report["cpuid"] = {
                    "raw": f"0x{value:08x}",
                    "implementer": value >> 24,
                    "variant": (value >> 20) & 15,
                    "architecture": (value >> 16) & 15,
                    "part": f"0x{(value >> 4) & 0xFFF:03x}",
                    "revision": value & 15,
                }
            if rom_table or rom_entry or rom_flow:
                # Exact table entries referenced by checksum-verified actual boot.
                table = {address: await read(address, 16) for address in (0x190, 0x1B0, 0x1C0)}
                report["rom_table_blocks"] = {f"0x{a:08x}": raw.hex() for a, raw in table.items()}
                report["rom_entries"] = {}
                for name, address in (("adfu", 0x19C), ("crc", 0x1B8), ("checksum", 0x1C8)):
                    block = table[address & ~15]
                    offset = address & 15
                    pointer = int.from_bytes(block[offset : offset + 4], "little")
                    report["rom_entries"][name] = f"0x{pointer:08x}"
            if rom_entry or rom_flow:
                if report["rom_entries"]["adfu"] != "0x00001a51":
                    raise RuntimeError("ROM ADFU table entry changed; fixed code read refused")
                report["rom_adfu_prefix_hex"] = (await read(0x1A50, 64) + await read(0x1A90, 64)).hex()
            if rom_flow:
                prefix = bytes.fromhex(report["rom_adfu_prefix_hex"])
                if hashlib.sha256(prefix).hexdigest() != (
                    "3e089a1137768e844ed0f299e5feda85abe0a53305d7b8898fcd7e8e00066098"
                ):
                    raise RuntimeError("ROM entry changed; fixed callee reads refused")
                chunks = [await read(address, 64) for address in range(0x1900, 0x1A40, 64)]
                chunks.append(await read(0x1A40, 16))
                report["rom_flow_hex"] = b"".join(chunks).hex()
            boot = await read(0x01000000, 16)
            if int.from_bytes(boot[4:8], "little") != 0x01000040:
                raise RuntimeError("Parameter pointer differs; no pointer chasing performed")
            raw = b"".join(
                [await read(0x01000320, 64), await read(0x01000360, 64), await read(0x010003A0, 16)]
            )
            version = raw[8:136]
            report["parameter_version_hex"] = version.hex()
            report["board_name"] = version[0x50:0x70].split(b"\0", 1)[0].decode("ascii")
            report["version_name"] = version[0x10:0x50].split(b"\0", 1)[0].decode("ascii")
        finally:
            if attempted and client.is_connected:
                await request(STOP)
                async with asyncio.timeout(5):
                    while not stream.ended:
                        await pump()
            if client.is_connected:
                await client.stop_notify(NOTIFY)
    report |= {"ack_count": stream.acks, "expected_ack_count": expected, "end_received": stream.ended}
    if stream.acks != expected or not stream.ended or stream.pending:
        raise RuntimeError("Incomplete log transport")


def main(
    out: Path, cpu: bool = False, rom_table: bool = False, rom_entry: bool = False, rom_flow: bool = False
):
    """Read identity; optional fixed CPUID or boot-referenced ROM table reads only."""
    if out.exists():
        raise FileExistsError(out)
    report = {"serial": OWNED_SERIAL, "captured_at": datetime.now(UTC).isoformat(), "ok": False}
    try:
        asyncio.run(capture(report, cpu=cpu, rom_table=rom_table, rom_entry=rom_entry, rom_flow=rom_flow))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x") as handle:
            handle.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    summary = {key: report[key] for key in ("ok", "board_name", "version_name")}
    if cpu:
        summary["cpuid"] = report["cpuid"]
    if rom_table or rom_entry or rom_flow:
        summary["rom_entries"] = report["rom_entries"]
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    typer.run(main)
