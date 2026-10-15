#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Verify the pinned MTU128 experiment offline; print owned-connection evidence only.

Input directory contains report.json, after.json, session.btsnoop, session.btmon.txt.
Pre-info is the sibling live-board-check-20261013-before.json. Full monitor captures
include unrelated devices and must remain private/ignored; only hashes are exported.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

HASHES = {
    "report.json": "c9ca29c3d096367851c50f8f646e35b043e7579fac00533f39103b476f2141d6",
    "after.json": "50722dbf1e51f0290c58fd78ec7e166e5432799c8db42688f92c8030bb608195",
    "session.btsnoop": "8fd163278d3c5bae3c2331aa79ef4c3991ccdad3deb1e9afc04ed5cf44136427",
    "session.btmon.txt": "dc9bafdc15c237c8765f54cfea0f77a569b846fb01d8456d852fb223e68c7ba4",
    "live-board-check-20261013-before.json": "50722dbf1e51f0290c58fd78ec7e166e5432799c8db42688f92c8030bb608195",
}
MAC_LE = bytes.fromhex("0e7caef0c050")
PREPARE = "1d108105000002000100"
START = "1d108105000002002000"
STOP = "1d108105000002002100"
MDB = "1d10811600011300646267206d6462203130303061623430203130"
VERSION = "1d10811100010e006b65726e656c2076657273696f6e"
ACK = "1d108107007f0400a0860100"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def records(raw: bytes):
    require(len(raw) >= 16, "Truncated btsnoop header")
    require(
        struct.unpack_from(">8sII", raw) == (b"btsnoop\0", 1, 2001), "Expected Linux monitor btsnoop v1/2001"
    )
    offset, number = 16, 0
    while offset < len(raw):
        require(len(raw) - offset >= 24, "Truncated monitor record header")
        original, included, flags, drops, timestamp = struct.unpack_from(">IIIIQ", raw, offset)
        offset += 24
        require(original == included <= len(raw) - offset, "Truncated/invalid monitor record payload")
        require(included > 0 or flags & 0xFFFF == 8, "Unexpected empty monitor record")
        require(drops == 0, "Monitor reports dropped records")
        number += 1
        yield number, flags >> 16, flags & 0xFFFF, timestamp, raw[offset : offset + included]
        offset += included


def owned_att(
    raw: bytes, *, expected_lifetime: tuple[int, int, int] = (172, 77, 171)
) -> tuple[list[dict], dict]:
    """Strict selected lifetime, ACL framing and per-direction L2CAP reassembly."""
    handle = connection = disconnect = None
    active = False
    pending = {}
    packets, fragmented = [], []
    count = 0
    for number, index, opcode, _timestamp, packet in records(raw):
        count = number
        if opcode == 3:  # BlueZ monitor HCI event (no H4 type byte).
            require(len(packet) >= 2 and len(packet) == packet[1] + 2, "Malformed HCI event")
            data = packet[2:]
            if packet[0] == 0x3E and data and data[0] == 0x0A:
                require(len(data) == 31, "Malformed LE Enhanced Connection Complete")
                if data[6:12] == MAC_LE:
                    require(index == 0 and connection is None, "Unexpected owned connection/index reuse")
                    require(data[1] == 0 and data[5] == 0, "Owned connection failed or address not public")
                    handle = int.from_bytes(data[2:4], "little")
                    require(handle == 2048, "Pinned owned connection handle changed")
                    connection, active = number, True
            elif packet[0] == 5 and len(data) == 4 and handle is not None:
                if int.from_bytes(data[1:3], "little") == handle:
                    require(index == 0 and active and not pending, "Incomplete owned disconnect/layer packet")
                    disconnect, active = number, False
            continue
        if opcode not in {4, 5} or index != 0:
            continue
        require(len(packet) >= 4, "Truncated ACL header")
        handle_flags, size = struct.unpack_from("<HH", packet)
        require(len(packet) == size + 4, "ACL length mismatch")
        if handle_flags & 0xFFF != handle:
            continue
        require(active, "Owned ACL outside observed lifetime")
        direction = "tx" if opcode == 4 else "rx"
        boundary = handle_flags >> 12
        payload = packet[4:]
        if boundary in {0, 2}:
            require(direction not in pending and len(payload) >= 4, "Overlapping/truncated L2CAP start")
            size, cid = struct.unpack_from("<HH", payload)
            pending[direction] = {"expected": size + 4, "cid": cid, "raw": payload, "records": [number]}
        elif boundary == 1:
            require(direction in pending, "Unowned ACL continuation")
            pending[direction]["raw"] += payload
            pending[direction]["records"].append(number)
        else:
            raise ValueError(f"Unsupported owned ACL boundary flags: {boundary}")
        state = pending[direction]
        require(len(state["raw"]) <= state["expected"], "L2CAP reassembly overrun")
        if len(state["raw"]) != state["expected"]:
            continue
        del pending[direction]
        if len(state["records"]) > 1:
            fragmented.append(state["records"])
        if state["cid"] == 4:
            att = state["raw"][4:]
            require(bool(att), "Empty owned ATT packet")
            packets.append({"direction": direction, "hex": att.hex(), "hci_records": state["records"]})
    require((count, connection, disconnect) == expected_lifetime, "Pinned capture/lifetime changed")
    require(not active and not pending, "Incomplete selected connection capture")
    return packets, {
        "monitor_records": count,
        "index": 0,
        "connection_handle": handle,
        "connection_record": connection,
        "disconnect_record": disconnect,
        "reported_drops": 0,
        "truncated_records": 0,
        "reassembled_l2cap_record_groups": fragmented,
    }


def verify(directory: Path) -> dict:
    paths = {name: directory / name for name in HASHES}
    before_name = "live-board-check-20261013-before.json"
    paths[before_name] = directory.parent / before_name
    raw = {name: path.read_bytes() for name, path in paths.items()}
    for name, data in raw.items():
        require(hashlib.sha256(data).hexdigest() == HASHES[name], f"Pinned source SHA256 mismatch: {name}")
    report, before, after = (json.loads(raw[name]) for name in ("report.json", before_name, "after.json"))
    require(before == after, "Before/after info differs")
    require(before["serial"] == report["serial"] == "C261CF0430", "Wrong owned serial")
    require(report["address"] == "50:C0:F0:AE:7C:0E", "Wrong report address")
    require(before["device"]["recording_state"] == "idle", "Expected idle recording state")
    require(len(bytes.fromhex(before["device"]["raw"])) == 52, "Expected complete 52-byte info")
    require(not report["ok"] and report["local_mtu"] == report["mtu"] == 128, "Unexpected experiment status")
    packets, lifetime = owned_att(raw["session.btsnoop"])
    projection = lambda rows: [(row["direction"], row["hex"]) for row in rows]
    require(projection(packets) == projection(report["att_packets"]), "HCI/socket complete ATT traces differ")
    mtus = [row for row in packets if bytes.fromhex(row["hex"])[0] in {2, 3}]
    require(
        projection(mtus) == [("tx", "028000"), ("rx", "03f700"), ("rx", "02f700"), ("tx", "038000")],
        "Both directions must advertise local128/peer247",
    )
    # Confirm owned Actions handles using characteristic discovery from this lifetime.
    discoveries = [
        bytes.fromhex(row["hex"])
        for row in packets
        if row["direction"] == "rx" and row["hex"].startswith("09")
    ]
    require(
        len(discoveries) == 1 and discoveries[0][1] == 21 and len(discoveries[0]) == 44,
        "Unexpected Actions characteristic discovery",
    )
    chars = discoveries[0][2:]
    require(
        chars[:5] == bytes.fromhex("15000c1600") and chars[21:26] == bytes.fromhex("1700101800"),
        "Actions declaration/value handles changed",
    )
    require(
        chars[5:21] == bytes.fromhex("d19f1b1f80f2b28ee8119af602309ae4")
        and chars[26:] == bytes.fromhex("d19f1b1f80f2b28ee8119af603309ae4"),
        "Actions UUIDs changed",
    )
    notifications, writes = [], []
    for row in packets:
        pdu = bytes.fromhex(row["hex"])
        if row["direction"] == "rx" and pdu[0] == 0x1B:
            require(len(pdu) >= 3 and pdu[1:3] == b"\x18\0", "Unexpected notification handle")
            notifications.append({"hex": pdu[3:].hex(), "hci_records": row["hci_records"]})
        elif row["direction"] == "tx" and pdu[0] in {0x12, 0x52}:
            require(pdu[0] == 0x12 and len(pdu) >= 3, "Unexpected application write opcode")
            handle = int.from_bytes(pdu[1:3], "little")
            if handle == 0x19:
                require(pdu == bytes.fromhex("1219000100"), "Unexpected CCCD write")
            else:
                require(handle == 0x16, "Unexpected application write handle")
                writes.append({"hex": pdu[3:].hex(), "hci_records": row["hci_records"]})
    values = [bytes.fromhex(row["hex"]) for row in notifications]
    require(
        len(values) == 14
        and [row["hex"] for row in notifications] == [row["hex"] for row in report["notifications"]],
        "All14 Actions HCI/socket values must match",
    )
    expected_writes = [PREPARE, START, MDB] + [VERSION] * 6
    require(
        [row["hex"] for row in writes] == expected_writes,
        "Wire commands differ from fixed read-only allowlist",
    )
    require(report["writes"] == expected_writes + [STOP], "STOP intent accounting changed")
    require(values[:8] == [bytes.fromhex(ACK)] * 8 and values[-1].hex() == ACK, "ACK ordering changed")
    fragments = values[8:12]
    require([len(value) for value in fragments] == [125, 125, 125, 12], "Unexpected incomplete frame slices")
    require(fragments[0][:5] == bytes.fromhex("1df081fb01"), "Expected declared512-byte F0 header")
    observed = b"".join(fragments)
    require(len(observed) == 387, "Unexpected first-frame observed byte count")
    next_frame = values[12]
    require(
        next_frame[:5] == bytes.fromhex("1df0813200") and len(next_frame) == 55,
        "Expected next independent complete55-byte F0 frame",
    )
    require(
        report["pending_hex"] == (observed + next_frame + values[-1]).hex(),
        "Strict decoder pending bytes differ",
    )
    require(
        report["capture_error"].startswith("TimeoutError:")
        and report["stop_error"].startswith("ConnectionError: ATT link unusable:"),
        "Cleanup failure differs",
    )
    require(
        report["ack_count"] == 8 and report["expected_ack_count"] == 10 and report["end_received"] is False,
        "Strict session failure accounting differs",
    )
    require(
        not any(value.startswith(bytes.fromhex("1df181")) for value in values), "Unexpected F1 end marker"
    )
    require([frame["hex"] for frame in report["frames"]] == [ACK] * 8, "Strict decoded frames changed")
    require(
        report["short_read"]
        == {
            "address": "1000ab40",
            "bytes": 16,
            "image_sha256": "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f",
            "expected_hex": "5e348df8123094f87034bdf800208df8",
            "flush_queries": 6,
        },
        "Short mapped-read scope differs",
    )
    return {
        "scope": "Pinned owned CoMi Linux MTU128 ATT/HCI comparison; offline verification, no dropped-byte reconstruction",
        "sources": {name: {"bytes": len(raw[name]), "sha256": HASHES[name]} for name in HASHES},
        "connection": lifetime,
        "mtu_exchange": mtus,
        "effective_att_mtu": 128,
        "notification_value_limit": 125,
        "all_owned_hci_att_pdus_equal_socket_trace": True,
        "all14_actions_hci_notifications_equal_socket_values": True,
        "owned_actions_hci_notifications": notifications,
        "owned_actions_hci_write_requests": writes,
        "incomplete_first_f0": {
            "declared_total_bytes": 512,
            "observed_value_lengths": [125, 125, 125, 12],
            "observed_total_bytes": 387,
            "deficit_before_next_independent_frame": 125,
            "next_independent_frame_bytes": 55,
            "missing_byte_position_known": False,
            "reconstructed": False,
        },
        "commands": {
            "wire_actions_write_requests": 9,
            "intent_list_entries": 10,
            "mapped_read": "dbg mdb 1000ab40 10",
            "kernel_version_fillers": 6,
            "gpio_nor_sd_recording_write_commands_on_wire": False,
            "verified_by": "Exact ordered allowlist of every owned application ATT write, plus CCCD enable only",
        },
        "cleanup": {
            "stop_in_intent_list": True,
            "stop_att_write_request_observed": False,
            "stop_hci_write_request_observed": False,
            "stop_sent_successfully": False,
            "capture_error": report["capture_error"],
            "stop_error": report["stop_error"],
            "reason": "Capture timeout invalidated/closed ATT link; STOP attempt failed before wire send",
            "raw_ack_notifications": 9,
            "strict_decoded_ack_frames": 8,
            "f1_end_observed": False,
            "strict_session_success": False,
        },
        "info": {
            "before_after_entire_json_equal": True,
            "raw52_hex": before["device"]["raw"],
            "raw52_sha256": hashlib.sha256(bytes.fromhex(before["device"]["raw"])).hexdigest(),
            "recording_state": "idle",
            "firmware_version": before["device"]["version"],
        },
        "experiment_ok": False,
        "comparison_verified": True,
        "limits": [
            "Fixed pinned capture/profile only; full Linux monitor/text include unrelated devices and remain ignored",
            "Only actual ACL fragmentation is reassembled; missing Actions chunks are never synthesized or repaired",
            "Zero reported monitor drops does not prove controller/logger completeness or establish over-the-air loss",
            "125-byte deficit does not establish its offset, missing packet count, or device-side root cause",
            "STOP in report writes records intent; absence from both socket/HCI excludes successful on-wire cleanup",
            "Unchanged full device info/idle state does not establish all internal state or independent hardware recovery",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(directory=args.capture_directory.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
