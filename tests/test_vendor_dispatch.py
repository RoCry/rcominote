"""Oracle: captured TBB bytes, independently decoded calls, and actual lost log row."""

import json
from pathlib import Path

import pytest

from rcominote.code_guards import observed_handler_entry, observed_vendor_call
from rcominote.code_references import inspect_references
from rcominote.readback_verify import verify_readback

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"


def test_actual_dispatch_excludes_inline_data_and_recovers_extra_command():
    report = inspect_references(
        EVIDENCE / "vendor-handler-first-2026-10-12.json",
        EVIDENCE / "vendor-handler-second-2026-10-12.json",
        handler=True,
    )
    cases = {int(row["command"], 16): row for row in report["dispatch"]["cases"]}
    # Hand-decoded final table entry 95 at b449 branches to b53a; BL there
    # is ff f7 bf fd, resolving to b0c0. App already assigns 1a to backlight.
    assert (cases[0x1A]["callee"], cases[0x3A]["callee"]) == ("0x1000b05c", "0x1000b0c0")
    decoded = {int(ins["address"], 16) for region in report["code_regions"] for ins in region["instructions"]}
    assert not any(0x1000B410 <= address < 0x1000B44A for address in decoded)


def test_captured_middle_row_loss_fails_despite_all_transport_acks():
    capture = json.loads((EVIDENCE / "vendor-handler-lost-row-2026-10-12.json").read_text())
    capture["ok"] = capture["transport_ok"]  # Replay the state before content validation.
    verify_readback(capture)
    assert capture["transport_ok"] and not capture["ok"] and "0x1000b504" in capture["error"]


def test_buffered_entry_does_not_authorize_further_reads():
    capture = json.loads((EVIDENCE / "vendor-handler-buffered-entry-2026-10-12.json").read_text())
    assert not observed_handler_entry(capture["frames"])


def test_changed_direct_call_rejects_old_callee_address():
    capture = json.loads((EVIDENCE / "vendor-handler-first-2026-10-12.json").read_text())
    assert observed_vendor_call(capture["frames"])
    for frame in capture["frames"]:
        frame["text"] = frame.get("text", "").replace("01 f0 32 f9", "01 f0 33 f9")
    with pytest.raises(ValueError, match="vendor call code changed"):
        observed_vendor_call(capture["frames"])
