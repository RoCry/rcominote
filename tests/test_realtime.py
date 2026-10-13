"""Capture publication and recorder cleanup across realistic failure sequences."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from rcominote import protocol as P
from rcominote.connection import Connection
from rcominote.realtime import capture_audio

# Real START/STOP replies from docs/evidence/realtime-live-2026-10-12.json.
START = bytes.fromhex("00323032363130313232323235313001")
STOP = bytes.fromhex("00323032363130313232323235313000004eec0101")
IDLE = {"recording_state": "idle"}
ACTIVE = {"recording_state": "recording"}
# Actual idle GET_DEVICE_INFO capture, also retained in test_comi.py.
IDLE_FRAME = bytes.fromhex(
    "d22d0105340000e8f20000e8f00164000100040101ff78696e6b5f746573740000000000000000000000000009ff0300010000000000000000b321"
)


class RealtimeExportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.out = Path(self.directory.name) / "capture.bin"
        self.client = AsyncMock()
        self.client.services.get_service = lambda _uuid: object()
        with patch("rcominote.connection.create_client", return_value=self.client):
            self.conn = Connection("replay")
        await self.conn.__aenter__()

    async def asyncTearDown(self):
        await self.conn.__aexit__(None, None, None)
        self.directory.cleanup()

    async def emit_when_subscribed(self, *chunks):
        while not self.conn._realtime_enabled:
            await asyncio.sleep(0)
        for chunk in chunks:
            self.conn._received_realtime(None, bytearray(chunk))

    def assert_no_output(self):
        self.assertEqual(list(self.out.parent.iterdir()), [])

    async def test_passive_capture_preserves_bytes_and_never_sends_command(self):
        emitter = asyncio.create_task(self.emit_when_subscribed(b"a", b"bc"))
        report = await capture_audio(self.conn, self.out, 0.1)
        await emitter
        self.assertEqual(self.out.read_bytes(), b"abc")
        # SHA-256('abc'), published FIPS180-4 example; independent byte oracle.
        self.assertEqual(report["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(report["completeness"], "unverified; no offline recording comparison")
        self.client.write_gatt_char.assert_not_awaited()
        self.client.stop_notify.assert_not_awaited()

    async def test_existing_recording_is_never_stopped(self):
        self.conn.device_info = AsyncMock(return_value=ACTIVE)
        self.conn.command = AsyncMock()
        with self.assertRaisesRegex(ValueError, "no command sent"):
            await capture_audio(self.conn, self.out, 0.1, record=True)
        self.conn.command.assert_not_awaited()
        self.assert_no_output()

    async def test_lost_start_ack_reports_unconfirmed_cleanup_without_reusing_session(self):
        failure = TimeoutError("lost START ACK")
        self.conn._next = AsyncMock(side_effect=[("cmd", IDLE_FRAME), failure])
        with self.assertRaisesRegex(RuntimeError, "Recording may still be running; reconnect") as caught:
            await capture_audio(self.conn, self.out, 0.1, record=True)
        self.assertIs(caught.exception.__cause__, failure)
        self.assertEqual([call.args[1][3] for call in self.client.write_gatt_char.await_args_list], [5, 6])
        self.assert_no_output()

    async def test_cancel_during_start_preserves_cancellation_and_cleanup_warning(self):
        started = asyncio.Event()
        self.conn.queue.put_nowait(("cmd", IDLE_FRAME))

        async def write(_characteristic, packet, **_kwargs):
            if packet[3] == P.START_RECORDING:
                started.set()

        self.client.write_gatt_char.side_effect = write
        task = asyncio.create_task(capture_audio(self.conn, self.out, 0.1, record=True))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError) as caught:
            await task
        self.assertIn("Recording may still be running; reconnect", caught.exception.__notes__[0])
        self.assertEqual([call.args[1][3] for call in self.client.write_gatt_char.await_args_list], [5, 6])
        self.assert_no_output()

    async def test_capture_limit_failure_stops_recording_and_discards_partial_file(self):
        self.conn.device_info = AsyncMock(side_effect=[IDLE, ACTIVE, ACTIVE, ACTIVE, IDLE])
        self.conn.command = AsyncMock(side_effect=[START, STOP])
        emitter = asyncio.create_task(self.emit_when_subscribed(b"abcd"))
        with (
            patch("rcominote.connection.REALTIME_BYTE_LIMIT", 3),
            self.assertRaisesRegex(RuntimeError, "16 MiB"),
        ):
            await capture_audio(self.conn, self.out, 0.1, record=True)
        await emitter
        self.assertEqual([call.args[0] for call in self.conn.command.await_args_list], [6, 7])
        self.assert_no_output()

    async def test_cleanup_failure_reports_both_errors(self):
        self.conn.device_info = AsyncMock(side_effect=[IDLE, ConnectionError("gone")])
        self.conn.command = AsyncMock(side_effect=TimeoutError("lost START ACK"))
        with self.assertRaisesRegex(RuntimeError, "lost START ACK; recording cleanup also failed: gone"):
            await capture_audio(self.conn, self.out, 0.1, record=True)
        self.assert_no_output()

    async def test_recording_stop_data_is_captured_before_publication(self):
        self.conn.device_info = AsyncMock(side_effect=[IDLE, ACTIVE, ACTIVE, ACTIVE, IDLE])

        async def command(opcode):
            if opcode == P.START_RECORDING:
                self.conn._received_realtime(None, bytearray(b"a"))
                return START
            self.conn._received_realtime(None, bytearray(b"bc"))
            return STOP

        self.conn.command = AsyncMock(side_effect=command)
        report = await capture_audio(self.conn, self.out, 0.1, record=True)
        self.assertEqual(self.out.read_bytes(), b"abc")
        self.assertEqual(report["recording"]["stop"]["name"], "20261012222510")
        self.assertEqual(report["bytes"], 3)

    async def test_empty_owned_recording_is_not_published(self):
        self.conn.device_info = AsyncMock(side_effect=[IDLE, ACTIVE, ACTIVE, ACTIVE, IDLE])
        self.conn.command = AsyncMock(side_effect=[START, STOP])
        with self.assertRaisesRegex(RuntimeError, "no realtime audio bytes"):
            await capture_audio(self.conn, self.out, 0.1, record=True)
        self.assert_no_output()

    async def test_changed_recording_name_fails_after_stop_and_idle_readback(self):
        self.conn.device_info = AsyncMock(side_effect=[IDLE, ACTIVE, ACTIVE, ACTIVE, IDLE, IDLE])
        # A different final digit, independent of the START name.
        other_stop = bytes.fromhex("00323032363130313232323235313100004eec0101")
        self.conn.command = AsyncMock(side_effect=[START, other_stop])
        with self.assertRaisesRegex(RuntimeError, "name differs"):
            await capture_audio(self.conn, self.out, 0.1, record=True)
        self.assert_no_output()

    async def test_racing_exporter_is_never_overwritten(self):
        async def competing_writer():
            await self.emit_when_subscribed(b"abc")
            self.out.write_bytes(b"other exporter")

        competitor = asyncio.create_task(competing_writer())
        with self.assertRaises(FileExistsError):
            await capture_audio(self.conn, self.out, 0.1)
        await competitor
        self.assertEqual([path.name for path in self.out.parent.iterdir()], ["capture.bin"])
        self.assertEqual(self.out.read_bytes(), b"other exporter")

    async def test_nonfinite_duration_and_dangling_symlink_fail_before_subscribing(self):
        for duration in (float("nan"), float("inf"), 0, 301):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                await capture_audio(self.conn, self.out, duration)
        self.out.symlink_to("missing")
        with self.assertRaises(FileExistsError):
            await capture_audio(self.conn, self.out, 0.1)
        self.assertFalse(self.conn._realtime_enabled)
