"""Experimental fixed FW010004 reads; live preflight currently fails log framing.

No successful audio snapshot yet. See docs/note-call-audio-2026-10-13.md.
"""

import asyncio
import gzip
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import typer

from rcominote import protocol as P
from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.code_guards import observed_block
from rcominote.connection import Connection
from rcominote.device_commands import change_recording, parse_record_reply, read_info
from rcominote.log_capture import START, STOP
from rcominote.log_probe import NOTIFY, PREPARE, SERVICE, WRITE
from rcominote.log_stream import Stream
from rcominote.output import new_output

IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
IMAGE = Path(__file__).resolve().parents[3] / (
    "docs/evidence/minimal-image-2026-10-13/original-system.bin.gz"
)
# Hash-bound code/literals for mode, policy, GPIO, word-load shell and ADC RMW helpers.
GUARDS = (
    (0x1000AB40, 16),
    (0x1000ABEC, 4),
    (0x1000207C, 16),
    (0x1000208C, 16),
    (0x10030608, 16),
    (0x100BC1F0, 12),
    (0x100A18E0, 16),
    (0x100A18F0, 14),
    (0x100251A0, 16),
    (0x100251B0, 16),
    (0x100BA800, 4),
    (0x100A5652, 16),
    (0x100A5662, 14),
    (0x100A5670, 16),
)
RAM_READS = {0x1800BE70: 1, 0x180015E2: 2, 0x180195B0: 4}
# Ordinary LDR or LDR/STR register access in the actual image; never byte-read MMIO.
WORD_READS = (0x40068234, 0x4005C104, 0x4005C130)


def now() -> str:
    return datetime.now(UTC).isoformat()


def guard_bytes() -> dict[int, bytes]:
    image = gzip.decompress(IMAGE.read_bytes())
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA:
        raise ValueError("Original system image hash differs; no device access permitted")
    return {address: image[address - 0x10000000 : address - 0x10000000 + size] for address, size in GUARDS}


class FixedReads:
    def __init__(self, conn: Connection, report: dict):
        self.conn = conn
        self.report = report
        self.stream = Stream()
        self.queue = asyncio.Queue(maxsize=256)
        self.expected = 0
        self.failure = None
        self.verified = False
        report.update(frames=self.stream.frames, reads=[], notifications=[])

    def receive(self, _sender, data):
        if len(self.report["notifications"]) >= 1024:
            self.failure = RuntimeError("Audio-state diagnostic notification limit exceeded")
            return
        self.report["notifications"].append({"received_at": now(), "hex": bytes(data).hex()})
        try:
            self.queue.put_nowait(bytes(data))
        except asyncio.QueueFull:
            self.failure = RuntimeError("Audio-state diagnostic queue overflow")

    async def pump(self):
        self.conn._check_failure()
        if self.failure:
            raise self.failure
        self.stream.feed(await asyncio.wait_for(self.queue.get(), timeout=5))
        if len(self.stream.frames) > 1024:
            raise RuntimeError("Audio-state diagnostic frame limit exceeded")

    async def request(self, packet: bytes):
        self.conn._check_failure()
        self.expected += 1
        async with asyncio.timeout(5):
            await self.conn.client.write_gatt_char(WRITE, packet, response=True)
            while self.stream.acks < self.expected:
                await self.pump()

    async def text(self, command: str):
        encoded = command.encode() + b"\n"
        tlv = b"\x01" + len(encoded).to_bytes(2, "little") + encoded
        await self.request(b"\x1d\x10\x81" + len(tlv).to_bytes(2, "little") + tlv)

    async def read(self, address: int, size: int, *, word: bool = False) -> int | bytes:
        if word:
            if not self.verified or address not in WORD_READS or size != 4:
                raise ValueError("Unverified or non-profile word read refused")
        elif (address, size) not in GUARDS and not (self.verified and RAM_READS.get(address) == size):
            raise ValueError("Non-profile byte read refused")
        command = f"dbg mdw {address:x} 1" if word else f"dbg mdb {address:x} {size:x}"
        start = len(self.stream.frames)
        row = {"command": command, "started_at": now(), "frame_start": start}
        self.report["reads"].append(row)
        await self.text(command)
        await self.text("help")
        async with asyncio.timeout(5):
            while True:
                frames = self.stream.frames[start:]
                if word:
                    text = "".join(frame.get("text", "") for frame in frames)
                    values = re.findall(rf"(?m)^{address:08x}: ([0-9a-fA-F]{{8}})[ \t]+[^\r\n]*\r?\n", text)
                    if len(values) > 1:
                        raise ValueError("Repeated MMIO row, not a single observation")
                    value = int(values[0], 16) if values else None
                else:
                    value = observed_block(frames, address, size)
                if value is not None:
                    row.update(
                        ended_at=now(),
                        frame_end=len(self.stream.frames),
                        value_hex=(f"{value:08x}" if word else value.hex()),
                    )
                    return value
                await self.pump()

    async def verify(self, guards: dict[int, bytes]):
        for address, expected in guards.items():
            if await self.read(address, len(expected)) != expected:
                raise ValueError(f"Live code/literal changed at {address:#x}; recording not started")
        self.verified = True

    async def snapshot(self) -> dict:
        policy = int.from_bytes(await self.read(0x180195B0, 4), "little")
        if policy != 0x180015D8:
            raise ValueError(f"Unexpected audio policy {policy:#x}; no pointer chasing")
        mode = int.from_bytes(await self.read(0x1800BE70, 1), "little")
        gain = int.from_bytes(await self.read(0x180015E2, 2), "little", signed=True)
        gpio = await self.read(0x40068234, 4, word=True)
        digital = await self.read(0x4005C104, 4, word=True)
        analog = await self.read(0x4005C130, 4, word=True)
        return {
            "mode_raw": mode,
            "mode": P.recording_mode(mode),
            "policy_pointer": f"{policy:08x}",
            "gain_raw": gain,
            "gpiob_idat": f"{gpio:08x}",
            "gpiob18_sample": (gpio >> 18) & 1,
            "adc_ch0_digital_word": f"{digital:08x}",
            "adc_ch0_digital_gain_field": digital & 15,
            "adc_ch0_analog_word": f"{analog:08x}",
            "adc_ch0_analog_gain_fields": analog & 0xF003,
        }


async def measure_recording(conn: Connection, reader: FixedReads, report: dict):
    before = report["before_start"] = await conn.device_info()
    if before["recording_state"] != "idle":
        raise ValueError("Recording already active; no START or STOP sent")
    try:
        report["start_attempted_at"] = now()
        report["start"] = parse_record_reply("start", await conn.command(P.START_RECORDING))
        async with asyncio.timeout(3):
            while (await conn.device_info())["recording_state"] != "recording":
                await asyncio.sleep(0.1)
        report["snapshot"] = await reader.snapshot()
        after = report["after_reads"] = await conn.device_info()
        if after["recording_state"] != "recording" or not (
            before["mode"] == after["mode"] == report["snapshot"]["mode"]
        ):
            raise RuntimeError("Recording state or mode changed across non-atomic snapshot")
    except BaseException as error:
        report["measurement_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        try:
            raw = await conn.command(P.GET_RECORDING_INFO)
            report["cleanup_recording_info_raw"] = raw.hex()
            if raw != b"\x01":
                if len(raw) < 20 or raw[0] not in (0, 2) or "start" not in report:
                    raise RuntimeError("Recording ownership unknown; reconnect and inspect manually")
                if P.text(raw[1:15]) != report["start"]["name"]:
                    raise RuntimeError("Current recording differs from owned test; STOP refused")
                report["stop"] = await change_recording(conn, "stop")
                if report["stop"]["name"] != report["start"]["name"]:
                    raise RuntimeError("STOP name differs from owned test")
            report["final_device_info"] = await conn.device_info()
            if report["final_device_info"]["recording_state"] != "idle":
                raise RuntimeError("Final recording state is not idle")
        except BaseException as error:
            report["cleanup_error"] = f"{type(error).__name__}: {error}"
            raise RuntimeError(
                "Recording cleanup not confirmed; reconnect and inspect immediately"
            ) from error


async def capture(report: dict):
    guards = guard_bytes()
    async with Connection(await find_device(serial=OWNED_SERIAL, seconds=8)) as conn:
        identity = report["identity"] = await read_info(conn, OWNED_SERIAL)
        if identity["device"]["version"] != "010004" or identity["device"]["recording_state"] != "idle":
            raise ValueError("Expected owned idle FW010004")
        if conn.client.services.get_service(SERVICE) is None:
            raise ValueError("Missing Actions diagnostic service")
        reader = FixedReads(conn, report)
        await conn.client.start_notify(NOTIFY, reader.receive)
        attempted = False
        try:
            await reader.request(PREPARE)
            attempted = True
            await reader.request(START)
            await reader.verify(guards)
            await measure_recording(conn, reader, report)
        except BaseException as error:
            report["capture_error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            try:
                if attempted and conn.client.is_connected:
                    await reader.request(STOP)
                    async with asyncio.timeout(5):
                        while not reader.stream.ended:
                            await reader.pump()
            except BaseException as error:
                report["log_cleanup_error"] = f"{type(error).__name__}: {error}"
                if "capture_error" not in report:
                    raise
            finally:
                report["transport"] = {
                    "acks": reader.stream.acks,
                    "expected_acks": reader.expected,
                    "end_received": reader.stream.ended,
                    "pending_bytes": len(reader.stream.pending),
                    "pending_hex": reader.stream.pending.hex(),
                }
                if conn.client.is_connected:
                    try:
                        await conn.client.stop_notify(NOTIFY)
                    except BaseException as error:
                        report["unsubscribe_error"] = f"{type(error).__name__}: {error}"
                        if "capture_error" not in report and "log_cleanup_error" not in report:
                            raise
        if not reader.stream.ended or reader.stream.pending or reader.stream.acks != reader.expected:
            raise RuntimeError("Diagnostic stream incomplete")


def main(out: Path, record: bool = False):
    """One fixed read profile; --record explicitly creates/stops an idle-device test."""
    new_output(out)
    if not record:
        raise ValueError("This profile measures active recording; explicit --record required")
    report = {"serial": OWNED_SERIAL, "started_at": now(), "image_sha256": IMAGE_SHA, "ok": False}
    try:
        asyncio.run(capture(report))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = now()
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"frames", "reads", "notifications"}},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    typer.run(main)
