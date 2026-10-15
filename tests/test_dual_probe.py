"""Fixed two-target session and real trace spans; all tests offline."""

import asyncio
import copy
import json
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_hci_interval import HANDLE, LOCAL, packets, record
from test_sd_nor_probe import END, attach_actions, info, receipt

from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci as C
from rcominote.experiments import dual_nor_probe as R
from rcominote.experiments import hci_interval as H
from rcominote.experiments import sd_nor_targets as T
from rcominote.experiments.dual_client import ACTION_CHARS, ACTION_DESCRIPTOR, ACTION_SERVICE, Actions
from rcominote.log_capture import START, STOP
from rcominote.log_probe import ACK


def setup():
    pairs = [
        ("02f700", "03f700"),
        ("100100ffff0028", "110620002b00e0e5"),
        ("102c00ffff0028", "01102c000a"),
        ("0820002b000328", "09072100042200e1e52300102400e2e52600102700e3e52900102a00e4e5"),
        ("082b002b000328", "01082b000a"),
        ("0425002500", "050125000229"),
        ("0428002800", "050128000229"),
        ("042b002b00", "05012b000229"),
        ("10140019000028", ACTION_SERVICE.hex()),
        ("08140019000328", ACTION_CHARS.hex()),
        ("0419001900", ACTION_DESCRIPTOR.hex()),
        ("1225000100", "13"),
        ("122b000100", "13"),
        ("1219000100", "13"),
    ]
    rows = [
        {"direction": d, "hex": value, "monotonic_ns": i * 2 + j}
        for i, pair in enumerate(pairs)
        for j, (d, value) in enumerate(zip(("tx", "rx"), pair))
    ]
    report = {"att_packets": rows, "setup_end": len(rows)}
    report["gatt_proof"] = A.setup(report)
    return report


def operation():
    op = receipt("rc0123456789", R.probe.BUFFER, 4096, phase=T.Phase.boot)
    attach_actions(op, producer=True)
    return op


def session_operation():
    session, op = setup(), operation()
    rows = op.pop("att_packets")[8:]
    op["actions_start"] = len(session["att_packets"])
    for row in rows:
        row["monotonic_ns"] += 100
    session["att_packets"] += rows
    op["actions_end"] = len(session["att_packets"])
    return session, op


def test_setup_and_real_spans_without_synthetic_second_discovery():
    session, op = session_operation()
    assert A.actions(session, op)["acks"] == 5
    second = copy.deepcopy(op)
    second["actions_start"] = op["actions_end"]
    session["att_packets"] += copy.deepcopy(session["att_packets"][op["actions_start"] : op["actions_end"]])
    second["actions_end"] = len(session["att_packets"])
    assert A.actions(session, second)["trace_span"][0] == op["actions_end"]
    second["actions_start"] = 0
    with pytest.raises(ValueError, match="span"):
        A.actions(session, second)


@pytest.mark.parametrize(
    "fault", ["cccd", "props", "mtu", "response", "f1", "late", "handle", "ack", "receipt"]
)
def test_actual_evidence_faults_fail(fault):
    s, op = session_operation()
    if fault == "cccd":
        s["att_packets"][22]["hex"] = "1228000100"
    elif fault == "props":
        s["att_packets"][7]["hex"] = s["att_packets"][7]["hex"].replace("210004", "21000c")
    elif fault == "mtu":
        s["att_packets"][1]["hex"] = "038000"
    elif fault == "response":
        s["att_packets"][op["actions_start"] + 1]["hex"] = "1300"
    elif fault == "f1":
        s["att_packets"].pop()
        op["actions_end"] -= 1
    elif fault == "late":
        s["att_packets"].append(s["att_packets"][-1])
        op["actions_end"] += 1
    elif fault == "handle":
        s["att_packets"][op["actions_start"] + 2]["hex"] = "1b2a00" + ACK.hex()
    elif fault == "ack":
        s["att_packets"].insert(op["actions_start"], {"direction": "rx", "hex": "1b1800" + ACK.hex()})
        op["actions_end"] += 1
    else:
        op["notifications"].pop()
    with pytest.raises(ValueError):
        A.actions(s, op)


def acl(pdu, direction, *, pb=2):
    body = struct.pack("<HH", len(pdu), 4) + pdu
    return struct.pack("<HH", HANDLE | pb << 12, len(body)) + body


def capture(rows):
    chunks = [record(p, op, stamp=100 + i) for i, (op, p) in enumerate(packets())]
    chunks += [
        record(
            acl(bytes.fromhex(r["hex"]), r["direction"]), 4 if r["direction"] == "tx" else 5, stamp=105 + i
        )
        for i, r in enumerate(rows)
    ]
    return H.HEADER + b"".join(chunks)


def test_hci_exact_direction_binding_and_fragment_reassembly():
    s = setup()
    s["transport"] = {"link": {"handle": HANDLE}}
    raw = capture(s["att_packets"])
    assert C.bind(s, raw)["packets"] == len(s["att_packets"])
    # Cross-direction scheduling order is immaterial, but own-direction is exact.
    s["att_packets"][0:2] = s["att_packets"][1::-1]
    assert C.bind(s, raw)["verified"]
    s["att_packets"].pop()
    with pytest.raises(ValueError, match="sequence"):
        C.bind(s, raw)
    pdu = b"\x1b\x2a\0" + bytes(244)
    body = struct.pack("<HH", len(pdu), 4) + pdu
    frag = H.HEADER + b"".join(record(p, op) for op, p in packets()[:2])
    frag += record(struct.pack("<HH", HANDLE | 0x2000, 10) + body[:10], 5)
    frag += record(struct.pack("<HH", HANDLE | 0x1000, len(body) - 10) + body[10:], 5)
    assert C.att_packets(frag, HANDLE)[0]["hex"] == pdu.hex()
    with pytest.raises(ValueError, match="Incomplete final"):
        C.att_packets(frag[: -24 - (len(body) - 10) - 4], HANDLE)


def test_hci_reconstructs_baseline_and_rejects_second_update():
    rows = [{"direction": "tx", "hex": "02f700"}]
    raw = capture(rows)
    parser = H.Snoop()
    parser.feed(raw, final=True)
    s = {
        "hci_capture": {"bytes": len(raw), "sha256": A.sha(raw), "records": parser.records},
        "monitor_exit": 0,
        "transport": {
            "link": {"handle": HANDLE, "local": LOCAL, "peer": H.PEER, "controller": "hci0"},
            "baseline": parser.events[1],
            "update_requested_us": 102,
            "applied": parser.events[4],
            "actual_hci_request": parser.events[2],
        },
    }
    op = {
        "condition_start_us": 104,
        "verified_end_us": 1000000,  # Host parsing finishes after last HCI RX; wire end remains authoritative.
        "phase": "boot",
        "download_start": 0,
        "verified_end": 1,
    }
    s["operations"] = [op]
    s["att_packets"] = rows
    assert A.hci(s, op, raw)["verified"]
    s["transport"]["baseline"] = s["transport"]["baseline"] | {"interval": 36}
    with pytest.raises(ValueError, match="Baseline"):
        A.hci(s, op, raw)


def fake_actions():
    session = {"att_packets": []}
    conn = SimpleNamespace(
        queue=asyncio.Queue(),
        _transaction=asyncio.Lock(),
        offline_allowed=False,
        _check_failure=lambda: None,
        _fail=lambda error: setattr(conn, "failure", error),
    )
    conn.client = SimpleNamespace(_link=SimpleNamespace(notifications=[]))
    actions = Actions(conn, session)

    async def send(p):
        actions.receive(None, ACK)
        if p == STOP:
            actions.receive(None, END)

    conn.client.action_write = AsyncMock(side_effect=send)
    return actions, conn


def test_actions_cleanup_once_and_sticky_failure():
    async def run():
        actions, conn = fake_actions()
        original = conn.client.action_write.side_effect

        async def broken(p):
            if p == START:
                actions.receive(None, b"bad-frame")
            else:
                await original(p)

        conn.client.action_write.side_effect = broken
        op = operation()
        with pytest.raises(ValueError):
            await actions.run(op)
        assert [c.args[0] for c in conn.client.action_write.await_args_list].count(STOP) == 1
        assert isinstance(conn.failure, RuntimeError)
        assert not op["sd_write_attempted"]

    asyncio.run(run())


def test_actions_success_missing_end_late_and_bounds():
    async def run():
        actions, conn = fake_actions()
        op = operation()
        await actions.run(op)
        assert op["log_session_complete"] and op["ack_count"] == 5
        with pytest.raises(ValueError, match="Late"):
            actions.receive(None, ACK)
        with pytest.raises(ValueError, match="Offline"):
            actions.guard_received(b"\x1b\x2a\0x")
        actions.operation = {"notifications": ["00"] * 1024}
        with pytest.raises(RuntimeError, match="bound"):
            actions.receive(None, ACK)
        actions.operation = None
        conn.client._link.notifications.append((24, ACK))
        with pytest.raises(ValueError, match="overlaps"):
            await actions.run(operation())

    asyncio.run(run())


def test_second_failure_preserves_first_checkpoint_and_bytes(tmp_path):
    async def run():
        first, second = operation(), operation()
        first.update(phase="boot", before=info(), live_complete=False)
        second["phase"] = "recovery-block1"
        report = {"operations": [first, second], "att_packets": [], "transport": {"applied": {"test": 1}}}
        (tmp_path / "boot").mkdir()
        conn = SimpleNamespace(_check_failure=lambda: None)

        async def identity(_conn, owner, key):
            owner[key] = info()
            return owner[key]

        async def download(_conn, op, directory):
            (directory / "download.bin").write_bytes(b"first retained")
            op["verification"] = {"sector_hex": "00" * 512}

        actions = SimpleNamespace(run=AsyncMock(side_effect=ValueError("second Actions failed")))
        with (
            patch.object(R, "download", side_effect=download),
            patch.object(R, "read_identity", side_effect=identity),
            patch.object(R.condition, "gate", return_value={"test": 1}),
            pytest.raises(ValueError, match="second Actions"),
        ):
            await R.remainder(conn, None, report, actions, tmp_path)
        assert (tmp_path / "boot/download.bin").read_bytes() == b"first retained"
        checkpoint = json.loads((tmp_path / "boot/checkpoint.json").read_text())
        assert checkpoint["operations"][0]["live_complete"]
        assert not checkpoint["operations"][1].get("live_complete")

    asyncio.run(run())


def test_preflight_rejects_wrong_image_before_parent_replay(tmp_path):
    path = tmp_path / "image"
    path.write_bytes(b"wrong")
    with patch.object(T, "verify_pair") as verify, pytest.raises(ValueError, match="complete FW"):
        R.prepare(path, tmp_path, tmp_path)
    verify.assert_not_called()


@pytest.mark.parametrize("fault", [None, "name", "declaration", "short", "late", "unrelated"])
def test_boyi_download_replays_actual_bytes_and_name(fault):
    from rcominote import protocol as P

    op = operation()
    op.update(actions_end=0, download_start=0)
    body = bytes(range(256)) * 16
    rows = [
        ("tx", b"\x52\x22\0" + P.frame(P.GET_FILE_DATA, op["name"].encode().ljust(14, b"\0") + bytes(4))),
        ("rx", b"\x1b\x24\0" + P.frame(P.GET_FILE_DATA, b"\0\0\0\x10\0")),
    ]
    rows += [("rx", b"\x1b\x2a\0" + body[i : i + 244]) for i in range(0, len(body), 244)]
    rows += [("rx", b"\x1b\x24\0" + P.frame(P.GET_FILE_DATA, b"\x02"))]
    if fault == "name":
        op["name"] = "rcaaaaaaaaaa"
    elif fault == "declaration":
        rows.pop(1)
    elif fault == "short":
        rows.pop(2)
    elif fault == "late":
        rows.append(rows[2])
    elif fault == "unrelated":
        rows.insert(2, ("rx", b"\x1b\x24\0" + P.frame(P.GET_SERIAL, b"C261CF0430")))
    session = {"att_packets": [{"direction": d, "hex": p.hex()} for d, p in rows]}
    op["download_end"] = len(rows)
    if fault:
        with pytest.raises(ValueError):
            A.download(session, op, body)
    else:
        assert A.download(session, op, body)["bytes"] == 4096


@pytest.mark.parametrize("fault", [None, "reported", "wire", "command", "crc", "crosshandle"])
def test_identity_is_reconstructed_from_actual_requests_and_crc_replies(fault):
    from rcominote import protocol as P

    s = setup()
    owner = {"after": info()}
    start = len(s["att_packets"])
    for cmd, payload in ((1, b"C261CF0430"), (2, b"\0"), (5, bytes.fromhex(info()["device"]["raw"]))):
        s["att_packets"] += [
            {"direction": "tx", "hex": (b"\x52\x22\0" + P.frame(cmd)).hex()},
            {"direction": "rx", "hex": (b"\x1b\x24\0" + P.frame(cmd, payload)).hex()},
        ]
    owner["after_span"] = [start, len(s["att_packets"])]
    if fault == "reported":
        owner["after"]["bound"] = True
    elif fault == "wire":
        s["att_packets"][start + 3]["hex"] = (b"\x1b\x24\0" + P.frame(2, b"\x01")).hex()
    elif fault == "command":
        s["att_packets"][start]["hex"] = (b"\x52\x22\0" + P.frame(4)).hex()
    elif fault == "crc":
        s["att_packets"][-1]["hex"] += "00"
    elif fault == "crosshandle":
        s["att_packets"][-1]["hex"] = "1b2a00" + s["att_packets"][-1]["hex"][6:]
    if fault:
        with pytest.raises(ValueError):
            A.identity(s, owner, "after")
    else:
        assert A.identity(s, owner, "after")["verified"]


def test_hci_second_update_inside_operation_is_not_hidden_by_host_timestamps():
    from test_hci_interval import update

    rows = [{"direction": "tx", "hex": "02f700"}, {"direction": "rx", "hex": "03f700"}]
    raw = capture(rows[:1]) + record(update(interval=12), stamp=106)
    raw += record(acl(bytes.fromhex(rows[1]["hex"]), "rx"), 5, stamp=107)
    parser = H.Snoop()
    parser.feed(raw, final=True)
    op = {"phase": "boot", "download_start": 0, "verified_end": 2, "verified_end_us": 105}
    session = {
        "att_packets": rows,
        "operations": [op],
        "monitor_exit": 0,
        "hci_capture": {"bytes": len(raw), "sha256": A.sha(raw), "records": parser.records},
        "transport": {
            "link": {"handle": HANDLE, "local": LOCAL, "peer": H.PEER, "controller": "hci0"},
            "baseline": parser.events[1],
            "update_requested_us": 102,
            "applied": parser.events[4],
            "actual_hci_request": parser.events[2],
        },
    }
    with pytest.raises(ValueError, match="Second parameter"):
        A.hci(session, op, raw)


@pytest.mark.parametrize("fault", [None, "early_op", "gap", "wrong_end", "early_final", "omitted_tail"])
def test_barrier_spans_cannot_reuse_an_earlier_identical_identity(fault):
    op = {"download_end": 100, "verified_end": 106, "after_span": [100, 106]}
    report = {"operations": [op], "after_span": [106, 112], "att_packets": [None] * 112}
    if fault == "early_op":
        op["after_span"] = [10, 16]
    elif fault == "gap":
        op["after_span"] = [101, 107]
    elif fault == "wrong_end":
        op["verified_end"] = 107
    elif fault == "early_final":
        report["after_span"] = [100, 106]
    elif fault == "omitted_tail":
        report["att_packets"].append(None)
    if fault:
        with pytest.raises(ValueError, match="actual"):
            R.barrier_span(report, op)
            R.barrier_span(report)
    else:
        R.barrier_span(report, op)
        R.barrier_span(report)
