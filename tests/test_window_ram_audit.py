"""Artificial complete ATT/HCI captures only; no private inventory or device I/O."""

import copy
import struct
from unittest.mock import patch

import pytest
from test_dual_probe import setup
from test_hci_interval import connection, event, record
from test_param_window import CONTROL, LINK, STATUS, command, fragment, remote, update
from test_sd_nor_probe import info

from rcominote import protocol as P
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import hci_interval as H
from rcominote.experiments import param_window as PW
from rcominote.experiments import window_ram_audit as V
from rcominote.experiments.sd_bootstrap import verify_state

ORACLE = bytes(range(256)) * 16
PARENT = {"directory": "/synthetic-parent", "unit_test_fixture": True}


def fixture(tmp_path, *, fault=None):
    """Build independently framed HCI, including CID5 signaling and all ATT."""
    report = setup()
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

    report.update(
        profile=V.PROFILE,
        serial=V.OWNED_SERIAL,
        name=V.W.NAME,
        source_image_sha256=V.W.IMAGE_SHA,
        expected_sha256=V.W.ORACLE_SHA,
        parent=copy.deepcopy(PARENT),
        sd_write_attempted=False,
        ok=False,
        transport={"link": LINK},
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
        operations=[],
    )
    identity(report, "before")
    start = len(report["att_packets"])
    emit("tx", b"\x52\x22\0" + P.frame(10))
    entry = b"\0" + b"test-recording".ljust(14, b"\0") + struct.pack(">I", 42) + b"\0"
    emit("rx", b"\x1b\x24\0" + P.frame(10, entry))
    if fault == "duplicate-list":
        emit("rx", b"\x1b\x24\0" + P.frame(10, entry))
    emit("rx", b"\x1b\x24\0" + P.frame(10, b"\x02"))
    report.update(file_list_span=[start, len(report["att_packets"])], listed_count=1)
    rows.extend(remote() + [update(12)])
    for index, name in enumerate(("first", "second")):
        op = {"operation_id": name, "name": V.W.NAME, "before": info(), "live_complete": True}
        op["normalization_requested_us"] = 99 + len(rows)
        rows.extend([command(), STATUS, update()])
        op["download_start"] = len(report["att_packets"])
        if fault == "remote-before-download" and index == 1:
            rows.extend(remote(32, 48, 4, 600, identifier=9))
        emit("tx", b"\x52\x22\0" + P.frame(11, V.W.NAME.encode().ljust(14, b"\0") + bytes(4)))
        emit("rx", b"\x1b\x24\0" + P.frame(11, b"\0" + struct.pack(">I", 4096)))
        for at in range(0, 4096, 244):
            emit("rx", b"\x1b\x2a\0" + ORACLE[at : at + 244])
        if not (fault == "remote-before-download" and index == 1):
            rows.extend(remote(32, 48, 4, 600, identifier=8 + index))
        if fault == "slow-apply-in-window" and index == 1:
            rows.append(update(48, 4, 600))
        emit("rx", b"\x1b\x24\0" + P.frame(11, b"\x02"))
        op["download_end"] = len(report["att_packets"])
        if not (fault == "slow-apply-in-window" and index == 1):
            rows.append(update(48, 4, 600))
        identity(op, "after")
        op.update(
            verified_end=len(report["att_packets"]),
            download_bytes=4096,
            received_bytes=4096,
            download_sha256=A.sha(ORACLE),
            state_verification=verify_state(info(), info(), sd_write=False),
        )
        op["download_trace_verification"] = A.download(report, op, ORACLE, minimum_start=report["setup_end"])
        directory = tmp_path / name
        directory.mkdir()
        (directory / "download.bin").write_bytes(ORACLE)
        report["operations"].append(op)
    identity(report, "after")
    report["state_verification"] = verify_state(info(), info(), sd_write=False)
    if fault == "extra-transaction":
        rows.extend([command(), STATUS, update()])
    if fault == "cleanup-disconnect":
        rows.append((3, event(5, struct.pack("<BHB", 0, LINK["handle"], 0x16))))
    raw = H.HEADER + b"".join(record(p, op, stamp=100 + i) for i, (op, p) in enumerate(rows))
    (tmp_path / "session.btsnoop").write_bytes(raw)
    observed = PW.inspect(raw, link=LINK, final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
    report["startup_settlement"] = observed["transactions"][0]
    for index, op in enumerate(report["operations"]):
        op["normalization"], op["slow_settlement"] = observed["transactions"][1 + 2 * index : 3 + 2 * index]
    report["att_hci_binding"] = dual_hci.bind(report, raw)
    return report


def validate(report, directory):
    # Isolate only the independently tested pinned-image/parent loader. All
    # GATT, identities, file list, download, HCI and transaction audits are real.
    with patch.object(V.W, "validate_inputs", return_value=(ORACLE, PARENT)):
        return V.validate(report, directory, directory / "synthetic-image")


@pytest.mark.parametrize("cleanup", [False, True])
def test_complete_two_downloads_allow_slow_request_before_end_but_apply_after(tmp_path, cleanup):
    report = fixture(tmp_path, fault="cleanup-disconnect" if cleanup else None)
    frozen = copy.deepcopy(report)
    result = validate(report, tmp_path)
    assert result["verified"] and result["parameter_transactions"] == 5
    assert result["sd_writes"] == result["new_raw_nor_coverage_bytes"] == 0
    assert [v["sha256"] for v in result["downloads"]] == [A.sha(ORACLE)] * 2
    assert report == frozen and report["ok"] is False
    assert "test-recording" not in str(result)


@pytest.mark.parametrize(
    "fault", ["slow-apply-in-window", "remote-before-download", "extra-transaction", "duplicate-list"]
)
def test_complete_wire_counterexamples_rejected(tmp_path, fault):
    report = fixture(tmp_path, fault=fault)
    with pytest.raises(ValueError):
        validate(report, tmp_path)


@pytest.mark.parametrize(
    "fault",
    [
        "error",
        "nested-error",
        "incomplete-second",
        "name",
        "source",
        "parent",
        "sd-write",
        "capture",
        "binding",
        "setup",
        "count",
        "startup",
        "normalization",
        "requested",
        "slow",
        "bytes",
        "hash",
        "span",
        "barrier-alias",
        "final-alias",
        "state",
        "monitor-timeout",
        "monitor-exited",
        "operation-id",
    ],
)
def test_receipt_mutations_cannot_promote_incomplete_or_misattributed_evidence(tmp_path, fault):
    report = fixture(tmp_path)
    first, second = report["operations"]
    match fault:
        case "error":
            report["after_error"] = "failure"
        case "nested-error":
            second["detail"] = {"decode_error": "failure"}
        case "incomplete-second":
            second["live_complete"] = False
        case "name":
            second["name"] = "other"
        case "source":
            report["source_image_sha256"] = "0" * 64
        case "parent":
            report["parent"]["unit_test_fixture"] = False
        case "sd-write":
            report["sd_write_attempted"] = True
        case "capture":
            report["hci_capture"]["records"] -= 1
        case "binding":
            report["att_hci_binding"]["packets"] -= 1
        case "setup":
            report["gatt_proof"]["setup_end"] -= 1
        case "count":
            report["listed_count"] = 0
        case "startup":
            report["startup_settlement"] = second["slow_settlement"]
        case "normalization":
            second["normalization"] = first["normalization"]
        case "requested":
            second["normalization_requested_us"] = 0
        case "slow":
            second["slow_settlement"] = first["slow_settlement"]
        case "bytes":
            second["received_bytes"] = 3852
        case "hash":
            second["download_sha256"] = "0" * 64
        case "span":
            second["download_start"] += 1
        case "barrier-alias":
            second["after_span"] = first["after_span"]
        case "final-alias":
            report["after_span"] = first["after_span"]
        case "state":
            second["state_verification"] = {}
        case "monitor-timeout":
            report["monitor_exit"] = 124
        case "monitor-exited":
            report["monitor_stop"] = {"signal": "SIGINT", "requested": False, "delivery": "already-exited"}
        case "operation-id":
            second["operation_id"] = "../first"
    with pytest.raises(ValueError):
        validate(report, tmp_path)


@pytest.mark.parametrize("file", ["first/download.bin", "second/download.bin", "session.btsnoop"])
def test_original_file_mutation_is_never_filled_or_repaired(tmp_path, file):
    report = fixture(tmp_path)
    path = tmp_path / file
    original = path.read_bytes()
    path.write_bytes(original[:-1])
    with pytest.raises(ValueError):
        validate(report, tmp_path)
    assert path.read_bytes() == original[:-1]
