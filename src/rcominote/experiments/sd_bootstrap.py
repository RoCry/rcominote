"""Fixed RAM/XIP→SD transfers without mdb/help; retain non-audio test files.

Independent identity + audited static command contract bootstrap this experiment.
Only the exact exported code range is verified; no raw NOR/flash execution.
"""

import asyncio
import hashlib
import json
import re
import secrets
import struct
from dataclasses import asdict
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import typer

from rcominote import protocol as P
from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.connection import Connection
from rcominote.device_commands import read_info
from rcominote.experiments.audio_state import IMAGE_SHA
from rcominote.experiments.linux_att import AttLink
from rcominote.experiments.linux_log import discover
from rcominote.experiments.sd_bridge import console_packet, require_idle
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE
from rcominote.log_stream import Stream

ADDRESS = 0x18000000
SIZE = 4096
ORACLE_SHA = "35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b"


class Source(StrEnum):
    ram = "ram"
    header = "header"
    handler = "handler"
    printk_hook = "printk-hook"
    fread = "fread"
    ring_code = "ring-code"
    printk_code = "printk-code"
    fread_descriptor = "fread-descriptor"
    logsrv_global_code = "logsrv-global-code"
    logsrv_global_literal = "logsrv-global-literal"
    heap_bounds = "heap-bounds"
    logsrv_slot_layout = "logsrv-slot-layout"
    logsrv_slot_copy = "logsrv-slot-copy"
    mdw_wrapper = "mdw-wrapper"
    mdw_load = "mdw-load"


SOURCES = {
    Source.ram: (ADDRESS, SIZE, 0xDD500),
    Source.header: (0x10000000, 32, 0),
    Source.handler: (0x10024A20, 160, 0x24A20),
    Source.printk_hook: (0x10020628, 16, 0x20628),
    Source.fread: (0x10025348, 16, 0x25348),
    Source.ring_code: (0x10026CD4, 68, 0x26CD4),
    Source.printk_code: (0x10026E6C, 104, 0x26E6C),
    Source.fread_descriptor: (0x100BB960, 16, 0xBB960),
    Source.logsrv_global_code: (0x1000BF82, 32, 0xBF82),
    Source.logsrv_global_literal: (0x1000C0C8, 16, 0xC0C8),
    Source.heap_bounds: (0x1009AA24, 48, 0x9AA24),
    Source.logsrv_slot_layout: (0x1000BD30, 32, 0xBD30),
    Source.logsrv_slot_copy: (0x1000BD80, 48, 0xBD80),
    Source.mdw_wrapper: (0x100A18EE, 10, 0xA18EE),
    Source.mdw_load: (0x100251AA, 24, 0x251AA),
}


def verify_state(before: dict, after: dict, *, sd_write: bool) -> dict:
    """Permit one MiB reporting step for a small SD write; reject every other change."""
    if type(sd_write) is not bool:
        raise ValueError("SD write state must be explicit")
    normalized = []
    for info in (before, after):
        if info["serial"] != OWNED_SERIAL:
            raise ValueError("Expected owned device identity")
        require_idle(info)
        payload = bytes.fromhex(info["device"]["raw"])
        if len(payload) != 52 or info["device"] != P.parse_device_info(payload):
            raise ValueError("Expected complete consistent52-byte device info")
        normalized.append(
            {key: value for key, value in info.items() if key != "device"}
            | {
                "device": {
                    key: value for key, value in info["device"].items() if key not in {"raw", "free_capacity"}
                }
            }
            | {"raw_except_free": (payload[:4] + payload[8:]).hex()}
        )
    delta = before["device"]["free_capacity"] - after["device"]["free_capacity"]
    if normalized[0] != normalized[1] or not 0 <= delta <= int(sd_write):
        raise ValueError("Unexpected state change beyond bounded SD capacity accounting")
    return {
        "other_state_equal": True,
        "free_capacity_unit": "MiB (integer firmware report)",
        "free_capacity_before": before["device"]["free_capacity"],
        "free_capacity_after": after["device"]["free_capacity"],
        "free_capacity_decrease": delta,
        "allowed_decrease": int(sd_write),
    }


async def identity() -> tuple[dict, list[dict]]:
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    async with Connection(device) as conn:
        info = await read_info(conn, OWNED_SERIAL)
        require_idle(info)
        return info, [asdict(entry) for entry in await conn.file_list()]


async def write_file(report: dict) -> None:
    from rcominote.experiments.sd_nor_targets import (
        BACKUP_PRODUCER,
        PRODUCER,
        RECOVERY_PRODUCER,
        validate_producer,
    )

    if report.get("producer") not in (None, PRODUCER, RECOVERY_PRODUCER, BACKUP_PRODUCER):
        raise ValueError(
            "Only fixed boot0 or explicit recovery-block1/backup-boot-block1 producer is allowed"
        )
    validate_producer(report)
    producer = report.get("producer")
    commands = ([producer] if producer is not None else []) + [report["dump_command"]]
    await write_commands(report, commands)


async def write_commands(report: dict, commands: list[str]) -> None:
    """Internal bounded session transport; caller must validate its fixed command profile."""
    if not 1 <= len(commands) <= 4:
        raise ValueError("Internal Actions session requires one to four fixed commands")
    packets = [console_packet(command) for command in commands]
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    async with AttLink(device.address, report) as link:
        await link.request(bytes.fromhex("02f700"), 0x03)
        write, notify, cccd = await discover(link, report)
        await link.request(b"\x12" + struct.pack("<HH", cccd, 1), 0x13)
        stream = Stream()
        report.update(frames=stream.frames, notifications=[], writes=[])
        expected = 0

        async def pump():
            handle, value = await link.next_notification()
            if handle != notify:
                raise ValueError(f"Unexpected notification handle {handle:#x}")
            report["notifications"].append(value.hex())
            stream.feed(value)

        async def send(packet: bytes):
            nonlocal expected
            expected += 1
            row = {"hex": packet.hex(), "att_write_confirmed": False}
            report["writes"].append(row)
            await link.request(b"\x12" + write.to_bytes(2, "little") + packet, 0x13)
            row["att_write_confirmed"] = True
            async with asyncio.timeout(5):
                while stream.acks < expected:
                    await pump()

        attempted = False
        failure: BaseException | None = None
        try:
            await send(PREPARE)
            attempted = True
            await send(START)
            for command, packet in zip(commands, packets, strict=True):
                if command.startswith("dbg dumpbuf "):
                    report["sd_write_attempted"] = True
                await send(packet)
        except BaseException as error:
            failure = error
            raise
        finally:
            try:
                if attempted:
                    await send(STOP)
                    async with asyncio.timeout(5):
                        while not stream.ended:
                            await pump()
                    if stream.pending or stream.acks != expected:
                        raise ValueError("Incomplete Actions session")
                    report["log_session_complete"] = True
            except BaseException as cleanup_error:
                report["cleanup_error"] = f"{type(cleanup_error).__name__}: {cleanup_error}"
                if failure is None:
                    raise
            finally:
                report.update(
                    mtu=link.mtu,
                    ack_count=stream.acks,
                    expected_ack_count=expected,
                    end_received=stream.ended,
                    pending_hex=stream.pending.hex(),
                )


async def download_file(report: dict, out: Path, expected_size: int, *, offset: int = 0) -> bytes:
    """Download one previously selected file; retain bytes even on failure."""
    if type(expected_size) is not int or not 0 < expected_size <= SIZE:
        raise ValueError("Expected download size must be1..4096 bytes")
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    async with Connection(device) as conn:
        require_idle(await read_info(conn, OWNED_SERIAL))
        data = bytearray()

        def sink(chunk):
            if len(data) + len(chunk) > expected_size:
                raise ValueError("Download exceeds fixed source profile")
            data.extend(chunk)

        try:
            report["download_bytes"] = await conn.download(report["name"], sink, offset=offset)
        finally:
            report["received_bytes"] = len(data)
            report["download_sha256"] = hashlib.sha256(data).hexdigest()
            with (out / "download.bin").open("xb") as handle:
                handle.write(data)
        if len(data) != expected_size:
            raise ValueError("Download length differs from fixed source profile")
        return bytes(data)


async def capture(report: dict, oracle: bytes, out: Path) -> None:
    report["before"], report["files_before"] = await identity()
    tail_only = report.get("tail_only", False)
    download_only = tail_only or report.get("download_only", False)
    if not download_only and report["name"] in {entry["name"] for entry in report["files_before"]}:
        raise FileExistsError("Random test name already listed; no SD write attempted")
    failure: BaseException | None = None
    try:
        if not download_only:
            await write_file(report)
        data = await download_file(report, out, len(oracle), offset=SIZE - len(oracle) if tail_only else 0)
        if data != oracle:
            raise ValueError("Download differs from independent oracle")
        report["exact_match"] = True
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            report["after"], report["files_after"] = await identity()
            report["state_verification"] = verify_state(
                report["before"], report["after"], sd_write=report.get("sd_write_attempted", False)
            )
        except BaseException as after_error:
            report["after_error"] = f"{type(after_error).__name__}: {after_error}"
            if failure is None:
                raise


def main(
    image: Path,
    out: Path,
    create_sd_file: bool = False,
    tail_report: Path | None = None,
    source: Source = Source.ram,
    existing_report: Path | None = None,
    tail_size: int = 128,
):
    parent_path = tail_report or existing_report
    if tail_report is not None and existing_report is not None:
        raise typer.BadParameter("Choose --tail-report or --existing-report")
    if not create_sd_file and parent_path is None:
        raise typer.BadParameter("Requires --create-sd-file; retains one non-audio SD test file")
    if create_sd_file and parent_path is not None:
        raise typer.BadParameter("Existing-file reads require omitting --create-sd-file")
    if tail_report is not None and source != Source.ram:
        raise typer.BadParameter("--tail-report requires the fixed RAM source")
    if tail_size not in (128, 512) or (tail_report is None and tail_size != 128):
        raise typer.BadParameter("--tail-size permits128 or512 only with --tail-report")
    raw = image.read_bytes()
    if hashlib.sha256(raw).hexdigest() != IMAGE_SHA:
        raise ValueError("Wrong independent actual CoMi system image")
    address, size, offset = SOURCES[source]
    oracle = raw[offset : offset + size]
    if len(oracle) != size or (source == Source.ram and hashlib.sha256(oracle).hexdigest() != ORACLE_SHA):
        raise ValueError("Independent RAM initialization oracle changed")
    name = "rc" + secrets.token_hex(5)
    if parent_path is not None:
        parent = json.loads(parent_path.read_text())
        name = parent["name"]
        expected_command = f"dbg dumpbuf {address} {size} /SD:/RECORDER/Call-{name}.mp3"
        if (
            not re.fullmatch(r"rc[0-9a-f]{10}", name)
            or parent["serial"] != OWNED_SERIAL
            or parent["source_image_sha256"] != IMAGE_SHA
            or parent["dump_command"] != expected_command
            or parent.get("log_session_complete") is not True
        ):
            raise ValueError("Existing-file read requires an owned matching fixed bootstrap receipt")
    if tail_report is not None:
        oracle = oracle[-tail_size:]
    path = f"/SD:/RECORDER/Call-{name}.mp3"
    command = f"dbg dumpbuf {address} {size} {path}"
    console_packet(command)  # Bound command length before any I/O; decimal is intentional.
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "serial": OWNED_SERIAL,
        "name": name,
        "device_path": path,
        "dump_command": command,
        "source_image_sha256": IMAGE_SHA,
        "expected_sha256": hashlib.sha256(oracle).hexdigest(),
        "source": source.value,
        "source_address": f"0x{address:08x}",
        "source_bytes": len(oracle),
        "scope": "Fixed RAM/XIP bootstrap; no raw NOR access, recording or reboot",
        "residue_policy": "Retain one non-audio SD test file; no audited safe deletion contract",
        "sd_write_attempted": False,
        "ok": False,
    }
    if tail_report is not None:
        report.update(
            tail_only=True,
            offset=SIZE - tail_size,
            expected_sha256=hashlib.sha256(oracle).hexdigest(),
            parent_report_sha256=hashlib.sha256(tail_report.read_bytes()).hexdigest(),
            scope=f"Read-only{tail_size}B suffix of existing RAM bootstrap file; no Actions/SD write/NOR access",
            residue_policy="No new SD file; existing bootstrap test file retained",
        )
    elif existing_report is not None:
        report.update(
            download_only=True,
            parent_report_sha256=hashlib.sha256(existing_report.read_bytes()).hexdigest(),
            scope="Read-only existing fixed bootstrap file; no Actions/SD write/NOR access",
            residue_policy="No new SD file; existing bootstrap test file retained",
        )
    try:
        asyncio.run(capture(report, oracle, out))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = datetime.now(UTC).isoformat()
        with (out / "report.json").open("x") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("ok", "download_bytes", "download_sha256")}))


if __name__ == "__main__":
    typer.run(main)
