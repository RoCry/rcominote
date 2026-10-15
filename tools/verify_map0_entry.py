#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Replay two historical slot0 word observations offline; no mapping or alias probe."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from verify_gpio28_word import replay as replay_previous
from verify_logsrv_slot import GLOBAL, check, context, sha

RECEIPT_SHA = "e24dc29bbc08dbf171420495fcc9c741c93c2b0c5f66b410c7459a6a782e3cd1"
RECOVERY_SHA = "19625b7b70eb8e4a91c889792c0ca383f51ea205629e67565b59c47d15e09906"
TARGETS = {"map0-cpu": 0x40010300, "map0-offset": 0x40010304}


def replay(receipt: Path, private_root: Path | None = None) -> dict:
    raw = receipt.read_bytes()
    check(sha(raw) == RECEIPT_SHA, "Pinned map0 receipt changed")
    data = json.loads(raw)
    old_path = receipt.parent / data["prior_word_bundle"]["file"]
    check(sha(old_path.read_bytes()) == data["prior_word_bundle"]["sha256"], "Prior word bundle changed")
    replay_previous(old_path)
    old = json.loads(old_path.read_bytes())
    slot = json.loads((receipt.parent / old["prior_slot_bundle"]["file"]).read_bytes())
    shared = json.loads((receipt.parent / slot["context_guard_bundle"]["file"]).read_bytes())
    guards = old["word_code_guards"] + slot["new_code_guards"] + shared["guards"]
    guard_hashes = sorted(row["source_report"]["sha256"] for row in guards)
    guard_end = max(
        datetime.fromisoformat(old["prior_guards_latest_end"]),
        *(datetime.fromisoformat(row["ended_at"]) for row in old["word_code_guards"]),
    )
    proof = data["recovery_proof"]
    recovery = (receipt.parent / proof["file"]).read_bytes()
    check(
        len(recovery) == 63288 and sha(recovery) == proof["sha256"] == RECOVERY_SHA,
        "Wrong actual recovery read proof",
    )
    expected_regions = {
        0xE4FA: "134d134a17682968",
        0xE548: "0003014004030140",
        0xE2BC: "41f00101",
        0xE550: "0f000010",
        0xE508: "44f00044",
    }
    check(
        {row["offset"]: row["hex"] for row in proof["regions"]} == expected_regions,
        "Wrong recovery LDR/helper/caller profile",
    )
    for offset, hex_value in expected_regions.items():
        expected = bytes.fromhex(hex_value)
        check(recovery[offset : offset + len(expected)] == expected, "Actual recovery proof bytes changed")

    def sample(record: dict) -> bytes:
        value = (receipt.parent / record["file"]).read_bytes()
        check(
            len(value) == record["bytes"] and sha(value) == record["sha256"],
            "Public sample size/hash mismatch",
        )
        return value

    observations = data["observations"]
    check([row["target"] for row in observations] == list(TARGETS), "Requires only two fixed slot0 targets")
    words, public_bytes = {}, 0
    for observation in observations:
        target, preflight, trial = observation["target"], observation["fresh_preflight"], observation["trial"]
        address = TARGETS[target]
        check(observation["guard_report_sha256"] == guard_hashes, "Original nine guard parents changed")
        times = []
        for row in [preflight["pointer"], preflight["context"], trial]:
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
                "Invalid evidence timestamp",
            )
            times.extend([start, end])
        check(
            guard_end <= times[0] and times == sorted(times),
            "Chronology must be guards→fresh pointer→context→trial",
        )
        pointer_raw = sample(preflight["pointer"]["raw"])
        check(
            len(pointer_raw) == 4 and preflight["pointer"]["source_address"] == hex(GLOBAL),
            "Wrong pointer global source",
        )
        pointer = int.from_bytes(pointer_raw, "little")
        check(
            pointer % 4 == 0 and 0x18003CA0 <= pointer <= 0x18045250 - 80,
            "Pointer outside bounded RAM/object80",
        )
        parent_fields = context(sample(preflight["context"]["raw"]))
        check(
            preflight["context"]["source_address"] == hex(pointer)
            and all(preflight["context"]["fields"][key] == value for key, value in parent_fields.items()),
            "Fresh historical context differs",
        )
        check(
            preflight["context"]["pointer_parent_sha256"]
            == trial["pointer_parent_sha256"]
            == preflight["pointer"]["source_report"]["sha256"]
            and trial["context_parent_sha256"] == preflight["context"]["source_report"]["sha256"],
            "Fresh parent hash chain changed",
        )
        index = parent_fields["wr"] & 7
        slot_address = 0x1800A9B0 + index * 512
        files = trial["files"]
        check(
            [(row["role"], row["source_address"], row["source_bytes"]) for row in files]
            == [("global", hex(GLOBAL), 4), ("metadata", hex(pointer), 32), ("slot", hex(slot_address), 512)],
            "Wrong parent-selected RAM snapshots",
        )
        check(
            len({row["test_path"] for row in files}) == 3
            and all(
                re.fullmatch(r"/SD:/RECORDER/Call-rc[0-9a-f]{10}\.mp3", row["test_path"]) for row in files
            ),
            "Unexpected test paths",
        )
        commands = [
            f"dbg dumpbuf {int(row['source_address'], 16)} {row['source_bytes']} {row['test_path']}"
            for row in files
        ]
        check(
            trial["commands"] == [commands[0], f"dbg mdw {address:x} 1", *commands[1:]],
            "Commands differ from fixed slot0 read",
        )
        check(
            all(row["received_bytes"] == row["download_bytes"] == row["source_bytes"] for row in files),
            "Incomplete retained download",
        )
        check(sample(files[0]["raw"]) == pointer_raw, "Trial pointer changed from historical parent")
        fields = context(sample(files[1]["raw"]))
        check(
            all(fields[key] == parent_fields[key] for key in fields if key != "slot_lengths")
            and fields["rd"] == fields["wr"]
            and (fields["flags_byte"], fields["log_type"], fields["new_log_type"], fields["drop_count"])
            == (3, 0, 0, 0),
            "Unexpected historical metadata fields",
        )
        check(
            all(trial["verification"]["metadata"][key] == value for key, value in fields.items()),
            "Trial metadata summary differs",
        )
        length = fields["slot_lengths"][index]
        check(
            1 <= length <= 504 and not any(n for i, n in enumerate(fields["slot_lengths"]) if i != index),
            "Unexpected slot lengths",
        )
        slot_file = files[2]
        check(
            slot_file["full_raw_published"] is False
            and slot_file["body_length"] == trial["verification"]["body_length"] == length,
            "Wrong private slot scope",
        )
        spans = slot_file["selected_spans"]
        check(
            [row["kind"] for row in spans] == ["nonce-marker", "word-row"]
            and sample(spans[0]["raw"])
            == b"done dumping to " + files[0]["test_path"].encode("ascii") + b"\r\n",
            "Wrong safe marker spans",
        )
        line = sample(spans[1]["raw"])
        match = re.fullmatch(f"{address:08x}: ".encode() + rb"([0-9a-f]{8}) {31}([\x20-\x7e]{4})\r\n", line)
        check(match is not None and len(line) == 55, "Malformed target word row")
        word = int(match[1], 16)
        check(
            match[2] == bytes(n if 32 <= n <= 126 else 46 for n in word.to_bytes(4, "little")),
            "ASCII differs from observed little-endian word",
        )
        check(
            trial["verification"]["address"] == hex(address)
            and trial["verification"]["observed_word"] == word,
            "Word summary differs from raw row",
        )
        for row, key in zip(spans, ("marker_body_span", "row_body_span"), strict=True):
            start, end = row["body_span"]
            check(
                0 <= start < end <= length
                and end - start == row["raw"]["bytes"]
                and row["slot_span"] == [start + 8, end + 8]
                and row["body_span"] == trial["verification"][key],
                "Selected span bounds changed",
            )
        check(spans[0]["body_span"][1] <= spans[1]["body_span"][0], "Wrong nonce→word order")
        public_bytes += sum(row["raw"]["bytes"] for row in [*preflight.values(), *files[:2], *spans])
        words[target] = word
    failed = data["failed_contexts"]
    check(len(failed) == 1, "Expected retained original postinfo-failed context")
    failed_context = failed[0]
    check(
        failed_context["original_ok"] is False
        and failed_context["error"]
        == failed_context["after_error"]
        == "OSError: [Errno 38] LE ATT connect failed"
        and failed_context["final_state_verified"] is False
        and failed_context["used_as_parent"] is False
        and failed_context["download_reused"] is False,
        "Failed historical context cannot be promoted or reused",
    )
    check(
        failed_context["actions"]
        == {"confirmed_writes": 4, "ack_count": 4, "f1_received": True, "pending_bytes": 0}
        and failed_context["pointer_parent_sha256"]
        == observations[1]["fresh_preflight"]["pointer"]["source_report"]["sha256"],
        "Failed context trace/pointer binding changed",
    )
    historical_fields = context(sample(failed_context["raw"]))
    check(
        all(failed_context["fields"][key] == value for key, value in historical_fields.items())
        and historical_fields["rd"] == historical_fields["wr"] == 210,
        "Historical failed context differs from saved32 bytes",
    )
    public_bytes += failed_context["raw"]["bytes"]
    check(
        public_bytes == data["public_new_raw_bytes"] == 392 and data["atomic_pair"] is False,
        "Wrong public count or atomicity claim",
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
        "words": {key: f"0x{value:08x}" for key, value in words.items()},
        "cpu_upper_bits_excluding_low_nibble": hex(words["map0-cpu"] & ~0xF),
        "cpu_low_nibble": hex(words["map0-cpu"] & 0xF),
        "offset_bit31_crc_attribute_source_comparison": bool(words["map0-offset"] & 0x80000000),
        "offset_without_bit31": hex(words["map0-offset"] & 0x7FFFFFFF),
        "atomic_pair": False,
        "public_new_bytes": 392,
        "full_slots_published": False,
        "private_source_hashes_verified": len(data["private_sources"]) if private_root else 0,
        "private_packet_audit_rerun": False,
        "scope": "Two historical configuration words; no window-size/alias/raw-NOR/encryption proof",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--private-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.receipt, args.private_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
