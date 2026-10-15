"""Synthetic NOR formatter + complete monitor captures; no device or private fixtures."""

import copy
import struct
from unittest.mock import patch

import pytest
from test_boot_tail_contract import echo, synthetic_ring
from test_boot_tail_contract import fixture as recipe_fixture
from test_dual_probe import setup
from test_hci_interval import connection, record
from test_param_window import CONTROL, LINK, STATUS, command, fragment, remote, update
from test_sd_nor_probe import END, info

from rcominote import protocol as P
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import hci_interval as H
from rcominote.experiments import param_window as PW
from rcominote.experiments import status_event as E
from rcominote.experiments import window_nor_audit as V
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.experiments.sd_bridge import console_packet
from rcominote.log_capture import START, STOP
from rcominote.log_probe import ACK, PREPARE


def fixture(tmp_path, *, optional=False, fault=None, status_at=None, startup=None):
    from rcominote.experiments import window_nor_contract as C

    report = recipe_fixture()
    report.update(setup())
    report.update(
        profile=C.PROFILE,
        transport={"policy": C.POLICY, "link": LINK},
        ok=False,
        pair_verified=False,
        parent={
            "directory": "/synthetic-early",
            "report_sha256": C.C.PARENT_SHA,
            "hci_sha256": C.C.PARENT_HCI_SHA,
        },
        window_parent={
            "directory": "/synthetic-window",
            "report_sha256": C.WINDOW_PARENT_SHA,
            "hci_sha256": C.WINDOW_HCI_SHA,
        },
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
    )
    rows, transaction_count = [CONTROL, (3, connection())], 0
    if startup in ("fast", "default"):
        report["startup_policy"] = V.startup.POLICY
    if status_at is not None or startup in ("fast", "default"):
        report.update(status_event_policy=E.POLICY, expected_before=info())
        report["predecessor_state_verification"] = verify_state(info(), info(), sd_write=False)
        E.init(report)

    def emit(direction, payload):
        report["att_packets"].append(
            {"direction": direction, "hex": payload.hex(), "monotonic_ns": len(rows)}
        )
        if status_at is not None:
            E.observe(report, len(report["att_packets"]) - 1, report["att_packets"][-1])
        rows.append(fragment(struct.pack("<HH", len(payload), 4) + payload, direction=direction))

    def notify(place):
        if status_at == place:
            emit("rx", b"\x1b\x24\0" + P.frame(15, bytes.fromhex("026401010009ffff030001000000000000000000")))

    def transaction(kind):
        nonlocal transaction_count
        index = transaction_count
        if kind == "fast":
            rows.extend(remote(identifier=7 + index) + [update(12)])
        elif kind == "default":
            rows.extend(remote(24, 40, identifier=7 + index) + [update(36)])
        elif kind == "norm":
            rows.extend([command(), STATUS, update()])
        else:
            rows.extend(remote(32, 48, 4, 600, identifier=7 + index) + [update(48, 4, 600)])
        transaction_count += 1
        return index

    def identity(owner, key, state, during=None):
        start = len(report["att_packets"])
        place = (
            ("before" if key == "before" else "final")
            if owner is report
            else owner["operation_id"] + "-identity"
        )
        notify(place + "-leading")
        for cmd, payload in ((1, b"C261CF0430"), (2, b"\0"), (5, bytes.fromhex(state["device"]["raw"]))):
            emit("tx", b"\x52\x22\0" + P.frame(cmd))
            emit("rx", b"\x1b\x24\0" + P.frame(cmd, payload))
            if cmd == 1:
                notify(place)
            if cmd == 1 and during is not None:
                during()
        notify(place + "-trailing")
        owner[key], owner[f"{key}_span"] = state, [start, len(report["att_packets"])]

    original_setup = report["att_packets"]
    report["att_packets"] = []
    for row in original_setup:
        emit(row["direction"], bytes.fromhex(row["hex"]))
    notify("setup")
    report["setup_end"] = len(report["att_packets"])
    report["gatt_proof"] = A.setup(report)
    notify("setup-gap")
    identity(report, "before", info())
    start = len(report["att_packets"])
    notify("list-leading")
    emit("tx", b"\x52\x22\0" + P.frame(10))
    report["listed_count"] = 0
    if fault == "visible-collision":
        name = report["operations"][0]["name"]
        emit("rx", b"\x1b\x24\0" + P.frame(10, b"\0" + name.encode().ljust(14, b"\0") + bytes(5)))
        report["listed_count"] = 1
    notify("list")
    emit("rx", b"\x1b\x24\0" + P.frame(10, b"\x02"))
    notify("list-trailing")
    report["file_list_span"] = [start, len(report["att_packets"])]
    transaction("default" if startup in ("default", "unflagged-default") else "fast")
    notify("warm-gap")
    indices, early_second_fast = [], []
    first_ring = None
    for index, op in enumerate(report["operations"]):
        first_fast = []
        if index == 0 and fault == "stale-first-fast":
            first_fast.append(transaction_count)
            rows.extend(remote(identifier=7 + transaction_count))
            transaction_count += 1
        op.update(before=info(index), live_complete=True, sd_write_attempted=True, ok=False)
        op["actions_start"] = len(report["att_packets"])
        notify(op["operation_id"] + "-actions-leading")
        packets = [PREPARE, START, console_packet(op["producer"]), console_packet(op["dump_command"]), STOP]
        op.update(
            writes=[{"hex": packet.hex(), "att_write_confirmed": True} for packet in packets],
            notifications=[ACK.hex()] * 5 + [END.hex()],
            frames=[{"command": 16, "hex": ACK.hex()}] * 5 + [{"command": 241, "hex": END.hex()}],
            log_session_complete=True,
        )
        for packet in packets:
            emit("tx", b"\x12\x16\0" + packet)
            emit("rx", b"\x13")
            emit("rx", b"\x1b\x18\0" + ACK)
            if packet == PREPARE:
                notify(op["operation_id"] + "-actions")
                if index == 0 and fault == "stale-first-fast":
                    rows.append(update(12))
                elif index == 0 and startup == "default" and optional:
                    first_fast.append(transaction("fast"))
        emit("rx", b"\x1b\x18\0" + END)
        notify(op["operation_id"] + "-actions-trailing")
        op["actions_end"] = len(report["att_packets"])
        op["actions_verification"] = A.actions(report, op)
        fast_indices = list(early_second_fast) if index else first_fast
        if (optional and index == 0 and not first_fast) or (
            index == 1 and not early_second_fast and fault != "missing-fast2"
        ):
            fast_indices.append(transaction("fast"))
        if fault == "duplicate-fast" and index == 1:
            fast_indices.append(transaction("fast"))
        op["normalization_requested_us"] = 99 + len(rows)
        norm = transaction("norm")
        notify(op["operation_id"] + "-normalization-gap")
        sector = bytes(range(256)) * 2
        if fault == "different-sectors" and index:
            sector = bytes([19]) * 512
        ring = synthetic_ring(
            op,
            sector,
            report["nor_offset"],
            previous=report["operations"][0]["dump_command"] if index else None,
        )
        if index and fault == "old-rows-new-failure":
            body = (
                first_ring.rstrip(b"\0")
                + b"\r\nfread read failed\r\n"
                + echo(op["producer"])
                + echo(op["dump_command"])
            )
            ring = body.ljust(4096, b"\0")
        if not index:
            first_ring = ring
        op["download_start"] = len(report["att_packets"])
        notify(op["operation_id"] + "-download-leading")
        emit("tx", b"\x52\x22\0" + P.frame(11, op["name"].encode().ljust(14, b"\0") + bytes(4)))
        emit("rx", b"\x1b\x24\0" + P.frame(11, b"\0" + struct.pack(">I", 4096)))
        for at in range(0, 4096, 244):
            emit("rx", b"\x1b\x2a\0" + ring[at : at + 244])
            if at == 0:
                notify(op["operation_id"] + "-download")
        slow = transaction_count
        rows.extend(remote(32, 48, 4, 600, identifier=7 + slow))
        transaction_count += 1
        if fault == "slow-update-in-window" and index:
            rows.append(update(48, 4, 600))
        emit("rx", b"\x1b\x24\0" + P.frame(11, b"\x02"))
        if not (fault == "slow-update-in-window" and index):
            rows.append(update(48, 4, 600))
        notify(op["operation_id"] + "-download-trailing")
        op["download_end"] = len(report["att_packets"])
        notify(op["operation_id"] + "-slow-gap")

        def during_identity():
            early_second_fast.append(transaction("fast"))

        identity(
            op,
            "after",
            info(index + 1),
            during_identity if fault == "fast-during-barrier" and not index else None,
        )
        op.update(
            verified_end=len(report["att_packets"]),
            download_bytes=4096,
            received_bytes=4096,
            download_sha256=A.sha(ring),
            state_verification=verify_state(info(index), info(index + 1), sd_write=True),
        )
        op["download_verification"] = A.download(report, op, ring)
        if fault != "old-rows-new-failure" or not index:
            op["verification"] = C.payload(report, op, ring)
        else:
            op["verification"] = copy.deepcopy(report["operations"][0]["verification"])
        directory = tmp_path / op["operation_id"]
        directory.mkdir()
        (directory / "download.bin").write_bytes(ring)
        (directory / "sector.bin").write_bytes(sector)
        indices.append((fast_indices, norm, slow))
        if index == 0:
            notify("between-operations")
    identity(report, "after", info(2))
    notify("final-tail")
    report["state_verification"] = verify_state(info(2), info(2), sd_write=False)
    if fault == "extra-transaction":
        transaction("fast")
    raw = H.HEADER + b"".join(
        record(packet, opcode, stamp=100 + i) for i, (opcode, packet) in enumerate(rows)
    )
    (tmp_path / "session.btsnoop").write_bytes(raw)
    observed = PW.inspect(raw, link=LINK, final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = dual_hci.bind(report, raw)
    report["startup_settlement"] = observed["transactions"][0]
    if "startup_policy" in report:
        report["startup_classification"] = V.startup.classify(
            report["startup_settlement"], policy=report["startup_policy"]
        )
    for op, (fast, norm, slow) in zip(report["operations"], indices, strict=True):
        op["pre_download_fast"] = [observed["transactions"][i] for i in fast]
        op["normalization"], op["slow_settlement"] = (
            observed["transactions"][norm],
            observed["transactions"][slow],
        )
    if startup == "default" and report["operations"][0]["pre_download_fast"]:
        first = report["operations"][0]
        first["default_activity_fast_verification"] = (
            {"forged_stale": True}
            if fault == "stale-first-fast"
            else V.default_activity_fast(
                report,
                first,
                report["startup_settlement"],
                first["pre_download_fast"][0],
                V.common.wire_positions(report, raw),
            )
        )
    return report


def validate(report, directory):
    from rcominote.experiments import window_nor_contract as C

    # Only pinned private parent replay is isolated. Actual recipe, NOR freshness,
    # state, Actions, ATT bytes, CID5 and HCI parser all execute normally.
    with patch.object(C, "validate_parents"):
        return V.validate(report, directory, directory / "synthetic-image")


@pytest.mark.parametrize("optional", [False, True])
def test_six_or_seven_complete_transactions_and_two_capacity_steps(tmp_path, optional):
    report = fixture(tmp_path, optional=optional)
    frozen = copy.deepcopy(report)
    result = validate(report, tmp_path)
    assert result == {
        "verified": True,
        "connections": 1,
        "parameter_transactions": 6 + optional,
        "listed_count": 0,
        "sd_writes": 2,
        "new_raw_nor_coverage_bytes": 0,
    }
    assert report == frozen and report["ok"] is False and report["pair_verified"] is False


def test_fast_during_previous_barrier_is_not_misattributed_to_current_actions(tmp_path):
    report = fixture(tmp_path, fault="fast-during-barrier")
    assert validate(report, tmp_path)["verified"]


def test_transport_audit_does_not_claim_equal_sectors_or_pair_coverage(tmp_path):
    report = fixture(tmp_path, fault="different-sectors")
    assert validate(report, tmp_path)["new_raw_nor_coverage_bytes"] == 0
    assert (tmp_path / "first/sector.bin").read_bytes() != (tmp_path / "second/sector.bin").read_bytes()


@pytest.mark.parametrize(
    "fault",
    [
        "missing-fast2",
        "duplicate-fast",
        "extra-transaction",
        "visible-collision",
        "slow-update-in-window",
        "old-rows-new-failure",
    ],
)
def test_whole_wire_or_freshness_counterexamples_rejected(tmp_path, fault):
    report = fixture(tmp_path, fault=fault)
    with pytest.raises(ValueError):
        validate(report, tmp_path)


@pytest.mark.parametrize(
    "fault",
    [
        "actions-gap",
        "download-gap",
        "barrier-alias",
        "final-alias",
        "late-invocation",
        "old-normalization",
        "old-slow",
        "old-fast",
        "pending-error",
        "incomplete",
        "sd-write-flag",
        "capacity",
        "monitor",
        "actions-proof",
        "sector-proof",
    ],
)
def test_mutated_receipt_cannot_reuse_old_evidence(tmp_path, fault):
    report = fixture(tmp_path)
    first, second = report["operations"]
    match fault:
        case "actions-gap":
            second["actions_start"] += 1
        case "download-gap":
            second["download_start"] += 1
        case "barrier-alias":
            second["after_span"] = first["after_span"]
        case "final-alias":
            report["after_span"] = first["after_span"]
        case "late-invocation":
            second["normalization_requested_us"] = 999999
        case "old-normalization":
            second["normalization"] = first["normalization"]
        case "old-slow":
            second["slow_settlement"] = first["slow_settlement"]
        case "old-fast":
            second["pre_download_fast"] = [report["startup_settlement"]]
        case "pending-error":
            second["cleanup_error"] = "failed STOP"
        case "incomplete":
            second["live_complete"] = False
        case "sd-write-flag":
            second["sd_write_attempted"] = False
        case "capacity":
            second["after"] = info(3)
        case "monitor":
            report["monitor_exit"] = 124
        case "actions-proof":
            second["actions_verification"] = {}
        case "sector-proof":
            second["verification"] = first["verification"]
    with pytest.raises(ValueError):
        validate(report, tmp_path)


@pytest.mark.parametrize(
    "file", ["first/download.bin", "second/download.bin", "second/sector.bin", "session.btsnoop"]
)
def test_raw_files_are_required_without_padding_or_partial_repair(tmp_path, file):
    report = fixture(tmp_path)
    path = tmp_path / file
    partial = path.read_bytes()[:-1]
    path.write_bytes(partial)
    with pytest.raises(ValueError):
        validate(report, tmp_path)
    assert path.read_bytes() == partial


def test_predecessor_gate_preserves_standalone_verification_and_receipt(tmp_path):
    report = fixture(tmp_path)
    standalone = validate(report, tmp_path)
    report["expected_before"] = copy.deepcopy(report["before"])
    report["predecessor_state_verification"] = verify_state(
        report["expected_before"], report["before"], sd_write=False
    )
    frozen = copy.deepcopy(report)
    assert validate(report, tmp_path) == standalone
    assert report == frozen


@pytest.mark.parametrize("fault", ["state", "forged-summary", "missing-summary", "orphan-summary"])
def test_predecessor_gate_fails_before_inventory_or_operations(tmp_path, fault):
    report = fixture(tmp_path)
    report["expected_before"] = copy.deepcopy(report["before"])
    report["predecessor_state_verification"] = verify_state(
        report["expected_before"], report["before"], sd_write=False
    )
    match fault:
        case "state":
            report["expected_before"] = info(1)
        case "forged-summary":
            report["predecessor_state_verification"] = {"verified": True}
        case "missing-summary":
            del report["predecessor_state_verification"]
        case "orphan-summary":
            del report["expected_before"]
    with (
        patch.object(V, "listed_nonce_gate", side_effect=AssertionError("Gate executed too late")),
        pytest.raises(ValueError),
    ):
        validate(report, tmp_path)
