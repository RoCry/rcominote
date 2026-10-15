"""Explicit status policy and real-index transaction parsing, all offline."""

import copy
import struct

import pytest
from test_dual_probe import operation, session_operation, setup
from test_sd_nor_probe import info

from rcominote import protocol as P
from rcominote.experiments import dual_audit as A
from rcominote.experiments import status_event as E
from rcominote.experiments import window_ram_audit as W

PAYLOAD = bytes.fromhex("026401010009ffff030001000000000000000000")


def row(payload=PAYLOAD, *, command=15, handle=36, direction="rx"):
    return {
        "direction": direction,
        "hex": (b"\x1b" + struct.pack("<H", handle) + P.frame(command, payload)).hex(),
    }


def enable(report):
    report.update(status_event_policy=E.POLICY, expected_before=info())
    E.init(report)
    return report


def observe_all(report):
    for i, value in enumerate(report["att_packets"]):
        E.observe(report, i, value)


def test_event_ledger_original_index_and_exact_fields():
    report = enable({"att_packets": [row()]})
    original = copy.deepcopy(report["att_packets"])
    event = E.observe(report, 0, report["att_packets"][0])
    assert event == {
        "index": 0,
        "frame_hex": P.frame(15, PAYLOAD).hex(),
        "payload_hex": PAYLOAD.hex(),
        "fields": P.parse_event(15, PAYLOAD),
    }
    assert E.verify(report) == ({0}, {"policy": E.POLICY, "events": 1, "indices": [0]})
    assert E.rows(report, 0, 1) == []
    E.bridge(report, 0, 1)
    with pytest.raises(ValueError, match="no actual"):
        E.edge(report, 0, 1)
    assert report["att_packets"] == original


def test_default_does_not_divert_events_or_create_fields():
    report = {"att_packets": [row()]}
    original = copy.deepcopy(report)
    E.init(report)
    assert E.observe(report, 0, report["att_packets"][0]) is None
    assert E.rows(report, 0, 1) == report["att_packets"]
    assert E.edge(report, 0, 1) == (0, 0)
    assert E.verify(report) == (set(), {"enabled": False, "events": 0, "indices": []})
    with pytest.raises(ValueError):
        E.bridge(report, 0, 1)
    assert report == original


@pytest.mark.parametrize("policy", [None, True, 1, "", E.POLICY + "-other"])
def test_unknown_policy_is_never_implicitly_enabled(policy):
    report = {"att_packets": [], "status_event_policy": policy}
    with pytest.raises(ValueError, match="Unknown"):
        E.init(report)
    with pytest.raises(ValueError, match="Unknown"):
        E.rows(report, 0, 0)


@pytest.mark.parametrize("fault", ["missing", "serial", "short", "summary", "busy", "voice"])
def test_policy_requires_complete_owned_idle_expected_state(fault):
    state = info()
    match fault:
        case "missing":
            state = None
        case "serial":
            state["serial"] = "other"
        case "short":
            state["device"]["raw"] = state["device"]["raw"][:-2]
        case "summary":
            state["device"]["battery"] = 99
        case "busy" | "voice":
            raw = bytearray.fromhex(state["device"]["raw"])
            raw[10 if fault == "busy" else 40] = 1
            state["device"] = P.parse_device_info(bytes(raw))
    with pytest.raises((ValueError, TypeError, RuntimeError)):
        E.init({"att_packets": [], "status_event_policy": E.POLICY, "expected_before": state})


@pytest.mark.parametrize("at", range(20))
def test_each_changed_payload_byte_fails_including_raw_charging(at):
    payload = bytearray(PAYLOAD)
    payload[at] ^= 1
    report = enable({"att_packets": [row(bytes(payload))]})
    with pytest.raises(ValueError, match="Status20"):
        E.observe(report, 0, report["att_packets"][0])
    with pytest.raises(ValueError):
        E.rows(report, 0, 1)


@pytest.mark.parametrize("payload", [PAYLOAD[:-1], PAYLOAD + b"\0"])
def test_short_or_extended_payload_fails(payload):
    report = enable({"att_packets": [row(payload)]})
    with pytest.raises(ValueError):
        E.observe(report, 0, report["att_packets"][0])


def test_wrong_crc_fails_without_being_hidden():
    value = row()
    value["hex"] = value["hex"][:-2] + "ff"
    report = enable({"att_packets": [value]})
    with pytest.raises(ValueError, match="CRC"):
        E.observe(report, 0, value)


@pytest.mark.parametrize("kwargs", [{"handle": 24}, {"handle": 42}, {"direction": "tx"}, {"command": 25}])
def test_other_channel_direction_or_opcode_is_not_an_allowlisted_event(kwargs):
    report = enable({"att_packets": [row(**kwargs)]})
    assert E.observe(report, 0, report["att_packets"][0]) is None
    assert E.indices(report, 0, 1) == [0]
    with pytest.raises(ValueError):
        E.bridge(report, 0, 1)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "fake", "field", "index", "reversed"])
def test_ledger_must_exactly_equal_every_actual_event(fault):
    report = enable({"att_packets": [row(), row()]})
    observe_all(report)
    match fault:
        case "missing":
            report["status_events"].pop()
        case "duplicate":
            report["status_events"].append(copy.deepcopy(report["status_events"][0]))
        case "fake":
            report["att_packets"][0] = row(command=5)
        case "field":
            report["status_events"][0]["fields"]["usb_connected"] = False
        case "index":
            report["status_events"][0]["index"] = 1
        case "reversed":
            report["status_events"].reverse()
    with pytest.raises(ValueError, match="ledger"):
        E.verify(report)


def test_max8_and_duplicate_observation_fail_without_overwriting_ledger():
    report = enable({"att_packets": [row() for _ in range(9)]})
    for i in range(8):
        E.observe(report, i, report["att_packets"][i])
    assert len(report["status_events"]) == 8
    for i in (7, 8):
        with pytest.raises(ValueError):
            E.observe(report, i, report["att_packets"][i])
    with pytest.raises(ValueError, match="bound"):
        E.verify(report)
    with pytest.raises(ValueError, match="overwrite"):
        E.init(report)
    del report["att_packets"][-1]
    assert E.verify(report)[0] == set(range(8))


@pytest.mark.parametrize("start,end", [(False, 1), (-1, 1), (1, 0), (0, 2)])
def test_invalid_indices_rejected(start, end):
    with pytest.raises(ValueError):
        E.rows(enable({"att_packets": [row()]}), start, end)


def test_orphan_ledger_and_substituted_callback_row_rejected():
    with pytest.raises(ValueError, match="requires explicit"):
        E.verify({"att_packets": [], "status_events": []})
    report = enable({"att_packets": [row()]})
    with pytest.raises(ValueError, match="original ATT"):
        E.observe(report, 0, row(command=5))


def test_setup_diverts_event_without_changing_gatt_proof():
    report = setup()
    expected = report["gatt_proof"]
    enable(report)
    # After actual command CCCD response, before remaining subscription requests.
    report["att_packets"].insert(24, row() | {"monotonic_ns": 23})
    report["setup_end"] += 1
    observe_all(report)
    assert A.setup(report) == expected | {"setup_end": report["setup_end"]}
    assert E.verify(report)[0] == {24}


def test_actions_diverts_interleaved_event_but_requires_all_acks_and_end():
    report, op = session_operation()
    enable(report)
    at = op["actions_start"] + 2
    report["att_packets"].insert(at, row())
    op["actions_end"] += 1
    observe_all(report)
    assert A.actions(report, op) == {
        "acks": 5,
        "end": True,
        "pending_bytes": 0,
        "trace_span": [op["actions_start"], op["actions_end"]],
    }
    report["att_packets"].pop(at + 1)  # A real ACK may not be replaced by status.
    op["actions_end"] -= 1
    with pytest.raises(ValueError):
        A.actions(report, op)


def identity(report):
    owner = {"after": info()}
    start = len(report["att_packets"])
    for command, payload in ((1, b"C261CF0430"), (2, b"\0"), (5, bytes.fromhex(info()["device"]["raw"]))):
        report["att_packets"].extend(
            [
                {"direction": "tx", "hex": (b"\x52\x22\0" + P.frame(command)).hex()},
                row(command=command, payload=payload),
                row(),
            ]
        )
    owner["after_span"] = [start, len(report["att_packets"])]
    return owner


def test_identity_keeps_real_span_with_interleaving_and_does_not_accept_fake_reply():
    report = enable(setup())
    owner = identity(report)
    observe_all(report)
    assert A.identity(report, owner, "after") == {"verified": True, "trace_span": owner["after_span"]}
    assert E.edge(report, *owner["after_span"]) == (owner["after_span"][0], owner["after_span"][1] - 2)
    report["att_packets"][owner["after_span"][0] + 1] = row()
    with pytest.raises(ValueError, match="three request"):
        A.identity(report, owner, "after")


def test_file_list_has_event_only_bridge_and_interleaving():
    report = enable({"att_packets": [], "setup_end": 0, "before_span": [0, 0], "listed_count": 0})
    report["att_packets"] = [
        row(),
        {"direction": "tx", "hex": (b"\x52\x22\0" + P.frame(10)).hex()},
        row(),
        row(command=10, payload=b"\x02"),
        row(),
    ]
    report["file_list_span"] = [1, 5]
    observe_all(report)
    assert W.file_list(report) == 0
    assert E.edge(report, 1, 5) == (1, 3)
    report["att_packets"][0] = row(command=5)
    with pytest.raises(ValueError, match="bridge"):
        W.file_list(report)


def test_download_routes_status_separately_and_preserves_actual_bytes():
    op = operation() | {"actions_end": 0, "download_start": 1}
    data = bytes(range(256)) * 16
    packets = [
        row(),
        {
            "direction": "tx",
            "hex": (b"\x52\x22\0" + P.frame(11, op["name"].encode().ljust(14, b"\0") + bytes(4))).hex(),
        },
        row(),
        row(command=11, payload=b"\0\0\0\x10\0"),
    ]
    packets.extend(
        {"direction": "rx", "hex": (b"\x1b\x2a\0" + data[i : i + 244]).hex()} for i in range(0, 4096, 244)
    )
    packets.extend([row(), row(command=11, payload=b"\x02"), row()])
    report = enable({"att_packets": packets})
    op["download_end"] = len(packets)
    observe_all(report)
    E.bridge(report, 0, 1)
    assert A.download(report, op, data)["trace_span"] == [1, len(packets)]
    assert E.edge(report, 1, len(packets)) == (1, len(packets) - 2)
    report["att_packets"][4] = row()  # Event cannot replace244 offline bytes.
    with pytest.raises(ValueError):
        A.download(report, op, data)
