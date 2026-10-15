"""Owned epoch ATT reassembly from final BlueZ capture; no I/O or packet repair."""

import struct

from rcominote.experiments import hci_interval as H
from rcominote.experiments.hci_monitor import Snoop


def att_packets(raw: bytes, handle: int) -> list[dict]:
    parser = Snoop()
    parser.feed(raw, final=True)
    connects = [e for e in parser.events if e["kind"] == "connect" and e["handle"] == handle]
    if len(connects) != 1 or connects[0]["status"] or connects[0]["address"] != H.PEER:
        raise ValueError("ATT replay requires one owned connection epoch")
    start = connects[0]["record"]
    stops = [
        e["record"]
        for e in parser.events
        if e["kind"] == "disconnect" and e["handle"] == handle and e["record"] > start
    ]
    stop = stops[0] if stops else parser.records + 1
    offset, index, pending, result = 16, 0, {}, []
    while offset < len(raw):
        _, size, flags, _, stamp = struct.unpack_from(">IIIIQ", raw, offset)
        packet = raw[offset + 24 : offset + 24 + size]
        offset += 24 + size
        index += 1
        if flags >> 16 or flags & 0xFFFF not in (4, 5) or not start < index < stop:
            continue
        if len(packet) < 4:
            raise ValueError("Truncated ACL header")
        word, length = struct.unpack_from("<HH", packet)
        if len(packet) != length + 4:
            raise ValueError("ACL length differs from captured bytes")
        if word & 0xFFF != handle:
            continue
        direction = "tx" if flags & 0xFFFF == 4 else "rx"
        pb = (word >> 12) & 3
        if word >> 14 or pb == 3:
            raise ValueError("Unexpected owned ACL broadcast/boundary flags")
        if pb in (0, 2):
            if direction in pending:
                raise ValueError("Overlapping owned L2CAP packets")
            pending[direction] = bytearray(packet[4:])
        elif direction not in pending:
            raise ValueError("Orphan owned ACL continuation")
        else:
            pending[direction].extend(packet[4:])
        body = pending[direction]
        if len(body) < 4:
            continue
        size, cid = struct.unpack_from("<HH", body)
        if len(body) > size + 4:
            raise ValueError("Owned L2CAP length overflow")
        if len(body) == size + 4:
            if cid == 4:
                if not 1 <= size <= 247:
                    raise ValueError("Owned ATT outside fixed MTU247")
                result.append({"direction": direction, "hex": bytes(body[4:]).hex(), "timestamp_us": stamp})
            del pending[direction]
    if pending:
        raise ValueError("Incomplete final owned ACL packet")
    return result


def timeline(session: dict, raw: bytes) -> list[int]:
    packets = att_packets(raw, session["transport"]["link"]["handle"])
    # Cross-direction task scheduling may invert successful send/receive hooks.
    # Each direction must still match every wire packet exactly, with no drops.
    positions, result = {}, [0] * len(session["att_packets"])
    for direction in ("tx", "rx"):
        indices = [i for i, r in enumerate(session["att_packets"]) if r["direction"] == direction]
        wire = [r for r in packets if r["direction"] == direction]
        if [session["att_packets"][i]["hex"] for i in indices] != [r["hex"] for r in wire]:
            raise ValueError(f"Owned HCI/host ATT {direction} sequence differs")
        positions[direction] = len(indices)
        for index, packet in zip(indices, wire, strict=True):
            result[index] = packet["timestamp_us"]
    if sum(positions.values()) != len(result):
        raise ValueError("Invalid host trace direction")
    return result


def bind(session: dict, raw: bytes) -> dict:
    stamps = timeline(session, raw)
    return {"verified": True, "packets": len(stamps), "comparison": "exact within each direction"}
