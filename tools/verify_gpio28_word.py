#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Replay pinned minimal GPIO28 word evidence offline; no device operations."""

import argparse
import gzip
import json
import re
from datetime import datetime
from pathlib import Path

from verify_logsrv_slot import GLOBAL, IMAGE_SHA, POINTER, check, context, sha
from verify_logsrv_slot import replay as replay_previous

RECEIPT_SHA = "986bbdbe1d9b57be02092cd69a51876d50ca77fac0fd9d2dae2c12f322273128"
ADDRESS = 0x40068074


def replay(receipt: Path, private_root: Path | None = None) -> dict:
    raw = receipt.read_bytes()
    check(sha(raw) == RECEIPT_SHA, "Pinned GPIO28 receipt changed")
    data = json.loads(raw)
    check(data["serial"] == "C261CF0430", "Wrong owned device")
    failed = data["failed_attempts"]
    check(
        [row["kind"] for row in failed] == ["discovery-timeout", "offline-invocation-error"],
        "Failure history changed",
    )
    for row in failed:
        check(
            row["original_ok"] is False
            and row["sd_write_attempted"] is False
            and row["actual_att_writes"] == row["actual_gpio_reads"] == row["downloaded_files"] == 0,
            "Prior failure cannot count as GPIO execution",
        )
    check(
        failed[0]["device_io"] is True
        and failed[0]["before_present"] is True
        and failed[0]["last_tx"] == "08140019000328"
        and failed[0]["error_class"] == "TimeoutError"
        and failed[0]["state"]["other_state_equal"] is True
        and failed[0]["state"]["free_capacity_decrease"] == 0,
        "Discovery failure boundary changed",
    )
    check(
        failed[1]["device_io"] is False
        and failed[1]["before_present"] is False
        and failed[1]["att_packets"] == 0
        and failed[1]["error_class"] == "FileNotFoundError",
        "Offline invocation must not count as device experiment",
    )
    check(
        data["attempt_accounting"]
        == {
            "invocations": 3,
            "radio_connections": 2,
            "gpio_read_invocations": 1,
            "offline_invocation_failures": 1,
        },
        "Invocation accounting changed",
    )
    prior = data["prior_slot_bundle"]
    check(sha((receipt.parent / prior["file"]).read_bytes()) == prior["sha256"], "Prior guard bundle changed")
    replay_previous(receipt.parent / prior["file"])
    image = gzip.decompress((receipt.parent / data["image"]["file"]).read_bytes())
    check(
        len(image) == 927632 and sha(image) == IMAGE_SHA == data["image"]["sha256"], "Wrong full image oracle"
    )

    static_ref = data["later_static_evidence"]
    static_raw = (receipt.parent / static_ref["file"]).read_bytes()
    check(sha(static_raw) == static_ref["sha256"], "Later static remux evidence changed")
    later = json.loads(static_raw)
    check(later["image_sha256"] == IMAGE_SHA and len(later["regions"]) == 9, "Wrong static remux profile")
    for region in later["regions"]:
        start, end = (int(region[key], 16) for key in ("address", "end_exclusive"))
        offset, expected = region["file_offset"], bytes.fromhex(region["hex"])
        check(
            start - 0x10000000 == offset
            and 0 <= offset < offset + end - start <= len(image)
            and end - start == len(expected)
            and image[offset : offset + len(expected)] == expected
            and sha(expected) == region["sha256"],
            "Static remux region bounds/raw/hash differ from image",
        )

    def sample(record: dict) -> bytes:
        value = (receipt.parent / record["file"]).read_bytes()
        check(
            len(value) == record["bytes"] and sha(value) == record["sha256"],
            "Public sample size/hash mismatch",
        )
        return value

    guards, preflight, trial = data["word_code_guards"], data["fresh_preflight"], data["trial"]
    check(
        len(guards) == 2
        and {int(row["source_address"], 16): row["source_bytes"] for row in guards}
        == {0x100A18EE: 10, 0x100251AA: 24},
        "Wrong fixed mdw guards",
    )
    for row in guards:
        offset = int(row["source_address"], 16) - 0x10000000
        check(
            sample(row["raw"]) == image[offset : offset + row["source_bytes"]],
            "Live mdw guard differs from image",
        )
    stages = guards + list(preflight.values()) + [trial]
    times = {}
    for row in stages:
        count = 7 if row is trial else 4
        check(
            row["original_ok"] is True
            and row["actions"]
            == {"confirmed_writes": count, "ack_count": count, "f1_received": True, "pending_bytes": 0},
            "Incomplete compact Actions proof",
        )
        state = row["state"]
        check(
            state["other_state_equal"] is True
            and state["free_capacity_before"] - state["free_capacity_after"]
            == state["free_capacity_decrease"]
            and 0 <= state["free_capacity_decrease"] <= state["allowed_decrease"] == 1,
            "Unexpected compact state comparison",
        )
        start, end = (datetime.fromisoformat(row[key]) for key in ("started_at", "ended_at"))
        check(
            start.utcoffset() is not None and end.utcoffset() is not None and start <= end,
            "Invalid evidence timestamps",
        )
        times[id(row)] = (start, end)
    pointer_start, pointer_end = times[id(preflight["pointer"])]
    context_start, context_end = times[id(preflight["context"])]
    prior_end = datetime.fromisoformat(data["prior_guards_latest_end"])
    check(
        prior_end.utcoffset() is not None
        and max(prior_end, *(times[id(row)][1] for row in guards)) <= pointer_start
        and pointer_end <= context_start
        and context_end <= times[id(trial)][0],
        "Chronology differs from guards→pointer→context→trial",
    )
    check(
        sample(preflight["pointer"]["raw"]) == POINTER.to_bytes(4, "little")
        and preflight["pointer"]["source_address"] == hex(GLOBAL),
        "Wrong fresh pointer",
    )
    check(
        0x18003CA0 <= POINTER and POINTER + 80 <= 0x18045250 and POINTER % 4 == 0,
        "Pointer object outside RAM bound",
    )
    old_fields = context(sample(preflight["context"]["raw"]))
    check(
        all(preflight["context"]["fields"][key] == value for key, value in old_fields.items())
        and old_fields["rd"] == old_fields["wr"] == 206,
        "Fresh parent metadata differs",
    )
    check(
        preflight["context"]["pointer_parent_sha256"]
        == trial["pointer_parent_sha256"]
        == preflight["pointer"]["source_report"]["sha256"]
        and trial["context_parent_sha256"] == preflight["context"]["source_report"]["sha256"],
        "Fresh parent hash chain changed",
    )
    check(
        set(trial["word_guard_report_sha256"]) == {row["source_report"]["sha256"] for row in guards},
        "Word guard chain changed",
    )
    index = old_fields["wr"] & 7
    slot_address = 0x1800A9B0 + index * 512
    files = trial["files"]
    check(
        [(row["role"], row["source_address"], row["source_bytes"]) for row in files]
        == [("global", hex(GLOBAL), 4), ("metadata", hex(POINTER), 32), ("slot", hex(slot_address), 512)],
        "Wrong fixed snapshot profile",
    )
    check(
        len({row["test_path"] for row in files}) == 3
        and all(re.fullmatch(r"/SD:/RECORDER/Call-rc[0-9a-f]{10}\.mp3", row["test_path"]) for row in files),
        "Unexpected test paths",
    )
    commands = [
        f"dbg dumpbuf {int(row['source_address'], 16)} {row['source_bytes']} {row['test_path']}"
        for row in files
    ]
    check(
        trial["commands"] == [commands[0], "dbg mdw 40068074 1", *commands[1:]],
        "Commands differ from fixed GPIO28 read",
    )
    for row in files:
        check(
            row["received_bytes"] == row["download_bytes"] == row["source_bytes"],
            "Incomplete retained download",
        )
    check(
        sample(files[0]["raw"]) == POINTER.to_bytes(4, "little"),
        "Trial pointer differs from historical parent",
    )
    fields = context(sample(files[1]["raw"]))
    check(
        all(trial["verification"]["metadata"][key] == value for key, value in fields.items()),
        "Trial metadata differs from raw32",
    )
    check(
        all(fields[key] == old_fields[key] for key in old_fields if key != "slot_lengths")
        and 1 <= fields["slot_lengths"][index] <= 504
        and not any(length for at, length in enumerate(fields["slot_lengths"]) if at != index),
        "Unexpected historical mode/counters/lengths",
    )
    slot = files[2]
    length = fields["slot_lengths"][index]
    check(
        slot["full_raw_published"] is False
        and slot["body_length"] == trial["verification"]["body_length"] == length,
        "Wrong private slot scope",
    )
    spans = slot["selected_spans"]
    check(
        [row["kind"] for row in spans] == ["nonce-marker", "gpio28-word-row"], "Unexpected public slot spans"
    )
    check(
        sample(spans[0]["raw"]) == b"done dumping to " + files[0]["test_path"].encode("ascii") + b"\r\n",
        "Fresh nonce marker differs",
    )
    line = sample(spans[1]["raw"])
    match = re.fullmatch(rb"40068074: ([0-9a-f]{8}) {31}([\x20-\x7e]{4})\r\n", line)
    check(match is not None and len(line) == 55, "Malformed one-word GPIO28 row")
    word = int(match[1], 16)
    word_le = word.to_bytes(4, "little")
    check(
        match[2] == bytes(byte if 32 <= byte <= 126 else 46 for byte in word_le),
        "Word ASCII differs from little-endian bytes",
    )
    verification = trial["verification"]
    check(
        verification["address"] == hex(ADDRESS)
        and verification["observed_word"] == word
        and verification["word_bytes_le"] == word_le.hex(),
        "Observed word summary differs",
    )
    for row, key in zip(spans, ("marker_body_span", "row_body_span"), strict=True):
        start, end = row["body_span"]
        check(
            0 <= start < end <= length
            and end - start == row["raw"]["bytes"]
            and row["slot_span"] == [start + 8, end + 8]
            and row["body_span"] == verification[key],
            "Selected span bounds changed",
        )
    check(spans[0]["body_span"][1] <= spans[1]["body_span"][0], "Wrong nonce→word order")
    static = data["static_pinmux"]
    for block in static["actual_image_blocks"]:
        offset = int(block["address"], 16) - 0x10000000
        check(sha(image[offset : offset + block["bytes"]]) == block["sha256"], "Actual pinmux block changed")
    check(
        (0x1001A001 + 28) << 2 == ADDRESS
        and static["mask"] == 0x7F3F
        and static["expected_mode"] == 0x4125
        and static["observed_masked"] == word & 0x7F3F
        and static["matches_static_mode"] == (word & 0x7F3F == 0x4125),
        "Pinmux interpretation differs",
    )
    records = [row["raw"] for row in guards + list(preflight.values()) + files[:2]] + [
        row["raw"] for row in spans
    ]
    check(
        sum(row["bytes"] for row in records) == data["public_new_raw_bytes"] == 214, "Wrong public byte count"
    )
    if private_root is not None:
        for name, expected in data["private_sources"].items():
            value = (private_root / name).read_bytes()
            check(
                len(value) == expected["bytes"] and sha(value) == expected["sha256"],
                f"Private source changed: {name}",
            )
    return {
        "compact_public_replay_verified": True,
        "original_trial_ok": True,
        "address": hex(ADDRESS),
        "observed_word": f"0x{word:08x}",
        "pinmux_masked": hex(word & 0x7F3F),
        "matches_static_mode": word & 0x7F3F == 0x4125,
        "public_new_bytes": 214,
        "full_slot_published": False,
        "private_source_hashes_verified": len(data["private_sources"]) if private_root else 0,
        "private_packet_audit_rerun": False,
        "scope": "One observed config word; no physical pad/read-clear guarantee/atomicity/NOR claim",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--private-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.receipt, args.private_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
