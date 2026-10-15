#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Replay pinned compact SD/NOR prerequisite evidence entirely offline.

published RECEIPT needs only tracked safe binaries and the existing gzipped system
image. original RECEIPT PRIVATE_ROOT additionally verifies retained source hashes;
it does not duplicate the package's recorded full Actions/identity semantic audit.
No device access, missing-byte repair, private-ring export or transfer retry.
"""

import argparse
import gzip
import hashlib
import json
import struct
from pathlib import Path

RECEIPT_SHA = "9a527138f5c92942d6f3ef2a0e4c4402cbdd7136b813ea43a93586ee01c0996f"
IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
RAM_SHA = "35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b"
POSTINFO_ERROR = "OSError: [Errno 38] LE ATT connect failed"
GUARDS = {
    "header": (0x10000000, 32),
    "handler": (0x10024A20, 160),
    "printk-hook": (0x10020628, 16),
    "fread": (0x10025348, 16),
    "ring-code": (0x10026CD4, 68),
    "printk-code": (0x10026E6C, 104),
    "fread-descriptor": (0x100BB960, 16),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def raw_file(root: Path, record: dict) -> bytes:
    data = (root / record["file"]).read_bytes()
    require(
        len(data) == record["bytes"] and sha(data) == record["sha256"],
        f"Public raw bytes/hash mismatch: {record['file']}",
    )
    return data


def actions(proof: dict) -> None:
    require(
        proof
        == {
            "confirmed_writes": 4,
            "ack_count": 4,
            "f1_received": True,
            "pending_bytes": 0,
            "source_commands": "PREPARE,START,one fixed dumpbuf,STOP; no fread producer",
        },
        "Compact Actions completion proof changed",
    )


def published(receipt: Path) -> tuple[dict, dict]:
    raw = receipt.read_bytes()
    require(sha(raw) == RECEIPT_SHA, "Pinned compact receipt changed")
    data = json.loads(raw)
    image = gzip.decompress((receipt.parent / data["image"]["file"]).read_bytes())
    require(
        len(image) == data["image"]["decompressed_bytes"] == 927632
        and sha(image) == data["image"]["decompressed_sha256"] == IMAGE_SHA,
        "Wrong complete system image",
    )
    require(
        data["private_audit"]["performed_offline"] is True and data["private_audit"]["device_io"] is False,
        "Private audit scope changed",
    )
    guards = data["guards"]
    require(
        len(guards) == 7 and {row["source"] for row in guards} == set(GUARDS), "Expected seven fixed guards"
    )
    new_guard_bytes = 0
    for row in guards:
        address, size = GUARDS[row["source"]]
        require(
            row["address"] == hex(address)
            and row["image_offset"] == address - 0x10000000
            and row["raw"]["bytes"] == size
            and row["original_ok"] is True,
            "Guard identity/range changed",
        )
        actual = raw_file(receipt.parent, row["raw"])
        require(
            actual == image[address - 0x10000000 : address - 0x10000000 + size],
            "Guard differs from full image",
        )
        actions(row["actions"])
        require(
            row["state"]["other_state_equal"] is True
            and 0 <= row["state"]["free_capacity_decrease"] <= int(not row["download_only"]),
            "Guard bounded state comparison changed",
        )
        if row["source"] not in {"header", "handler"}:
            new_guard_bytes += size
        if row["download_only"]:
            require(
                row["source"] == "handler"
                and row["write_parent_report_sha256"]
                == data["private_sources"]["artifacts/live-sd-handler160-20261013/report.json"]["sha256"],
                "Read-only handler write-parent binding changed",
            )
    require(new_guard_bytes == 220, "Expected five new code guards totaling220B")
    old = data["historical_printk_code_failure"]
    require(
        old["original_ok"] is False
        and old["download_bytes_exact"] == 104
        and old["retrospective_bounded_sd_state_comparison"]["free_capacity_decrease"] == 1
        and old["retrospective_bounded_sd_state_comparison"]["other_state_equal"] is True,
        "Historical capacity failure must stay failed",
    )
    context = data["context"]
    body = raw_file(receipt.parent, context["raw"])
    require(len(body) == 28 and context["address"] == "0x1800e008", "Wrong historical context range")
    read, write, used, capacity, buffer = struct.unpack("<5I", body[:20])
    require(
        capacity == 4096
        and buffer == 0x1803EE09
        and max(read, write, used) <= capacity
        and body[20:22] == b"\x01\0",
        "Historical context struct invalid",
    )
    require(
        context["fields"]
        == {
            "read": read,
            "write": write,
            "used": used,
            "capacity": capacity,
            "buffer": hex(buffer),
            "init": 1,
            "panic": 0,
        },
        "Context fields differ from bytes",
    )
    original, postcheck = context["original"], context["postcheck"]
    actions(original["actions"])
    require(
        original["ok"] is False
        and original["error"] == POSTINFO_ERROR
        and postcheck["ok"] is True
        and postcheck["parent_report_sha256"] == original["report_sha256"]
        and postcheck["download_reused"] is True
        and postcheck["new_context_sample"] is False
        and postcheck["started_at_preserved"] is True,
        "Context postcheck must reuse the still-failed original acquisition",
    )
    require(
        original["report_sha256"]
        == data["private_sources"]["artifacts/nor-sd-guards-20261013/context/report.json"]["sha256"]
        and postcheck["report_sha256"]
        == data["private_sources"]["artifacts/nor-sd-guards-20261013/context-postcheck/report.json"][
            "sha256"
        ],
        "Context private parent identity changed",
    )
    baseline = data["baseline"]
    actions(baseline["actions"])
    require(
        baseline["original_ok"] is False
        and baseline["requested_bytes"] == 4096
        and baseline["retained_private_bytes"] == 3852
        and baseline["payload_published"] is False
        and baseline["payload_semantic_validation_complete"] is False
        and baseline["missing_offset_known"] is False
        and baseline["previous_context_postcheck_report_sha256"] == postcheck["report_sha256"],
        "Incomplete private baseline cannot be promoted to success",
    )
    hci = baseline["hci"]
    require(
        hci["notification_count"] == 17
        and hci["lengths"] == [244, 244, 24] + [244] * 13 + [168]
        and sum(hci["lengths"]) == hci["bytes"] == 3852
        and hci["sha256"] == baseline["retained_private_sha256"]
        and hci["raw_snoop_equals_btmon"] is True
        and hci["hci_concat_equals_saved_file"] is True
        and hci["capture_drop_fields"] == [0],
        "Compact HCI length/hash proof changed",
    )
    require(
        hci["sha256"]
        == data["private_sources"]["artifacts/nor-sd-guards-20261013/baseline/download.bin"]["sha256"],
        "Baseline retained-private hash changed",
    )
    ram = image[0xDD500:0xDE500]
    require(len(ram) == 4096 and sha(ram) == RAM_SHA, "RAM initialization oracle changed")
    warm = data["warm_download"]
    tail128 = raw_file(receipt.parent, warm["tail"]["raw"])
    partial = raw_file(receipt.parent, warm["full"]["raw"])
    require(
        warm["original_ok"] is False
        and warm["sd_write_attempted"] is False
        and warm["tail"]["transfer_complete"] is True
        and warm["tail"]["offset"] == 3968
        and tail128 == ram[-128:]
        and warm["full"]["transfer_complete"] is False
        and len(partial) == 3852
        and warm["info_barrier_other_state_equal"] is True,
        "Warm trial outcome/oracle mismatch",
    )
    deficit = len(ram) - len(partial)
    # Compare existing data against one deletion from a known oracle; never fill missing bytes.
    intervals = [
        [i, i + deficit]
        for i in range(len(partial) + 1)
        if ram[:i] == partial[:i] and ram[i + deficit :] == partial[i:]
    ]
    require(
        intervals == [warm["full"]["unique_deletion_interval_vs_ram_oracle"]] == [[756, 1000]]
        and warm["full"]["reconstructed"] is False,
        "Warm unique deletion relationship changed",
    )
    suffix = data["tail512"]
    require(
        raw_file(receipt.parent, suffix["raw"]) == ram[3584:]
        and suffix["offset"] == 3584
        and suffix["requested_bytes"] == 512
        and suffix["transfer_complete"] is True
        and suffix["exact_match"] is True
        and suffix["original_ok"] is False
        and suffix["error"] == suffix["after_error"] == POSTINFO_ERROR
        and suffix["sd_write_attempted"] is False,
        "Exact suffix transfer is separate from failed final identity",
    )
    parent_sha = data["private_sources"]["artifacts/live-sd-bootstrap-20261013/report.json"]["sha256"]
    require(
        warm["ram_write_parent_report_sha256"] == suffix["ram_write_parent_report_sha256"] == parent_sha,
        "Read-only RAM files lack their original write parent",
    )
    late = data["late_state_observation"]
    require(
        late["serial"] == "C261CF0430"
        and late["firmware_version"] == "010004"
        and late["recording_state"] == "idle"
        and late["free_capacity_mib"] == 59597,
        "Late independent info changed",
    )
    require(
        {row["source_report_sha256"] for row in late["comparisons"]}
        == {baseline["source_report_sha256"], warm["source_report_sha256"], suffix["source_report_sha256"]},
        "Late state comparison parent set changed",
    )
    for comparison in late["comparisons"]:
        state = comparison["read_only_state_verification"]
        require(
            comparison["original_ok"] is False
            and state["other_state_equal"] is True
            and state["free_capacity_decrease"] == state["allowed_decrease"] == 0,
            "Independent later state must not rewrite original failures",
        )
    require(
        data["boot_phase_attempted_in_this_sequence"] is False, "Baseline did not pass the boot-phase gate"
    )
    return data, {
        "compact_public_replay_verified": True,
        "guards_verified": 7,
        "new_code_guard_bytes": new_guard_bytes,
        "historical_context_bytes": 28,
        "context_reacquired_by_postcheck": False,
        "warm_tail_exact_bytes": 128,
        "warm_full_observed_bytes": 3852,
        "warm_full_unique_deletion_interval": intervals[0],
        "warm_overall_success": False,
        "ram_tail_exact_bytes": 512,
        "tail512_original_overall_success": False,
        "baseline_private_bytes": 3852,
        "baseline_missing_offset_known": False,
        "baseline_hci_value_lengths": hci["lengths"],
        "boot_phase_attempted": False,
        "limits": [
            "Pinned compact metadata/raw replay; complete private semantic audit is recorded, not rerun here",
            "No repair, joined transfer, new context sample, raw NOR backup or general reliability claim",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    public = commands.add_parser("published")
    public.add_argument("receipt", type=Path)
    original = commands.add_parser("original")
    original.add_argument("receipt", type=Path)
    original.add_argument("private_root", type=Path)
    args = parser.parse_args()
    data, result = published(args.receipt)
    if args.mode == "original":
        for name, expected in data["private_sources"].items():
            raw = (args.private_root / name).read_bytes()
            require(
                len(raw) == expected["bytes"] and sha(raw) == expected["sha256"],
                f"Private source changed: {name}",
            )
        result["private_source_hashes_verified"] = len(data["private_sources"])
        result["package_semantic_audit_rerun"] = False
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
