"""Oracle: real completed BLE frames with its final F1 deliberately lost."""

import json
from copy import deepcopy
from pathlib import Path

from rcominote.log_stream import Stream
from rcominote.readback_verify import finish_capture


def test_missing_shared_end_cannot_publish_already_read_windows():
    path = Path(__file__).resolve().parents[1] / "docs/evidence/printk-nor-tail-second-2026-10-12.json"
    result = json.loads(path.read_text())
    record = deepcopy(result)
    result["batch_records"] = [record]
    stream = Stream()
    for frame in result["frames"]:
        if frame["command"] != 0xF1:
            stream.feed(bytes.fromhex(frame["hex"]))
    finish_capture(result, stream, result["ack_count"])
    assert not result["ok"] and not record["ok"] and not record["readback_complete"]
