"""Oracles: actual timer stores and service-header branches captured on FW010004."""

import json
from pathlib import Path

import pytest

from rcominote.code_guards import observed_storage_reference
from rcominote.code_references import inspect_references

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"
FIRST = EVIDENCE / "shell-first-2026-10-12.json"
SECOND = EVIDENCE / "shell-second-2026-10-12.json"


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
