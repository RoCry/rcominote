"""Deletion sequences: captured list/status and independent official-JS wire oracles."""

import asyncio
import json
import signal
import unittest
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from rcominote.cli import app
from rcominote.connection import Connection
from rcominote.recording_delete import DeletionUnverified, delete_recording

NAME = "20261012112429"
SERIAL = "C261CF0430"
# Captured on 2026-10-12; source and fields documented in test_comi.py.
SERIAL_REPLY = bytes.fromhex("d22d01010a4332363143463034333060bb")
OTHER_FILE = bytes.fromhex("d22d010a1400323032363130313230383535343200001e7c01e12f")
LIST_END = bytes.fromhex("d22d010a01021fdb")
IDLE = bytes.fromhex(
    "d22d0105340000e8f20000e8f00164000100040101ff78696e6b5f746573740000000000000000000000000009ff0300010000000000000000b321"
)
# Official Bt/ry/ho JS executed independently; see docs/file-deletion.md.
# TARGET is a synthetic listed file of size3. ACK has no proven result-byte meaning.
TARGET = bytes.fromhex("d22d010a140032303236313031323131323432390000000301f54d")
DELETE = bytes.fromhex("d22d010d0e32303236313031323131323432391ec2")
ACK = bytes.fromhex("d22d010d01002fdb")
SHORT_ENTRY = bytes.fromhex("d22d010a01009e1a")
BUSY = bytes.fromhex(
    "d22d0105340000e8f20000e8f00164010100040101ff78696e6b5f746573740000000000000000000000000009ff03000100000000000000004fe3"
)


def replay(*, before=(TARGET, OTHER_FILE, LIST_END), after=(OTHER_FILE, LIST_END), on_delete=None, info=IDLE):
    client = AsyncMock()
    client.services.get_service = lambda _uuid: object()
    with patch("rcominote.connection.create_client", return_value=client):
        conn = Connection("delete-replay")
    lists = 0

    async def on_write(_uuid, packet, **_kwargs):
        nonlocal lists
        if packet[3] == 1:
            packets = (SERIAL_REPLY,)
        elif packet[3] == 5:
            packets = (info,)
        elif packet[3] == 10:
            packets = before if lists == 0 else after
            lists += 1
        elif packet[3] == 13:
            if on_delete:
                await on_delete()
            packets = (ACK,)
        else:
            raise AssertionError(f"Unexpected wire request: {packet.hex()}")
        for response in packets:
            conn._received("cmd", response)

    client.write_gatt_char.side_effect = on_write
    return conn, client


def writes(client):
    return [call.args[1] for call in client.write_gatt_char.await_args_list]


class RecordingDeleteTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_golden_request_and_complete_list_absence(self):
        conn, client = replay()
        result = await delete_recording(conn, NAME)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "target_absent")
        self.assertEqual([entry["name"] for entry in result["after"]], ["20261012085542"])
        self.assertEqual([packet for packet in writes(client) if packet[3] == 13], [DELETE])
        self.assertFalse(result["secure_erasure_verified"])

    async def test_ack_with_target_still_listed_fails_without_retry(self):
        conn, client = replay(after=(TARGET, OTHER_FILE, LIST_END))
        with self.assertRaises(DeletionUnverified) as caught:
            await delete_recording(conn, NAME)
        self.assertEqual(caught.exception.outcome["status"], "target_still_listed")
        self.assertTrue(caught.exception.outcome["response_received"])
        self.assertEqual([packet[3] for packet in writes(client)], [5, 10, 13, 10])

    async def test_short_or_unterminated_post_list_is_unknown_and_late_ack_cannot_reuse(self):
        for after in ((SHORT_ENTRY,), (OTHER_FILE,)):
            with self.subTest(after=after):
                conn, client = replay(after=after)
                actual_list = conn.file_list

                async def bounded_list(actual_list=actual_list):
                    return await actual_list(timeout=0.01)

                with (
                    patch.object(conn, "file_list", new=bounded_list),
                    self.assertRaises(DeletionUnverified) as caught,
                ):
                    await delete_recording(conn, NAME)
                self.assertEqual(caught.exception.outcome["status"], "unknown")
                self.assertTrue(caught.exception.outcome["response_received"])
                self.assertIsNone(caught.exception.outcome["after"])
                self.assertEqual([packet[3] for packet in writes(client)], [5, 10, 13, 10])
                conn._received("cmd", ACK)
                conn._received("cmd", LIST_END)
                with self.assertRaisesRegex(ConnectionError, "reconnect"):
                    await conn.serial()
                self.assertEqual(len(writes(client)), 4)

    async def test_absent_duplicate_or_incomplete_before_list_never_deletes(self):
        for before in ((OTHER_FILE, LIST_END), (TARGET, TARGET, LIST_END), (SHORT_ENTRY,)):
            with self.subTest(before=before):
                conn, client = replay(before=before)
                with self.assertRaises(ValueError):
                    await delete_recording(conn, NAME)
                self.assertEqual([packet[3] for packet in writes(client)], [5, 10])

    async def test_active_recording_stops_before_file_list_or_delete(self):
        conn, client = replay(info=BUSY)
        with self.assertRaisesRegex(ValueError, "idle"):
            await delete_recording(conn, NAME)
        self.assertEqual([packet[3] for packet in writes(client)], [5])

    async def test_cancellation_pending_after_buffered_before_list_never_sends_delete(self):
        conn, client = replay()
        actual_list = conn.file_list

        async def cancel_after_complete_list():
            entries = await actual_list()
            asyncio.current_task().cancel()
            return entries

        with patch.object(conn, "file_list", new=cancel_after_complete_list):
            task = asyncio.create_task(delete_recording(conn, NAME))
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual([packet[3] for packet in writes(client)], [5, 10])


class RecordingDeleteCliTests(unittest.TestCase):
    def test_missing_options_and_mismatched_confirmation_fail_before_bluetooth(self):
        for args in (
            ["delete", NAME],
            ["delete", NAME, "--confirm-delete", NAME],
            ["delete", NAME, "--serial", SERIAL],
            ["delete", NAME, "--serial", SERIAL, "--confirm-delete", "other"],
            ["delete", NAME, "--serial", "", "--confirm-delete", NAME],
            ["delete", NAME, "--serial", " ", "--confirm-delete", NAME],
        ):
            with (
                self.subTest(args=args),
                patch("rcominote.recording_delete.find_device", new=AsyncMock()) as find,
            ):
                result = CliRunner().invoke(app, args)
                self.assertNotEqual(result.exit_code, 0)
                find.assert_not_awaited()

    def test_identity_mismatch_stops_before_any_delete_preparation(self):
        conn, client = replay()
        with (
            patch("rcominote.recording_delete.find_device", new=AsyncMock(return_value="delete-replay")),
            patch("rcominote.recording_delete.Connection", return_value=conn),
        ):
            result = CliRunner().invoke(app, ["delete", NAME, "--serial", "WRONG", "--confirm-delete", NAME])
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual([packet[3] for packet in writes(client)], [1])
        client.__aexit__.assert_awaited_once()

    def test_real_sigint_after_delete_is_unknown_exit_130_and_disconnect(self):
        async def interrupt_pending_write():
            signal.raise_signal(signal.SIGINT)
            # Model cancellation while the actual GATT write awaits its callback.
            await asyncio.Event().wait()

        self.assert_sigint_outcome(interrupt_pending_write, response_received=False)

    def test_real_sigint_with_synchronously_buffered_ack_never_sends_post_list(self):
        async def interrupt_without_suspending():
            signal.raise_signal(signal.SIGINT)
            # Return synchronously: the ACK and all list replies are immediately
            # available, so only a cooperative checkpoint can deliver cancellation.

        self.assert_sigint_outcome(interrupt_without_suspending, response_received=True)

    def assert_sigint_outcome(self, interrupt_write, *, response_received):
        conn, client = replay(on_delete=interrupt_write)
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            with (
                patch("rcominote.recording_delete.find_device", new=AsyncMock(return_value="delete-replay")),
                patch("rcominote.recording_delete.Connection", return_value=conn),
            ):
                result = CliRunner().invoke(
                    app, ["delete", NAME, "--serial", SERIAL, "--confirm-delete", NAME]
                )
        finally:
            signal.signal(signal.SIGINT, previous)
        self.assertEqual(result.exit_code, 130, result.output)
        outcome = json.loads(result.stdout)
        self.assertEqual(outcome["status"], "unknown")
        self.assertFalse(outcome["ok"])
        self.assertTrue(outcome["cancelled"])
        self.assertEqual(outcome["response_received"], response_received)
        self.assertEqual([packet[3] for packet in writes(client)], [1, 5, 10, 13])
        client.__aexit__.assert_awaited_once()
