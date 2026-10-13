"""Actual reply oracles and recording-ownership failure sequences for fixed reads."""

import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from rcominote.experiments.audio_state import FixedReads, measure_recording

# Captured NOTE START/STOP, FW010004, 2026-10-13 physical screen oracle.
START = bytes.fromhex("00323032363130313330393432333501")
STOP = bytes.fromhex("00323032363130313330393432333500005ea40101")
# Recording-info field table: status, 14-byte name, big-endian size, file kind.
OWNED = bytes.fromhex("00323032363130313330393432333500005ea401")
OTHER = bytes.fromhex("00323032363130313330393435313100005f3600")
IDLE = {"recording_state": "idle", "mode": "note"}
ACTIVE = {"recording_state": "recording", "mode": "note"}


class AudioStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_corrupt_stream_fails_before_any_read_and_retains_notifications(self):
        evidence = (
            Path(__file__).resolve().parents[1] / "docs/evidence/note-call-runtime-attempt-2026-10-13.json"
        )
        packets = json.loads(evidence.read_text())["diagnostic_only_control"]["notifications"]
        conn = AsyncMock()
        conn._check_failure = lambda: None
        report = {}
        reader = FixedReads(conn, report)
        for packet in packets:
            reader.receive(None, bytes.fromhex(packet["hex"]))
        with self.assertRaisesRegex(ValueError, "Unexpected Actions log header: 7973696361"):
            for _ in packets:
                await reader.pump()
        self.assertEqual([row["hex"] for row in report["notifications"]], [row["hex"] for row in packets])
        conn.client.write_gatt_char.assert_not_called()

    async def test_existing_recording_is_not_started_or_stopped(self):
        conn = AsyncMock()
        conn.device_info.return_value = ACTIVE
        with self.assertRaisesRegex(ValueError, "already active"):
            await measure_recording(conn, AsyncMock(), {})
        conn.command.assert_not_called()

    async def test_read_timeout_still_stops_owned_recording(self):
        conn = AsyncMock()
        conn.device_info.side_effect = [IDLE, ACTIVE, ACTIVE, IDLE, IDLE]
        conn.command.side_effect = [START, OWNED, STOP]
        reader = AsyncMock()
        reader.snapshot.side_effect = TimeoutError("MMIO reply not delivered")
        report = {}
        with self.assertRaisesRegex(TimeoutError, "MMIO reply"):
            await measure_recording(conn, reader, report)
        self.assertEqual([call.args[0] for call in conn.command.await_args_list], [6, 21, 7])
        self.assertEqual(report["final_device_info"]["recording_state"], "idle")

    async def test_replaced_recording_refuses_stop(self):
        conn = AsyncMock()
        conn.device_info.side_effect = [IDLE, ACTIVE, ACTIVE]
        conn.command.side_effect = [START, OTHER]
        reader = AsyncMock()
        reader.snapshot.return_value = {"mode": "note"}
        report = {}
        with self.assertRaisesRegex(RuntimeError, "cleanup not confirmed"):
            await measure_recording(conn, reader, report)
        self.assertIn("Current recording differs", report["cleanup_error"])
        self.assertEqual([call.args[0] for call in conn.command.await_args_list], [6, 21])

    async def test_lost_start_reply_does_not_claim_ownership_or_cleanup_success(self):
        conn = AsyncMock()
        conn.device_info.return_value = IDLE
        conn.command.side_effect = [TimeoutError("START reply lost"), OWNED]
        report = {}
        with self.assertRaisesRegex(RuntimeError, "cleanup not confirmed"):
            await measure_recording(conn, AsyncMock(), report)
        self.assertIn("START reply lost", report["measurement_error"])
        self.assertIn("ownership unknown", report["cleanup_error"])
        self.assertEqual([call.args[0] for call in conn.command.await_args_list], [6, 21])

    async def test_mmio_refused_until_guards_match_and_byte_reads_never_touch_mmio(self):
        conn = AsyncMock()
        reader = FixedReads(conn, {})
        with self.assertRaisesRegex(ValueError, "Unverified"):
            await reader.read(0x40068234, 4, word=True)
        reader.verified = True
        with self.assertRaisesRegex(ValueError, "Non-profile byte"):
            await reader.read(0x40068234, 4)
        conn.client.write_gatt_char.assert_not_called()

    async def test_changed_code_does_not_enable_runtime_reads(self):
        reader = FixedReads(AsyncMock(), {})
        reader.read = AsyncMock(return_value=bytes.fromhex("01ba0018"))
        # Fixed actual GET_INFO context literal from complete system image.
        with self.assertRaisesRegex(ValueError, "Live code/literal changed"):
            await reader.verify({0x1000ABEC: bytes.fromhex("00ba0018")})
        self.assertFalse(reader.verified)


if __name__ == "__main__":
    unittest.main()
