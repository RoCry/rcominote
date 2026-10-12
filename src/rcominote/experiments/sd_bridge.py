"""Fixed known-source → SD → Boyi experiment; retains non-audio SD files."""

import asyncio
import hashlib
import json
import re
import secrets
import struct
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.code_guards import observed_block
from rcominote.connection import Connection
from rcominote.device_commands import read_info
from rcominote.image_store import inspect_image
from rcominote.log_capture import START, STOP
from rcominote.log_probe import NOTIFY, PREPARE, SERVICE, WRITE
from rcominote.log_stream import Stream
from rcominote.nor_windows import LINE, ROWS
from rcominote.printk_ring import BUFFER, CAPACITY, CONTEXT
from rcominote.printk_ring import GUARDS as RING_GUARDS
from rcominote.printk_state import GUARDS as STATE_GUARDS
from rcominote.printk_tail import GUARDS as FREAD_GUARDS
from rcominote.printk_tail import NorTarget, block_offset, producer

SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
SIZE = 4096


class Source(StrEnum):
    mapped = "mapped"
    ram = "ram"
    nor_ring = "nor-ring"
    rom_flow = "rom-flow"


# RAM source: independently decoded startup memcpy(18000000,100dd500,12c8).
SOURCES = {
    Source.mapped: (0x10000000, 0),
    Source.ram: (0x18000000, 0xDD500),
    Source.nor_ring: (BUFFER, None),
    Source.rom_flow: (0x1900, None),
}


def rom_oracle() -> bytes:
    data = Path("docs/evidence/rom-flow-2026-10-13.bin").read_bytes()
    if len(data) != 336 or hashlib.sha256(data).hexdigest() != (
        "0dda0a4532813627df78b506bfa1f7e5dc8ae4b9886cc32173265592defcaa67"
    ):
        raise ValueError("Independent ROM1900..1a50 oracle changed")
    return data


def ring_rows(data: bytes):
    if len(data) != CAPACITY:
        raise ValueError("Expected exact4096-byte physical ring")
    rows = []
    # Include preceding delimiter even when the first row begins at byte0/1.
    for match in LINE.finditer((data[-2:] + data + data).decode("latin1")):
        prefix, values = match.groups()
        offset = int(prefix, 16)
        if offset in ROWS and prefix == f"{offset:8x}":
            rows.append((match.start() - 2, match.end() - 2, offset, values))
    return rows


def sector_from_ring(
    data: bytes, *, nor_offset: int | None = None, producer_command: str = "", dump_command: str = ""
) -> bytes:
    rows = ring_rows(data)
    candidates = []
    for index, (start, _, offset, _) in enumerate(rows):
        if not 0 <= start < CAPACITY or offset != 0:
            continue
        window = rows[index : index + 32]
        if tuple(row[2] for row in window) != ROWS:
            continue
        if any(left[1] != right[0] for left, right in pairwise(window)):
            continue
        if window[-1][1] - (start - 2) > CAPACITY:
            continue
        if nor_offset is not None:
            text = (data * 3).decode("latin1")
            first, last = start + CAPACITY, window[-1][1] + CAPACITY
            status = re.search(
                rf"\r\nfread 512b: offset=0x{nor_offset:x}, buf=0x[0-9a-f]+\r\n(?:\r\n)*$",
                text[:first],
            )
            if status is None:
                continue
            # Bound the entire producer/status/rows/unique dump echo to one circle.
            suffix = text[last : status.start() + CAPACITY]
            echo = re.search(rf"logsrv: cmd\([0-9]+\) {re.escape(producer_command)}\n\r\n", suffix)
            if echo is None or dump_command not in suffix[echo.end() :]:
                continue
        candidates.append(bytes(int(token, 16) for row in window for token in row[3].split()))
    if len(candidates) != 1:
        raise ValueError(f"Expected one contiguous circular NOR sector; found {len(candidates)}")
    return candidates[0]


def console_packet(command: str) -> bytes:
    encoded = command.encode("ascii") + b"\n"
    # Actual FW010004 reads at most64 B and forces buf[min(len,63)]=0.
    # Longer TLVs also desynchronize outer remaining-length accounting.
    if len(encoded) > 64:
        raise ValueError("Actions console text exceeds64 bytes including final newline")
    tlv = b"\x01" + len(encoded).to_bytes(2, "little") + encoded
    return b"\x1d\x10\x81" + len(tlv).to_bytes(2, "little") + tlv


def require_idle(identity: dict) -> None:
    if identity["device"]["version"] != "010004" or identity["device"]["recording_state"] != "idle":
        raise RuntimeError("SD bridge requires owned idle FW010004")


async def create_file(conn: Connection, report: dict, image: bytes) -> None:
    queue = asyncio.Queue(maxsize=2048)
    stream = Stream()
    report["frames"] = stream.frames
    expected = 0
    failure: Exception | None = None

    def receive(_sender, packet):
        nonlocal failure
        try:
            queue.put_nowait(bytes(packet))
        except asyncio.QueueFull:
            failure = RuntimeError("SD bridge notification queue overflow")

    async def pump():
        conn._check_failure()
        if failure is not None:
            raise failure
        packet = await asyncio.wait_for(queue.get(), timeout=5)
        if packet is None:
            raise ConnectionError("SD bridge log connection lost")
        stream.feed(packet)
        if len(stream.frames) > 2048:
            raise RuntimeError("SD bridge log frame limit exceeded")

    client = conn.client
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
        packet = console_packet(command)
        report["fixed_text_commands"].append(command)
        await request(packet)

    async def read_live(address, length):
        start = len(stream.frames)
        await text(f"dbg mdb {address:x} {length:x}")
        await text("help")
        async with asyncio.timeout(5):
            result = bytearray()
            for offset in range(0, length, 16):
                count = min(16, length - offset)
                while (raw := observed_block(stream.frames[start:], address + offset, count)) is None:
                    await pump()
                result.extend(raw)
            return bytes(result)

    async def verify(address, length, image_offset=None):
        raw = await read_live(address, length)
        index = address - 0x10000000 if image_offset is None else image_offset
        if raw != image[index : index + length]:
            raise ValueError(f"Live code/header differs at {address:#x}")

    attempted = False
    try:
        await request(PREPARE)
        attempted = True
        await request(START)
        # Fixed mapped header prefix and entire dumpbuf handler/literals.
        # All addresses lie within the independently verified system image.
        await verify(0x10000000, 32)
        for address, length in ((0x10024A20, 64), (0x10024A60, 64), (0x10024AA0, 32)):
            await verify(address, length)
        if report["source"] == Source.ram:
            await verify(0x18000000, 32, image_offset=0xDD500)
        if report["source"] == Source.rom_flow:
            known = rom_oracle()
            for address, expected_bytes in ((0x1900, known[:16]), (0x1A40, known[-16:])):
                if await read_live(address, 16) != expected_bytes:
                    raise ValueError(f"Live ROM source guard differs at {address:#x}")
        if report["source"] == Source.nor_ring:
            for address, expected_hex in (*RING_GUARDS, *STATE_GUARDS, *FREAD_GUARDS):
                await verify(address, len(bytes.fromhex(expected_hex)))
            raw = await read_live(CONTEXT, 28)
            r, w, used, capacity, buffer = struct.unpack("<5I", raw[:20])
            if (capacity, buffer) != (CAPACITY, BUFFER) or max(r, w, used) > CAPACITY:
                raise ValueError("Live printk ring differs from fixed profile")
            if raw[20:22] != b"\x01\x00":
                raise ValueError("Live printk ring is not in normal DMA mode")
            report["ring_context_before"] = raw.hex()
            report["transfer_phase_start"] = time.monotonic()
            if report.get("phase") != "baseline":
                await text(report["producer"])
        command = report["dump_command"]
        report["sd_write_attempted"] = True
        await text(command)
        # ACK/done are not write-integrity evidence: download comparison is.
        await text("help")
        if report["source"] == Source.nor_ring:
            report["ring_context_after"] = (await read_live(CONTEXT, 28)).hex()
    finally:
        original = sys.exception()
        if attempted:
            try:
                await request(STOP)
                async with asyncio.timeout(5):
                    while not stream.ended:
                        await pump()
                if stream.pending or stream.acks != expected:
                    raise RuntimeError("Incomplete SD bridge Actions session")
                report["log_session_complete"] = True
            except BaseException as cleanup_error:
                if original is None:
                    raise
                report["cleanup_error"] = f"{type(cleanup_error).__name__}: {cleanup_error}"
                original.add_note(f"Actions STOP cleanup also failed: {cleanup_error}")
    await client.stop_notify(NOTIFY)


async def capture(report: dict, image: bytes, oracle: bytes | None, out: Path) -> None:
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    async with Connection(device) as conn:
        identity = await read_info(conn, OWNED_SERIAL)
        require_idle(identity)
        report["before"] = identity
        entries = await conn.file_list()
        report["files_before"] = [asdict(entry) for entry in entries]
        if report["name"] in {entry.name for entry in entries}:
            raise FileExistsError("Random SD bridge filename already listed; no write attempted")
        await create_file(conn, report, image)
        require_idle(await read_info(conn, OWNED_SERIAL))
        data = bytearray()

        def sink(chunk):
            if len(data) + len(chunk) > report["source_bytes"]:
                raise ValueError("SD bridge file exceeds fixed source profile")
            data.extend(chunk)

        started = time.monotonic()
        report["download_bytes"] = await conn.download(report["name"], sink)
        report["download_seconds"] = time.monotonic() - started
        if "transfer_phase_start" in report:
            report["transfer_phase_seconds"] = time.monotonic() - report.pop("transfer_phase_start")
        # Preserve the core evidence before unrelated status/list queries.
        with (out / "download.bin").open("xb") as handle:
            handle.write(data)
        report["download_sha256"] = hashlib.sha256(data).hexdigest()
        report["after"] = await read_info(conn, OWNED_SERIAL)
        require_idle(report["after"])
        report["files_after"] = [asdict(entry) for entry in await conn.file_list()]
    if report["source"] == Source.nor_ring:
        if report.get("phase") == "baseline":
            if report["dump_command"].encode("ascii") not in data + data:
                raise ValueError("Baseline lacks its unique live console command; stop without fread")
            if any(0 <= start < CAPACITY for start, *_ in ring_rows(data)):
                raise ValueError("Producer baseline contains old NOR rows; stop without fread")
            report["live_marker_present"] = True
            report["no_nor_rows"] = True
            return
        compared = sector_from_ring(
            data,
            nor_offset=report["nor_offset"],
            producer_command=report["producer"],
            dump_command=report["dump_command"],
        )
        with (out / "sector.bin").open("xb") as handle:
            handle.write(compared)
        report["sector_sha256"] = hashlib.sha256(compared).hexdigest()
    else:
        compared = data
    if oracle is None:
        report["oracle_comparison"] = "Unavailable; requires independent repeat and target-format validation"
        return
    if compared != oracle:
        raise ValueError("SD bridge bytes differ from independently acquired source oracle")
    report["exact_match"] = True


def main(
    image: Path,
    out: Path,
    create_sd_file: bool = False,
    source: Source = Source.ram,
    nor_target: NorTarget = NorTarget.boot,
    nor_block: int = 0,
):
    if not create_sd_file:
        raise typer.BadParameter("Requires --create-sd-file; leaves non-audio .mp3 files on device SD")
    if nor_target == NorTarget.factory_rw:
        private_root = Path(__file__).resolve().parents[3] / "artifacts"
        if not out.resolve().is_relative_to(private_root.resolve()):
            raise typer.BadParameter("Sensitive factory-RW captures must stay under repo artifacts/")
    data = image.read_bytes()
    inspect_image(data)
    if hashlib.sha256(data).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact independently acquired FW010004 image")
    if (nor_target != NorTarget.boot or nor_block) and source != Source.nor_ring:
        raise typer.BadParameter("NOR options require --source nor-ring")
    name = "rc" + secrets.token_hex(5)
    device_path = f"/SD:/RECORDER/Call-{name}.mp3"
    address, offset = SOURCES[source]
    if source == Source.nor_ring:
        if nor_target == NorTarget.boot and nor_block == 0:
            oracle_path = Path("docs/evidence/boot-complete-2026-10-12/raw.bin")
            oracle_sha = "782c26c3ba9bee07a8b0b464898fb963a76eb35a2916586b854f8f45993f4166"
        elif nor_target == NorTarget.recovery and 93 <= nor_block <= 123:
            oracle_path = Path("docs/evidence/recovery-raw-prefix-2026-10-12.bin")
            oracle_sha = "20a8547720d14eb92339643f48e93ce5248023e142457990076f95eca03a63e8"
        elif nor_target in (NorTarget.param0, NorTarget.param1, NorTarget.factory_rw):
            block_offset(nor_target, nor_block)  # Fixed extents from actual ACPT only.
            oracle_path = None
        else:
            raise typer.BadParameter("Only boot0, bounded recovery tail, param slots or factory-RW supported")
        if oracle_path is None:
            oracle = None  # Requires paired reads plus independent target-format checks.
        else:
            known = oracle_path.read_bytes()
            if hashlib.sha256(known).hexdigest() != oracle_sha:
                raise ValueError("Independent NOR oracle changed")
            oracle = known[nor_block * 512 : (nor_block + 1) * 512] or None
    elif source == Source.rom_flow:
        oracle = rom_oracle()
    else:
        oracle = data[offset : offset + SIZE]
    size = len(oracle) if source == Source.rom_flow else SIZE
    command = f"dbg dumpbuf {address} {size} {device_path}"
    console_packet(command)  # Pure preflight, before any device I/O.
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "captured_at": datetime.now(UTC).isoformat(),
        "serial": OWNED_SERIAL,
        "name": name,
        "device_path": device_path,
        "dump_command": command,
        "source": source.value,
        "source_address": hex(address),
        "oracle_file_offset": offset,
        "source_bytes": size,
        "source_image_sha256": SHA,
        "expected_sha256": hashlib.sha256(oracle).hexdigest() if oracle is not None else None,
        "fixed_text_commands": [],
        "sd_write_attempted": False,
        "residue_policy": "Retained SD test file; no audited safe deletion command; not valid audio",
        "scope": "Fixed transfer proof; not ROM extent, full NOR backup or atomic printk snapshot",
        "ok": False,
    }
    if source == Source.nor_ring:
        report.update(
            nor_target=nor_target.value,
            nor_block=nor_block,
            nor_offset=block_offset(nor_target, nor_block),
            producer=producer(nor_target, nor_block),
        )
    started = time.monotonic()
    try:
        if source == Source.nor_ring:
            baseline_out = out / "baseline"
            baseline_out.mkdir()
            baseline_name = "rc" + secrets.token_hex(5)
            baseline_path = f"/SD:/RECORDER/Call-{baseline_name}.mp3"
            baseline = report | {
                "phase": "baseline",
                "name": baseline_name,
                "device_path": baseline_path,
                "dump_command": f"dbg dumpbuf {address} 4096 {baseline_path}",
                "fixed_text_commands": [],
                "expected_sha256": None,
            }
            try:
                asyncio.run(capture(baseline, data, oracle, baseline_out))
                baseline["ok"] = True
            except BaseException as error:
                baseline["error"] = f"{type(error).__name__}: {error}"
                raise
            finally:
                (baseline_out / "report.json").write_text(
                    json.dumps(baseline, ensure_ascii=False, indent=2) + "\n"
                )
            report["baseline"] = {
                "download_sha256": baseline["download_sha256"],
                "no_nor_rows": baseline["no_nor_rows"],
                "live_marker_present": baseline["live_marker_present"],
                "device_path": baseline_path,
            }
        asyncio.run(capture(report, data, oracle, out))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["total_seconds"] = time.monotonic() - started
        with (out / "report.json").open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")


if __name__ == "__main__":
    typer.run(main)
