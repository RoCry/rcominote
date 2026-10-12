"""Captured literals/function name, and the known complete-transport/lost-text failure."""

import json
from pathlib import Path

import pytest

from rcominote.code_guards import observed_capacity_entries
from rcominote.code_references import inspect_references
from rcominote.log_capture import observed_logsrv_literals, observed_vendor_code, verify_readback

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"
FIRST = EVIDENCE / "code-references-first-2026-10-12.json"
SECOND = EVIDENCE / "code-references-second-2026-10-12.json"


def test_actual_literals_and_name_match_independent_reads():
    report = inspect_references(FIRST, SECOND)
    assert report["blocks"][1]["little_endian_words"] == ["0x100c26ba", "0x100ba51c"]
    assert report["blocks"][2]["ascii"] == "_logsrv_init\0"
    assert report["blocks"][4]["undecoded_tail_hex"] == "46f0"


def test_dropped_last_row_is_failure_despite_complete_transport():
    capture = json.loads(FIRST.read_text())
    for frame in capture["frames"]:
        frame["text"] = "\n".join(
            line for line in frame.get("text", "").split("\n") if not line.startswith("1000bf30:")
        )
    verify_readback(capture)
    assert capture["transport_ok"] and not capture["ok"] and not capture["readback_complete"]
    assert "0x1000bf30" in capture["error"]


def test_changed_literal_prevents_following_old_pointer():
    capture = json.loads(FIRST.read_text())
    assert observed_logsrv_literals(capture["frames"])
    for frame in capture["frames"]:
        frame["text"] = frame.get("text", "").replace("ba 26 0c 10", "00 00 00 00")
    with pytest.raises(ValueError, match="literals changed"):
        observed_logsrv_literals(capture["frames"])


def test_truncated_duplicate_row_cannot_hide_behind_complete_row():
    capture = json.loads(FIRST.read_text())
    capture["frames"].append({"text": "\n1000bf30: 60 4b\n"})
    verify_readback(capture)
    assert not capture["ok"] and "duplicate" in capture["error"]


def test_vendor_thumb_instruction_crosses_transport_row_boundary():
    report = inspect_references(
        EVIDENCE / "vendor-code-first-2026-10-12.json",
        EVIDENCE / "vendor-code-second-2026-10-12.json",
        vendor=True,
    )
    # Actual bytes span rows a05c and a06c; decoding each row independently
    # would lose the first half or misinterpret the second half of this ORR.
    instructions = report["code_regions"][1]["instructions"]
    instruction = next(row for row in instructions if row["address"] == "0x1000a06a")
    assert (instruction["bytes"], instruction["mnemonic"], instruction["operands"]) == (
        "44f09570",
        "orr",
        "r0, r4, #0x12a0000",
    )


def test_changed_vendor_code_blocks_literal_reads():
    capture = json.loads((EVIDENCE / "vendor-code-first-2026-10-12.json").read_text())
    assert observed_vendor_code(capture["frames"])
    assert not observed_vendor_code([{"text": "1000a01c: 8f b5 54 4c"}])
    for frame in capture["frames"]:
        frame["text"] = frame.get("text", "").replace("8f b5 54 4c", "8f b5 55 4c")
    with pytest.raises(ValueError, match="vendor_read code changed"):
        observed_vendor_code(capture["frames"])


def test_device_info_decode_keeps_literal_pool_out_of_code():
    report = inspect_references(
        EVIDENCE / "device-info-first-2026-10-12.json",
        EVIDENCE / "device-info-second-2026-10-12.json",
        info=True,
    )
    # Actual BL targets and function returns delimit these three spans;
    # the 16-byte pool following abE4 must never become instructions.
    assert [(row["address"], row["length"]) for row in report["code_regions"]] == [
        ("0x1000aad0", 276),
        ("0x100549c0", 88),
        ("0x10054a28", 88),
    ]


def test_changed_capacity_callee_blocks_continuation():
    capture = json.loads((EVIDENCE / "device-info-first-2026-10-12.json").read_text())
    for frame in capture["frames"]:
        frame["text"] = frame.get("text", "").replace("da f7 3c fc", "da f7 00 fc")
    with pytest.raises(ValueError, match="capacity getter code changed"):
        observed_capacity_entries(capture["frames"])


def test_storage_dispatch_decodes_actual_indirect_call():
    report = inspect_references(
        EVIDENCE / "storage-first-2026-10-12.json",
        EVIDENCE / "storage-second-2026-10-12.json",
        storage=True,
    )
    # Hand-decoded Thumb from the captured VFS: mount->fs (+1c),
    # fs->statvfs (+44), BLX r3. It must not become a direct guessed BL.
    instructions = {
        row["address"]: (row["mnemonic"], row["operands"])
        for region in report["code_regions"]
        for row in region["instructions"]
    }
    assert [instructions[address] for address in ("0x1002f2ae", "0x1002f2b0", "0x1002f2ba")] == [
        ("ldr", "r3, [r0, #0x1c]"),
        ("ldr", "r3, [r3, #0x44]"),
        ("blx", "r3"),
    ]


def test_moved_mount_pointer_prevents_stale_ram_dereference():
    from rcominote.code_guards import observed_storage_reference

    capture = json.loads((EVIDENCE / "storage-first-2026-10-12.json").read_text())
    for frame in capture["frames"]:
        frame["text"] = frame.get("text", "").replace("64 0a 01 18", "00 00 00 00")
    with pytest.raises(ValueError, match="SD mount pointer and flags code changed"):
        observed_storage_reference(capture["frames"], "dbg mdb 18010a64 10")
