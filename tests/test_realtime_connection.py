"""Actual CCC lifecycle regression and sink/disconnect failure sequences."""

import asyncio
import io
import unittest
from unittest.mock import AsyncMock, patch

from rcominote import protocol as P
from rcominote.connection import Connection


class RealtimeConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = AsyncMock()
        with patch("rcominote.connection.BleakClient", return_value=self.client):
            self.conn = Connection(object())

    async def test_capture_close_retains_subscription_and_second_capture_excludes_gap(self):
        first, second = io.BytesIO(), io.BytesIO()
        async with self.conn.realtime_capture(first.write) as capture:
            self.conn._received_realtime(None, bytearray(b"\xff\xf3\x48\xc0"))
            self.conn._received_realtime(None, bytearray(b"\x01\x02"))
        self.conn._received_realtime(None, bytearray(b"gap"))
        async with self.conn.realtime_capture(second.write):
            self.conn._received_realtime(None, bytearray(b"next"))
        self.assertEqual(
            (first.getvalue(), second.getvalue(), capture.bytes, capture.packets),
            (b"\xff\xf3\x48\xc0\x01\x02", b"next", 6, 2),
        )
        self.client.start_notify.assert_awaited_once_with(P.NOTIFY_REALTIME, self.conn._received_realtime)
        self.client.stop_notify.assert_not_awaited()

    async def test_short_write_fails_capture_but_commands_still_work_for_stop(self):
        with self.assertRaisesRegex(OSError, "Short write"):
            async with self.conn.realtime_capture(lambda _data: 1):
                self.conn._received_realtime(None, bytearray(b"abc"))
                await self.conn._write(P.STOP_RECORDING)
        self.client.write_gatt_char.assert_awaited_once()
        self.assertIsNone(self.conn._realtime_capture)

    async def test_disconnect_interrupts_wait_and_detaches_capture(self):
        with self.assertRaisesRegex(ConnectionError, "disconnected"):
            async with self.conn.realtime_capture(io.BytesIO().write) as capture:
                asyncio.get_running_loop().call_soon(self.conn._dropped, None)
                await capture.wait(10)
        self.assertIsNone(self.conn._realtime_capture)

    async def test_concurrent_capture_cannot_replace_first_sink(self):
        sink = io.BytesIO()
        async with self.conn.realtime_capture(sink.write):
            with self.assertRaisesRegex(RuntimeError, "already active"):
                async with self.conn.realtime_capture(io.BytesIO().write):
                    self.fail("second capture entered")
            self.conn._received_realtime(None, bytearray(b"first"))
        self.assertEqual(sink.getvalue(), b"first")

    async def test_subscribe_failure_detaches_and_allows_retry(self):
        self.client.start_notify.side_effect = [OSError("CCC rejected"), None]
        with self.assertRaisesRegex(OSError, "CCC rejected"):
            async with self.conn.realtime_capture(io.BytesIO().write):
                self.fail("capture entered after rejected subscription")
        async with self.conn.realtime_capture(io.BytesIO().write):
            pass
        self.assertEqual(self.client.start_notify.await_count, 2)
