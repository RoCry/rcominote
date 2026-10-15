"""Synthetic seed/data ATT+CID5+HCI bytes; only aggregate source loading mocked."""

import copy
import json
import struct
from unittest.mock import patch

import pytest
from test_dual_probe import setup
from test_hci_interval import connection, event, record
from test_param_window import CONTROL, LINK, STATUS, command, fragment, remote, update
from test_sd_nor_probe import END, info

from rcominote import protocol as P
from rcominote.experiments import startup_ram_audit as V
from rcominote.log_capture import START, STOP
from rcominote.log_probe import ACK, PREPARE
from rcominote.log_stream import Stream

ORACLE = bytes(range(256)) * 16


def fixture(directory, *, kind="data", base=1000, fault=None):
    """Seven complete data transactions, exact3ACK pulses, retained F0 and F1."""
    directory.mkdir(parents=True, exist_ok=True)
    report = setup()
    report.update(
        profile=f"{V.C.PROFILE}/{kind}",
        expected_before=info(),
        status_event_policy=V.E.POLICY,
        status_events=[],
        sd_write_attempted=False,
        startup_policy=V.C.startup.LEGACY_POLICY if kind == "seed" else V.C.startup.POLICY,
        transport={"link": LINK},
        operations=[],
        ok=False,
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
        started_at=f"2026-10-14T10:0{3 if kind == 'seed' else 5}:00+00:00",
        ended_at=f"2026-10-14T10:0{4 if kind == 'seed' else 6}:00+00:00",
    )
    rows = [CONTROL, (3, connection())]

    def emit(direction, pdu, *, existing=False):
        if not existing:
            report["att_packets"].append(
                {"direction": direction, "hex": pdu.hex(), "monotonic_ns": len(rows)}
            )
        rows.append(fragment(struct.pack("<HH", len(pdu), 4) + pdu, direction=direction))

    for row in report["att_packets"]:
        emit(row["direction"], bytes.fromhex(row["hex"]), existing=True)

    def identity(owner, key):
        start = len(report["att_packets"])
        for cmd, payload in ((1, b"C261CF0430"), (2, b"\0"), (5, bytes.fromhex(info()["device"]["raw"]))):
            emit("tx", b"\x52\x22\0" + P.frame(cmd))
            emit("rx", b"\x1b\x24\0" + P.frame(cmd, payload))
        owner[key] = info()
        owner[f"{key}_span"] = [start, len(report["att_packets"])]

    identity(report, "before")
    report["predecessor_state_verification"] = V.verify_state(info(), info(), sd_write=False)
    if kind == "seed":
        rows.extend(remote() + [update(12)])
    else:
        start = len(report["att_packets"])
        emit("tx", b"\x52\x22\0" + P.frame(10))
        entry = b"\0" + b"existing-file".ljust(14, b"\0") + struct.pack(">I", 4096) + b"\0"
        emit("rx", b"\x1b\x24\0" + P.frame(10, entry))
        emit("rx", b"\x1b\x24\0" + P.frame(10, b"\2"))
        report.update(file_list_span=[start, len(report["att_packets"])], listed_count=1)
        rows.extend(
            remote(6, 12) + [update(12)] if fault == "startup-fast" else remote(24, 40) + [update(36)]
        )
        for index, label in enumerate(("first", "second")):
            operation = {
                "operation_id": label,
                "name": V.C.RAM.NAME,
                "before": info(),
                "sd_write_attempted": False,
                "ok": False,
                "live_complete": True,
                "actions_start": len(report["att_packets"]),
                "started_at": f"2026-10-14T10:05:{10 + index * 20:02d}+00:00",
                "ended_at": f"2026-10-14T10:05:{20 + index * 20:02d}+00:00",
            }
            fast = remote(identifier=20 + index) + [update(12)]
            if fault == "stale-fast" and index == 0:
                rows.extend(fast)
            notifications, stream = [], Stream()
            for number, packet in enumerate((PREPARE, START, STOP)):
                emit("tx", b"\x12\x16\0" + packet)
                emit("rx", b"\x13")
                if number == 0 and not (fault == "stale-fast" and index == 0):
                    rows.extend(fast)
                emit("rx", b"\x1b\x18\0" + ACK)
                notifications.append(ACK.hex())
                stream.feed(ACK)
                if number == 1:
                    payload = b"\x01" + struct.pack("<H", 10) + b"background"
                    f0 = b"\x1d\xf0\x81" + struct.pack("<H", len(payload)) + payload
                    emit("rx", b"\x1b\x18\0" + f0)
                    notifications.append(f0.hex())
                    stream.feed(f0)
            emit("rx", b"\x1b\x18\0" + END)
            notifications.append(END.hex())
            stream.feed(END)
            operation.update(
                actions_end=len(report["att_packets"]),
                notifications=notifications,
                frames=stream.frames,
                writes=[{"hex": p.hex(), "att_write_confirmed": True} for p in (PREPARE, START, STOP)],
                log_session_complete=True,
                normalization_requested_us=base + len(rows) - 1,
            )
            operation["actions_verification"] = V.pulse(report, operation)
            rows.extend([command(), STATUS, update()])
            operation["download_start"] = len(report["att_packets"])
            emit("tx", b"\x52\x22\0" + P.frame(11, V.C.RAM.NAME.encode().ljust(14, b"\0") + bytes(4)))
            emit("rx", b"\x1b\x24\0" + P.frame(11, b"\0" + struct.pack(">I", 4096)))
            for at in range(0, len(ORACLE), 244):
                emit("rx", b"\x1b\x2a\0" + ORACLE[at : at + 244])
            rows.extend(remote(32, 48, 4, 600, identifier=30 + index))
            if fault == "early-slow" and index == 0:
                rows.append(update(48, 4, 600))
            emit("rx", b"\x1b\x24\0" + P.frame(11, b"\2"))
            operation["download_end"] = len(report["att_packets"])
            if not (fault == "early-slow" and index == 0):
                rows.append(update(48, 4, 600))
            identity(operation, "after")
            operation.update(
                verified_end=len(report["att_packets"]),
                download_bytes=4096,
                received_bytes=4096,
                download_sha256=V.A.sha(ORACLE),
                state_verification=V.verify_state(info(), info(), sd_write=False),
            )
            operation["download_trace_verification"] = V.A.download(
                report, operation, ORACLE, minimum_start=report["setup_end"]
            )
            target = directory / label
            target.mkdir()
            (target / "download.bin").write_bytes(ORACLE)
            report["operations"].append(operation)
    identity(report, "after")
    report["state_verification"] = V.verify_state(info(), info(), sd_write=False)
    if fault == "extra-transaction":
        rows.extend(remote(identifier=77) + [update(12)])
    elif fault == "pending":
        rows.extend(remote(identifier=77))
    report["close_requested_us"] = base + len(rows) - 1
    rows.append((3, event(5, struct.pack("<BHB", 0, LINK["handle"], 8 if fault == "disconnect" else 0x16))))
    report["close_completed_us"] = base + len(rows)
    report["disconnect_observed_us"] = base + len(rows) + 1
    bind(report, directory, rows, base=base)
    observed = V.parameters.inspect((directory / "session.btsnoop").read_bytes(), link=LINK, final=True)
    report["startup_settlement"] = observed["transactions"][0]
    report["startup_classification"] = V.C.startup.classify(
        report["startup_settlement"], policy=report["startup_policy"]
    )
    wire = V.common.wire_positions(report, (directory / "session.btsnoop").read_bytes())
    previous = report["startup_settlement"]
    for index, operation in enumerate(report["operations"]):
        fast, normalization, slow = observed["transactions"][1 + index * 3 : 4 + index * 3]
        operation.update(activity_fast=fast, normalization=normalization, slow_settlement=slow)
        operation["activity_fast_verification"] = (
            {"forged_stale": True}
            if fault == "stale-fast" and index == 0
            else V.activity_fast(report, operation, previous, fast, wire)
        )
        previous = slow
    return report


def bind(report, directory, rows, *, base=1000):
    raw = V.parameters.H.HEADER + b"".join(
        record(packet, opcode, stamp=base + i) for i, (opcode, packet) in enumerate(rows)
    )
    (directory / "session.btsnoop").write_bytes(raw)
    observed = V.parameters.inspect(raw, link=LINK, final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": V.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = V.dual_hci.bind(report, raw)
    report["disconnect_observation"] = {
        "observed": True,
        "event": observed["disconnects"][0],
        "max_wait_seconds": 8,
    }


def replace_att(report, directory):
    """Reframe mutated actual ATT while retaining the original parameter records."""
    raw = (directory / "session.btsnoop").read_bytes()
    rows, index = [], 0
    for _, opcode, _, packet in V.parameters.records(raw, report["hci_capture"]["records"]):
        if opcode in (4, 5) and int.from_bytes(packet[6:8], "little") == 4:
            row = report["att_packets"][index]
            pdu = bytes.fromhex(row["hex"])
            opcode, packet = fragment(struct.pack("<HH", len(pdu), 4) + pdu, direction=row["direction"])
            index += 1
        rows.append((opcode, packet))
    bind(report, directory, rows)


def test_complete_synthetic_seed_and_default_two_pulse_windows(tmp_path):
    seed_dir, data_dir = tmp_path / "seed", tmp_path / "data"
    seed = fixture(seed_dir, kind="seed")
    data = fixture(data_dir)
    frozen = copy.deepcopy((seed, data))
    assert V.seed(seed, seed_dir)["parameter_transactions"] == 1
    proof = V.data(data, data_dir, ORACLE)
    assert proof["parameter_transactions"] == 7 and proof["activity_pulses"] == 2
    assert proof["sd_writes"] == proof["new_raw_nor_coverage_bytes"] == 0
    assert [p["sha256"] for p in proof["downloads"]] == [V.A.sha(ORACLE)] * 2
    assert [op["actions_verification"]["acks"] for op in data["operations"]] == [3, 3]
    assert all(any(frame["command"] == 0xF0 for frame in op["frames"]) for op in data["operations"])
    assert (seed, data) == frozen


@pytest.mark.parametrize(
    "fault", ["startup-fast", "stale-fast", "early-slow", "extra-transaction", "pending", "disconnect"]
)
def test_real_wire_counterexamples_reject_before_control_promotion(tmp_path, fault):
    report = fixture(tmp_path, fault=fault)
    with pytest.raises(ValueError):
        V.data(report, tmp_path, ORACLE)


@pytest.mark.parametrize(
    "fault",
    [
        "console",
        "five-acks",
        "f1",
        "drop-f0",
        "incomplete",
        "state",
        "policy",
        "barrier",
        "host-time",
        "old-normalization",
        "oracle",
        "close-time",
        "late-observation",
    ],
)
def test_receipt_or_body_mutation_never_bypasses_actual_pulse_and_data_proofs(tmp_path, fault):
    report = fixture(tmp_path)
    first, second = report["operations"]
    if fault == "console":
        report["att_packets"][first["actions_start"]]["hex"] = (
            "121600" + V.A.console_packet("dbg shell").hex()
        )
        replace_att(report, tmp_path)
    elif fault == "five-acks":
        first["writes"].extend([{"hex": START.hex(), "att_write_confirmed": True}] * 2)
    elif fault == "f1":
        report["att_packets"][first["actions_end"] - 1]["hex"] = "1b1800" + ACK.hex()
        replace_att(report, tmp_path)
    elif fault == "drop-f0":
        first["frames"] = [frame for frame in first["frames"] if frame["command"] != 0xF0]
    elif fault == "incomplete":
        second["live_complete"] = False
    elif fault == "state":
        second["after"] = info(1)
    elif fault == "policy":
        report["startup_policy"] = V.C.startup.LEGACY_POLICY
    elif fault == "barrier":
        second["after_span"] = first["after_span"]
    elif fault == "host-time":
        second["normalization_requested_us"] = 0
    elif fault == "old-normalization":
        second["normalization"] = first["normalization"]
    elif fault == "oracle":
        (tmp_path / "second/download.bin").write_bytes(bytes(4096))
    elif fault == "close-time":
        report["close_requested_us"] = report["disconnect_observation"]["event"]["timestamp_us"] + 1
    elif fault == "late-observation":
        report["disconnect_observed_us"] = report["close_completed_us"] + 8_000_001
    with pytest.raises(ValueError):
        V.data(report, tmp_path, ORACLE)


def test_original_host_ce_hint_is_required(tmp_path):
    report = fixture(tmp_path)
    raw = (tmp_path / "session.btsnoop").read_bytes()
    rows, changed = [], False
    for _, opcode, _, packet in V.parameters.records(raw, report["hci_capture"]["records"]):
        if not changed and opcode == 2 and packet[:2] == b"\x13\x20" and packet[-4:] == b"\1\0\1\0":
            packet, changed = packet[:-4] + bytes(4), True
        rows.append((opcode, packet))
    raw = V.parameters.H.HEADER + b"".join(record(p, op, stamp=1000 + i) for i, (op, p) in enumerate(rows))
    (tmp_path / "session.btsnoop").write_bytes(raw)
    report["hci_capture"].update(bytes=len(raw), sha256=V.A.sha(raw))
    assert changed
    with pytest.raises(ValueError):
        V.data(report, tmp_path, ORACLE)


def aggregate(root, *, data_base=10000):
    reports = {
        "seed": fixture(root / "seed", kind="seed", base=1000),
        "data": fixture(root / "data", base=data_base),
    }
    for index, (kind, report) in enumerate(reports.items()):
        report.update(
            ok=True,
            started_at=f"2026-10-14T10:0{3 + index * 2}:00+00:00",
            ended_at=f"2026-10-14T10:0{4 + index * 2}:00+00:00",
        )
        for operation in report["operations"]:
            operation["ok"] = True
        report["verification"] = (
            V.seed(report, root / kind) if kind == "seed" else V.data(report, root / kind, ORACLE)
        )
        V.C.S.save(root / kind / "report.json", report)
    plan = {
        "planned_at": "2026-10-14T10:01:00+00:00",
        "state_parent": {"ended_at": "2026-10-14T10:00:00+00:00"},
        "expected_before": info(),
    }
    V.C.S.save(root / "plan.json", plan)
    job = {
        "profile": V.C.PROFILE,
        "plan": V.J.reference(root, root / "plan.json"),
        "started_at": "2026-10-14T10:02:00+00:00",
        "ended_at": "2026-10-14T10:07:00+00:00",
        "phases": {kind: V.J.reference(root, root / kind / "report.json") for kind in reports},
    }
    return job


@pytest.mark.parametrize(
    "fault", [None, "phase-failed", "op-failed", "state-parent", "job-time", "epoch-overlap", "phase-path"]
)
def test_aggregate_replay_requires_both_original_phases_and_distinct_epochs(tmp_path, fault):
    job = aggregate(tmp_path, data_base=1000 if fault == "epoch-overlap" else 10000)
    if fault in ("phase-failed", "op-failed", "state-parent"):
        path = tmp_path / "data/report.json"
        report = json.loads(path.read_bytes())
        if fault == "phase-failed":
            report["ok"] = False
        elif fault == "op-failed":
            report["operations"][0]["ok"] = False
        else:
            report["expected_before"] = info(1)
        path.write_text(json.dumps(report, ensure_ascii=False))
        job["phases"]["data"] = V.J.reference(tmp_path, path)
    elif fault == "job-time":
        job["ended_at"] = "2026-10-14T10:05:00+00:00"
    elif fault == "phase-path":
        job["phases"]["data"]["file"] = "../data/report.json"
    with patch.object(V.C, "source_gate", return_value=ORACLE):
        if fault:
            with pytest.raises(ValueError):
                V.validate(job, tmp_path, tmp_path / "image")
        else:
            result = V.validate(job, tmp_path, tmp_path / "image")
            assert result["actual_default_tested"] is True and result["connections"] == 2
            assert result["parameter_transactions"] == 8 and result["downloads"] == 2
