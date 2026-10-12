"""Oracles: independently captured tails from two offset-zero reads."""

import json
from pathlib import Path

from rcominote.printk_tail import append_tail, inspect
from rcominote.readback_verify import verify_readback

ROOT = Path(__file__).resolve().parents[1] / "docs/evidence"


def captured(name="second"):
    return json.loads((ROOT / f"printk-nor-tail-{name}-2026-10-12.json").read_text())


def test_repeated_actual_nor_tail_rows():
    expected = (
        "     1e0: b7 13 b7 80 78 f2 cd 58 e3 7b 82 e2 c3 86 2e a2 \r\n"
        "     1f0: 9f 8b 4b 71 c1 a8 d7 8e 2e 69 f7 cc 8b b5 48 e1 \r\n"
    )
    assert all(expected in inspect(captured(name))["text"] for name in ("second", "third"))


def test_in_progress_capture_can_schedule_tail_once():
    # First live attempt failed here because read_block required completed state.
    capture = captured()
    capture["ok"] = False
    capture.pop("tail_appended")
    capture["fixed_text_commands"] = capture["fixed_text_commands"][:-2]
    append_tail(capture)
    append_tail(capture)
    assert capture["fixed_text_commands"][-3:] == ["help", "dbg mdb 1803f2de 100", "help"]


def test_missing_actual_tail_row_rejects_ack_success():
    capture = captured()
    for frame in capture["frames"]:
        if "1803f2de:" in frame.get("text", ""):
            frame["text"] = frame["text"].replace("1803f2de:", "lost-row:")
    verify_readback(capture)
    assert not capture["ok"] and not capture["readback_complete"] and "console_tail" not in capture
