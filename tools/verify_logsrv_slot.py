#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Offline pinned compact replay; full private slot and ATT audit are not published."""

import argparse
import gzip
import hashlib
import json
import re
import struct
from pathlib import Path

RECEIPT_SHA = "8f00e34196d409df3ffd129f5863d9f2a1a0dcc003d20806ef770244b4d26006"
IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
CONTEXT_RECEIPT_SHA = "90473a21b77b898c9e96b449208ab409bb831b03684e21f6e7d3c63bbcca3051"
POINTER, GLOBAL, SLOT = 0x180111FC, 0x1800A9AC, 0x1800B1B0
ORACLE = bytes.fromhex("5e348df8123094f87034bdf800208df8")
ROW = b"1000ab40: 5e 34 8d f8 12 30 94 f8 70 34 bd f8 00 20 8d f8    ^4...0..p4... ..\r\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def context(raw: bytes) -> dict:
    check(len(raw) == 32, "Expected complete32-byte historical context")
    return {
        "stream_pointer": hex(int.from_bytes(raw[:4], "little")),
        "flags_byte": raw[4],
        "log_type": raw[5],
        "new_log_type": raw[6],
        "rd": raw[7],
        "wr": raw[8],
        "slot_lengths": list(struct.unpack_from("<8H", raw, 10)),
        "drop_count": int.from_bytes(raw[28:32], "little"),
    }


def replay(receipt: Path, private_root: Path | None = None) -> dict:
    raw = receipt.read_bytes()
    check(sha(raw) == RECEIPT_SHA, "Pinned slot receipt changed")
    data = json.loads(raw)
    check(data["serial"] == "C261CF0430", "Wrong owned device")
    image = gzip.decompress((receipt.parent / data["image"]["file"]).read_bytes())
    check(
        len(image) == data["image"]["decompressed_bytes"] == 927632
        and sha(image) == data["image"]["sha256"] == IMAGE_SHA,
        "Wrong full image",
    )
    old = data["context_guard_bundle"]
    old_raw = (receipt.parent / old["file"]).read_bytes()
    check(sha(old_raw) == old["sha256"] == CONTEXT_RECEIPT_SHA, "Context guard bundle changed")

    def sample(record: dict) -> bytes:
        value = (receipt.parent / record["file"]).read_bytes()
        check(
            len(value) == record["bytes"] and sha(value) == record["sha256"],
            "Public sample size/hash mismatch",
        )
        return value

    shared = json.loads(old_raw)["guards"]
    check(
        {int(row["address"], 16): row["bytes"] for row in shared}
        == {0x10000000: 32, 0x10024A20: 160, 0x1000BF82: 32, 0x1000C0C8: 16, 0x1009AA24: 48},
        "Wrong shared guard profile",
    )
    for row in shared:
        offset = int(row["address"], 16) - 0x10000000
        check(sample(row["raw"]) == image[offset : offset + row["bytes"]], "Shared guard differs from image")
    guards = data["new_code_guards"]
    check(
        len(guards) == 2
        and {int(row["source_address"], 16): row["source_bytes"] for row in guards}
        == {0x1000BD30: 32, 0x1000BD80: 48},
        "Wrong slot guard profile",
    )
    for row in guards:
        offset = int(row["source_address"], 16) - 0x10000000
        check(
            sample(row["raw"]) == image[offset : offset + row["source_bytes"]],
            "Slot guard differs from image",
        )
    preflight, trial = data["fresh_preflight"], data["trial"]
    for row in guards + list(preflight.values()) + [trial]:
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
    check(
        preflight["pointer"]["source_address"] == hex(GLOBAL)
        and sample(preflight["pointer"]["raw"]) == POINTER.to_bytes(4, "little"),
        "Wrong fresh preflight pointer",
    )
    check(
        0x18003CA0 <= POINTER and POINTER + 80 <= 0x18045250 and POINTER % 4 == 0,
        "Pointer object outside RAM bound",
    )
    check(
        preflight["context"]["pointer_parent_sha256"]
        == trial["pointer_parent_sha256"]
        == preflight["pointer"]["source_report"]["sha256"]
        and trial["context_parent_sha256"] == preflight["context"]["source_report"]["sha256"],
        "Fresh parent hash chain changed",
    )
    check(
        trial["slot_guard_report_sha256"] == [row["source_report"]["sha256"] for row in guards],
        "Slot guard parent chain changed",
    )
    original_fields = context(sample(preflight["context"]["raw"]))
    check(
        all(preflight["context"]["fields"][key] == value for key, value in original_fields.items())
        and original_fields["rd"] == original_fields["wr"] == 204,
        "Fresh historical context differs",
    )
    files = trial["files"]
    check(
        [(row["role"], row["source_address"], row["source_bytes"]) for row in files]
        == [("global", hex(GLOBAL), 4), ("metadata", hex(POINTER), 32), ("slot", hex(SLOT), 512)],
        "Wrong fixed trial sources",
    )
    check(
        len({row["test_path"] for row in files}) == 3
        and all(re.fullmatch(r"/SD:/RECORDER/Call-rc[0-9a-f]{10}\.mp3", row["test_path"]) for row in files),
        "Unexpected trial paths",
    )
    commands = [
        f"dbg dumpbuf {int(row['source_address'], 16)} {row['source_bytes']} {row['test_path']}"
        for row in files
    ]
    check(
        trial["commands"] == [commands[0], "dbg mdb 1000ab40 10", *commands[1:]],
        "Trial commands differ from fixed profile",
    )
    for row in files:
        check(
            row["received_bytes"] == row["download_bytes"] == row["source_bytes"],
            "Incomplete retained download",
        )
    check(
        sample(files[0]["raw"]) == POINTER.to_bytes(4, "little"),
        "Trial pointer differs from historical pointer",
    )
    fields = context(sample(files[1]["raw"]))
    check(
        all(trial["verification"]["metadata"][key] == value for key, value in fields.items()),
        "Trial context summary differs",
    )
    check(
        fields == original_fields | {"slot_lengths": [0, 0, 0, 0, 431, 0, 0, 0]},
        "Unexpected trial historical context",
    )
    slot = files[2]
    check(
        slot["full_raw_published"] is False
        and slot["body_length"] == trial["verification"]["body_length"] == 431,
        "Wrong private slot scope",
    )
    spans = slot["selected_spans"]
    check(
        [row["kind"] for row in spans] == ["nonce-marker", "known-mdb16-row"], "Unexpected public slot spans"
    )
    check(
        sample(spans[0]["raw"]) == b"done dumping to " + files[0]["test_path"].encode("ascii") + b"\r\n",
        "Fresh nonce marker differs",
    )
    check(sample(spans[1]["raw"]) == ROW and image[0xAB40:0xAB50] == ORACLE, "Known row differs from image")
    for row, key in zip(spans, ("marker_body_span", "row_body_span"), strict=True):
        start, end = row["body_span"]
        check(
            0 <= start < end <= 431
            and end - start == row["raw"]["bytes"]
            and row["slot_span"] == [start + 8, end + 8]
            and row["body_span"] == trial["verification"][key],
            "Selected span bounds changed",
        )
    check(
        spans[0]["body_span"][1] <= spans[1]["body_span"][0]
        and trial["verification"]["known_bytes_hex"] == ORACLE.hex()
        and trial["verification"]["known_bytes_sha256"] == sha(ORACLE),
        "Nonce-row order/oracle changed",
    )
    records = [row["raw"] for row in guards + list(preflight.values()) + files[:2]] + [
        row["raw"] for row in spans
    ]
    check(
        sum(row["bytes"] for row in records) == data["public_new_raw_bytes"] == 284, "Wrong public byte count"
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
        "known_bytes_sha256": sha(ORACLE),
        "public_new_bytes": 284,
        "private_slot_bytes": 512,
        "private_slot_sha256": slot["sha256"],
        "full_slot_published": False,
        "private_source_hashes_verified": len(data["private_sources"]) if private_root else 0,
        "private_packet_audit_rerun": False,
        "scope": "One historical nonce-associated known row; no atomicity/general512/NOR claim",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--private-root", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.receipt, args.private_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
