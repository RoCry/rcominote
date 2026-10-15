"""Fixed owned-device Linux LE discovery/log control; no recording or firmware writes."""

import asyncio
import json
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import typer

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.code_guards import observed_block
from rcominote.experiments.audio_state import IMAGE_SHA, guard_bytes
from rcominote.experiments.linux_att import AttError, AttLink
from rcominote.log_capture import START, STOP
from rcominote.log_probe import NOTIFY, PREPARE, SERVICE, WRITE
from rcominote.log_stream import Stream
from rcominote.output import new_output


def uuid_text(raw: bytes) -> str:
    if len(raw) == 2:
        return f"0000{int.from_bytes(raw, 'little'):04x}-0000-1000-8000-00805f9b34fb"
    if len(raw) == 16:
        return str(UUID(bytes=raw[::-1]))
    raise ValueError("Unexpected GATT UUID length")


def table_rows(pdu: bytes, widths: tuple[int, ...]) -> list[bytes]:
    if len(pdu) < 2 or pdu[1] not in widths or len(pdu) == 2 or (len(pdu) - 2) % pdu[1]:
        raise ValueError(f"Malformed GATT table: {pdu.hex()}")
    return [pdu[i : i + pdu[1]] for i in range(2, len(pdu), pdu[1])]


async def discover(link: AttLink, report: dict) -> tuple[int, int, int]:
    services = report["services"] = []
    start = 1
    for _ in range(32):
        try:
            response = await link.request(b"\x10" + struct.pack("<HHH", start, 0xFFFF, 0x2800), 0x11)
        except AttError as error:
            if error.pdu == b"\x01\x10" + start.to_bytes(2, "little") + b"\x0a":
                break
            raise
        for row in table_rows(response, (6, 20)):
            first, last = struct.unpack_from("<HH", row)
            if not start <= first <= last <= 0xFFFF:
                raise ValueError("Non-monotonic service handles")
            services.append({"start": first, "end": last, "uuid": uuid_text(row[4:])})
            start = last + 1
        if start > 0xFFFF:
            break
    else:
        raise ValueError("Service discovery exceeded fixed bound")
    matches = [row for row in services if row["uuid"] == SERVICE]
    if len(matches) != 1:
        raise ValueError("Expected one Actions log service")
    service = matches[0]
    start, end = service["start"], service["end"]
    response = await link.request(b"\x08" + struct.pack("<HHH", start, end, 0x2803), 0x09)
    chars = report["log_characteristics"] = []
    for row in table_rows(response, (7, 21)):
        declaration, properties, value = struct.unpack_from("<HBH", row)
        if not start < declaration < value <= end:
            raise ValueError("Characteristic outside log service")
        chars.append(
            {"declaration": declaration, "properties": properties, "value": value, "uuid": uuid_text(row[5:])}
        )
    # Fixed FW010004 profile: exactly the known write and notify characteristics.
    if len(chars) != 2 or {row["uuid"] for row in chars} != {WRITE, NOTIFY}:
        raise ValueError("Actions characteristic layout differs from fixed profile")
    write = next(row for row in chars if row["uuid"] == WRITE)
    notify = next(row for row in chars if row["uuid"] == NOTIFY)
    if not write["properties"] & 8 or not notify["properties"] & 16:
        raise ValueError("Required Write Request/Notify properties absent")
    cccd = notify["value"] + 1
    if cccd != end:
        raise ValueError("CCCD position differs from fixed profile")
    response = await link.request(b"\x04" + struct.pack("<HH", cccd, cccd), 0x05)
    if response != b"\x05\x01" + struct.pack("<HH", cccd, 0x2902):
        raise ValueError("Notify descriptor is not the expected CCCD")
    return write["value"], notify["value"], cccd


async def short_read(send, stream: Stream, report: dict) -> None:
    """One known mapped-code row, with at most eight read-only version fillers."""
    address = 0x1000AB40
    expected = guard_bytes()[address]
    report["short_read"] = {
        "address": f"{address:08x}",
        "bytes": len(expected),
        "image_sha256": IMAGE_SHA,
        "expected_hex": expected.hex(),
        "flush_queries": 0,
    }

    async def text(command: str):
        encoded = command.encode()
        tlv = b"\x01" + len(encoded).to_bytes(2, "little") + encoded
        await send(b"\x1d\x10\x81" + len(tlv).to_bytes(2, "little") + tlv)

    await text("dbg mdb 1000ab40 10")
    for count in range(9):
        if (value := observed_block(stream.frames, address, len(expected))) is not None:
            report["short_read"]["observed_hex"] = value.hex()
            if value != expected:
                raise ValueError("Known mapped-code row differs from independent image")
            return
        if count == 8:
            raise ValueError("Known row not received within eight version fillers")
        report["short_read"]["flush_queries"] = count + 1
        await text("kernel version")


async def capture(report: dict, *, read_short: bool = False, small_mtu: bool = False) -> None:
    if sys.platform != "linux":
        raise RuntimeError("Direct LE experiment requires Linux; no device access attempted")
    if read_short:
        guard_bytes()  # Reject a changed oracle before any device access.
    device = await find_device(serial=OWNED_SERIAL, seconds=10)
    report["address"] = device.address
    local_mtu = 128 if small_mtu else 247
    report["local_mtu"] = local_mtu
    async with AttLink(device.address, report, local_mtu=local_mtu) as link:
        await link.request(b"\x02" + local_mtu.to_bytes(2, "little"), 0x03)
        write, notify, cccd = await discover(link, report)
        await link.request(b"\x12" + struct.pack("<HH", cccd, 1), 0x13)
        stream = Stream()
        report.update(frames=stream.frames, notifications=[], writes=[])
        expected = 0
        attempted = False

        async def pump():
            handle, value = await link.next_notification()
            if handle != notify:
                raise ValueError(f"Unexpected notification handle {handle:#x}")
            report["notifications"].append({"hex": value.hex()})
            stream.feed(value)

        async def send(packet: bytes):
            nonlocal expected
            expected += 1
            report["writes"].append(packet.hex())
            await link.request(b"\x12" + write.to_bytes(2, "little") + packet, 0x13)
            async with asyncio.timeout(10):
                while stream.acks < expected:
                    await pump()

        try:
            await send(PREPARE)
            attempted = True
            await send(START)
            # Same exact commands as the failed macOS control, no newline added.
            if read_short:
                await short_read(send, stream, report)
            else:
                for text in (b"help", b"dbg"):
                    tlv = b"\x01" + len(text).to_bytes(2, "little") + text
                    await send(b"\x1d\x10\x81" + len(tlv).to_bytes(2, "little") + tlv)
        except BaseException as error:
            report["capture_error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            try:
                if attempted:
                    await send(STOP)
                    async with asyncio.timeout(10):
                        while not stream.ended:
                            await pump()
            except BaseException as error:
                report["stop_error"] = f"{type(error).__name__}: {error}"
                if "capture_error" not in report:
                    raise
                # Keep the independent raw ATT reader alive after decoder failure.
                # No resynchronization and no promotion of raw ACK/F1 to success.
                await asyncio.sleep(0.5)
                report["raw_cleanup_window_seconds"] = 0.5
            finally:
                report.update(
                    mtu=link.mtu,
                    ack_count=stream.acks,
                    expected_ack_count=expected,
                    end_received=stream.ended,
                    pending_hex=stream.pending.hex(),
                )
        if stream.acks != expected or not stream.ended or stream.pending:
            raise ValueError("Incomplete Actions stream")
        text = "".join(row.get("text", "") for row in stream.frames)
        if not read_short and ("Available commands:" not in text or "dbg" not in text):
            raise ValueError("Missing expected diagnostic output")
        report["text_bytes"] = sum(
            len(bytes.fromhex(row["hex"])) - 8 for row in stream.frames if row["command"] == 0xF0
        )


def main(
    out: Path,
    read_short: bool = typer.Option(False, "--short-read"),
    small_mtu: bool = typer.Option(False, "--small-mtu"),
):
    new_output(out)
    report = {
        "serial": OWNED_SERIAL,
        "started_at": datetime.now(UTC).isoformat(),
        "ok": False,
        "scope": (
            "Direct LE ATT; one fixed mapped-code read, at most eight kernel version fillers; no recording"
            if read_short
            else "Direct public LE ATT; service discovery, MTU, log CCCD, PREPARE/START/help/dbg/STOP only"
        ),
    }
    try:
        asyncio.run(capture(report, read_short=read_short, small_mtu=small_mtu))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = datetime.now(UTC).isoformat()
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x") as file:
            file.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("ok", "mtu", "ack_count", "end_received", "text_bytes")}))


if __name__ == "__main__":
    typer.run(main)
