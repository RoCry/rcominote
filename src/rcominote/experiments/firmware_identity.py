"""Read only fixed FW010004 getter evidence and its cached parameter version block."""

import asyncio
import json
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


async def capture(report: dict) -> None:
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


def main(out: Path):
    """Capture a fixed128 B identity block; no storage reads/writes or getter execution."""
    if out.exists():
        raise FileExistsError(out)
    report = {"serial": OWNED_SERIAL, "captured_at": datetime.now(UTC).isoformat(), "ok": False}
    try:
        asyncio.run(capture(report))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x") as handle:
            handle.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in ("ok", "board_name", "version_name")}, ensure_ascii=False))


if __name__ == "__main__":
    typer.run(main)
