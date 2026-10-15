"""Fixed known-mdb16 slot contract and evidence checks; no device I/O."""

import re
from datetime import datetime
from pathlib import Path

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import logsrv_context_probe as context
from rcominote.experiments.sd_bridge import console_packet
from rcominote.experiments.sd_nor_probe import IMAGE_SHA, command, downloaded, load, same_identity, sha
from rcominote.experiments.sd_nor_probe import validate_actions as single_actions
from rcominote.log_capture import START, STOP
from rcominote.log_probe import NOTIFY, PREPARE, WRITE
from rcominote.log_stream import Stream

POINTER = 0x180111FC
STREAM = 0x18011254
INDEX = 204
SLOT = 0x1800B1B0
MDB = "dbg mdb 1000ab40 10"
ORACLE = bytes.fromhex("5e348df8123094f87034bdf800208df8")
# Exact public linux-short-read-2026-10-13.json text, including ASCII and CRLF.
ROW = b"1000ab40: 5e 34 8d f8 12 30 94 f8 70 34 bd f8 00 20 8d f8    ^4...0..p4... ..\r\n"
SLOT_GUARDS = {0x1000BD30: 32, 0x1000BD80: 48}
FILES = (("global", context.GLOBAL, 4), ("metadata", POINTER, 32), ("slot", SLOT, 512))


def times(directory: Path) -> tuple[datetime, datetime]:
    report, _ = load(directory)
    start, end = (datetime.fromisoformat(report[key]) for key in ("started_at", "ended_at"))
    if start.utcoffset() is None or end.utcoffset() is None or start > end:
        raise ValueError("Parent chronology requires ordered timezone-aware receipt timestamps")
    return start, end


def commands(report: dict) -> list[str]:
    if report["serial"] != OWNED_SERIAL or report["source_image_sha256"] != IMAGE_SHA:
        raise ValueError("Requires owned fixed firmware profile")
    if report.get("producer") is not None or report.get("download_only") or report.get("tail_only"):
        raise ValueError("Only the fixed known-mdb16 slot profile is permitted")
    files = report["files"]
    if len(files) != 3:
        raise ValueError("Requires exactly three distinct fixed snapshot files")
    result, names = [], set()
    for item, (role, address, size) in zip(files, FILES, strict=True):
        if item["role"] != role or item["source_address"] != hex(address) or item["source_bytes"] != size:
            raise ValueError("Snapshot role/source differs from fixed slot profile")
        text = command(item, address, size)
        if item["name"] in names:
            raise ValueError("Snapshot names must be distinct")
        names.add(item["name"])
        if len((text + "\n").encode()) > 63:
            raise ValueError("Fixed command exceeds63-byte budget")
        result.append(text)
    expected = [result[0], MDB, result[1], result[2]]
    if "commands" in report and report["commands"] != expected:
        raise ValueError("Declared commands differ from fixed slot sequence")
    return expected


def metadata(data: bytes) -> dict:
    fields = context.context_fields(data)
    expected = {
        "stream_pointer": hex(STREAM),
        "flags_byte": 3,
        "log_type": 0,
        "new_log_type": 0,
        "rd": INDEX,
        "wr": INDEX,
        "drop_count": 0,
    }
    if any(fields[k] != v for k, v in expected.items()):
        raise ValueError("Context changed from fixed stream/mode/counters/drop; do not select another slot")
    lengths = fields["slot_lengths"]
    if not 1 <= lengths[4] <= 504 or any(n for i, n in enumerate(lengths) if i != 4):
        raise ValueError("Expected only slot4 to contain a bounded active prefix")
    return fields


def validate_slot_guards(directories: list[Path], image: bytes) -> list[dict]:
    return validate_code_guards(directories, image, SLOT_GUARDS)


def validate_code_guards(directories: list[Path], image: bytes, ranges: dict[int, int]) -> list[dict]:
    """Internal fixed-profile guard validator; callers supply their compile-time ranges."""
    if len(directories) != len(ranges) or len({p.resolve() for p in directories}) != len(ranges):
        raise ValueError("Requires distinct complete fixed code guards")
    result, seen = [], set()
    for directory in directories:
        report, raw = load(directory)
        address = int(report["source_address"], 16)
        size = ranges.get(address)
        if (
            size is None
            or address in seen
            or report["source_bytes"] != size
            or report["serial"] != OWNED_SERIAL
            or report["source_image_sha256"] != IMAGE_SHA
            or report.get("ok") is not True
            or report.get("error")
            or report.get("sd_write_attempted") is not True
            or any(report.get(k) for k in ("download_only", "tail_only", "download_reused"))
        ):
            raise ValueError("Invalid independent slot code guard")
        seen.add(address)
        command(report, address, size)
        same_identity(report)
        single_actions(report)
        oracle = image[address - 0x10000000 : address - 0x10000000 + size]
        if downloaded(report, directory, size) != oracle or report["expected_sha256"] != sha(oracle):
            raise ValueError("Slot live code differs from pinned image")
        result.append(
            {
                "directory": str(directory.resolve()),
                "report_sha256": sha(raw),
                "address": hex(address),
                "bytes": size,
            }
        )
    return sorted(result, key=lambda row: row["address"])


def validate_parents(
    image: bytes,
    guards: list[Path],
    slot_guards: list[Path],
    pointer_parent: Path,
    context_parent: Path,
    handler_parent: Path | None,
) -> dict:
    verified = context.validate_guards(guards, image, handler_parent)
    if image[0xAB40:0xAB50] != ORACLE:
        raise ValueError("Independent mdb16 oracle changed")
    slots = validate_slot_guards(slot_guards, image)
    pointer_start, pointer_end = times(pointer_parent)
    context_start, _ = times(context_parent)
    if max(times(path)[1] for path in [*guards, *slot_guards]) > pointer_start or pointer_end > context_start:
        raise ValueError("Parent chronology must be guards→pointer→context; stale204 context is insufficient")
    pointer_link = context.previous(pointer_parent, verified)
    if pointer_link["pointer"] != hex(POINTER):
        raise ValueError("Pointer parent differs from fixed180111fc")
    report, raw = load(context_parent)
    if (
        report.get("phase") != context.Phase.context
        or report.get("ok") is not True
        or report.get("error")
        or report["serial"] != OWNED_SERIAL
        or report["source_image_sha256"] != IMAGE_SHA
        or report["guards"] != verified
        or report["previous"] != pointer_link
        or report.get("sd_write_attempted") is not True
        or any(report.get(k) for k in ("download_only", "tail_only", "download_reused", "postcheck_parent"))
    ):
        raise ValueError("Context parent must be independently complete with matching pointer/guard chain")
    if context.request(report) != (POINTER, 32):
        raise ValueError("Wrong fixed context source")
    same_identity(report)
    single_actions(report)
    fields = metadata(downloaded(report, context_parent, 32))
    if report["verification"] != fields:
        raise ValueError("Context parent summary differs from actual bytes")
    return {
        "guards": verified,
        "slot_guards": slots,
        "pointer": pointer_link,
        "context": {"directory": str(context_parent.resolve()), "report_sha256": sha(raw), "fields": fields},
    }


def verify_payload(report: dict, global_data: bytes, meta_data: bytes, slot_data: bytes) -> dict:
    commands(report)
    if context.pointer(global_data) != POINTER:
        raise ValueError("Current-pointer snapshot changed; historical dereference not revalidated")
    fields = metadata(meta_data)
    if len(slot_data) != 512:
        raise ValueError("Slot requires complete512-byte transfer")
    length = fields["slot_lengths"][4]
    body = slot_data[8 : 8 + length]
    marker = b"done dumping to " + report["files"][0]["device_path"].encode("ascii")
    matches = list(re.finditer(rb"(?m)(?:^|(?<=\n))" + re.escape(marker) + rb"\r?\n", body))
    rows = list(re.finditer(rb"(?m)(?:^|(?<=\n))" + re.escape(ROW), body))
    if (
        len(matches) != 1
        or body.count(marker) != 1
        or len(rows) != 1
        or body.count(b"1000ab40:") != 1
        or matches[0].end() > rows[0].start()
    ):
        raise ValueError("Missing, duplicated, stale-order or incomplete nonce→known-mdb16 row within L")
    return {
        "pointer_matches_historical": True,
        "metadata": fields,
        "body_length": length,
        "marker_body_span": list(matches[0].span()),
        "row_body_span": list(rows[0].span()),
        "known_bytes_hex": ORACLE.hex(),
        "known_bytes_sha256": sha(ORACLE),
        "scope": "Fresh-marker-associated known row in saved prefix; no atomic/current-pointer/partial-state proof",
    }


def validate_actions(report: dict) -> None:
    """Reconstruct consumed Actions frames from actual ATT trace, including write responses."""
    packets = [PREPARE, START, *[console_packet(cmd) for cmd in commands(report)], STOP]
    validate_action_packets(report, packets)


def validate_action_packets(report: dict, packets: list[bytes]) -> None:
    """Internal ATT replay; fixed-profile callers construct the exact expected packet list."""
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
