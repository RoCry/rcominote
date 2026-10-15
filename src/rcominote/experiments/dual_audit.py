"""Session GATT proof and real per-operation spans; never invent repeated discovery."""

import hashlib

from rcominote import protocol as P
from rcominote.experiments import dual_hci
from rcominote.experiments import dual_interval as condition
from rcominote.experiments import hci_interval as H
from rcominote.experiments import status_event as events
from rcominote.experiments.dual_client import ACTION_CHARS, ACTION_DESCRIPTOR, ACTION_SERVICE
from rcominote.experiments.hci_monitor import Snoop
from rcominote.experiments.sd_bridge import console_packet
from rcominote.linux_client import table_rows, uuid_string
from rcominote.log_capture import START, STOP
from rcominote.log_probe import NOTIFY, PREPARE, SERVICE, WRITE
from rcominote.log_stream import Stream


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def setup(session):
    trace = events.rows(session, 0, session["setup_end"])
    pending, chars, services, descriptors, enabled = None, {}, {}, {}, []
    action_queries = []
    peer_mtu = False
    local_mtu = False
    last_time = -1
    for row in trace:
        p = bytes.fromhex(row["hex"])
        stamp = row["monotonic_ns"]
        if not p or type(stamp) is not int or stamp < last_time:
            raise ValueError("Malformed/nonmonotonic ATT trace")
        last_time = stamp
        if row["direction"] == "tx":
            if p[0] == 3:  # Response to peer MTU exchange.
                if not peer_mtu or p != bytes.fromhex("03f700"):
                    raise ValueError("Unmatched peer MTU response")
                peer_mtu = False
                continue
            if p[0] == 2 and p != bytes.fromhex("02f700"):
                raise ValueError("Expected local MTU247")
            if pending is not None or p[0] not in (2, 4, 8, 16, 18):
                raise ValueError("Overlapping/unexpected setup ATT request")
            if p[0] == 18 and p not in (bytes.fromhex(v) for v in ("1219000100", "1225000100", "122b000100")):
                raise ValueError("Unexpected CCCD/command in setup")
            pending = p
        elif row["direction"] == "rx":
            if p[0] == 2:
                if peer_mtu or len(p) != 3 or not 247 <= int.from_bytes(p[1:], "little") <= 517:
                    raise ValueError("Unexpected peer MTU request")
                peer_mtu = True
                continue
            if pending is None:
                raise ValueError("Unsolicited setup response/notification")
            if p[0] == 1:
                if p != b"\x01" + pending[:3] + b"\x0a" or pending[0] not in (4, 8, 16):
                    raise ValueError("Unexpected setup ATT error")
            elif p[0] != pending[0] + 1:
                raise ValueError("Mismatched setup ATT response")
            elif p[0] == 3:
                if local_mtu or len(p) != 3 or not 247 <= int.from_bytes(p[1:], "little") <= 517:
                    raise ValueError("Expected negotiated MTU247")
                local_mtu = True
            elif p[0] == 0x13:
                if p != b"\x13":
                    raise ValueError("Malformed CCCD response")
                enabled.append(pending.hex())
            elif p[0] == 0x11:
                for value in table_rows(p, (6, 20)):
                    services[uuid_string(value[4:])] = (
                        int.from_bytes(value[:2], "little"),
                        int.from_bytes(value[2:4], "little"),
                    )
            elif p[0] == 9:
                for value in table_rows(p, (7, 21)):
                    key = uuid_string(value[5:])
                    if key in chars:
                        raise ValueError("Duplicate session characteristic")
                    chars[key] = (
                        int.from_bytes(value[:2], "little"),
                        value[2],
                        int.from_bytes(value[3:5], "little"),
                    )
            elif p[0] == 5:
                if p[1] != 1:
                    raise ValueError("Unexpected descriptor format")
                for value in table_rows(bytes((5, 4)) + p[2:], (4,)):
                    descriptors[int.from_bytes(value[:2], "little")] = value[2:].hex()
            if pending in (bytes.fromhex(v) for v in ("10140019000028", "08140019000328", "0419001900")):
                action_queries.append(p)
            pending = None
        else:
            raise ValueError("Invalid ATT trace direction")
    expected = {
        WRITE: (21, 12, 22),
        NOTIFY: (23, 16, 24),
        P.WRITE: (33, 4, 34),
        P.NOTIFY_CMD: (35, 16, 36),
        P.NOTIFY_REALTIME: (38, 16, 39),
        P.NOTIFY_OFFLINE: (41, 16, 42),
    }
    if (
        pending is not None
        or peer_mtu
        or not local_mtu
        or services.get(SERVICE) != (20, 25)
        or services.get(P.SERVICE) != (32, 43)
        or chars != expected
        or any(descriptors.get(h) != "0229" for h in (25, 37, 40, 43))
        or sorted(enabled) != sorted(("1219000100", "1225000100", "122b000100"))
        or action_queries != [ACTION_SERVICE, ACTION_CHARS, ACTION_DESCRIPTOR]
    ):
        raise ValueError("Incomplete fixed session GATT/CCCD evidence")
    return {
        "actions_write": 22,
        "actions_notify": 24,
        "boyi_write": 34,
        "boyi_command": 36,
        "boyi_offline": 42,
        "setup_end": session["setup_end"],
    }


def actions(session, operation):
    return action_frames(
        session,
        operation,
        expected=[
            PREPARE,
            START,
            console_packet(operation["producer"]),
            console_packet(operation["dump_command"]),
            STOP,
        ],
    )


def action_frames(session, operation, *, expected: list[bytes]):
    """Exact original frames, including bounded background F0; caller fixes the recipe."""
    if not expected or any(not isinstance(packet, bytes) or not packet for packet in expected):
        raise ValueError("Actions audit requires explicit nonempty byte packets")
    if setup(session) != session["gatt_proof"]:
        raise ValueError("Session GATT proof changed")
    start, end = operation["actions_start"], operation["actions_end"]
    if not session["setup_end"] <= start < end <= len(session["att_packets"]):
        raise ValueError("Invalid real Actions trace span")
    writes, notifications, awaiting = [], [], False
    stream = Stream()
    for row in events.rows(session, start, end):
        p = bytes.fromhex(row["hex"])
        if row["direction"] == "tx":
            if awaiting or len(writes) >= len(expected) or p != b"\x12\x16\0" + expected[len(writes)]:
                raise ValueError("Operation contains an unexpected/overlapping ATT write")
            writes.append(p[3:])
            awaiting = True
        elif row["direction"] == "rx" and p == b"\x13" and awaiting:
            awaiting = False
        elif row["direction"] == "rx" and p[:3] == b"\x1b\x18\0":
            if stream.ended:
                raise ValueError("Late Actions bytes after F1")
            notifications.append(p[3:].hex())
            stream.feed(p[3:])
            if stream.acks > len(writes) or (stream.ended and len(writes) != len(expected)):
                raise ValueError("Operation ACK/end precedes exact write")
        else:
            raise ValueError("Unexpected traffic inside exclusive Actions operation")
    if (
        awaiting
        or writes != expected
        or stream.pending
        or stream.acks != len(expected)
        or not stream.ended
        or sum(f["command"] == 0xF1 for f in stream.frames) != 1
        or notifications != operation["notifications"]
        or stream.frames != operation["frames"]
        or operation["writes"] != [{"hex": p.hex(), "att_write_confirmed": True} for p in expected]
        or operation.get("log_session_complete") is not True
        or operation.get("cleanup_error")
    ):
        raise ValueError("Incomplete or inconsistent operation Actions evidence")
    return {"acks": len(expected), "end": True, "pending_bytes": 0, "trace_span": [start, end]}


def hci(session, operation, raw):
    parser = Snoop()
    parser.feed(raw, final=True)
    if session["hci_capture"] != {"bytes": len(raw), "sha256": sha(raw), "records": parser.records}:
        raise ValueError("Session HCI bytes/summary changed")
    exit_code = session.get("monitor_exit")
    if exit_code not in (0, 124, 137, 130) or (
        exit_code == 130
        and session.get("monitor_stop") != {"signal": "SIGINT", "requested": True, "delivery": "sent"}
    ):
        raise ValueError("Capture process exit lacks a valid bounded stop receipt")
    transport = session["transport"]
    link = transport["link"]
    if link["peer"] != H.PEER or link["controller"] != "hci0":
        raise ValueError("Wrong session HCI peer/controller")
    requested = transport["update_requested_us"]
    before = [e for e in parser.events if e["timestamp_us"] < requested]
    baseline = H.current(before, link["handle"], link["local"])
    early = condition.is_early(session)
    if early and transport.get("policy") != condition.POLICY:
        raise ValueError("Early experiment transport policy changed")
    if early and condition.baseline(before, link) != baseline:
        raise ValueError("Early baseline differs from its complete owned epoch")
    if (
        baseline != transport["baseline"]
        or (not early and baseline["latency"] != 0)
        or not 6 < baseline["interval"] <= 3200
    ):
        raise ValueError("Baseline differs from actual HCI state")
    stamps = dual_hci.timeline(session, raw)
    # First Actions precedes the update; every subsequent Actions packet must
    # itself fall inside the applied window, not merely a claimed host timestamp.
    first = session["operations"][0] is operation or operation["phase"] == "boot"
    start = operation["download_start"] if first and not early else operation["actions_start"]
    if first and early:
        start = session["before_span"][0]
    last = operation["verified_end"]
    if not 0 <= start < last <= len(stamps):
        raise ValueError("Invalid HCI-bound operation/barrier span")
    # Host parser completion can postdate the final captured RX record. Use
    # the bound wire requests/responses, never require a fictitious later record.
    begin, end = min(stamps[start:last]), max(stamps[start:last])
    if not transport["update_requested_us"] <= begin <= end <= parser.last_stamp:
        raise ValueError("HCI capture does not span complete operation")
    for cutoff in (begin, end):
        events = [e for e in parser.events if e["timestamp_us"] <= cutoff]
        result = condition.applied(events, transport)
        if result is None or result != transport["applied"]:
            raise ValueError("Operation did not retain actual interval6 condition")
    requests = [
        e
        for e in parser.events
        if e["kind"] == "request" and e["handle"] == link["handle"] and requested <= e["timestamp_us"] <= end
    ]
    if requests != [transport["actual_hci_request"]]:
        raise ValueError("Actual per-link HCI request differs from receipt")
    return {
        "verified": True,
        "interval": 6,
        "latency": 0,
        "timeout": 500 if early else transport["baseline"]["timeout"],
        "wire_start_us": begin,
        "wire_end_us": end,
    }


def download(session, operation, data, *, minimum_start=None):
    """Rebuild exact sole Boyi file transaction from actual socket RX/TX rows."""
    import struct

    start, end = operation["download_start"], operation["download_end"]
    boundary = operation["actions_end"] if minimum_start is None else minimum_start
    if not boundary <= start < end <= len(session["att_packets"]):
        raise ValueError("Invalid real Boyi download trace span")
    request = P.frame(P.GET_FILE_DATA, operation["name"].encode().ljust(14, b"\0") + bytes(4))
    sent = declared = ended = False
    received = bytearray()
    for row in events.rows(session, start, end):
        p = bytes.fromhex(row["hex"])
        if row["direction"] == "tx":
            if sent or p != b"\x52\x22\0" + request:
                raise ValueError("Unexpected Boyi download command")
            sent = True
        elif row["direction"] == "rx" and p[:3] == b"\x1b\x2a\0":
            if not declared or ended or len(received) + len(p[3:]) > 4096:
                raise ValueError("Offline bytes outside declared transaction/overflow")
            received.extend(p[3:])
        elif row["direction"] == "rx" and p[:3] == b"\x1b\x24\0":
            command, payload = P.parse(p[3:])
            if not sent or command != P.GET_FILE_DATA or ended:
                raise ValueError("Unrelated/late Boyi response")
            if payload == b"\0" + struct.pack(">I", 4096) and not declared:
                declared = True
            elif payload == b"\x02" and declared and len(received) == 4096:
                ended = True
            else:
                raise ValueError("Boyi declaration/end differs from fixed4096")
        else:
            raise ValueError("Unexpected traffic inside exclusive Boyi download")
    if not ended or bytes(received) != data:
        raise ValueError("Retained data differs from complete actual Boyi notifications")
    return {"bytes": 4096, "declared": True, "end": True, "sha256": sha(data), "trace_span": [start, end]}


def identity(session, owner, key):
    start, end = owner[f"{key}_span"]
    if not session["setup_end"] <= start < end <= len(session["att_packets"]):
        raise ValueError("Invalid identity trace span")
    rows = events.rows(session, start, end)
    if len(rows) != 6:
        raise ValueError("Identity requires exactly three request/reply pairs")
    payloads = []
    for index, command in enumerate((P.GET_SERIAL, P.GET_BIND_INFO, P.GET_DEVICE_INFO)):
        tx, rx = rows[index * 2 : index * 2 + 2]
        p = bytes.fromhex(rx["hex"])
        if tx["direction"] != "tx" or bytes.fromhex(tx["hex"]) != b"\x52\x22\0" + P.frame(command):
            raise ValueError("Identity request differs from fixed read-only command")
        if rx["direction"] != "rx" or p[:3] != b"\x1b\x24\0":
            raise ValueError("Identity response differs from Boyi command handle")
        actual, payload = P.parse(p[3:])
        if actual != command:
            raise ValueError("Identity reply command mismatch")
        payloads.append(payload)
    if len(payloads[2]) != 52:
        raise ValueError("Identity lacks complete52-byte device info")
    value = {
        "serial": P.text(payloads[0]),
        "bound": any(payloads[1]),
        "device": P.parse_device_info(payloads[2]),
    }
    if value != owner[key]:
        raise ValueError("Identity summary differs from actual ATT response bytes")
    return {"verified": True, "trace_span": [start, end]}
