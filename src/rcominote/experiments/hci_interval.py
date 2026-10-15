"""Strict BlueZ monitor btsnoop connection-interval evidence; no device operations."""

import struct
import time

PEER = "50:C0:F0:AE:7C:0E"
HEADER = b"btsnoop\0" + struct.pack(">II", 1, 2001)
EPOCH_US = 0x00DC_DDB3_0F2F_8000
LIMIT = 8 * 1024 * 1024


def timestamp_us() -> int:
    return EPOCH_US + time.time_ns() // 1000


def mac(raw: bytes) -> str:
    return ":".join(f"{byte:02X}" for byte in raw[::-1])


class Snoop:
    """Incremental records: incomplete live tail waits; truncated final input fails."""

    def __init__(self):
        self.buffer = bytearray()
        self.started = False
        self.total = self.records = self.last_stamp = 0
        self.events: list[dict] = []

    def feed(self, data: bytes, *, final: bool = False) -> None:
        self.total += len(data)
        if self.total > LIMIT:
            raise ValueError("HCI capture exceeds 8 MiB bound")
        self.buffer.extend(data)
        if not self.started and len(self.buffer) >= 16:
            if self.buffer[:16] != HEADER:
                raise ValueError("Requires BlueZ monitor btsnoop version1/type2001")
            del self.buffer[:16]
            self.started = True
        while self.started and len(self.buffer) >= 24:
            original, size, flags, drops, stamp = struct.unpack_from(">IIIIQ", self.buffer)
            if original != size or size > 65535 or drops or stamp < self.last_stamp:
                raise ValueError("Truncated/dropped/nonmonotonic HCI record")
            if len(self.buffer) < 24 + size:
                break
            packet = bytes(self.buffer[24 : 24 + size])
            del self.buffer[: 24 + size]
            self.records += 1
            self.last_stamp = stamp
            if flags >> 16 != 0:  # hci0 exclusively; unrelated controllers never prove this gate.
                continue
            event = decode(flags & 0xFFFF, packet)
            if event is not None:
                self.events.append(event | {"record": self.records, "timestamp_us": stamp})
        if final and (not self.started or self.buffer):
            raise ValueError("Incomplete final btsnoop header/record")


def decode(opcode: int, packet: bytes) -> dict | None:
    if opcode == 0:  # HCI_MON_NEW_INDEX
        if len(packet) != 16:
            raise ValueError("Malformed controller index record")
        return {"kind": "controller", "address": mac(packet[2:8])}
    if opcode == 1:  # HCI_MON_DEL_INDEX
        return {"kind": "controller-removed"}
    if opcode == 2:  # HCI_MON_COMMAND_PKT
        if len(packet) < 3 or len(packet) != 3 + packet[2]:
            raise ValueError("Malformed HCI command length")
        if packet[:2] == b"\x13\x20":
            if len(packet) != 17:
                raise ValueError("Malformed LE Connection Update command")
            fields = struct.unpack("<7H", packet[3:])
            return dict(
                zip(
                    ("handle", "min", "max", "latency", "timeout", "min_length", "max_length"),
                    fields,
                    strict=True,
                )
            ) | {"kind": "request"}
    if opcode != 3:  # HCI_MON_EVENT_PKT
        return None
    if len(packet) < 2 or len(packet) != packet[1] + 2:
        raise ValueError("Malformed HCI event length")
    event, body = packet[0], packet[2:]
    if event == 0x0F and len(body) == 4 and body[2:] == b"\x13\x20":
        return {"kind": "status", "status": body[0]}
    if event == 5:
        if len(body) != 4:
            raise ValueError("Malformed Disconnection Complete")
        return {
            "kind": "disconnect",
            "status": body[0],
            "handle": int.from_bytes(body[1:3], "little"),
            "reason": body[3],
        }
    if event != 0x3E or not body:
        return None
    sub, data = body[0], body[1:]
    if sub in (1, 10):
        if len(data) != (18 if sub == 1 else 30):
            raise ValueError("Malformed LE Connection Complete")
        offset = 11 if sub == 1 else 23
        interval, latency, timeout = struct.unpack_from("<3H", data, offset)
        return {
            "kind": "connect",
            "status": data[0],
            "handle": int.from_bytes(data[1:3], "little"),
            "role": data[3],
            "address_type": data[4],
            "address": mac(data[5:11]),
            "interval": interval,
            "latency": latency,
            "timeout": timeout,
        }
    if sub == 3:
        if len(data) != 9:
            raise ValueError("Malformed LE Connection Update Complete")
        handle, interval, latency, timeout = struct.unpack_from("<4H", data, 1)
        return {
            "kind": "update",
            "status": data[0],
            "handle": handle,
            "interval": interval,
            "latency": latency,
            "timeout": timeout,
        }
    return None


def epoch(events: list[dict], handle: int, local: str) -> list[dict]:
    if any(e["kind"] == "controller-removed" for e in events):
        raise ValueError("Captured hci0 was removed")
    controllers = [e for e in events if e["kind"] == "controller"]
    if not controllers or any(e["address"] != local for e in controllers):
        raise ValueError("Active socket local address is not captured hci0")
    matches = [e for e in events if e["kind"] == "connect" and e["handle"] == handle]
    if len(matches) != 1:
        raise ValueError("Requires exactly one fresh connection epoch; no handle reuse")
    first = matches[0]
    if (first["status"], first["role"], first["address_type"], first["address"]) != (0, 0, 0, PEER):
        raise ValueError("HCI handle is not owned public peer on a central connection")
    selected = [e for e in events if e["record"] >= first["record"] and e.get("handle") == handle]
    if any(e["kind"] == "disconnect" for e in selected):
        raise ConnectionError("Selected HCI connection disconnected; no handle reuse/reconnect")
    return selected


def current(events: list[dict], handle: int, local: str) -> dict:
    states = [e for e in epoch(events, handle, local) if e["kind"] in ("connect", "update")]
    if any(e["status"] != 0 for e in states):
        raise ValueError("Connection parameter update failed before the experiment")
    return states[-1]


def applied(events: list[dict], handle: int, local: str, baseline: dict, requested_us: int) -> dict | None:
    selected = epoch(events, handle, local)
    later = [e for e in selected if e["timestamp_us"] >= requested_us]
    requests = [e for e in later if e["kind"] == "request"]
    updates = [e for e in later if e["kind"] == "update"]
    if len(requests) > 1 or len(updates) > 1:
        raise ValueError("Second parameter request/update: experimental condition changed")
    if not requests:
        if updates:
            raise ValueError("Parameters changed before our update request")
        return None
    request = requests[0]
    if (
        request["min"],
        request["max"],
        request["latency"],
        request["timeout"],
        request["min_length"],
        request["max_length"],
    ) != (
        6,
        6,
        0,
        baseline["timeout"],
        1,
        1,
    ):
        raise ValueError("Observed HCI request differs from fixed hcitool interval6/CE-hints1 policy")
    if updates and updates[0]["record"] < request["record"]:
        raise ValueError("Parameters changed before our HCI command")
    statuses = [e for e in events if e["kind"] == "status" and e["record"] > request["record"]]
    # Command Status has no handle. Refuse an interleaved same-opcode command
    # instead of attributing another connection's status to this request.
    status_end = statuses[0]["record"] if statuses else float("inf")
    if any(e["kind"] == "request" and request["record"] < e["record"] < status_end for e in events):
        raise ValueError("Ambiguous interleaved LE Connection Update command status")
    if statuses and statuses[0]["status"]:
        raise ValueError("Controller rejected LE Connection Update")
    if not updates or not statuses:
        return None
    result = updates[0]
    if statuses[0]["record"] >= result["record"] or (
        result["status"],
        result["interval"],
        result["latency"],
        result["timeout"],
    ) != (0, 6, 0, baseline["timeout"]):
        raise ValueError("7.5 ms update not applied with unchanged latency/timeout")
    return result
