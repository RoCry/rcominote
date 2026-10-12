#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["bleak>=1.1,<2", "typer>=0.16,<1"]
# ///
"""Oracle: actual CoMi notification fragments and observed shell response."""

import json
import unittest
from pathlib import Path

from log_capture import Stream

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"


class LogTests(unittest.TestCase):
    def test_real_fragmented_version_and_missing_command(self):
        capture = json.loads((EVIDENCE / "log-device-info-2026-10-12.json").read_text())
        stream = Stream()
        for row in capture["notifications"]:
            stream.feed(bytes.fromhex(row["hex"]))
        text = "".join(frame.get("text", "") for frame in stream.frames)
        self.assertIn("Zephyr version 2.7.0", text)
        self.assertEqual(text.count("device: command not found"), 2)
        self.assertEqual((stream.acks, stream.ended, bytes(stream.pending)), (6, True, b""))

    def test_disconnect_mid_frame_preserves_incomplete_evidence(self):
        capture = json.loads((EVIDENCE / "log-device-info-2026-10-12.json").read_text())
        wire = b"".join(bytes.fromhex(row["hex"]) for row in capture["notifications"])
        stream = Stream()
        stream.feed(wire[:-1])
        self.assertFalse(stream.ended)
        self.assertTrue(stream.pending)


if __name__ == "__main__":
    unittest.main()
