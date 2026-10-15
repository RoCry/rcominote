"""Offline evidence gate for two known RAM-file downloads; never repairs receipts."""

import struct
from pathlib import Path

from rcominote import protocol as P
from rcominote.ble_target import OWNED_SERIAL
from rcominote.connection import validate_filename
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import param_window as windows
from rcominote.experiments import sd_warm_download as W
from rcominote.experiments import status_event as events
from rcominote.experiments.sd_bootstrap import verify_state

PROFILE = "per-download-window-known-ram4096"


def no_errors(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("error") and item:
                raise ValueError("Failed evidence cannot pass the window audit")
            no_errors(item)
    elif isinstance(value, list):
        for item in value:
            no_errors(item)


def span(report, value):
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(x) is not int for x in value)
        or not report["setup_end"] <= value[0] < value[1] <= len(report["att_packets"])
    ):
        raise ValueError("Invalid actual transaction span")
    return value


def file_list(report):
    start, end = span(report, report["file_list_span"])
    events.bridge(report, report["before_span"][1], start)
    rows = events.rows(report, start, end)
    if not rows:
        raise ValueError("File list requires an actual transaction")
    if rows[0]["direction"] != "tx" or bytes.fromhex(rows[0]["hex"]) != b"\x52\x22\0" + P.frame(
        P.GET_FILE_LIST
    ):
        raise ValueError("Expected exactly one actual file-list request")
    names, ended = set(), False
    for row in rows[1:]:
        packet = bytes.fromhex(row["hex"])
        if ended or row["direction"] != "rx" or packet[:3] != b"\x1b\x24\0":
            raise ValueError("Unrelated or late file-list traffic")
        command, payload = P.parse(packet[3:])
        if command != P.GET_FILE_LIST:
            raise ValueError("File-list reply command mismatch")
        if payload == b"\x02":
            ended = True
        elif len(payload) == 20 and payload[0] == 0:
            entry = P.parse_file_entry(payload)
            validate_filename(entry.name)
            if entry.name in names:
                raise ValueError("Duplicate actual file-list entry")
            names.add(entry.name)
        else:
            raise ValueError("Malformed or failed file-list reply")
    if not ended or type(report["listed_count"]) is not int or report["listed_count"] != len(names):
        raise ValueError("File list lacks complete terminator or correct entry count")
    return len(names)  # Never return the private inventory.


def wire_positions(report, raw):
    """Bind all ATT, then retain record bounds for causal checks across directions.

    Timestamps can invert across TX/RX. Do not sort/clamp them or use their
    global order instead of the original monitor record sequence.
    """
    stamps = dual_hci.timeline(report, raw)
    handle = report["transport"]["link"]["handle"]
    pending, packets = {}, {"tx": [], "rx": []}
    for number, opcode, stamp, packet in windows.records(raw, report["hci_capture"]["records"]):
        if opcode >> 16 or opcode & 0xFFFF not in (4, 5):
            continue
        word = int.from_bytes(packet[:2], "little")
        if word & 0xFFF != handle:
            continue
        direction = "tx" if opcode & 0xFFFF == 4 else "rx"
        if word >> 12 & 3 in (0, 2):
            pending[direction] = [number, bytearray()]
        first, body = pending[direction]
        body.extend(packet[4:])
        if len(body) >= 4:
            size, cid = struct.unpack_from("<HH", body)
            if len(body) == size + 4:
                if cid == 4:
                    packets[direction].append((first, number, stamp))
                del pending[direction]
    indices = {"tx": 0, "rx": 0}
    result = []
    for row, stamp in zip(report["att_packets"], stamps, strict=True):
        direction = row["direction"]
        value = packets[direction][indices[direction]]
        indices[direction] += 1
        if value[2] != stamp:
            raise ValueError("ATT record mapping differs from complete wire binding")
        result.append(value)
    return result


def transaction(value, *, origin, parameters):
    if value["origin"] != origin or windows.parameters(value["request"]) != parameters:
        raise ValueError("Unexpected parameter transaction order or tuple")
    if origin == "host" and (value["request"]["min_length"], value["request"]["max_length"]) != (1, 1):
        raise ValueError("Normalization must preserve explicit CE hints1/1")


def validate(report: dict, out: Path, image: Path) -> dict:
    """Audit a live candidate without changing it; replay must separately require original ok."""
    no_errors(report)
    events.verify(report)
    if (
        report.get("profile") != PROFILE
        or report.get("serial") != OWNED_SERIAL
        or report.get("name") != W.NAME
        or report.get("source_image_sha256") != W.IMAGE_SHA
        or report.get("expected_sha256") != W.ORACLE_SHA
        or report.get("sd_write_attempted") is not False
    ):
        raise ValueError("Requires fixed read-only known RAM4096 experiment")
    oracle, parent = W.validate_inputs(image, Path(report["parent"]["directory"]))
    if report["parent"] != parent:
        raise ValueError("Fixed RAM parent/source chain changed")
    if report["monitor_exit"] != 0 or report["monitor_stop"] != {
        "signal": "SIGINT",
        "requested": True,
        "delivery": "sent",
    }:
        raise ValueError("Capture did not finish cleanly")
    raw = (out / "session.btsnoop").read_bytes()
    observed = windows.inspect(raw, link=report["transport"]["link"], final=True)
    if observed["pending"] or report["hci_capture"] != {
        "bytes": len(raw),
        "sha256": A.sha(raw),
        "records": observed["records"],
    }:
        raise ValueError("Incomplete logical HCI settlement or changed complete capture")
    if A.setup(report) != report["gatt_proof"]:
        raise ValueError("Actual session GATT proof changed")
    if report["att_hci_binding"] != dual_hci.bind(report, raw):
        raise ValueError("Actual complete ATT/HCI binding changed")
    wire = wire_positions(report, raw)
    if any(event["record"] <= max(p[1] for p in wire) for event in observed["disconnects"]):
        raise ValueError("Disconnect before the final actual ATT packet")
    transactions = observed["transactions"]
    if len(transactions) != 5:
        raise ValueError("Requires exactly startup, host1, slow1, host2, slow2 transactions")
    warm = transactions[0]
    transaction(warm, origin="remote", parameters=(6, 12, 0, 500))
    if report["startup_settlement"] != warm:
        raise ValueError("Startup settlement differs from complete actual transaction")
    if span(report, report["before_span"])[0] != report["setup_end"]:
        raise ValueError("Initial identity must immediately follow real setup")
    A.identity(report, report, "before")
    verify_state(report["before"], report["before"], sd_write=False)
    if events.enabled(report):
        verify_state(report["expected_before"], report["before"], sd_write=False)
    count = file_list(report)
    operations = report["operations"]
    if len(operations) != 2 or [op["operation_id"] for op in operations] != ["first", "second"]:
        raise ValueError("Requires exactly two independent download transactions")
    boundary, before, previous = report["file_list_span"][1], report["before"], warm
    proofs = []
    for index, op in enumerate(operations):
        normalization, slow = transactions[1 + 2 * index : 3 + 2 * index]
        transaction(normalization, origin="host", parameters=(6, 6, 0, 500))
        transaction(slow, origin="remote", parameters=(32, 48, 4, 600))
        if (
            op.get("live_complete") is not True
            or op["name"] != W.NAME
            or op["before"] != before
            or op["download_start"] != boundary
            or op["normalization"] != normalization
            or op["slow_settlement"] != slow
        ):
            raise ValueError("Download boundary, identity or parameter transaction changed")
        if (
            not previous["update"]["timestamp_us"]
            <= op["normalization_requested_us"]
            <= normalization["request"]["timestamp_us"]
        ):
            raise ValueError("Normalization invocation precedes settlement or follows its wire request")
        data = (out / op["operation_id"] / "download.bin").read_bytes()
        if data != oracle or (op["download_bytes"], op["received_bytes"], op["download_sha256"]) != (
            4096,
            4096,
            A.sha(oracle),
        ):
            raise ValueError("Each complete download must equal the independent RAM oracle")
        proof = A.download(report, op, data, minimum_start=report["setup_end"])
        if op["download_trace_verification"] != proof:
            raise ValueError("Actual complete download trace proof changed")
        after_span = span(report, op["after_span"])
        if after_span != [op["download_end"], op["verified_end"]]:
            raise ValueError("Post-download identity is not the immediate actual barrier")
        start, end = wire[op["download_start"]], wire[op["download_end"] - 1]
        if not (
            previous["update"]["record"]
            < normalization["request"]["record"]
            < normalization["update"]["record"]
            < start[0]
            <= slow["remote_request"]["records"][0]
            and wire[boundary - 1][1] < normalization["request"]["record"]
            and end[1] < slow["update"]["record"] < wire[after_span[0]][0]
            and normalization["update"]["timestamp_us"] < start[2] <= slow["remote_request"]["timestamp_us"]
            and end[2] < slow["update"]["timestamp_us"] < wire[after_span[0]][2]
        ):
            raise ValueError(
                "Effective parameters changed inside download or settlement/barrier order failed"
            )
        A.identity(report, op, "after")
        if op["state_verification"] != verify_state(before, op["after"], sd_write=False):
            raise ValueError("Read-only per-download state proof changed")
        proofs.append({"operation_id": op["operation_id"], "bytes": 4096, "sha256": A.sha(data)})
        boundary, before, previous = op["verified_end"], op["after"], slow
    if span(report, report["after_span"]) != [boundary, len(report["att_packets"])]:
        raise ValueError("Final identity must consume exactly the complete remaining ATT tail")
    A.identity(report, report, "after")
    if report["state_verification"] != verify_state(report["before"], report["after"], sd_write=False):
        raise ValueError("Final read-only state proof changed")
    return {
        "verified": True,
        "connections": 1,
        "downloads": proofs,
        "parameter_transactions": 5,
        "listed_count": count,
        "sd_writes": 0,
        "new_raw_nor_coverage_bytes": 0,
    }
