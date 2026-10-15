"""Fully synthetic original ATT/CID5/HCI nine-transaction scratch control."""

import copy
import struct

import pytest
from test_dual_probe import setup
from test_hci_interval import connection, event, record
from test_nor_freshness import place
from test_param_window import CONTROL, LINK, STATUS, command, fragment, remote, update
from test_scratch_reuse_parser import NONCE, OTHER, SECTOR, chain
from test_sd_nor_probe import END, info

from rcominote import protocol as P
from rcominote.experiments import scratch_reuse_audit as V
from rcominote.log_probe import ACK
from rcominote.log_stream import Stream


def plan_fixture():
    summary = {
        "state_parent": {"latest_info": info(), "ended_at": "2026-10-14T09:00:00+00:00"},
        "oracles": {
            key: {"sha256": V.A.sha(data)}
            for key, data in (("boot0", SECTOR), ("4200", bytes(reversed(SECTOR))))
        },
    }
    operations = [
        {
            "operation_id": label,
            "name": V.F.NAME,
            "nonce": nonce,
            "nor_offset": offset,
            "uptime_command": f"kernel uptime {nonce}",
            "producer": f"dbg fread spi_flash {'0' if offset == 0 else hex(offset)}",
            "dump_command": V.F.DUMP,
        }
        for label, nonce, offset in (("first", NONCE, 0), ("second", OTHER, 0x4200))
    ]
    return {
        "profile": V.C.PROFILE,
        "serial": info()["serial"],
        "name": V.F.NAME,
        "sources": summary,
        "expected_before": info(),
        "planned_at": "2026-10-14T10:00:00+00:00",
        "startup_policy": V.startup.LEGACY_POLICY,
        "status_event_policy": V.E.POLICY,
        "stages": list(V.C.STAGES),
        "stage_timeout_scope": V.C.STAGE_SCOPE,
        "budget": V.C.BUDGET.copy(),
        "operations": operations,
    }


def fixture(directory, *, fault=None):
    plan = plan_fixture()
    baseline = b"." * 4096
    first = place(chain(), 0)
    second = place(chain(OTHER, 0x4200, bytes(reversed(SECTOR))), 2200, initial=first)
    report = setup() | V.C.report(plan)
    report.update(
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
    start = len(report["att_packets"])
    emit("tx", b"\x52\x22\0" + P.frame(10))
    if fault in ("listed-name", "listed-nonce"):
        name = V.F.NAME if fault == "listed-name" else NONCE
        entry = b"\0" + name.encode().ljust(14, b"\0") + struct.pack(">I", 4096) + b"\0"
        emit("rx", b"\x1b\x24\0" + P.frame(10, entry))
    emit("rx", b"\x1b\x24\0" + P.frame(10, b"\2"))
    report.update(
        file_list_span=[start, len(report["att_packets"])],
        listed_count=int(fault in ("listed-name", "listed-nonce")),
    )
    rows.extend(remote(24, 40) + [update(36)] if fault == "default" else remote() + [update(12)])
    for index, (op, raw) in enumerate(
        zip([report["baseline"], *report["operations"]], [baseline, first, second], strict=True)
    ):
        directory.joinpath(op["operation_id"]).mkdir(parents=True)
        op.update(
            before=info(),
            live_complete=True,
            started_at=f"2026-10-14T10:01:{index * 18 + 1:02d}+00:00",
            ended_at=f"2026-10-14T10:01:{index * 18 + 16:02d}+00:00",
        )
        if index:
            expected = V.C.recipe(op)
            op.update(
                actions_start=len(report["att_packets"]), sd_write_attempted=True, producer_attempted=True
            )
            notifications, stream = [], Stream()
            fast = remote(identifier=20 + index) + [update(12)]
            if fault == "stale-fast" and index == 1:
                rows.extend(fast)
            for number, packet in enumerate(expected):
                emit("tx", b"\x12\x16\0" + packet)
                emit("rx", b"\x13")
                if number == 0 and not (fault == "stale-fast" and index == 1):
                    rows.extend(fast)
                emit("rx", b"\x1b\x18\0" + ACK)
                notifications.append(ACK.hex())
                stream.feed(ACK)
                if number == (1 if fault == "uptime-before-command" else 2):
                    text = {
                        "missing-uptime": b"background",
                        "uptime-partial": b"Uptime: 1234 ms",
                        "uptime-duplicate": b"Uptime: 1234 ms\nUptime: 9 ms\n",
                    }.get(fault, b"Uptime: 1234 ms\n")
                    payload = b"\1" + struct.pack("<H", len(text)) + text
                    frame = b"\x1d\xf0\x81" + struct.pack("<H", len(payload)) + payload
                    for part in (frame[:11], frame[11:]):
                        emit("rx", b"\x1b\x18\0" + part)
                        notifications.append(part.hex())
                        stream.feed(part)
            emit("rx", b"\x1b\x18\0" + END)
            notifications.append(END.hex())
            stream.feed(END)
            op.update(
                actions_end=len(report["att_packets"]),
                notifications=notifications,
                frames=stream.frames,
                writes=[{"hex": p.hex(), "att_write_confirmed": True} for p in expected],
                log_session_complete=True,
            )
            op["actions_verification"] = (
                V.actions(report, op)
                if fault
                not in ("missing-uptime", "uptime-partial", "uptime-duplicate", "uptime-before-command")
                else {}
            )
        op["normalization_requested_us"] = 1000 + len(rows) - 1
        rows.extend([command(ce=0 if fault == "host-hint" and index == 1 else 1), STATUS, update()])
        op["download_start"] = len(report["att_packets"])
        emit("tx", b"\x52\x22\0" + P.frame(11, V.F.NAME.encode().ljust(14, b"\0") + bytes(4)))
        emit("rx", b"\x1b\x24\0" + P.frame(11, b"\0" + struct.pack(">I", 4096)))
        for at in range(0, 4096, 244):
            emit("rx", b"\x1b\x2a\0" + raw[at : at + 244])
        rows.extend(remote(32, 48, 4, 600, identifier=30 + index))
        if fault == "early-slow" and index == 1:
            rows.append(update(48, 4, 600))
        emit("rx", b"\x1b\x24\0" + P.frame(11, b"\2"))
        op["download_end"] = len(report["att_packets"])
        if not (fault == "early-slow" and index == 1):
            rows.append(update(48, 4, 600))
        identity(op, "after")
        op.update(
            verified_end=len(report["att_packets"]),
            download_bytes=4096,
            received_bytes=4096,
            download_sha256=V.A.sha(raw),
            state_verification=V.verify_state(info(), info(), sd_write=bool(index)),
        )
        op["download_verification"] = V.A.download(report, op, raw, minimum_start=report["setup_end"])
        (directory / op["operation_id"] / "download.bin").write_bytes(raw)
        if index:
            previous = baseline if index == 1 else first
            op["verification"] = V.C.payload(op, raw, previous, plan)
            (directory / op["operation_id"] / "sector.bin").write_bytes(
                bytes.fromhex(op["verification"]["sector_hex"])
            )
    identity(report, "after")
    report["state_verification"] = V.verify_state(info(), info(), sd_write=False)
    if fault == "extra":
        rows.extend(remote(identifier=90) + [update(12)])
    report["close_requested_us"] = 1000 + len(rows) - 1
    rows.append((3, event(5, struct.pack("<BHB", 0, LINK["handle"], 0x16))))
    report.update(close_completed_us=1000 + len(rows), disconnect_observed_us=1001 + len(rows))
    raw = V.P.H.HEADER + b"".join(
        record(packet, opcode, stamp=1000 + i) for i, (opcode, packet) in enumerate(rows)
    )
    (directory / "session.btsnoop").write_bytes(raw)
    observed = V.P.inspect(raw, link=LINK, final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": V.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = V.dual_hci.bind(report, raw)
    report["disconnect_observation"] = {
        "observed": True,
        "event": observed["disconnects"][0],
        "max_wait_seconds": 8,
    }
    report["startup_settlement"] = observed["transactions"][0]
    report["startup_classification"] = V.startup.classify(
        report["startup_settlement"], policy=V.startup.POLICY if fault == "default" else None
    )
    wire = V.common.wire_positions(report, raw)
    normal, slow = observed["transactions"][1:3]
    report["baseline"].update(normalization=normal, slow_settlement=slow)
    previous = slow
    for index, op in enumerate(report["operations"]):
        fast, normal, slow = observed["transactions"][3 + index * 3 : 6 + index * 3]
        op.update(pre_download_fast=[fast], normalization=normal, slow_settlement=slow)
        op["activity_fast_verification"] = (
            {}
            if fault == "stale-fast" and index == 0
            else V.W.default_activity_fast(report, op, previous, fast, wire)
        )
        previous = slow
    return report, plan, baseline


def test_complete_original_nine_transactions_six_ack_uptime_and_known_targets(tmp_path):
    report, plan, baseline = fixture(tmp_path)
    proof = V.validate(report, tmp_path, plan, baseline)
    assert proof["parameter_transactions"] == 9 and proof["downloads"] == 3
    assert proof["sd_writes"] == 2 and proof["new_files"] == proof["new_raw_nor_coverage_bytes"] == 0
    assert [op["actions_verification"]["acks"] for op in report["operations"]] == [6, 6]


@pytest.mark.parametrize(
    "fault",
    [
        "default",
        "stale-fast",
        "host-hint",
        "early-slow",
        "extra",
        "missing-uptime",
        "listed-name",
        "listed-nonce",
    ],
)
def test_complete_original_wire_faults_reject(tmp_path, fault):
    with pytest.raises(ValueError):
        report, plan, baseline = fixture(tmp_path, fault=fault)
        V.validate(report, tmp_path, plan, baseline)


@pytest.mark.parametrize(
    "fault", ["baseline", "short", "oracle", "nonce", "path", "policy", "before", "flag", "proof", "close"]
)
def test_saved_material_or_receipt_mutations_reject(tmp_path, fault):
    report, plan, baseline = fixture(tmp_path)
    op = report["operations"][0]
    if fault in ("baseline", "short"):
        p = tmp_path / ("baseline" if fault == "baseline" else "first") / "download.bin"
        p.write_bytes(bytes(4096) if fault == "baseline" else p.read_bytes()[:-1])
    elif fault == "oracle":
        plan["sources"]["oracles"]["boot0"]["sha256"] = "0" * 64
    elif fault == "nonce":
        op["nonce"] = OTHER
    elif fault == "path":
        op["name"] = OTHER
    elif fault == "policy":
        report["startup_policy"] = V.startup.POLICY
    elif fault == "before":
        op["before"] = {}
    elif fault == "flag":
        op["live_complete"] = False
    elif fault == "proof":
        op["verification"]["freshness"]["nonce_span"][0] += 1
    else:
        report["disconnect_observed_us"] += 9_000_000
    with pytest.raises((ValueError, KeyError)):
        V.validate(report, tmp_path, plan, baseline)


def test_audit_does_not_mutate_original_receipts(tmp_path):
    report, plan, baseline = fixture(tmp_path)
    frozen = copy.deepcopy((report, plan))
    V.validate(report, tmp_path, plan, baseline)
    assert (report, plan) == frozen


@pytest.mark.parametrize("fault", ["uptime-partial", "uptime-duplicate", "uptime-before-command"])
def test_uptime_f0_requires_unique_complete_output_after_original_command(tmp_path, fault):
    report, _plan, _baseline = fixture(tmp_path, fault=fault)
    op = report["operations"][0]
    assert V.A.action_frames(report, op, expected=V.C.recipe(op))["acks"] == 6
    with pytest.raises(ValueError, match="uptime F0"):
        V.actions(report, op)


def test_original_stage_deadline_cannot_be_expanded_by_saved_budget(tmp_path):
    report, plan, baseline = fixture(tmp_path)
    report["baseline"]["ended_at"] = "2026-10-14T10:01:20+00:00"
    with pytest.raises(ValueError, match="deadline"):
        V.validate(report, tmp_path, plan, baseline)
