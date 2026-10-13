#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["bleak>=1.1,<2", "typer>=0.16,<1"]
# ///
"""Independently validate raw Android callbacks; never repair a failed stream."""

import hashlib
import json
import sys
from itertools import pairwise
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rcominote.log_probe import NOTIFY, PREPARE
from rcominote.log_stream import Stream
from rcominote.protocol import (
    GET_DEVICE_INFO,
    GET_SERIAL,
    NOTIFY_CMD,
    WRITE,
    frame,
    parse,
    parse_device_info,
    text,
)

START = bytes.fromhex("1d108105000002002000")
HELP = bytes.fromhex("1d1081070001040068656c70")
STOP = bytes.fromhex("1d108105000002002100")
LOG_WRITE = "e49a3002-f69a-11e8-8eb2-f2801f1b9fd1"
BASELINE = Path(__file__).resolve().parents[1] / "docs/evidence/log-commands-2026-10-12.json"


def verify(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) > 512 * 1024 or not raw.endswith(b"\n"):
        raise ValueError("Oversized or incomplete Android JSONL")
    rows = [json.loads(line) for line in raw.splitlines()]
    if not 1 <= len(rows) <= 1024 or rows[0]["event"] != "session":
        raise ValueError("Missing session or unexpected record count")
    session = rows[0]
    if session["serial"] != "C261CF0430" or session["mode"] not in {"info", "help"}:
        raise ValueError("Unexpected target or mode")
    times = [row["elapsed_ns"] for row in rows]
    if any(b < a for a, b in pairwise(times)):
        raise ValueError("Non-monotonic persisted event times")
    results = [row for row in rows if row["event"] == "result"]
    if len(results) != 1:
        raise ValueError("Experiment did not persist exactly one final result")
    result = results[0]
    errors = [row for row in rows if row["event"] in {"error", "cleanup_error", "close_error"}]
    boyi = [
        parse(bytes.fromhex(row["hex"]))
        for row in rows
        if row["event"] == "notify" and row["characteristic"] == NOTIFY_CMD
    ]
    serials = [text(payload) for cmd, payload in boyi if cmd == GET_SERIAL]
    infos = [parse_device_info(payload) for cmd, payload in boyi if cmd == GET_DEVICE_INFO]
    identity_ok = serials == [session["serial"]]
    before_ok = bool(infos and infos[0]["version"] == "010004" and infos[0]["recording_state"] == "idle")
    states_match = len(infos) == 2 and infos[0] == infos[1]
    writes = [(row["characteristic"], row["hex"]) for row in rows if row["event"] == "write"]
    expected = [(WRITE, frame(GET_SERIAL).hex()), (WRITE, frame(GET_DEVICE_INFO).hex())]
    if session["mode"] == "help":
        expected += [(LOG_WRITE, packet.hex()) for packet in (PREPARE, START, HELP, STOP)]
        expected += [(WRITE, frame(GET_DEVICE_INFO).hex())]
    stream = Stream()
    notifications = [
        bytes.fromhex(row["hex"])
        for row in rows
        if row["event"] == "notify" and row["characteristic"] == NOTIFY
    ]
    parse_error = None
    failure_index = None
    for index, packet in enumerate(notifications):
        if parse_error is not None:
            continue  # Preserve raw tail; no resynchronization after first failure.
        try:
            if stream.ended:
                raise ValueError("Actions data after F1")
            stream.feed(packet)
        except ValueError as error:
            parse_error = str(error)
            failure_index = index
    baseline_raw = BASELINE.read_bytes()
    baseline = json.loads(baseline_raw)
    expected_f0 = [row["hex"] for row in baseline["frames"] if row["command"] == 0xF0][:3]
    observed_f0 = [row["hex"] for row in stream.frames if row["command"] == 0xF0]
    help_matches = observed_f0 == expected_f0
    strict_ok = parse_error is None and stream.acks == 4 and stream.ended and not stream.pending
    capture_ok = (
        identity_ok
        and before_ok
        and not errors
        and writes == expected
        and result["ok"] is True
        and (session["mode"] == "info" or (strict_ok and help_matches and states_match))
    )
    return {
        "scope": "Offline Android raw-callback validation; no hardware, inferred bytes or repaired captures",
        "capture_sha256": hashlib.sha256(raw).hexdigest(),
        "baseline_sha256": hashlib.sha256(baseline_raw).hexdigest(),
        "mode": session["mode"],
        "app_result": result,
        "identity_verified": identity_ok,
        "idle_fw010004_before": before_ok,
        "info_responses": len(infos),
        "before_after_full_info_match": states_match,
        "fixed_writes_match": writes == expected,
        "fixed_write_prefix_match": writes == expected[: len(writes)],
        "actions_notification_lengths": [len(packet) for packet in notifications],
        "strict_parse_error": parse_error,
        "first_failed_notification_index": failure_index,
        "strict_acks": stream.acks,
        "strict_end": stream.ended,
        "strict_pending_hex": stream.pending.hex(),
        "f0_lengths": [len(bytes.fromhex(value)) for value in observed_f0],
        "help_matches_independent_baseline": help_matches,
        "errors": errors,
        "ok": capture_ok,
        "limits": [
            "Android callbacks are host observations, not over-the-air or device-side transmission evidence",
            "Exact help comparison is against a pinned independent session; changed text alone is not proof of loss",
            "Failed capture remains failed even if STOP ACK/F1 occur later in raw notifications",
            "No full NOR, throughput, recovery or custom firmware capability follows from this experiment",
        ],
    }


def main(path: Path, out: Path | None = None):
    report = verify(path)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if out is not None:
        with out.open("x") as file:
            file.write(encoded)
    print(encoded, end="")
    if not report["ok"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
