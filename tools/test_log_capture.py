#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["bleak>=1.1,<2", "typer>=0.16,<1"]
# ///
"""Oracle: actual CoMi notification fragments and observed shell response."""

import json
import unittest
from pathlib import Path

from log_capture import Stream, observed_logsrv_entry

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

    def test_real_nvram_bytes_reach_ble(self):
        capture = json.loads((EVIDENCE / "log-platform-info-2026-10-12.json").read_text())
        stream = Stream()
        for row in capture["notifications"]:
            stream.feed(bytes.fromhex(row["hex"]))
        text = "".join(frame.get("text", "") for frame in stream.frames)
        self.assertIn("nvram get: FW_VERION fail", text)
        self.assertIn("nvram get(len=14): BT_LE_NAME", text)
        self.assertIn("43 6f 4d 69 20 4e 6f 74 65 20 32 46 30 31", text)

    def test_live_entry_guard_accepts_observed_thread_and_rejects_changed_firmware(self):
        capture = json.loads((EVIDENCE / "log-threads-2026-10-12.json").read_text())
        frames = capture["frames"]
        self.assertTrue(observed_logsrv_entry(frames))
        changed = [
            dict(row, text=row.get("text", "").replace("entry: 0x1000bf21", "entry: 0x1000cf21")) for row in frames
        ]
        with self.assertRaisesRegex(ValueError, "entry changed"):
            observed_logsrv_entry(changed)
        self.assertFalse(observed_logsrv_entry([]))

    def test_disconnect_mid_frame_preserves_incomplete_evidence(self):
        capture = json.loads((EVIDENCE / "log-device-info-2026-10-12.json").read_text())
        wire = b"".join(bytes.fromhex(row["hex"]) for row in capture["notifications"])
        stream = Stream()
        stream.feed(wire[:-1])
        self.assertFalse(stream.ended)
        self.assertTrue(stream.pending)


if __name__ == "__main__":
    unittest.main()
