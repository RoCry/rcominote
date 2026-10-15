"""Fully synthetic fixed Actions bytes, parameter epochs and readonly identity."""

import copy
import json
import struct

import pytest
from test_dual_probe import setup
from test_hci_interval import connection, event, record
from test_param_window import CONTROL, LINK, STATUS, command, fragment, remote, update
from test_sd_nor_probe import info

from rcominote import protocol as Boyi
from rcominote.experiments import actions_fast_control as C
from rcominote.log_probe import ACK
from rcominote.log_stream import Stream

ORACLE = bytes(range(256))


def echo(command):
    return f"logsrv: cmd({len(command)}) {command}\r\n\n".encode()


def content(plan, data=ORACLE):
    rows = []
    for index in range(16):
        chunk = data[index * 16 : index * 16 + 16]
        rows.append(
            f"{0x18000000 + index * 16:08x}: ".encode()
            + b" ".join(f"{b:02x}".encode() for b in chunk)
            + b"    "
            + bytes(b if 32 <= b <= 126 else 46 for b in chunk)
            + b"\r\n"
        )
    return echo(plan["marker_command"]) + b"\r\n" + b"".join(rows) + b"[logsrv][I][679]: " + echo(C.MDB)


def f0(text):
    payload = b"\0" + len(text).to_bytes(2, "little") + text
    return b"\x1d\xf0\x81" + len(payload).to_bytes(2, "little") + payload


def fixture(
    root,
    *,
    mode="fast",
    fillers=0,
    early_data=False,
    terminal_tail=b"",
    plan_override=None,
    oracle=ORACLE,
    output=None,
):
    state = info(9)
    plan = {
        "profile": C.PROFILE,
        "marker": "afc0123456789abcdef",
        "marker_command": "kernel uptime afc0123456789abcdef",
        "mdb_command": C.MDB,
        "filler_command": C.VERSION,
        "state_reference": {
            "directory": "/synthetic/historical-only",
            "profile": C.C.PREFILLED_PROFILE,
            "ended_at": "2026-10-14T09:00:00+00:00",
            "latest_info": state,
            "verification": {"verified": True},
            "historical_report": {"file": "report.json", "sha256": "0" * 64},
            "historical_identity_only": True,
            "current_owned_file_verified": False,
        },
        "expected_before": state,
        "ram_oracle": {"sha256": C.RAM.RAM_SHA, "bytes": 4096},
        "oracle_slice": [0, 256],
        "oracle_bytes": 256,
        "oracle_sha256": C.A.A.sha(ORACLE),
        "budget": C.BUDGET.copy(),
        "startup_policy": C.C.startup.POLICY,
        "status_event_policy": C.C.E.POLICY,
        "planned_at": "2026-10-14T10:00:00+00:00",
    }
    if plan_override is not None:
        plan = copy.deepcopy(plan_override)
    actual = setup() | C.report(plan)
    actual.update(
        att_packets=setup()["att_packets"],
        setup_end=setup()["setup_end"],
        gatt_proof=setup()["gatt_proof"],
        transport={"link": LINK},
        status_events=[],
        started_at="2026-10-14T10:01:00+00:00",
        ended_at="2026-10-14T10:02:00+00:00",
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
    )
    rows = [CONTROL, (3, connection())]

    def emit(direction, pdu, *, existing=False):
        if not existing:
            actual["att_packets"].append(
                {"direction": direction, "hex": pdu.hex(), "monotonic_ns": len(rows)}
            )
        rows.append(fragment(struct.pack("<HH", len(pdu), 4) + pdu, direction=direction))

    for row in actual["att_packets"]:
        emit(row["direction"], bytes.fromhex(row["hex"]), existing=True)

    def identity(key):
        start = len(actual["att_packets"])
        for cmd, payload in ((1, b"C261CF0430"), (2, b"\0"), (5, bytes.fromhex(state["device"]["raw"]))):
            emit("tx", b"\x52\x22\0" + Boyi.frame(cmd))
            emit("rx", b"\x1b\x24\0" + Boyi.frame(cmd, payload))
        actual[key] = copy.deepcopy(state)
        actual[f"{key}_span"] = [start, len(actual["att_packets"])]

    identity("before")
    rows.extend(remote(24, 40, 0, 500) + [update(36)] if mode == "default" else remote() + [update(12)])
    op = actual["operation"]
    op.update(
        started_at="2026-10-14T10:01:01+00:00",
        ended_at="2026-10-14T10:01:30+00:00",
        actions_start=len(actual["att_packets"]),
        notifications=[],
        frames=[],
        sd_write_attempted=False,
        log_session_complete=True,
        condition_applied=True,
        live_complete=True,
        fillers=fillers,
        phase="complete",
    )

    def notify(data):
        emit("rx", b"\x1b\x18\0" + data)
        op["notifications"].append(data.hex())

    def send(packet, *, ack=True):
        emit("tx", b"\x12\x16\0" + packet)
        emit("rx", b"\x13")
        if ack:
            notify(ACK)

    expected = C.recipe(plan, fillers)
    send(expected[0])
    if mode == "default":
        rows.extend(
            remote(identifier=9) + [update(12)]
        )  # Deliberately BEFORE START; no causation requirement.
    send(expected[1])
    base = C.A.P.H.EPOCH_US + int(C.A.datetime.fromisoformat(actual["started_at"]).timestamp() * 1_000_000)
    op["normalization_requested_us"] = base + (len(rows) + 1) * 1000 - 1
    rows.extend([command(), STATUS, update()])
    op["burst_start"] = len(actual["att_packets"])
    send(expected[2])

    text = content(plan) if output is None else output
    chunks = []
    for at in range(0, len(text), 504):
        frame = f0(text[at : at + 504])
        chunks.extend(frame[i : i + 244] for i in range(0, len(frame), 244))
    if early_data == "partial":
        notify(chunks[0])  # Early row bytes; complete frame arrives after MDB.
    elif early_data:
        for chunk in chunks:
            notify(chunk)
    send(expected[3], ack=early_data != "partial")
    if early_data == "partial":
        for chunk in chunks[1:]:
            notify(chunk)
        notify(ACK)
    elif not early_data:
        for chunk in chunks:
            notify(chunk)
    for packet in expected[4:-1]:
        send(packet)
    send(expected[-1])
    notify(b"\x1d\xf1\x81\0\0" + terminal_tail)
    op["actions_end"] = len(actual["att_packets"])
    stream = Stream()
    for raw in op["notifications"]:
        stream.feed(bytes.fromhex(raw))
    op.update(
        frames=stream.frames,
        writes=[{"hex": p.hex(), "att_write_confirmed": True} for p in expected],
        ack_count=stream.acks,
        end_received=stream.ended,
        pending_hex=stream.pending.hex(),
        content_verification=C.parse(stream.frames, plan, oracle),
    )
    identity("after")
    rows.append((3, event(0x05, b"\0" + struct.pack("<H", LINK["handle"]) + b"\x16")))
    raw = C.A.P.H.HEADER + b"".join(
        record(p, opcode, stamp=base + i * 1000) for i, (opcode, p) in enumerate(rows, 1)
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "session.btsnoop").write_bytes(raw)
    observed = C.A.P.inspect(raw, link=LINK, final=True)
    actual.update(
        hci_capture={"bytes": len(raw), "sha256": C.A.A.sha(raw), "records": observed["records"]},
        att_hci_binding=C.A.dual_hci.bind(actual, raw),
        startup_settlement=observed["transactions"][0],
        startup_classification=C.C.startup.classify(
            observed["transactions"][0], policy=plan["startup_policy"]
        ),
        predecessor_state_verification=C.A.verify_state(state, state, sd_write=False),
        state_verification=C.A.verify_state(state, state, sd_write=False),
    )
    op["normalization"] = observed["transactions"][-1]
    op["activity_fast"] = observed["transactions"][1:2] if mode == "default" else []
    dis = observed["disconnects"][0]
    actual.update(
        close_requested_us=dis["timestamp_us"] - 1,
        close_completed_us=dis["timestamp_us"] + 1,
        disconnect_observed_us=dis["timestamp_us"] + 2,
        disconnect_observation={"observed": True, "event": dis, "max_wait_seconds": 8},
    )
    (root / "plan.json").write_text(json.dumps(plan))
    actual["plan"] = C.C.J.reference(root, root / "plan.json")
    return actual, plan


@pytest.mark.parametrize("tail", [ACK, f0(b"trailing text")])
def test_same_notification_f1_then_another_frame_is_not_terminal(tmp_path, tail):
    actual, plan = fixture(tmp_path, terminal_tail=tail)
    with pytest.raises(ValueError):
        C.validate(actual, tmp_path, plan, ORACLE)


def test_historical_source_reference_does_not_claim_current_owned_file(tmp_path):
    from unittest.mock import patch

    original, expected = fixture(tmp_path)
    source = expected["state_reference"] | {
        "baseline_sha256": "old-owned-file-must-not-be-claimed",
        "prior_names": ["rc0123456789"],
        "references": {"report": expected["state_reference"]["historical_report"]},
    }
    ram = ORACLE + b"x" * (4096 - 256)
    with (
        patch.object(C.C, "parent_gate", return_value=(b"old file", original["before"], source)),
        patch.object(C.RAM, "ram_source", return_value=(ram, expected["ram_oracle"])),
    ):
        plan, oracle = C.prepare(tmp_path / "image", tmp_path)
        assert C.source_gate(plan, tmp_path / "image") == oracle == ORACLE
        assert plan["state_reference"]["current_owned_file_verified"] is False
        assert "baseline_sha256" not in plan["state_reference"]
        assert not plan["marker"].startswith("rc")
        source["references"]["report"] = {"file": "other", "sha256": "f" * 64}
        with pytest.raises(ValueError, match="Historical identity"):
            C.source_gate(plan, tmp_path / "image")


@pytest.mark.parametrize("fault", ["budget-bool", "owned-claim", "mdb", "fillers", "rc-marker"])
def test_closed_plan_has_no_storage_address_or_unbounded_command_escape(tmp_path, fault):
    _actual, plan = fixture(tmp_path)
    if fault == "budget-bool":
        plan["budget"]["sd_writes"] = False
    elif fault == "owned-claim":
        plan["state_reference"]["current_owned_file_verified"] = True
    elif fault == "mdb":
        plan["mdb_command"] = "dbg mdb 40000000 100"
    elif fault == "fillers":
        with pytest.raises(ValueError):
            C.recipe(plan, 9)
        return
    else:
        plan["marker"] = "rc0123456789"
    with pytest.raises(ValueError):
        C.validate_plan(plan)


@pytest.mark.parametrize("mode,fillers", [("fast", 0), ("default", 0), ("fast", 8)])
def test_full_synthetic_wire_applied6_after_start_and_all_current_ram_bytes(mode, fillers, tmp_path):
    actual, plan = fixture(tmp_path, mode=mode, fillers=fillers)
    proof = C.validate(actual, tmp_path, plan, ORACLE)
    assert proof["acks"] == 5 + fillers and proof["parameter_transactions"] == (3 if mode == "default" else 2)
    assert (
        proof["bytes"] == 256
        and proof["sd_writes"] == proof["nor_writes"] == proof["new_raw_nor_coverage_bytes"] == 0
    )
    assert (
        proof["requested_ce_hints"] == [1, 1]
        and proof["text_origin"]["rows_span"]["command_att_index"] == actual["operation"]["burst_start"] + 3
    )


@pytest.mark.parametrize("early", [True, "partial"])
def test_complete_known_output_before_mdb_tx_cannot_be_current_read(tmp_path, early):
    actual, plan = fixture(tmp_path, early_data=early)
    with pytest.raises(ValueError, match="precede their actual command"):
        C.validate(actual, tmp_path, plan, ORACLE)


@pytest.mark.parametrize(
    "fault",
    [
        "normalization",
        "early-request",
        "missing-f1",
        "pending-summary",
        "final-state",
        "condition",
        "oracle",
        "source-policy",
        "frame-proof",
        "marker",
        "count",
    ],
)
def test_wire_and_original_evidence_are_required_even_when_ram_bytes_match(tmp_path, fault):
    actual, plan = fixture(tmp_path)
    op = actual["operation"]
    if fault == "normalization":
        op["normalization"]["request"]["min_length"] = 0
    elif fault == "early-request":
        op["normalization_requested_us"] = actual["startup_settlement"]["update"]["timestamp_us"]
    elif fault == "missing-f1":
        op["end_received"] = False
    elif fault == "pending-summary":
        op["pending_hex"] = "1d"
    elif fault == "final-state":
        actual["after"] = {}
    elif fault == "condition":
        op["condition_applied"] = False
    elif fault == "oracle":
        plan["oracle_sha256"] = "0" * 64
        (tmp_path / "plan.json").write_text(json.dumps(plan))
        actual["plan"] = C.C.J.reference(tmp_path, tmp_path / "plan.json")
    elif fault == "source-policy":
        actual["startup_policy"] = C.C.startup.LEGACY_POLICY
    elif fault == "frame-proof":
        op["content_verification"]["rows"] = 15
    elif fault == "marker":
        actual["marker"] = "rc0123456789"
    else:
        op["fillers"] = True
    with pytest.raises((ValueError, KeyError)):
        C.validate(actual, tmp_path, plan, ORACLE)


def test_exact_nonnewline_wire_and_observed_original_mdb_ascii_formatter():
    assert C.packet(C.MDB)[8:] == C.MDB.encode() and not C.packet(C.MDB).endswith(b"\n")
    # Original Linux short-read rawF0 row; independent of fixture formatter.
    row = b"1000ab40: 5e 34 8d f8 12 30 94 f8 70 34 bd f8 00 20 8d f8    ^4...0..p4... .."
    data = bytes.fromhex(row[10:57].decode())
    assert row[57:61] == b"    " and row[61:] == bytes(b if 32 <= b <= 126 else 46 for b in data)
