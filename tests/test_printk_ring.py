"""Oracles: retained actual BLE capture, including its self-overwritten log payload."""

import json
from pathlib import Path

from rcominote.printk_ring import inspect
from rcominote.readback_verify import verify_readback

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/printk-ring-live-2026-10-12.json"


def captured():
    return json.loads(EVIDENCE.read_text())


def test_actual_ring_snapshot():
    result = inspect(captured())
    assert (result["bytes"], result["before"]["write_index"], result["after"]["write_index"]) == (
        4096,
        2203,
        1907,
    )
    assert bytes.fromhex(result["physical_order_hex"]).startswith(b"owing m    :actlog commands")


def test_lost_payload_row_invalidates_transport_success():
    capture = captured()
    for frame in capture["frames"]:
        if "1803ee10:" in frame.get("text", ""):
            frame["text"] = frame["text"].replace("1803ee10:", "lost-row:")
    verify_readback(capture)
    assert not capture["ok"] and not capture["readback_complete"] and "console_ring" not in capture


def test_changed_buffer_pointer_refuses_snapshot():
    capture = captured()
    for frame in capture["frames"]:
        if "1800e018: 09 ee 03 18" in frame.get("text", ""):
            frame["text"] = frame["text"].replace("1800e018: 09 ee 03 18", "1800e018: 00 00 00 40")
    verify_readback(capture)
    assert not capture["ok"] and "address/capacity" in capture["error"]
