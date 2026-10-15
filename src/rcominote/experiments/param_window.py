"""Offline owned-epoch parameter transactions; no device operations or repairs.

Preserve monitor record order/timestamps. CID5 accepted requests explain remote
HCI updates; unassociated host normalization is only6/6/0/500 with CE hints1/1.
Final input needs complete framing, not necessarily a completed last update.
"""

import struct

from rcominote.experiments import hci_interval as H
from rcominote.experiments.hci_monitor import Snoop

PARAMETERS = ("min", "max", "latency", "timeout")
HOST = (6, 6, 0, 500, 1, 1)


def parameters(value: dict) -> tuple[int, ...]:
    return tuple(value[key] for key in PARAMETERS)


def validate_parameters(value: dict) -> None:
    low, high, latency, timeout = parameters(value)
    if not (6 <= low <= high <= 3200 and 0 <= latency <= 499 and 10 <= timeout <= 3200):
        raise ValueError("Invalid connection parameter request range/latency/timeout")


def records(raw: bytes, count: int):
    offset = 16
    for number in range(1, count + 1):
        _, size, flags, _, stamp = struct.unpack_from(">IIIIQ", raw, offset)
        yield number, flags, stamp, raw[offset + 24 : offset + 24 + size]
        offset += 24 + size


class ACL:
    def __init__(self, handle: int, start: int, end: int | None):
        self.handle, self.start, self.end = handle, start, end
        self.pending: dict[str, dict] = {}

    def feed(self, number: int, opcode: int, stamp: int, packet: bytes) -> list[dict]:
        if len(packet) < 4:
            raise ValueError("Truncated ACL header")
        word, length = struct.unpack_from("<HH", packet)
        if len(packet) != length + 4:
            raise ValueError("ACL length differs from complete monitor record")
        if word & 0xFFF != self.handle:
            return []
        if number <= self.start or (self.end is not None and number >= self.end):
            raise ValueError("Owned ACL outside the sole connection epoch")
        boundary = word >> 12 & 3
        if word >> 14 or boundary == 3:
            raise ValueError("Unsupported owned ACL broadcast/boundary flags")
        direction = "tx" if opcode == 4 else "rx"
        if boundary in (0, 2):
            if direction in self.pending:
                raise ValueError("Overlapping owned L2CAP packets")
            self.pending[direction] = {"raw": bytearray(), "records": [], "timestamps_us": []}
        elif direction not in self.pending:
            raise ValueError("Orphan owned ACL continuation")
        state = self.pending[direction]
        state["raw"].extend(packet[4:])
        state["records"].append(number)
        state["timestamps_us"].append(stamp)
        body = state["raw"]
        if len(body) < 4:
            return []
        size, cid = struct.unpack_from("<HH", body)
        if len(body) > size + 4:
            raise ValueError("Owned L2CAP reassembly overflow")
        if len(body) < size + 4:
            return []
        del self.pending[direction]
        if cid != 5:
            return []
        if size < 4:
            raise ValueError("Empty or truncated CID5 signaling command")
        result, offset = [], 4
        while offset < len(body):
            if len(body) - offset < 4:
                raise ValueError("Truncated CID5 signaling header")
            code, identifier, length = struct.unpack_from("<BBH", body, offset)
            offset += 4
            if identifier == 0 or offset + length > len(body):
                raise ValueError("Invalid CID5 identifier or signaling length")
            payload = bytes(body[offset : offset + length])
            offset += length
            if code not in (0x12, 0x13):
                continue
            value = {
                "kind": "remote-request" if code == 0x12 else "remote-accept",
                "identifier": identifier,
                "record": number,
                "timestamp_us": stamp,
                "records": state["records"].copy(),
                "timestamps_us": state["timestamps_us"].copy(),
                "direction": direction,
            }
            if code == 0x12:
                if direction != "rx" or len(payload) != 8:
                    raise ValueError("Remote parameter request requires RX and exact8 bytes")
                value.update(zip(PARAMETERS, struct.unpack("<4H", payload), strict=True))
                validate_parameters(value)
            else:
                if direction != "tx" or payload != b"\0\0":
                    raise ValueError("Remote parameter acceptance requires TX and exact success0")
                value["result"] = 0
            result.append(value)
        return result


class Transactions:
    def __init__(self, handle: int):
        self.handle = handle
        self.completed: list[dict] = []
        self.active: dict | None = None
        self.awaiting_status: dict | None = None

    def signal(self, value: dict) -> None:
        if value["kind"] == "remote-request":
            if self.active is not None:
                raise ValueError("Two overlapping owned parameter transactions")
            self.active = {
                "request": None,
                "status": None,
                "update": None,
                "origin": "remote",
                "remote_request": value,
                "remote_accept": None,
            }
        elif (
            self.active is None
            or self.active["remote_request"] is None
            or self.active["remote_accept"] is not None
            or self.active["remote_request"]["identifier"] != value["identifier"]
        ):
            raise ValueError("Unmatched or duplicate remote parameter acceptance")
        else:
            self.active["remote_accept"] = value

    def event(self, value: dict) -> None:
        match value["kind"]:
            case "request":
                if self.awaiting_status is not None:
                    raise ValueError("Ambiguous overlapping global HCI command statuses")
                validate_parameters(value)
                if value["handle"] != self.handle:
                    self.awaiting_status = {"request": value, "status": None, "origin": "other-connection"}
                    return
                own = parameters(value) + (value["min_length"], value["max_length"]) == HOST
                if self.active is None:
                    if not own:
                        raise ValueError("Unassociated host command differs from fixed normalization")
                    self.active = {
                        "request": value,
                        "status": None,
                        "update": None,
                        "origin": "host",
                        "remote_request": None,
                        "remote_accept": None,
                    }
                elif (
                    self.active["request"] is not None
                    or self.active["remote_accept"] is None
                    or own
                    or parameters(value) != parameters(self.active["remote_request"])
                ):
                    raise ValueError("Owned HCI command overlaps or differs from accepted remote request")
                else:
                    self.active["request"] = value
                self.awaiting_status = self.active
            case "status":
                if self.awaiting_status is None:
                    raise ValueError("Unmatched global LE Connection Update Command Status")
                if value["status"]:
                    raise ValueError("Controller rejected LE Connection Update command")
                self.awaiting_status["status"] = value
                self.awaiting_status = None
            case "update" if value["handle"] == self.handle:
                if self.active is None or self.active["request"] is None or self.active["status"] is None:
                    raise ValueError("Unknown or premature owned Connection Update Complete")
                request = self.active["request"]
                if value["status"] or not (
                    request["min"] <= value["interval"] <= request["max"]
                    and value["latency"] == request["latency"]
                    and value["timeout"] == request["timeout"]
                ):
                    raise ValueError("Owned update failed or differs from requested parameters")
                self.active["update"] = value
                self.completed.append(self.active)
                self.active = None

    def pending(self) -> list[dict]:
        result = []
        if self.active is not None:
            stage = (
                "awaiting-accept"
                if self.active["origin"] == "remote" and self.active["remote_accept"] is None
                else "awaiting-command"
                if self.active["request"] is None
                else "awaiting-status"
                if self.active["status"] is None
                else "awaiting-update"
            )
            result.append(self.active | {"stage": stage})
        if self.awaiting_status is not None and self.awaiting_status is not self.active:
            result.append(self.awaiting_status | {"stage": "awaiting-status"})
        return result


def inspect(raw: bytes, *, link: dict, final: bool = False) -> dict:
    if not isinstance(raw, bytes) or (
        link.get("peer") != H.PEER
        or link.get("controller") != "hci0"
        or type(link.get("handle")) is not int
        or not 0 <= link["handle"] < 0xF00
    ):
        raise ValueError("Requires bytes and fixed owned hci0 peer/handle")
    parser = Snoop()
    parser.feed(raw, final=final)
    events = parser.events
    if any(e["kind"] == "controller-removed" for e in events):
        raise ValueError("Owned controller was removed")
    controllers = [e for e in events if e["kind"] == "controller"]
    if any(e["address"] != link.get("local") for e in controllers):
        raise ValueError("Captured controller differs from active local socket")
    connects = [e for e in events if e["kind"] == "connect" and e["handle"] == link["handle"]]
    if len(connects) > 1:
        raise ValueError("Owned handle reused; requires one connection epoch")
    connection = connects[0] if connects else None
    if connection is not None and (
        not controllers
        or (connection["status"], connection["role"], connection["address_type"], connection["address"])
        != (0, 0, 0, H.PEER)
    ):
        raise ValueError("Connection is not the owned public peer in central role")
    if final and connection is None:
        raise ValueError("Final capture lacks owned connection epoch")
    disconnects = [e for e in events if e["kind"] == "disconnect" and e["handle"] == link["handle"]]
    if len(disconnects) > 1 or any(
        e["status"] or connection is None or e["record"] <= connection["record"] for e in disconnects
    ):
        raise ValueError("Invalid owned disconnect/epoch order")
    acl = ACL(
        link["handle"],
        connection["record"] if connection else parser.records + 1,
        disconnects[0]["record"] if disconnects else None,
    )
    transactions = Transactions(link["handle"])
    by_record = {e["record"]: e for e in events}
    for number, flags, stamp, packet in records(raw, parser.records):
        if flags >> 16:
            continue
        if flags & 0xFFFF == 3 and packet[:1] == b"\x0f" and len(packet) != 6:
            raise ValueError("Malformed HCI Command Status length")
        if flags & 0xFFFF in (4, 5):
            for value in acl.feed(number, flags & 0xFFFF, stamp, packet):
                transactions.signal(value)
        if (value := by_record.get(number)) is not None:
            if (
                value["kind"] in ("request", "update")
                and value["handle"] == link["handle"]
                and (
                    connection is None
                    or number <= connection["record"]
                    or (disconnects and number >= disconnects[0]["record"])
                )
            ):
                raise ValueError("Owned HCI transaction outside connection epoch")
            transactions.event(value)
    if final and acl.pending:
        raise ValueError("Incomplete final owned ACL/L2CAP packet")
    pending = transactions.pending()
    for direction, value in acl.pending.items():
        pending.append(
            {
                "kind": "acl-fragment",
                "direction": direction,
                "records": value["records"],
                "timestamps_us": value["timestamps_us"],
                "bytes": len(value["raw"]),
            }
        )
    if parser.buffer:
        pending.append({"kind": "capture-tail", "bytes": len(parser.buffer)})
    return {
        "transactions": transactions.completed,
        "pending": pending,
        "connection": connection,
        "disconnects": disconnects,
        "records": parser.records,
        "last_stamp": parser.last_stamp,
        "timestamp_inversions": parser.timestamp_inversions,
    }
