"""Oracle: actual 2026-10-12 RAM rows; captured ACK/F1 are insufficient alone."""

import json
from pathlib import Path

from rcominote.printk_state import inspect_state
from rcominote.readback_verify import verify_readback

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/printk-state-first-2026-10-12.json"


def captured():
    return json.loads(EVIDENCE.read_text())


def test_actual_console_fields_and_branch():
    state = inspect_state(captured())
    # Captured row bytes: 60 9f 0b 10; 01 00; c9 78 02 10.
    assert {
        key: state[key] for key in ("device_pointer", "init", "panic", "character_hook", "branch_from_flags")
    } == {
        "device_pointer": "0x100b9f60",
        "init": 1,
        "panic": 0,
        "character_hook": "0x100278c9",
        "branch_from_flags": "dma_buffer",
    }


def test_missing_ram_declaration_invalidates_previous_result():
    capture = captured()
    capture["fixed_text_commands"].remove("dbg mdb 180018c8 4")
    verify_readback(capture)
    assert not capture["ok"] and not capture["readback_complete"] and "console_state" not in capture


def test_changed_actual_literal_rejects_state():
    capture = captured()
    for frame in capture["frames"]:
        if "10026ed0: 04 e0 00 18" in frame.get("text", ""):
            frame["text"] = frame["text"].replace("10026ed0: 04 e0 00 18", "10026ed0: 08 e0 00 18")
    verify_readback(capture)
    assert not capture["ok"] and "code/literal changed" in capture["error"]
