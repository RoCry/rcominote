"""Independent HCI byte fixtures, epoch ownership and parameter gating."""

import copy
import struct

import pytest

from rcominote.experiments import hci_interval as H

LOCAL = "AC:19:8E:26:2B:F8"
HANDLE = 2048


def addr(value):
    return bytes.fromhex(value.replace(":", ""))[::-1]


def event(code, body):
    return bytes((code, len(body))) + body


def record(packet, opcode=3, *, index=0, stamp=100, drops=0, original=None):
    return (
        struct.pack(
            ">IIIIQ",
            len(packet) if original is None else original,
            len(packet),
            index << 16 | opcode,
            drops,
            stamp,
        )
        + packet
    )


def connection(*, enhanced=True, peer=H.PEER, handle=HANDLE):
    body = b"\0" + struct.pack("<HBB", handle, 0, 0) + addr(peer)
    if enhanced:
        body += bytes(12)
    body += struct.pack("<HHHB", 12, 0, 500, 0)
    return event(0x3E, bytes((10 if enhanced else 1,)) + body)


def update(interval=6, latency=0, timeout=500, status=0, handle=HANDLE):
    return event(0x3E, b"\x03" + struct.pack("<B4H", status, handle, interval, latency, timeout))


def request(handle=HANDLE, ce=1):
    return b"\x13\x20\x0e" + struct.pack("<7H", handle, 6, 6, 0, 500, ce, ce)


def packets():
    return [
        (0, b"\0\0" + addr(LOCAL) + b"hci0\0\0\0\0"),
        (3, connection()),
        (2, request()),
        (3, event(0x0F, b"\0\x01\x13\x20")),
        (3, update()),
    ]


def parsed():
    parser = H.Snoop()
    parser.feed(
        H.HEADER + b"".join(record(p, op, stamp=100 + i) for i, (op, p) in enumerate(packets())), final=True
    )
    return parser.events


def test_fragmented_stream_and_both_connection_event_layouts():
    raw = H.HEADER + b"".join(record(p, op, stamp=100 + i) for i, (op, p) in enumerate(packets()))
    parser = H.Snoop()
    for byte in raw:
        parser.feed(bytes([byte]))
    parser.feed(b"", final=True)
    assert parser.events == parsed()
    for enhanced in (True, False):
        c = H.decode(3, connection(enhanced=enhanced))
        assert (c["address"], c["interval"], c["latency"], c["timeout"]) == (H.PEER, 12, 0, 500)


@pytest.mark.parametrize("fault", ["header", "tail", "drop", "truncated", "length", "backwards"])
def test_bad_capture_never_becomes_applied(fault):
    p = packets()[0][1]
    raw = H.HEADER + record(p, 0)
    if fault == "header":
        raw = b"x" + raw[1:]
    elif fault == "tail":
        raw = raw[:-1]
    elif fault == "drop":
        raw = H.HEADER + record(p, 0, drops=1)
    elif fault == "truncated":
        raw = H.HEADER + record(p, 0, original=len(p) + 1)
    elif fault == "length":
        raw += record(b"\x3e\xff\x03", stamp=101)
    else:
        raw += record(p, 0, stamp=99)
    with pytest.raises(ValueError):
        H.Snoop().feed(raw, final=True)


def test_other_controller_cannot_supply_owned_connection():
    parser = H.Snoop()
    parser.feed(H.HEADER + record(packets()[0][1], 0) + record(connection(), index=1, stamp=101), final=True)
    with pytest.raises(ValueError, match="fresh connection"):
        H.current(parser.events, HANDLE, LOCAL)


def test_gate_requires_command_status_and_actual_update_not_just_command_exit():
    events = parsed()
    base = H.current(events[:2], HANDLE, LOCAL)
    for count in (2, 3, 4):
        assert H.applied(events[:count], HANDLE, LOCAL, base, 102) is None
    assert H.applied(events, HANDLE, LOCAL, base, 102) == events[-1]


@pytest.mark.parametrize(
    "fault",
    [
        "peer",
        "role",
        "address-type",
        "local",
        "reuse",
        "disconnect",
        "request-timeout",
        "ce",
        "interval",
        "latency",
        "timeout",
        "status",
        "update-status",
        "second-request",
        "second-update",
        "race",
    ],
)
def test_wrong_epoch_or_changed_parameters_reject(fault):
    events = parsed()
    base = copy.deepcopy(events[1])
    local = LOCAL
    if fault in ("peer", "role", "address-type"):
        key, value = {
            "peer": ("address", "00:00:00:00:00:01"),
            "role": ("role", 1),
            "address-type": ("address_type", 1),
        }[fault]
        events[1][key] = value
    elif fault == "local":
        local = "00:00:00:00:00:01"
    elif fault in ("reuse", "second-request", "second-update"):
        source = {"reuse": 1, "second-request": 2, "second-update": 4}[fault]
        events.append(events[source] | {"record": 6, "timestamp_us": 105})
    elif fault == "disconnect":
        events.append({"kind": "disconnect", "handle": HANDLE, "status": 0, "record": 6, "timestamp_us": 105})
    elif fault == "request-timeout":
        events[2]["timeout"] = 400
    elif fault == "ce":
        events[2]["min_length"] = 0
    elif fault in ("interval", "latency", "timeout", "update-status"):
        events[4]["status" if fault == "update-status" else fault] = {
            "interval": 12,
            "latency": 4,
            "timeout": 400,
            "update-status": 1,
        }[fault]
    elif fault == "status":
        events[3]["status"] = 0x0C
    else:
        events[4]["record"] = 2
    with pytest.raises((ValueError, ConnectionError)):
        H.applied(events, HANDLE, local, base, 102)


def test_current_parameters_include_last_successful_natural_update():
    events = parsed()[:2]
    events.append({**events[1], "kind": "update", "record": 3, "interval": 36, "timeout": 600})
    assert H.current(events, HANDLE, LOCAL)["timeout"] == 600


def test_same_opcode_other_handle_cannot_supply_command_status():
    events = parsed()
    events.insert(3, events[2] | {"handle": HANDLE + 1, "record": 3.5})
    with pytest.raises(ValueError, match="Ambiguous"):
        H.applied(events, HANDLE, LOCAL, events[1], 102)


def test_controller_removal_rejects_epoch():
    events = parsed() + [{**H.decode(1, b""), "record": 6, "timestamp_us": 105}]
    with pytest.raises(ValueError, match="removed"):
        H.current(events, HANDLE, LOCAL)
