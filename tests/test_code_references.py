"""Captured literals/function name, and the known complete-transport/lost-text failure."""

import json
from pathlib import Path

import pytest

from rcominote.code_references import inspect_references
from rcominote.log_capture import observed_logsrv_literals, verify_readback

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
