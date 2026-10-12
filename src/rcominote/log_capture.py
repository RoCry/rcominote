"""Bounded Actions logs and fixed diagnostic queries; no arbitrary shell, storage writes, or reboot."""

import asyncio
import time
from datetime import UTC, datetime

from bleak import BleakClient
from bleak.exc import BleakError

from .ble_target import OWNED_SERIAL, find_device
from .code_guards import (
    observed_block,
    observed_capacity_entries,
    observed_code,
    observed_handler_entry,
    observed_logsrv_code,
    observed_logsrv_entry,
    observed_logsrv_literals,
    observed_vendor_call,
    observed_vendor_code,
    observed_vendor_entries,
)
from .code_references import (
    BLOCKS,
    HANDLER_BLOCKS,
    HANDLER_CORE_BLOCKS,
    INFO_BLOCKS,
    INFO_BODY_BLOCKS,
    INFO_CAPACITY,
    INFO_REFERENCES,
    SPECIAL_BLOCKS,
    VENDOR_BLOCKS,
    read_block,
)
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


def verify_readback(result: dict) -> None:
    """Transport completion does not prove shell output survived firmware buffering."""
    result["transport_ok"] = result["ok"]
    reads = [
        block
        for block in dict.fromkeys((*BLOCKS, *VENDOR_BLOCKS, *HANDLER_BLOCKS, *INFO_BLOCKS))
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


def flushed_reads(blocks: tuple) -> list[str]:
    """Bound bursts; help flushes the firmware's short-output buffer after each batch."""
    commands = []
    for offset in range(0, len(blocks), 4):
        commands.extend(f"dbg mdb {b[0]:x} {b[1]:x}" for b in blocks[offset : offset + 4])
        commands.append("help")
    return commands


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
    vendor_handler: bool = False,
    device_info_code: bool = False,
) -> dict:
    if (
        code_sample or code_literals or code_references or vendor_code or vendor_handler or device_info_code
    ) and serial != OWNED_SERIAL:
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
                ["app", "system", "dbg nvram FW_VERION", "dbg nvram BT_LE_NAME", "dbg nvram BT_NAME", "help"]
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
            + (
                [
                    "kernel threads",
                    "dbg mdb 1000a01c 10",
                    "help",
                    "dbg mdb 1000a14c 10",
                    "help",
                    *(f"dbg mdb {b[0]:x} {b[1]:x}" for b in HANDLER_BLOCKS[2:4]),
                    # Firmware buffers short log output. Flush entry rows before
                    # the guard needs their bytes, otherwise ACK alone stalls it.
                    "help",
                    *flushed_reads(HANDLER_CORE_BLOCKS[4:]),
                    *(f"dbg mdb {b[0]:x} {b[1]:x}" for b in SPECIAL_BLOCKS[:2]),
                    "help",
                    *(f"dbg mdb {b[0]:x} {b[1]:x}" for b in SPECIAL_BLOCKS[2:4]),
                    "help",
                    *(f"dbg mdb {b[0]:x} {b[1]:x}" for b in SPECIAL_BLOCKS[4:6]),
                    "help",
                    *(f"dbg mdb {b[0]:x} {b[1]:x}" for b in SPECIAL_BLOCKS[6:]),
                    "help",
                ]
                if vendor_handler
                else []
            )
            + (["kernel uptime", "kernel threads", "kernel uptime", "help"] if threads else [])
            + (
                [
                    "kernel threads",
                    *flushed_reads(INFO_BLOCKS[:1]),
                    *flushed_reads(INFO_BLOCKS[1:2]),
                    *flushed_reads(INFO_BLOCKS[2:4]),
                    *flushed_reads(INFO_BLOCKS[4:7]),
                    *flushed_reads(INFO_BLOCKS[7:9]),
                    *flushed_reads(INFO_BODY_BLOCKS[9:]),
                    *flushed_reads(INFO_REFERENCES),
                    *flushed_reads(INFO_CAPACITY),
                ]
                if device_info_code
                else []
            )
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
            pending_reads = []
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
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in HANDLER_BLOCKS[2:]}:
                    async with asyncio.timeout(5):
                        while not observed_vendor_call(stream.frames):
                            await pump(timeout=5)
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in HANDLER_BLOCKS[4:]}:
                    async with asyncio.timeout(5):
                        while not observed_handler_entry(stream.frames):
                            await pump(timeout=5)
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in SPECIAL_BLOCKS}:
                    async with asyncio.timeout(5):
                        while not (
                            observed_code(
                                stream.frames,
                                0x1000B444,
                                "9a9a9a9a9a9521463046fff77dfad5e7",
                                "dispatch table tail",
                            )
                            and observed_code(
                                stream.frames,
                                0x1000B534,
                                "fff792fd62e721463046fff7bffd5de7",
                                "command 0x3a call",
                            )
                        ):
                            await pump(timeout=5)
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in SPECIAL_BLOCKS[2:]}:
                    async with asyncio.timeout(5):
                        while not (
                            observed_code(
                                stream.frames,
                                0x1000B0C0,
                                "30b58bb004460d461c22002103a80291",
                                "command 0x3a entry",
                            )
                            and observed_code(
                                stream.frames,
                                0x1000B0D0,
                                "aef0fafaa11c2023aa1e02a8aef0c7fa",
                                "command 0x3a continuation",
                            )
                        ):
                            await pump(timeout=5)
                if command in {"dbg mdb 100c26ba d", "dbg mdb 100ad486 10", "dbg mdb 1000bf30 10"}:
                    # Pinned r1 literal, BL target, and BL return address. Do not
                    # follow arbitrary pointer values or infer physical offsets.
                    async with asyncio.timeout(5):
                        while not observed_logsrv_literals(stream.frames):
                            await pump(timeout=5)
                encoded = command.encode("ascii")
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in INFO_CAPACITY}:
                    async with asyncio.timeout(5):
                        while not observed_capacity_entries(stream.frames):
                            await pump(timeout=5)
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in INFO_REFERENCES}:
                    async with asyncio.timeout(5):
                        while not (
                            observed_code(
                                stream.frames,
                                0x1000AAF0,
                                "ebfd3d4849f064ff04463b4849f094ff",
                                "capacity getter calls",
                            )
                            and observed_code(
                                stream.frames,
                                0x1000ABE4,
                                "80a70b1043120c1000ba0018e8210c10",
                                "device-info literals",
                            )
                        ):
                            await pump(timeout=5)
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in INFO_BLOCKS[9:]}:
                    async with asyncio.timeout(5):
                        while not observed_code(
                            stream.frames,
                            0x1000AAD0,
                            "30b58fb0fff76cfb424b1a88adf80020",
                            "GET_DEVICE_INFO entry",
                        ):
                            await pump(timeout=5)
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in INFO_BLOCKS[7:]}:
                    async with asyncio.timeout(5):
                        while not (
                            observed_code(
                                stream.frames,
                                0x1000B404,
                                "7b1e392b00f29c80dfe803f01d22272c",
                                "command range and TBB",
                            )
                            and observed_code(
                                stream.frames,
                                0x1000B414,
                                "31363b40454a4f555b9a9a61676c7277",
                                "command 0x05 table entry",
                            )
                            and observed_code(
                                stream.frames,
                                0x1000B474,
                                "3046fff72bfbc1e721463046fff7b8fb",
                                "GET_DEVICE_INFO direct call",
                            )
                        ):
                            await pump(timeout=5)
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in SPECIAL_BLOCKS[6:]}:
                    async with asyncio.timeout(5):
                        while not observed_code(
                            stream.frames, 0x1000B110, "bb220c10", "command 0x3a r0 literal"
                        ):
                            await pump(timeout=5)
                if command in {f"dbg mdb {b[0]:x} {b[1]:x}" for b in SPECIAL_BLOCKS[4:]}:
                    async with asyncio.timeout(5):
                        while not observed_code(
                            stream.frames,
                            0x1000B0E0,
                            "02a8f5f7fbfd02a9421c0948a2f073f9",
                            "command 0x3a literal load",
                        ):
                            await pump(timeout=5)
                tlv = b"\x01" + len(encoded).to_bytes(2, "little") + encoded
                await request(b"\x1d\x10\x81" + len(tlv).to_bytes(2, "little") + tlv)
                if vendor_handler or device_info_code:
                    if command.startswith("dbg mdb "):
                        _, _, address, length = command.split()
                        pending_reads.append((int(address, 16), int(length, 16)))
                    elif command == "help":
                        # A captured long burst lost row b504 with all ACKs.
                        # Require this batch's actual rows before issuing more reads.
                        async with asyncio.timeout(5):
                            while any(
                                observed_block(stream.frames, address, length) is None
                                for address, length in pending_reads
                            ):
                                await pump(timeout=5)
                        pending_reads.clear()
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
