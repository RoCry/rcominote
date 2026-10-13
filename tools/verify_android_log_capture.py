#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Reproduce the fixed Android HCI/callback/baseline comparison, entirely offline."""

import hashlib
import json
import struct
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
SNOOP_SHA = "3764b2af668271f075d01b7e827e374b3e498d7481adc44c67ed8aaf15df1ab7"
NOTIFY = "e49a3003-f69a-11e8-8eb2-f2801f1b9fd1"


def records(raw: bytes):
    if len(raw) < 16 or struct.unpack_from(">8sII", raw) != (b"btsnoop\0", 1, 1002):
        raise ValueError("Expected complete Android H4 btsnoop v1/linktype1002")
    offset = 16
    number = 0
    while offset < len(raw):
        if len(raw) - offset < 24:
            raise ValueError("Truncated btsnoop record header")
        original, included, flags, drops, timestamp = struct.unpack_from(">IIIIQ", raw, offset)
        offset += 24
        if not 0 < included == original <= len(raw) - offset or drops:
            raise ValueError("Truncated/dropped btsnoop record; cannot establish complete payload")
        number += 1
        yield number, flags & 1, timestamp, raw[offset : offset + included]
        offset += included


def verify(directory: Path) -> dict:
    snoop = directory / "android-btsnoop_hci.log"
    raw = snoop.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SNOOP_SHA:
        raise ValueError("This evidence verifier accepts only the pinned Android capture")
    notifications, writes, parameters, characteristic_rows = [], [], [], []
    mappings = {}
    connection = disconnected = False
    count = 0
    connection_packet = disconnect_packet = None
    for number, direction, timestamp, packet in records(raw):
        count = number
        # Fixed observed connection handle5; connect event binds it to owned public MAC.
        if packet[0] == 4:
            if len(packet) != packet[2] + 3:
                raise ValueError("HCI event length mismatch")
            data = packet[3:]
            if packet[1] == 0x3E and data[0] == 0x0A and data[1:4] == b"\0\x05\0":
                if connection or data[5] != 0 or data[6:12] != bytes.fromhex("0e7caef0c050"):
                    raise ValueError("Unexpected connection handle reuse or peer identity")
                connection = True
                connection_packet = number
            if packet[1] == 5 and data[1:3] == b"\x05\0":
                disconnected = True
                disconnect_packet = number
            if connection and not disconnected and packet[1] == 0x3E:
                subcode = data[0]
                handle_at = 1 if subcode == 7 else 2
                if subcode in {3, 7, 12} and data[handle_at : handle_at + 2] == b"\x05\0":
                    row = {"packet": number, "subcode": subcode, "hex": data.hex()}
                    if subcode == 3:
                        row |= {"interval_ms": int.from_bytes(data[4:6], "little") * 1.25}
                    elif subcode == 7:
                        row |= {"tx_octets": int.from_bytes(data[3:5], "little")}
                        row |= {"rx_octets": int.from_bytes(data[7:9], "little")}
                    else:
                        row |= {"tx_phy": data[4], "rx_phy": data[5]}
                    parameters.append(row)
            continue
        if packet[0] != 2 or int.from_bytes(packet[1:3], "little") & 0xFFF != 5:
            continue
        if not connection or disconnected:
            raise ValueError("Selected ACL packet outside observed connection lifetime")
        handle_flags, length = struct.unpack_from("<HH", packet, 1)
        if len(packet) != length + 5 or handle_flags >> 12 not in {0, 2}:
            raise ValueError("Selected trace differs from observed unfragmented ACL layout")
        l2length, cid = struct.unpack_from("<HH", packet, 5)
        if length != l2length + 4:
            raise ValueError("Incomplete L2CAP PDU; this bounded verifier does not reassemble")
        if cid != 4:
            continue
        att = packet[9:]
        if not att:
            raise ValueError("Empty ATT packet")
        if att[0] in {2, 3}:
            parameters.append(
                {"packet": number, "att_opcode": att[0], "mtu": int.from_bytes(att[1:], "little")}
            )
        if direction == 1 and att[0] == 9:
            width = att[1]
            if width not in {7, 21} or (len(att) - 2) % width:
                raise ValueError("Unexpected characteristic discovery response")
            for offset in range(2, len(att), width):
                entry = att[offset : offset + width]
                handle = int.from_bytes(entry[3:5], "little")
                uuid = (
                    str(UUID(bytes=entry[5:][::-1]))
                    if width == 21
                    else f"0000{int.from_bytes(entry[5:], 'little'):04x}-0000-1000-8000-00805f9b34fb"
                )
                mappings[handle] = uuid
                characteristic_rows.append({"packet": number, "handle": handle, "uuid": uuid})
        if att[0] in {0x1B, 0x12, 0x52}:
            handle = int.from_bytes(att[1:3], "little")
            row = {
                "packet": number,
                "timestamp_us": timestamp,
                "characteristic": mappings.get(handle),
                "hex": att[3:].hex(),
            }
            if direction == 1 and att[0] == 0x1B:
                if row["characteristic"] is None:
                    raise ValueError("Notification handle absent from this connection's discovery")
                notifications.append(row)
            elif direction == 0 and row["characteristic"] is not None:
                writes.append(row)
    if not connection or not disconnected:
        raise ValueError("Incomplete selected connection lifetime")
    app_path = directory / "help.jsonl"
    app = [json.loads(line) for line in app_path.read_text().splitlines()]
    projection = lambda rows: [(row["characteristic"], row["hex"]) for row in rows]
    app_notifications = [row for row in app if row["event"] == "notify"]
    app_writes = [row for row in app if row["event"] == "write"]
    if projection(notifications) != projection(app_notifications) or projection(writes) != projection(
        app_writes
    ):
        raise ValueError("Raw HCI and Android callbacks/writes disagree")
    baseline_path = ROOT / "docs/evidence/log-commands-2026-10-12.json"
    linux_path = ROOT / "docs/evidence/linux-log-hci-loss-2026-10-13.json"
    frames = [
        bytes.fromhex(row["hex"])
        for row in json.loads(baseline_path.read_text())["frames"]
        if row["command"] == 240
    ]
    actions = [row for row in notifications if row["characteristic"] == NOTIFY]
    values = [bytes.fromhex(row["hex"]) for row in actions]
    linux = json.loads(linux_path.read_text())["hci_notifications"]
    if [row["hex"] for row in actions] != [row["hex"] for row in linux]:
        raise ValueError("Android no longer matches all11 independent Linux HCI notifications")
    if b"".join(values[2:5]) != frames[0] or values[5:7] != [frames[1][244:488], frames[1][488:512]]:
        raise ValueError("Independent baseline missing-prefix relationship changed")
    if values[7] != frames[2] or values[-1] != bytes.fromhex("1df1810000"):
        raise ValueError("Unexpected third frame or raw cleanup tail")
    return {
        "scope": "Pinned Android HCI raw-record/discovery/callback/baseline comparison; no byte reconstruction",
        "sources": {
            str(path.relative_to(ROOT)): {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in (snoop, app_path, baseline_path, linux_path)
        },
        "snoop_records": count,
        "truncated_records": 0,
        "reported_drops": 0,
        "connection_handle": 5,
        "connection_packet": connection_packet,
        "disconnect_packet": disconnect_packet,
        "discovered_characteristics": characteristic_rows,
        "link_parameters": parameters,
        "all_notifications_and_characteristic_writes_match_callbacks": True,
        "hci_actions_notifications": actions,
        "all11_actions_notifications_match_linux_hci": True,
        "second_frame_received_slices": [[244, 488], [488, 512]],
        "missing_slice_relative_to_independent_baseline": [0, 244],
        "experiment_ok": False,
        "comparison_verified": True,
        "limits": [
            "Pinned unfragmented CID4 capture verifier, not a general HCI/L2CAP parser",
            "Zero reported drops does not prove controller/logger completeness",
            "No over-the-air or device-TX trace; shared device enqueue/controller path remains a hypothesis",
            "Raw STOP ACK/F1 after parser failure is not strict session success",
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uv run tools/verify_android_log_capture.py CAPTURE_DIRECTORY")
    print(json.dumps(verify(Path(sys.argv[1]).resolve()), ensure_ascii=False, indent=2))
