"""Synthetic monitor fixtures only; parameter parsing never accesses a device."""

import struct

import pytest
from test_hci_interval import HANDLE, LOCAL, addr, connection, event, record

from rcominote.experiments import hci_interval as H
from rcominote.experiments import param_window as P

LINK = {"peer": H.PEER, "local": LOCAL, "controller": "hci0", "handle": HANDLE}
CONTROL = (0, b"\0\0" + addr(LOCAL) + b"hci0\0\0\0\0")
STATUS = (3, event(0x0F, b"\0\x01\x13\x20"))


def capture(rows, *, conn=None):
    rows = [CONTROL, (3, connection() if conn is None else conn)] + rows
    return H.HEADER + b"".join(record(p, op, stamp=100 + i) for i, (op, p) in enumerate(rows))


def command(low=6, high=6, latency=0, timeout=500, *, ce=1, handle=HANDLE):
    return 2, b"\x13\x20\x0e" + struct.pack("<7H", handle, low, high, latency, timeout, ce, ce)


def update(interval=6, latency=0, timeout=500, *, status=0, handle=HANDLE):
    return 3, event(0x3E, b"\x03" + struct.pack("<B4H", status, handle, interval, latency, timeout))


def fragment(payload, *, direction="rx", boundary=2):
    return 5 if direction == "rx" else 4, struct.pack("<HH", HANDLE | boundary << 12, len(payload)) + payload


def signaling(code, identifier, payload, *, direction="rx"):
    body = struct.pack("<BBH", code, identifier, len(payload)) + payload
    return fragment(struct.pack("<HH", len(body), 5) + body, direction=direction)


def remote(low=6, high=12, latency=0, timeout=500, *, identifier=7):
    return [
        signaling(0x12, identifier, struct.pack("<4H", low, high, latency, timeout)),
        signaling(0x13, identifier, b"\0\0", direction="tx"),
        command(low, high, latency, timeout, ce=0),
        STATUS,
    ]


def inspect(rows, *, final=True):
    return P.inspect(capture(rows), link=LINK, final=final)


def test_remote_fast_host_normalization_and_pending_remote_slow_are_distinct():
    rows = remote() + [update(12), command(), STATUS, update()]
    rows += remote(32, 48, 4, 600, identifier=8)
    value = inspect(rows)
    assert [(t["origin"], t["update"]["interval"]) for t in value["transactions"]] == [
        ("remote", 12),
        ("host", 6),
    ]
    first, own = value["transactions"]
    assert first["remote_request"]["identifier"] == first["remote_accept"]["identifier"] == 7
    assert first["remote_request"]["records"] == [3]
    assert first["remote_request"]["timestamps_us"] == [102]
    assert own["remote_request"] is own["remote_accept"] is None
    assert len(value["pending"]) == 1
    pending = value["pending"][0]
    assert pending["stage"] == "awaiting-update" and pending["origin"] == "remote"
    assert (pending["request"]["min"], pending["request"]["max"]) == (32, 48)
    assert pending["update"] is None


@pytest.mark.parametrize(
    "count,stage",
    [(1, "awaiting-accept"), (2, "awaiting-command"), (3, "awaiting-status"), (4, "awaiting-update")],
)
def test_final_framing_can_preserve_a_logically_incomplete_transaction(count, stage):
    value = inspect(remote()[:count])
    assert value["transactions"] == [] and value["pending"][0]["stage"] == stage


@pytest.mark.parametrize("split", [1, 3, 5, 9])
def test_cross_record_acl_reassembly_preserves_original_record_stamps(split):
    request = remote()[0][1][4:]
    rows = [fragment(request[:split]), fragment(request[split:], boundary=1)] + remote()[1:] + [update(12)]
    value = inspect(rows)
    proof = value["transactions"][0]["remote_request"]
    assert proof["record"] == 4 and proof["timestamp_us"] == 103
    assert proof["records"] == [3, 4] and proof["timestamps_us"] == [102, 103]


def test_live_partial_record_and_acl_wait_but_final_requires_complete_framing():
    partial = fragment(remote()[0][1][4:9])
    value = inspect([partial], final=False)
    assert value["pending"][0]["kind"] == "acl-fragment"
    with pytest.raises(ValueError, match="Incomplete final owned ACL"):
        inspect([partial])
    raw = capture(remote()[:2])[:-1]
    value = P.inspect(raw, link=LINK)
    assert value["pending"][-1]["kind"] == "capture-tail" and value["records"] == 3
    with pytest.raises(ValueError, match="Incomplete final"):
        P.inspect(raw, link=LINK, final=True)
    assert P.inspect(H.HEADER[:8], link=LINK)["connection"] is None


@pytest.mark.parametrize(
    "fault",
    ["orphan", "overlap", "overflow", "length", "broadcast", "boundary", "signal-length", "identifier"],
)
def test_malformed_acl_and_signaling_fail_without_salvage(fault):
    packet = bytearray(remote()[0][1])
    rows = []
    if fault == "orphan":
        rows = [fragment(b"x", boundary=1)]
    elif fault == "overlap":
        rows = [fragment(packet[4:9]), remote()[0]]
    elif fault == "overflow":
        packet[4:6] = struct.pack("<H", 1)
    elif fault == "length":
        packet[2:4] = struct.pack("<H", 1)
    elif fault == "broadcast":
        packet[1] |= 0x40
    elif fault == "boundary":
        packet[1] |= 0x10
    elif fault == "signal-length":
        packet[10:12] = struct.pack("<H", 100)
    else:
        packet[9] = 0
    with pytest.raises(ValueError):
        inspect(rows or [(5, bytes(packet))])


@pytest.mark.parametrize(
    "fault",
    [
        "identifier",
        "reject",
        "duplicate",
        "direction",
        "length",
        "unmatched",
        "request-direction",
        "request-length",
    ],
)
def test_remote_request_and_acceptance_are_exact_and_unique(fault):
    rows = remote()
    if fault == "identifier":
        rows[1] = signaling(0x13, 8, b"\0\0", direction="tx")
    elif fault == "reject":
        rows[1] = signaling(0x13, 7, b"\x01\0", direction="tx")
    elif fault == "duplicate":
        rows.insert(2, rows[1])
    elif fault == "direction":
        rows[1] = signaling(0x13, 7, b"\0\0")
    elif fault == "length":
        rows[1] = signaling(0x13, 7, b"\0", direction="tx")
    elif fault == "unmatched":
        rows = rows[1:]
    elif fault == "request-direction":
        rows[0] = signaling(0x12, 7, struct.pack("<4H", 6, 12, 0, 500), direction="tx")
    else:
        rows[0] = signaling(0x12, 7, bytes(7))
    with pytest.raises(ValueError):
        inspect(rows)


@pytest.mark.parametrize(
    "fault",
    [
        "status",
        "update-status",
        "interval",
        "latency",
        "timeout",
        "unknown-update",
        "early-update",
        "duplicate-status",
        "duplicate-update",
        "wrong-command",
        "overlap",
        "global-overlap",
        "remote-overlap",
        "command-before-accept",
        "own-with-remote",
    ],
)
def test_parameter_transactions_cannot_be_misattributed_or_changed(fault):
    rows = [command(), STATUS, update()]
    if fault == "status":
        rows[1] = 3, event(0x0F, b"\x0c\x01\x13\x20")
    elif fault == "update-status":
        rows[2] = update(status=1)
    elif fault == "interval":
        rows[2] = update(12)
    elif fault == "latency":
        rows[2] = update(latency=1)
    elif fault == "timeout":
        rows[2] = update(timeout=600)
    elif fault == "unknown-update":
        rows = [update()]
    elif fault == "early-update":
        rows = [command(), update(), STATUS]
    elif fault == "duplicate-status":
        rows.insert(2, STATUS)
    elif fault == "duplicate-update":
        rows.append(update())
    elif fault == "wrong-command":
        rows[0] = command(6, 12, ce=0)
    elif fault == "overlap":
        rows.insert(2, command())
    elif fault == "global-overlap":
        rows.insert(1, command(handle=HANDLE + 1))
    elif fault == "remote-overlap":
        rows = remote()[:1] * 2
    elif fault == "command-before-accept":
        rows = [remote()[0], remote()[2], remote()[1]]
    else:
        rows = remote(6, 6)[:2] + [command()]
    with pytest.raises(ValueError):
        inspect(rows)


def test_foreign_command_status_is_not_mistaken_for_an_owned_command():
    rows = [command(handle=HANDLE + 1), STATUS, command(), STATUS, update()]
    value = inspect(rows)
    assert len(value["transactions"]) == 1 and value["transactions"][0]["request"]["record"] == 5
    with pytest.raises(ValueError, match="Unmatched global"):
        inspect([STATUS])
    with pytest.raises(ValueError, match="Command Status length"):
        inspect([command(), (3, event(0x0F, b"\0\x13\x20"))])


def test_remote_forwarding_requires_identical_parameters_not_only_same_handle():
    rows = remote()
    rows[2] = command(6, 12, timeout=600, ce=0)
    with pytest.raises(ValueError, match="differs from accepted"):
        inspect(rows)
    with pytest.raises(ValueError, match="CID5 signaling"):
        inspect([fragment(struct.pack("<HH", 0, 5))])


@pytest.mark.parametrize(
    "low,high,latency,timeout",
    [(5, 12, 0, 500), (12, 6, 0, 500), (6, 3201, 0, 500), (6, 12, 500, 500), (6, 12, 0, 9)],
)
def test_invalid_remote_parameter_fields_fail_before_any_acceptance(low, high, latency, timeout):
    with pytest.raises(ValueError, match="Invalid connection"):
        inspect(remote(low, high, latency, timeout)[:1])


@pytest.mark.parametrize(
    "fault",
    [
        "peer",
        "role",
        "address-type",
        "connect-status",
        "local",
        "reuse",
        "preconnect-acl",
        "postdisconnect-acl",
    ],
)
def test_owned_epoch_and_acl_boundaries_are_strict(fault):
    conn = bytearray(connection())
    link = LINK.copy()
    rows = []
    if fault == "peer":
        conn[8] ^= 1
    elif fault in ("role", "address-type", "connect-status"):
        conn[{"role": 6, "address-type": 7, "connect-status": 3}[fault]] = 1
    elif fault == "local":
        link["local"] = "00:00:00:00:00:00"
    elif fault == "reuse":
        rows = [(3, bytes(conn))]
    elif fault == "postdisconnect-acl":
        rows = [(3, event(5, b"\0" + struct.pack("<H", HANDLE) + b"\x13")), remote()[0]]
    raw = capture(rows, conn=bytes(conn))
    if fault == "preconnect-acl":
        op, packet = remote()[0]
        raw = H.HEADER + record(packet, op) + raw[16:]
    with pytest.raises(ValueError):
        P.inspect(raw, link=link, final=True)


def test_disconnect_record_is_retained_without_claiming_a_pending_update_completed():
    rows = remote(32, 48, 4, 600) + [(3, event(5, b"\0" + struct.pack("<H", HANDLE) + b"\x13"))]
    value = inspect(rows)
    assert len(value["disconnects"]) == 1 and value["transactions"] == []
    assert value["pending"][0]["stage"] == "awaiting-update"


@pytest.mark.parametrize("fault", ["drop", "length", "limit"])
def test_monitor_structural_guards_remain_active(fault, monkeypatch):
    raw = capture([])
    if fault == "drop":
        raw += record(b"x", 17, stamp=110, drops=1)
    elif fault == "length":
        raw += record(b"x", 17, stamp=110, original=2)
    else:
        monkeypatch.setattr(H, "LIMIT", len(raw) - 1)
    with pytest.raises(ValueError):
        P.inspect(raw, link=LINK, final=True)
