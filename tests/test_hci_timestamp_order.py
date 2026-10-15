"""Monitor queue order differs from timestamp order; causal gates remain strict."""

import struct

import pytest

from rcominote.experiments import hci_interval as H
from rcominote.experiments import hci_monitor as M

LOCAL = "AC:19:8E:26:2B:F8"
HANDLE = 2048
ACL = struct.pack("<HHHH", 0x2800, 5, 1, 4) + b"\x13"
CONTROLLER = b"\0\0" + bytes.fromhex("F82B268E19AC") + b"hci0\0\0\0\0"


def record(opcode, stamp, packet=ACL, *, controller=0, drops=0, original=None):
    return (
        struct.pack(
            ">IIIIQ",
            len(packet) if original is None else original,
            len(packet),
            controller << 16 | opcode,
            drops,
            stamp,
        )
        + packet
    )


def test_cross_class_inversion_preserves_order_stamps_and_capture_maximum():
    parser = M.Snoop()
    parser.feed(H.HEADER + record(0, 100, CONTROLLER) + record(5, 90) + record(5, 95), final=True)
    assert parser.records == 3 and parser.last_stamp == 100
    assert parser.events == [{"kind": "controller", "address": LOCAL, "record": 1, "timestamp_us": 100}]
    assert parser.timestamp_inversions == [
        {"previous_record": 1, "record": 2, "previous_flags": 0, "flags": 5, "delta_us": -10}
    ]
    assert not parser.buffer


def test_legacy_parser_still_rejects_known_ctrl_event_to_acl_rx_inversion():
    # Same classes/delta as real records162/163; payload deliberately synthetic.
    raw = H.HEADER + record(17, 1000, b"control event") + record(5, 900)
    with pytest.raises(ValueError, match="nonmonotonic"):
        H.Snoop().feed(raw, final=True)
    modern = M.Snoop()
    modern.feed(raw, final=True)
    assert modern.timestamp_inversions == [
        {"previous_record": 1, "record": 2, "previous_flags": 17, "flags": 5, "delta_us": -100}
    ]
    assert modern.last_stamp == 1000


def test_acl_tx_rx_and_controllers_have_independent_clocks():
    parser = M.Snoop()
    parser.feed(
        H.HEADER
        + record(4, 100)
        + record(5, 90)
        + record(4, 80, controller=1)
        + record(5, 70, controller=1)
        + record(4, 101)
        + record(5, 91),
        final=True,
    )
    assert parser.records == 6 and parser.last_stamp == 101
    assert [row["delta_us"] for row in parser.timestamp_inversions] == [-10, -10, -10, -10]


@pytest.mark.parametrize("opcode", [4, 5])
@pytest.mark.parametrize("controller", [0, 1])
def test_same_direction_acl_inversion_rejected_without_commit(opcode, controller):
    parser = M.Snoop()
    parser.feed(H.HEADER + record(opcode, 100, controller=controller))
    with pytest.raises(ValueError, match="directional ACL"):
        parser.feed(record(opcode, 99, controller=controller), final=True)
    assert parser.records == 1 and parser.last_stamp == 100
    assert parser.timestamp_inversions == []


@pytest.mark.parametrize("controller", [0, 1])
def test_gating_events_are_one_monotonic_stream_per_controller(controller):
    parser = M.Snoop()
    parser.feed(H.HEADER + record(0, 100, CONTROLLER, controller=controller))
    # Different monitor opcodes still share the gating-event stream.
    request = b"\x13\x20\x0e" + struct.pack("<7H", HANDLE, 6, 6, 0, 500, 1, 1)
    with pytest.raises(ValueError, match="gating-event"):
        parser.feed(record(2, 99, request, controller=controller), final=True)
    assert parser.records == 1 and parser.timestamp_inversions == []


def test_unrelated_event_timestamp_does_not_change_gating_clock():
    parser = M.Snoop()
    # Number Of Completed Packets is not decoded as a parameter/epoch gate.
    unrelated = b"\x13\x05\x01\x00\x08\x01\x00"
    parser.feed(
        H.HEADER
        + record(0, 100, CONTROLLER)
        + record(3, 80, unrelated)
        + record(0, 90, CONTROLLER, controller=1)
        + record(1, 101, b""),
        final=True,
    )
    assert [event["record"] for event in parser.events] == [1, 4]
    assert parser.last_stamp == 101
    assert len(parser.timestamp_inversions) == 1


def test_fragmented_payload_does_not_commit_clock_or_inversion_twice():
    parser = M.Snoop()
    parser.feed(H.HEADER + record(0, 100, CONTROLLER))
    raw = record(5, 90)
    parser.feed(raw[:-1])
    assert parser.records == 1 and parser.last_stamp == 100
    assert parser.timestamp_inversions == []
    assert (0, 5) not in parser._stream_stamps
    parser.feed(raw[-1:], final=True)
    assert parser.records == 2 and parser.last_stamp == 100
    assert len(parser.timestamp_inversions) == 1


@pytest.mark.parametrize("fault", ["drop", "length", "tail", "event", "bound"])
def test_structure_and_bounds_still_fail_before_record_commit(fault, monkeypatch):
    parser = M.Snoop()
    raw = record(5, 90)
    if fault == "drop":
        raw = record(5, 90, drops=1)
    elif fault == "length":
        raw = record(5, 90, original=len(ACL) + 1)
    elif fault == "tail":
        raw = raw[:-1]
    elif fault == "event":
        raw = record(3, 90, b"\x3e\xff\x03")
    else:
        monkeypatch.setattr(H, "LIMIT", len(H.HEADER + raw) - 1)
    with pytest.raises(ValueError):
        parser.feed(H.HEADER + raw, final=True)
    assert parser.records == parser.last_stamp == 0
    assert parser.events == parser.timestamp_inversions == []
    assert parser._stream_stamps == {}


def test_second_parameter_request_still_rejected_with_cross_class_inversion():
    connect = (
        b"\x3e\x13\x01\0"
        + struct.pack("<HBB", HANDLE, 0, 0)
        + bytes.fromhex(H.PEER.replace(":", ""))[::-1]
        + struct.pack("<HHHB", 36, 0, 500, 0)
    )
    request = b"\x13\x20\x0e" + struct.pack("<7H", HANDLE, 6, 6, 0, 500, 1, 1)
    status = b"\x0f\x04\0\x01\x13\x20"
    update = b"\x3e\x0a\x03" + struct.pack("<B4H", 0, HANDLE, 6, 0, 500)
    parser = M.Snoop()
    parser.feed(
        H.HEADER
        + record(0, 100, CONTROLLER)
        + record(3, 101, connect)
        + record(2, 102, request)
        + record(3, 103, status)
        + record(3, 104, update)
        + record(5, 103)
        + record(2, 105, request),
        final=True,
    )
    base = H.current(parser.events[:2], HANDLE, LOCAL)
    assert H.applied(parser.events[:-1], HANDLE, LOCAL, base, 102)["interval"] == 6
    with pytest.raises(ValueError, match="Second parameter"):
        H.applied(parser.events, HANDLE, LOCAL, base, 102)
    assert parser.timestamp_inversions[0]["delta_us"] == -1
