"""Oracles: actual timer stores and service-header branches captured on FW010004."""

import json
from pathlib import Path

import pytest

from rcominote.code_guards import observed_storage_reference
from rcominote.code_references import inspect_references

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"
FIRST = EVIDENCE / "boot-info-first-2026-10-12.json"
SECOND = EVIDENCE / "boot-info-second-2026-10-12.json"


def test_actual_timer_and_header_edges():
    report = inspect_references(FIRST, SECOND, shell=True)
    instructions = {
        row["address"]: (row["mnemonic"], row["operands"])
        for region in report["code_regions"]
        for row in region["instructions"]
    }
    assert instructions["0x1009c8ec"] == ("strd", "r6, r5, [r4, #0x14]")
    assert instructions["0x1000c13e"] == ("beq", "#0x1000c150")
    assert instructions["0x1000c166"] == ("bne.w", "#0x1000c308")


def test_changed_service_branch_blocks_success_target_read():
    capture = json.loads(FIRST.read_text())
    for frame in capture["frames"]:
        frame["text"] = frame.get("text", "").replace("1d 2a 07 d0", "1d 2a 08 d0")
    with pytest.raises(ValueError, match="logsrv service-ID success branch code changed"):
        observed_storage_reference(capture["frames"], "dbg mdb 1000c150 10")


def test_text_dispatch_and_backend_literal_boundaries():
    report = inspect_references(FIRST, SECOND, shell=True)
    regions = {region["address"]: region for region in report["code_regions"]}
    assert regions["0x100242a8"]["length"] == 4
    literal = next(block for block in report["blocks"] if block["address"] == "0x100242ac")
    assert literal["little_endian_words"] == ["0x100ba644"]
    instructions = {
        row["address"]: (row["mnemonic"], row["operands"])
        for region in regions.values()
        for row in region["instructions"]
    }
    assert instructions["0x1000c25a"] == ("beq", "#0x1000c2cc")
    # BL crosses transport rows c2dc/c2ec; independently decoding rows loses it.
    assert instructions["0x1000c2ea"] == ("bl", "#0x100242b0")
    assert instructions["0x1000c2f4"] == ("bl", "#0x100a0e1a")
    assert instructions["0x100a0e52"] == ("bl", "#0x10023020")


def test_changed_text_execute_call_blocks_callee_read():
    capture = json.loads(FIRST.read_text())
    for frame in capture["frames"]:
        frame["text"] = frame.get("text", "").replace("94 f0 91 fd", "94 f0 92 fd")
    with pytest.raises(ValueError, match="logsrv backend getter and execute calls code changed"):
        observed_storage_reference(capture["frames"], "dbg mdb 100a0e1a 10")


def test_actual_registry_bounds_and_dbg_static_pointer():
    report = inspect_references(FIRST, SECOND, shell=True)
    blocks = {row["address"]: row for row in report["blocks"]}
    assert blocks["0x10023d94"]["little_endian_words"] == ["0x100ba674", "0x100ba6dc"]
    assert bytes.fromhex(blocks["0x100c69dd"]["hex"]) == b"dbg\0"
    assert blocks["0x100bbba4"]["little_endian_words"] == ["0x0", "0x100bb8d4"]
    instructions = {
        row["address"]: (row["mnemonic"], row["operands"])
        for region in report["code_regions"]
        for row in region["instructions"]
    }
    assert instructions["0x10023d5e"] == ("cmp.w", "r3, r2, lsr #3")
    assert instructions["0x10023d68"] == ("ldr", "r4, [r1, #4]")
    assert instructions["0x10023d88"] == ("movs", "r0, #0x14")


def test_moved_registry_boundary_blocks_old_table():
    capture = json.loads(FIRST.read_text())
    for frame in capture["frames"]:
        frame["text"] = frame.get("text", "").replace("74 a6 0b 10 dc a6 0b 10", "74 a6 0b 10 d4 a6 0b 10")
    with pytest.raises(ValueError, match="shell root registry start/end code changed"):
        observed_storage_reference(capture["frames"], "dbg mdb 100ba674 10")


def test_changed_partition_pointer_blocks_stale_header():
    capture = json.loads(FIRST.read_text())
    for frame in capture["frames"]:
        frame["text"] = frame.get("text", "").replace("1800ecb4: 40 00 00 01", "1800ecb4: 50 00 00 01")
    with pytest.raises(ValueError, match="live partition table pointer code changed"):
        observed_storage_reference(capture["frames"], "dbg mdb 1000040 10")


def test_boot_candidate_correlations_keep_param_mismatch_visible():
    report = inspect_references(FIRST, SECOND, shell=True)["boot_info_candidate"]
    # Actual words 0x01000040/0x24000/0 conflict with a blindly assumed complete SDK ABI.
    assert report["candidate_fields"]["param_save_addr"] == "0x1000040"
    assert report["candidate_fields"]["system_phy_addr"] == "0x24000"
    assert report["candidate_fields"]["param_phy_addr"] == "0x0"
    assert report["system_matches"] == [5]
    assert report["param_matches"] == []
