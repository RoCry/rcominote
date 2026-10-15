"""Original full-wire proof of one baseline and two fixed known overwrites."""

import re
from datetime import datetime
from itertools import pairwise
from pathlib import Path

from rcominote import protocol as Boyi
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import param_window as P
from rcominote.experiments import scratch_reuse_contract as C
from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as E
from rcominote.experiments import window_nor_audit as W
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state


def actions(report, op):
    proof = A.action_frames(report, op, expected=C.recipe(op))
    # Retain every original F0 byte and its ATT index. F0 frame boundaries need
    # not coincide with lines or notifications; no background text is dropped.
    raw, origins, writes = bytearray(), [], []
    for index in E.indices(report, op["actions_start"], op["actions_end"]):
        row = report["att_packets"][index]
        packet = bytes.fromhex(row["hex"])
        if row["direction"] == "tx":
            writes.append(index)
        elif packet[:3] == b"\x1b\x18\0":
            raw.extend(packet[3:])
            origins.extend([index] * (len(packet) - 3))
    text, positions = bytearray(), []
    cursor = 0
    for frame in op["frames"]:
        value = bytes.fromhex(frame["hex"])
        if bytes(raw[cursor : cursor + len(value)]) != value:
            raise ValueError("Original Actions frame byte boundaries changed")
        if frame["command"] == 0xF0:
            text.extend(value[8:])
            positions.extend(origins[cursor + 8 : cursor + len(value)])
        cursor += len(value)
    lines = list(re.finditer(rb"(?<![^\r\n])Uptime: [0-9]+ ms\r?\n", text))
    if len(lines) != 1 or bytes(text).count(b"Uptime:") != 1 or positions[lines[0].start()] <= writes[2]:
        raise ValueError("Requires one complete actual uptime F0 line after its command")
    proof["uptime"] = {
        "text_sha256": A.sha(bytes(text)),
        "bytes": len(text),
        "line_hex": lines[0][0].hex(),
        "att_span": [positions[lines[0].start()], positions[lines[0].end() - 1] + 1],
        "command_att_index": writes[2],
        "value_used_for_freshness": False,
    }
    return proof


def download(report, op, directory):
    raw = (directory / op["operation_id"] / "download.bin").read_bytes()
    if len(raw) != 4096 or (op["download_bytes"], op["received_bytes"], op["download_sha256"]) != (
        4096,
        4096,
        A.sha(raw),
    ):
        raise ValueError("Every scratch download requires exact declared/received4096 bytes")
    if op["download_verification"] != A.download(report, op, raw, minimum_start=report["setup_end"]):
        raise ValueError("Original exclusive Boyi download changed")
    return raw


def barrier(report, op, before, *, writing):
    E.bridge(report, op["download_end"], op["after_span"][0])
    A.identity(report, op, "after")
    if op["verified_end"] != op["after_span"][1] or op["state_verification"] != verify_state(
        before, op["after"], sd_write=writing
    ):
        raise ValueError("Immediate original identity/state barrier changed")


def baseline_window(report, op, wire, startup_tx, normal, slow):
    common.transaction(normal, origin="host", parameters=(6, 6, 0, 500))
    common.transaction(slow, origin="remote", parameters=W.SLOW)
    first, last = E.edge(report, op["download_start"], op["download_end"])
    barrier_first, _ = E.edge(report, *op["after_span"])
    if (
        op["normalization"] != normal
        or op["slow_settlement"] != slow
        or not startup_tx["update"]["record"]
        < normal["request"]["record"]
        < normal["update"]["record"]
        < wire[first][0]
        <= slow["remote_request"]["records"][0]
        or not wire[last][1] < slow["update"]["record"] < wire[barrier_first][0]
        or not startup_tx["update"]["timestamp_us"]
        <= op["normalization_requested_us"]
        <= normal["request"]["timestamp_us"]
        or not normal["update"]["timestamp_us"] < wire[first][2] <= slow["remote_request"]["timestamp_us"]
        or not wire[last][2] < slow["update"]["timestamp_us"] < wire[barrier_first][2]
    ):
        raise ValueError("Baseline FAST/normalization/download/SLOW/barrier window changed")


def inventory(report, plan):
    count = common.file_list(report)
    forbidden = {F.NAME, *(slot["nonce"] for slot in plan["operations"])}
    for row in E.rows(report, *report["file_list_span"])[1:]:
        _, payload = Boyi.parse(bytes.fromhex(row["hex"])[3:])
        if payload[:1] == b"\0" and Boyi.parse_file_entry(payload).name in forbidden:
            raise ValueError("Visible inventory collides with dedicated scratch/nonce")
    return count


def stages(report, directory, plan, baseline, observed, wire):
    transactions = observed["transactions"]
    if len(transactions) != 9:
        raise ValueError("Requires exactly nine complete FAST/host/SLOW transactions")
    warm = transactions[0]
    classification = startup.classify(warm)
    if report["startup_settlement"] != warm or report["startup_classification"] != classification:
        raise ValueError("Actual startup must retain original strict FAST classification")
    if inventory(report, plan) != report["listed_count"]:
        raise ValueError("Original visible file inventory changed")
    E.bridge(report, report["before_span"][1], report["file_list_span"][0])
    op = report["baseline"]
    if (
        op.get("name") != F.NAME
        or op.get("operation_id") != "baseline"
        or any(key in op for key in ("actions_start", "producer", "sd_write_attempted"))
    ):
        raise ValueError("Baseline permits only the fixed readonly download")
    E.bridge(report, report["file_list_span"][1], op["download_start"])
    previous = download(report, op, directory)
    if previous != baseline or op["before"] != report["before"]:
        raise ValueError("Actual readonly baseline differs from original complete owned object")
    F.absent(previous, [slot["nonce"] for slot in plan["operations"]])
    baseline_window(report, op, wire, warm, transactions[1], transactions[2])
    barrier(report, op, report["before"], writing=False)
    state, boundary, previous_tx, cursor = op["after"], op["verified_end"], transactions[2], 3
    previous_end = op["ended_at"]
    for slot, op in zip(plan["operations"], report["operations"], strict=True):
        if (
            any(op.get(key) != value for key, value in slot.items())
            or op.get("sd_write_attempted") is not True
            or op["before"] != state
        ):
            raise ValueError("Original overwrite recipe, SD attempt or predecessor state changed")
        J.time_order(previous_end, op["started_at"], op["ended_at"])
        E.bridge(report, boundary, op["actions_start"])
        E.bridge(report, op["actions_end"], op["download_start"])
        if op["actions_verification"] != actions(report, op):
            raise ValueError("Original six-ACK/F1/uptime proof changed")
        normal, slow, cursor = W.parameter_stage(
            transactions, cursor, op, previous_tx, first_fast_required=True
        )
        fast = op["pre_download_fast"][0]
        if op["activity_fast_verification"] != W.default_activity_fast(report, op, previous_tx, fast, wire):
            raise ValueError("FAST request precedes current Actions or previous settlement")
        raw = download(report, op, directory)
        decoded = C.payload(op, raw, previous, plan)
        if decoded != op["verification"] or (
            directory / op["operation_id"] / "sector.bin"
        ).read_bytes() != bytes.fromhex(decoded["sector_hex"]):
            raise ValueError("Current retained ring/sector proof differs from independent replay")
        if op["operation_id"] == "first":
            F.absent(raw, [plan["operations"][1]["nonce"]])
        W.download_window(wire, op, normal, slow, report=report)
        barrier(report, op, state, writing=True)
        previous, state, boundary, previous_tx, previous_end = (
            raw,
            op["after"],
            op["verified_end"],
            slow,
            op["ended_at"],
        )
    if cursor != 9:
        raise ValueError("Unconsumed parameter transaction")
    return state, boundary


def validate(report, directory: Path, plan, baseline: bytes):
    C.validate_plan(plan)
    common.no_errors(report)
    if (
        report.get("profile") != C.PROFILE
        or report.get("budget") != C.BUDGET
        or report.get("stage_timeout_scope") != C.STAGE_SCOPE
        or report.get("startup_policy") != startup.LEGACY_POLICY
        or report.get("status_event_policy") != E.POLICY
        or report.get("expected_before") != plan["expected_before"]
        or report.get("monitor_exit") != 0
        or report.get("monitor_stop") != {"signal": "SIGINT", "requested": True, "delivery": "sent"}
    ):
        raise ValueError("Fixed scratch profile, policy, predecessor or clean monitor changed")
    for op in [report["baseline"], *report["operations"]]:
        if op.get("live_complete") is not True:
            raise ValueError("Every stage must originally complete before success audit")
        J.time_order(report["started_at"], op["started_at"], op["ended_at"], report["ended_at"])
        if (
            datetime.fromisoformat(op["ended_at"]) - datetime.fromisoformat(op["started_at"])
        ).total_seconds() > 18:
            raise ValueError("Original post-startup transfer stage exceeds18-second deadline")
    rows = report["att_packets"]
    if any(type(row["monotonic_ns"]) is not int for row in rows) or any(
        a["monotonic_ns"] > b["monotonic_ns"] for a, b in pairwise(rows)
    ):
        raise ValueError("Original host ATT timestamps must be monotonic")
    _, events = E.verify(report)
    raw = (directory / "session.btsnoop").read_bytes()
    observed = P.inspect(raw, link=report["transport"]["link"], final=True)
    if (
        observed["pending"]
        or report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
        or report["gatt_proof"] != A.setup(report)
        or report["att_hci_binding"] != dual_hci.bind(report, raw)
    ):
        raise ValueError("Incomplete or changed original GATT/ATT/HCI/parameter evidence")
    wire = common.wire_positions(report, raw)
    disconnects = observed["disconnects"]
    if (
        len(disconnects) != 1
        or disconnects[0]["status"] != 0
        or disconnects[0]["reason"] != 0x16
        or disconnects[0]["record"] <= max(p[1] for p in wire)
        or report.get("disconnect_observation")
        != {"observed": True, "event": disconnects[0], "max_wait_seconds": 8}
    ):
        raise ValueError("Requires sole normal local disconnect after final ATT")
    requested, completed, recorded = [
        report[k] for k in ("close_requested_us", "close_completed_us", "disconnect_observed_us")
    ]
    if (
        not requested <= completed <= recorded <= completed + 8_000_000
        or not requested <= disconnects[0]["timestamp_us"] <= completed + 8_000_000
    ):
        raise ValueError("Original disconnect observation exceeds bounded close timing")
    E.bridge(report, report["setup_end"], report["before_span"][0])
    A.identity(report, report, "before")
    if report["predecessor_state_verification"] != verify_state(
        plan["expected_before"], report["before"], sd_write=False
    ):
        raise ValueError("Initial actual state differs from immutable predecessor")
    state, boundary = stages(report, directory, plan, baseline, observed, wire)
    E.bridge(report, boundary, report["after_span"][0])
    A.identity(report, report, "after")
    E.bridge(report, report["after_span"][1], len(rows))
    if report["state_verification"] != verify_state(state, report["after"], sd_write=False):
        raise ValueError("Final state differs from last successful overwrite")
    return {
        "verified": True,
        "connections": 1,
        "downloads": 3,
        "sd_writes": 2,
        "new_files": 0,
        "known_offsets": [0, 0x4200],
        "parameter_transactions": 9,
        "startup_mode": "fast",
        "new_raw_nor_coverage_bytes": 0,
        "status_events": events,
    }
