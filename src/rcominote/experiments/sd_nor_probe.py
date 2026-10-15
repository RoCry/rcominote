"""Separate guarded context/baseline/boot0 trials; retain SD scratch files."""

import asyncio
import hashlib
import json
import re
import secrets
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import sd_bootstrap
from rcominote.experiments import sd_nor_targets as targets
from rcominote.experiments.sd_bridge import console_packet, require_idle, ring_rows, sector_from_ring
from rcominote.experiments.sd_nor_targets import Phase, Transport
from rcominote.log_capture import START, STOP
from rcominote.log_probe import NOTIFY, PREPARE, WRITE
from rcominote.log_stream import Stream
from rcominote.printk_ring import BUFFER, CAPACITY, CONTEXT

IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
BOOT_SHA = targets.BOOT_SHA
PRODUCER = targets.PRODUCER
GUARDS = {
    "header": (0x10000000, 32),
    "handler": (0x10024A20, 160),
    "printk-hook": (0x10020628, 16),
    "fread": (0x10025348, 16),
    "ring-code": (0x10026CD4, 68),
    "printk-code": (0x10026E6C, 104),
    "fread-descriptor": (0x100BB960, 16),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(directory: Path) -> tuple[dict, bytes]:
    raw = (directory / "report.json").read_bytes()
    return json.loads(raw), raw


def same_identity(report: dict) -> None:
    sd_write = report.get("sd_write_attempted")
    if type(sd_write) is not bool:
        raise ValueError("Receipt must declare boolean sd_write_attempted")
    for key in ("before", "after"):
        info = report[key]
        if info["serial"] != OWNED_SERIAL:
            raise ValueError("Receipt identity is not the owned device")
        require_idle(info)
        if len(bytes.fromhex(info["device"]["raw"])) != 52:
            raise ValueError("Receipt requires complete52-byte device info")
    if report.get("after_error"):
        raise ValueError("Receipt final identity failed")
    verification = sd_bootstrap.verify_state(report["before"], report["after"], sd_write=sd_write)
    if "state_verification" in report and report["state_verification"] != verification:
        raise ValueError("Receipt state verification summary differs from actual info")
    report["state_verification"] = verification


def command(report: dict, address: int, size: int) -> str:
    if not re.fullmatch(r"rc[0-9a-f]{10}", report["name"]):
        raise ValueError("Invalid fixed scratch filename")
    path = f"/SD:/RECORDER/Call-{report['name']}.mp3"
    expected = f"dbg dumpbuf {address} {size} {path}"
    if report["device_path"] != path or report["dump_command"] != expected:
        raise ValueError("Receipt dump command does not match fixed source")
    console_packet(expected)
    return expected


def validate_actions(report: dict, *, producer: bool = False) -> None:
    """Reconstruct consumed Actions frames from actual ATT trace, including write responses."""
    packets = [PREPARE, START]
    if producer:
        targets.validate_producer(report)
        if report.get("producer") is None:
            raise ValueError("Only exact boot0 producer or recovery-block1 is permitted")
        packets.append(console_packet(report["producer"]))
    elif report.get("producer") is not None:
        raise ValueError("Unexpected producer in non-boot phase")
    packets += [console_packet(report["dump_command"]), STOP]
    expected_characteristics = [
        {"declaration": 21, "properties": 12, "value": 22, "uuid": WRITE},
        {"declaration": 23, "properties": 16, "value": 24, "uuid": NOTIFY},
    ]
    discovery = bytes.fromhex(
        "091515000c1600d19f1b1f80f2b28ee8119af602309ae41700101800d19f1b1f80f2b28ee8119af603309ae4"
    )
    if report["log_characteristics"] != expected_characteristics:
        raise ValueError("Actions characteristic identity differs from fixed FW010004")
    trace = report["att_packets"]
    writes, notifications = [], []
    last_time = -1
    awaiting_response = None
    discovered = cccd_confirmed = False
    stream = Stream()
    for row in trace:
        timestamp, direction, raw = row["monotonic_ns"], row["direction"], bytes.fromhex(row["hex"])
        if type(timestamp) is not int or timestamp < last_time or direction not in ("tx", "rx") or not raw:
            raise ValueError("Malformed or unordered ATT trace")
        last_time = timestamp
        if direction == "tx":
            if raw[0] == 0x12:
                if awaiting_response or not discovered:
                    raise ValueError("Overlapping or undiscovered ATT write")
                if raw == bytes.fromhex("1219000100") and not cccd_confirmed and not writes:
                    awaiting_response = "cccd"
                elif raw[:3] == bytes.fromhex("121600") and cccd_confirmed:
                    if len(writes) >= len(packets) or raw[3:] != packets[len(writes)]:
                        raise ValueError("ATT Actions write differs from exact phase sequence")
                    writes.append(raw[3:])
                    awaiting_response = "action"
                else:
                    raise ValueError("Unexpected ATT write handle/value")
            elif raw[0] not in (0x02, 0x03, 0x04, 0x08, 0x10):
                raise ValueError("Unexpected transmitted ATT opcode")
        elif direction == "rx" and raw[0] == 0x1B:
            if len(raw) < 3 or raw[1:3] != bytes.fromhex("1800") or not cccd_confirmed:
                raise ValueError("Unexpected ATT notification handle")
            if stream.ended:
                raise ValueError("Actions bytes received after end")
            notifications.append(raw[3:])
            stream.feed(raw[3:])
            if stream.acks > len(writes) or (stream.ended and stream.acks != len(packets)):
                raise ValueError("Actions ACK/end arrived before corresponding writes")
        elif direction == "rx" and raw[0] == 0x13:
            if raw != b"\x13" or awaiting_response is None:
                raise ValueError("Unmatched ATT Write Response")
            cccd_confirmed |= awaiting_response == "cccd"
            awaiting_response = None
        elif direction == "rx" and awaiting_response and raw[0] != 0x02:
            raise ValueError("Actions write lacks ATT Write Response")
        elif direction == "rx" and raw[0] == 0x09:
            if raw != discovery or discovered:
                raise ValueError("Actions characteristic discovery differs from fixed FW010004")
            discovered = True
        elif direction == "rx" and raw[0] == 0x1D:
            raise ValueError("Unexpected ATT indication")
    if awaiting_response or not cccd_confirmed or writes != packets:
        raise ValueError("ATT Actions writes differ from exact phase sequence")
    if report["writes"] != [{"hex": packet.hex(), "att_write_confirmed": True} for packet in packets]:
        raise ValueError("Actions write receipt differs from actual ATT trace")
    if report["notifications"] != [value.hex() for value in notifications]:
        raise ValueError("Unconsumed or missing ATT notification evidence")
    if (
        stream.pending
        or stream.acks != len(packets)
        or not stream.ended
        or sum(row["command"] == 0xF1 for row in stream.frames) != 1
        or stream.frames != report["frames"]
        or report.get("ack_count") != len(packets)
        or report.get("expected_ack_count") != len(packets)
        or report.get("end_received") is not True
        or report.get("pending_hex") != ""
        or report.get("log_session_complete") is not True
        or report.get("cleanup_error")
    ):
        raise ValueError("Incomplete or inconsistent Actions session")


def downloaded(report: dict, directory: Path, size: int) -> bytes:
    data = (directory / "download.bin").read_bytes()
    if (
        len(data) != size
        or report.get("received_bytes") != size
        or report.get("download_bytes") != size
        or report.get("download_sha256") != sha(data)
    ):
        raise ValueError("Missing, partial or altered downloaded file")
    return data


def validate_guards(directories: list[Path], image: bytes, handler_parent: Path | None) -> list[dict]:
    if len(image) != 927632 or sha(image) != IMAGE_SHA:
        raise ValueError("Wrong independently verified FW010004 image")
    if len(directories) != len(GUARDS) or len({path.resolve() for path in directories}) != len(GUARDS):
        raise ValueError("Requires seven distinct complete guard directories")
    result, seen, names = [], set(), set()
    for directory in directories:
        report, receipt = load(directory)
        source = report["source"]
        if source not in GUARDS or source in seen or report["name"] in names:
            raise ValueError("Duplicate or unexpected guard source/file")
        seen.add(source)
        names.add(report["name"])
        address, size = GUARDS[source]
        if (
            report["serial"] != OWNED_SERIAL
            or report["source_image_sha256"] != IMAGE_SHA
            or report["source_address"] != f"0x{address:08x}"
            or report["source_bytes"] != size
            or report.get("ok") is not True
            or report.get("error")
            or report.get("tail_only")
        ):
            raise ValueError("Guard receipt does not match complete fixed source")
        command(report, address, size)
        same_identity(report)
        oracle = image[address - 0x10000000 : address - 0x10000000 + size]
        if downloaded(report, directory, size) != oracle or report["expected_sha256"] != sha(oracle):
            raise ValueError("Guard bytes differ from fixed image")
        if report.get("download_only"):
            if source != "handler" or handler_parent is None or report.get("sd_write_attempted"):
                raise ValueError("Read-only guard requires explicit handler parent")
            if any(key in report for key in ("att_packets", "writes", "frames", "notifications", "producer")):
                raise ValueError("Read-only handler guard contains unexpected Actions evidence")
            parent, parent_raw = load(handler_parent)
            if (
                sha(parent_raw) != report["parent_report_sha256"]
                or any(
                    parent[key] != report[key]
                    for key in (
                        "name",
                        "dump_command",
                        "source_image_sha256",
                        "source",
                        "source_address",
                        "source_bytes",
                        "serial",
                        "device_path",
                    )
                )
                or parent.get("sd_write_attempted") is not True
            ):
                raise ValueError("Handler write parent hash or source mismatch")
            same_identity(parent)
            validate_actions(parent)
            parent_evidence = {"directory": str(handler_parent.resolve()), "report_sha256": sha(parent_raw)}
        else:
            if report.get("sd_write_attempted") is not True:
                raise ValueError("Guard lacks write evidence")
            validate_actions(report)
            parent_evidence = None
        result.append(
            {
                "source": source,
                "directory": str(directory.resolve()),
                "report_sha256": sha(receipt),
                "download_sha256": sha(oracle),
                "name": report["name"],
                "write_parent": parent_evidence,
            }
        )
    return sorted(result, key=lambda row: row["source"])


def context_fields(data: bytes) -> dict:
    if len(data) != 28:
        raise ValueError("Expected exact28-byte ring context")
    r, w, used, capacity, buffer = struct.unpack("<5I", data[:20])
    if capacity != CAPACITY or buffer != BUFFER or max(r, w, used) > CAPACITY or data[20:22] != b"\x01\x00":
        raise ValueError("Ring context differs from active fixed DMA profile")
    return {
        "read": r,
        "write": w,
        "used": used,
        "capacity": capacity,
        "buffer": hex(buffer),
        "init": 1,
        "panic": 0,
        "raw_hex": data.hex(),
    }


def validate_payload(report: dict, data: bytes) -> dict:
    phase = Phase(report["phase"])
    if phase == Phase.context:
        return context_fields(data)
    if len(data) != CAPACITY:
        raise ValueError("Expected exact4096-byte physical ring")
    if report.get("transport_profile") == Transport.interval:
        # Count a complete echo in physical circular order, including its newline.
        marker = re.compile(
            rb"logsrv: cmd\([0-9]+\) " + re.escape(report["dump_command"].encode()) + rb"\n\r\n"
        )
        if sum(m.start() < CAPACITY for m in marker.finditer(data + data)) != 1:
            raise ValueError("Interval ring requires one complete current dump marker")
    if phase == Phase.baseline:
        marker = report["dump_command"].encode("ascii")
        starts = [m.start() for m in re.finditer(re.escape(marker), data + data) if m.start() < CAPACITY]
        if len(starts) != 1:
            raise ValueError("Baseline lacks unique live dump command")
        if any(0 <= start < CAPACITY for start, *_ in ring_rows(data)):
            raise ValueError("Baseline contains old NOR rows")
        return {"live_marker_present": True, "no_nor_rows": True}
    if phase == Phase.backup:
        from rcominote.experiments.sd_nor_unknown import payload

        return payload(report, data)
    offset, oracle, manifest = targets.oracle(phase)
    if phase == Phase.recovery and report.get("oracle") != manifest:
        raise ValueError("Recovery oracle receipt differs from complete raw source")
    sector = sector_from_ring(
        data, nor_offset=offset, producer_command=targets.producer(phase), dump_command=report["dump_command"]
    )
    if sector != oracle:
        raise ValueError("Raw NOR sector differs from independent oracle")
    return {"sector_sha256": sha(sector), "sector_hex": sector.hex()}


def previous(
    directory: Path, phase: Phase, guards: list[dict], image: bytes, handler_parent: Path | None
) -> dict:
    report, raw = load(directory)
    if (
        report.get("ok") is not True
        or report.get("error")
        or report["phase"] != phase.value
        or report["source_image_sha256"] != IMAGE_SHA
        or report["guards"] != guards
        or report["serial"] != OWNED_SERIAL
        or report.get("sd_write_attempted") is not True
    ):
        raise ValueError("Previous receipt phase, guards or identity mismatch")
    if "postcheck_parent" in report or report.get("download_reused"):
        from rcominote.experiments.sd_nor_postcheck import validate_derived

        validate_derived(report, directory, image)
    same_identity(report)
    address, size = (CONTEXT, 28) if phase == Phase.context else (BUFFER, CAPACITY)
    if report.get("source_address") != hex(address) or report.get("source_bytes") != size:
        raise ValueError("Previous receipt source range differs from fixed phase")
    command(report, address, size)
    validate_actions(report, producer=phase in targets.PRODUCER_PHASES)
    data = downloaded(report, directory, size)
    validate_payload(report, data)
    if report.get("transport_profile") == Transport.interval:
        from rcominote.experiments.sd_nor_interval import replay

        replay(report["transport"], directory)
    if phase == Phase.baseline or (
        phase in targets.PRODUCER_PHASES and report.get("transport_profile") == Transport.interval
    ):
        link = report["previous"]
        parent = previous(Path(link["directory"]), targets.PARENT_PHASE[phase], guards, image, handler_parent)
        if link != parent:
            raise ValueError("Baseline context parent file/hash changed")
    if phase == Phase.backup:
        from rcominote.experiments.sd_nor_unknown import validate_gate

        validate_gate(report, image)
    return {"directory": str(directory.resolve()), "report_sha256": sha(raw), "download_sha256": sha(data)}


async def capture(report: dict, out: Path) -> None:
    report["before"], report["files_before"] = await sd_bootstrap.identity()
    same_identity({"before": report["before"], "after": report["before"], "sd_write_attempted": False})
    if report["name"] in {entry["name"] for entry in report["files_before"]}:
        raise FileExistsError("Scratch name already listed; no write attempted")
    failure: BaseException | None = None
    try:
        await sd_bootstrap.write_file(report)
        validate_actions(report, producer=report["phase"] in targets.PRODUCER_PHASES)
        if report.get("transport_profile") == Transport.interval:
            from rcominote.experiments.sd_nor_interval import download

            await download(report, out)
        else:
            await sd_bootstrap.download_file(report, out, report["source_bytes"])
        data = downloaded(report, out, report["source_bytes"])
        report["verification"] = validate_payload(report, data)
        if report["phase"] in targets.PRODUCER_PHASES:
            (out / "sector.bin").write_bytes(bytes.fromhex(report["verification"]["sector_hex"]))
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            report["after"], report["files_after"] = await sd_bootstrap.identity()
            same_identity(report)
        except BaseException as error:
            report["after_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


def main(
    image: Path,
    out: Path,
    guard: Annotated[list[Path], typer.Option("--guard")],
    create_sd_file: bool = False,
    phase: Phase = Phase.context,
    previous_path: Annotated[Path | None, typer.Option("--previous")] = None,
    handler_parent: Path | None = None,
    transport: Transport = Transport.natural,
    sudo_password_stdin: bool = False,
    known_pair_second: Path | None = None,
) -> None:
    if (
        (phase == Phase.context and transport != Transport.natural)
        or (sudo_password_stdin and transport != Transport.interval)
        or (phase in (Phase.recovery, Phase.backup) and transport != Transport.interval)
    ):
        raise typer.BadParameter(
            "Interval transport is baseline/boot only or fixed nonzero profiles; nonzero targets and sudo input require interval profile"
        )
    if not create_sd_file:
        raise typer.BadParameter(
            "Requires --create-sd-file; retains one non-audio SD file and metadata writes"
        )
    out.mkdir(parents=True, exist_ok=False)
    address, size = (CONTEXT, 28) if phase == Phase.context else (BUFFER, CAPACITY)
    name = "rc" + secrets.token_hex(5)
    path = f"/SD:/RECORDER/Call-{name}.mp3"
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "serial": OWNED_SERIAL,
        "phase": phase.value,
        "name": name,
        "device_path": path,
        "dump_command": f"dbg dumpbuf {address} {size} {path}",
        "source_address": hex(address),
        "source_bytes": size,
        "source_image_sha256": IMAGE_SHA,
        "scope": "Fixed context/baseline/boot0/recovery-block1/backup-boot-block1 trial; no arbitrary address, NOR write or code execution",
        "residue_policy": "Retain non-audio SD scratch file and filesystem metadata; no automatic deletion",
        "sd_write_attempted": False,
        "ok": False,
        "transport_profile": transport.value,
    }
    try:
        raw = image.read_bytes()
        if len(raw) != 927632 or sha(raw) != IMAGE_SHA:
            raise ValueError("Wrong independently verified FW010004 image")
        report["guards"] = validate_guards(guard, raw, handler_parent)
        targets.prepare(report, raw, previous_path, handler_parent, known_pair_second)
        command(report, address, size)
        if transport == Transport.interval:
            from rcominote.experiments.hci_interval_io import authorize

            authorize(password_stdin=sudo_password_stdin)
        asyncio.run(capture(report, out))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = datetime.now(UTC).isoformat()
        with (out / "report.json").open("x") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ok": True, "phase": phase.value, "verification": report["verification"]}))


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
