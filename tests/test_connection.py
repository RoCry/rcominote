"""Transaction oracles: captured list frames and explicit protocol sequences.

Download frames below encode the documented status/size layout; state-machine
tests never call the framing implementation to manufacture their inputs.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from rcominote.connection import Connection, validate_filename
from rcominote.recording_export import export_recording

# Real CoMi capture, 2026-10-12 (also used by test_comi).
FILE_ENTRY = bytes.fromhex("d22d010a1400323032363130313230383535343200001e7c01e12f")
LIST_END = bytes.fromhex("d22d010a01021fdb")
SERIAL_REPLY = bytes.fromhex("d22d01010a4332363143463034333060bb")
# Literal valid wire fixtures: GET_FILE_DATA status 0, size 3; status 2 end.
SIZE_THREE = bytes.fromhex("d22d010b0500000000035f6a")
SIZE_ZERO = bytes.fromhex("d22d010b0500000000001f6b")
DOWNLOAD_END = bytes.fromhex("d22d010b01024e1b")
UNKNOWN_DOWNLOAD = bytes.fromhex("d22d010b01038fdb")
SHORT_DECLARATION = bytes.fromhex("d22d010b03000000d5d3")
UNKNOWN_LIST = bytes.fromhex("d22d010a0103de1b")
EMPTY_LIST = bytes.fromhex("d22d010a00e61e")
MALFORMED_LIST_END = bytes.fromhex("d22d010a0202006ac8")


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    def replay(self, *events):
        client = AsyncMock()
        client.services.get_service = lambda _uuid: object()
        with patch("rcominote.connection.BleakClient", return_value=client):
            conn = Connection("replay")
        for event in events:
            conn.queue.put_nowait(event)
        return conn

    async def test_notification_setup_failure_disconnects(self):
        conn = self.replay()
        conn.client.start_notify.side_effect = [None, RuntimeError("offline notify unavailable")]
        with self.assertRaisesRegex(RuntimeError, "offline notify unavailable"):
            await conn.__aenter__()
        conn.client.__aexit__.assert_awaited_once()

    async def test_missing_service_disconnects(self):
        conn = self.replay()
        conn.client.services.get_service = lambda _uuid: None
        with self.assertRaisesRegex(ValueError, "Boyi control service"):
            await conn.__aenter__()
        conn.client.__aexit__.assert_awaited_once()

    async def test_captured_file_list(self):
        conn = self.replay(("cmd", FILE_ENTRY), ("cmd", LIST_END))
        entries = await conn.file_list()
        self.assertEqual([(item.name, item.size) for item in entries], [("20261012085542", 7804)])

    async def test_malformed_lists_fail_instead_of_returning_empty(self):
        for packet in (UNKNOWN_LIST, EMPTY_LIST, MALFORMED_LIST_END):
            with self.subTest(packet=packet.hex()):
                conn = self.replay(("cmd", packet), ("cmd", LIST_END))
                with self.assertRaises(ValueError):
                    await conn.file_list()

    async def test_duplicate_file_entry_fails(self):
        conn = self.replay(("cmd", FILE_ENTRY), ("cmd", FILE_ENTRY), ("cmd", LIST_END))
        with self.assertRaisesRegex(ValueError, "Duplicate recording"):
            await conn.file_list()

    async def test_complete_download_requires_size_bytes_and_end(self):
        conn = self.replay(("cmd", SIZE_THREE), ("off", b"a"), ("off", b"bc"), ("cmd", DOWNLOAD_END))
        chunks = []
        received = await conn.download("20261012085542", chunks.append)
        self.assertEqual((received, b"".join(chunks)), (3, b"abc"))

    async def test_empty_file_with_explicit_size_and_end(self):
        conn = self.replay(("cmd", SIZE_ZERO), ("cmd", DOWNLOAD_END))
        received = await conn.download("empty", lambda _data: self.fail("Unexpected bytes"))
        self.assertEqual(received, 0)

    async def test_nonzero_offset_uses_total_size_and_exports_only_suffix(self):
        conn = self.replay(("cmd", SIZE_THREE), ("off", b"bc"), ("cmd", DOWNLOAD_END))
        with tempfile.TemporaryDirectory() as directory:
            result = await export_recording(conn, "recording", Path(directory), expected_size=3, offset=1)
            self.assertEqual(Path(result["path"]).name, "recording.offset-1.bin")
            self.assertEqual(Path(result["path"]).read_bytes(), b"bc")
            self.assertEqual(result["scope"], "recording_suffix")
        wire = conn.client.write_gatt_char.call_args.args[1]
        self.assertEqual(wire[5:-2], b"recording\0\0\0\0\0\x00\x00\x00\x01")

    async def test_offset_at_eof_requires_explicit_end_and_no_data(self):
        conn = self.replay(("cmd", SIZE_THREE), ("cmd", DOWNLOAD_END))
        self.assertEqual(
            await conn.download("recording", lambda _: self.fail("Unexpected bytes"), offset=3), 0
        )

    async def test_suffix_size_and_offset_fail_before_accepting_wrong_bytes(self):
        for offset, events, message in (
            (4, [("cmd", SIZE_THREE)], "exceeds file size"),
            (1, [("cmd", SIZE_THREE), ("off", b"abc")], "exceeds declared remaining size"),
            (1, [("cmd", SIZE_THREE), ("off", b"b"), ("cmd", DOWNLOAD_END)], "Short download"),
        ):
            with (
                self.subTest(offset=offset, message=message),
                self.assertRaisesRegex((ValueError, RuntimeError), message),
            ):
                await self.replay(*events).download("recording", lambda _: None, offset=offset)

    async def test_invalid_offset_never_sends_request(self):
        for offset in (-1, 0x100000000, True, 1.5):
            conn = self.replay()
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "offset must"):
                await conn.download("recording", lambda _: None, offset=offset)
            conn.client.write_gatt_char.assert_not_awaited()

    async def test_invalid_transfer_sequences_fail(self):
        sequences = [
            ([("cmd", DOWNLOAD_END)], ValueError, "without a valid size"),
            ([("off", b"abc")], ValueError, "before its size"),
            ([("cmd", SIZE_THREE), ("off", b"a"), ("cmd", DOWNLOAD_END)], RuntimeError, "Short download"),
            ([("cmd", SIZE_THREE), ("off", b"abcd")], ValueError, "exceeds declared"),
            ([("cmd", UNKNOWN_DOWNLOAD)], ValueError, "Unknown GET_FILE_DATA"),
            ([("cmd", SHORT_DECLARATION)], ValueError, "Malformed or duplicate"),
            ([("cmd", SIZE_THREE), ("cmd", SIZE_THREE)], ValueError, "Malformed or duplicate"),
            ([("cmd", SIZE_THREE), None], ConnectionError, "disconnected"),
            ([("cmd", SIZE_THREE), ("off", b"abc")], TimeoutError, "deadline exceeded"),
        ]
        for events, error, message in sequences:
            with self.subTest(events=events):
                conn = self.replay(*events)
                with self.assertRaisesRegex(error, message):
                    await conn.download("recording", lambda _data: None, timeout=0.005)

    async def test_oversize_chunk_never_reaches_output(self):
        conn = self.replay(("cmd", SIZE_THREE), ("off", b"abcd"))
        chunks = []
        with self.assertRaisesRegex(ValueError, "exceeds declared"):
            await conn.download("recording", chunks.append)
        self.assertEqual(chunks, [])

    async def test_unrelated_notifications_cannot_extend_download_deadline(self):
        conn = self.replay(("cmd", SIZE_THREE))

        async def noise():
            while True:
                conn.queue.put_nowait(("cmd", SERIAL_REPLY))
                await asyncio.sleep(0.001)

        producer = asyncio.create_task(noise())
        try:
            with self.assertRaisesRegex(TimeoutError, "CoMi response deadline exceeded"):
                await asyncio.wait_for(conn.download("recording", lambda _data: None, timeout=0.01), 0.1)
        finally:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)

    async def test_partial_sink_write_fails(self):
        conn = self.replay(("cmd", SIZE_THREE), ("off", b"abc"))
        with self.assertRaisesRegex(OSError, "partial write"):
            await conn.download("recording", lambda _data: 2)

    async def test_failed_download_cannot_mix_late_tail_with_next_file(self):
        conn = self.replay(("cmd", SIZE_THREE), ("off", b"a"))

        def full_disk(_data):
            raise OSError("disk full")

        with self.assertRaisesRegex(OSError, "disk full"):
            await conn.download("first", full_disk)
        # With no stream/file ID, old tail 'b' plus new bytes 'cd' would pass
        # the next size=3 check. Reusing this session must be refused instead.
        for event in (("cmd", SIZE_THREE), ("off", b"b"), ("off", b"cd"), ("cmd", DOWNLOAD_END)):
            conn.queue.put_nowait(event)
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.download("second", lambda _data: self.fail("Mixed bytes reached output"))
        conn.client.write_gatt_char.assert_awaited_once()

    async def test_command_timeout_cannot_accept_late_reply_on_retry(self):
        conn = self.replay()
        with self.assertRaisesRegex(TimeoutError, "deadline exceeded"):
            await conn.command(1, timeout=0.001)
        conn.queue.put_nowait(("cmd", SERIAL_REPLY))
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.serial()
        conn.client.write_gatt_char.assert_awaited_once()

    async def test_malformed_file_list_prevents_a_following_command(self):
        conn = self.replay(("cmd", UNKNOWN_LIST), ("cmd", LIST_END), ("cmd", SERIAL_REPLY))
        with self.assertRaisesRegex(ValueError, "Malformed GET_FILE_LIST"):
            await conn.file_list()
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.serial()
        conn.client.write_gatt_char.assert_awaited_once()

    async def test_cancelled_inflight_request_invalidates_session(self):
        conn = self.replay()
        written = asyncio.Event()
        conn.client.write_gatt_char.side_effect = lambda *_args, **_kwargs: written.set()
        task = asyncio.create_task(conn.download("recording", lambda _data: None))
        await written.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.serial()
        conn.client.write_gatt_char.assert_awaited_once()

    async def test_cancelled_lock_waiter_does_not_invalidate_active_or_next_request(self):
        conn = self.replay()
        written = asyncio.Event()
        conn.client.write_gatt_char.side_effect = lambda *_args, **_kwargs: written.set()
        active = asyncio.create_task(conn.serial())
        await written.wait()
        waiter = asyncio.create_task(conn.file_list())
        await asyncio.sleep(0)
        waiter.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiter
        conn.queue.put_nowait(("cmd", SERIAL_REPLY))
        self.assertEqual(await active, "C261CF0430")
        conn.queue.put_nowait(("cmd", SERIAL_REPLY))
        self.assertEqual(await conn.serial(), "C261CF0430")
        self.assertEqual(conn.client.write_gatt_char.await_count, 2)

    async def test_preflight_errors_leave_session_usable(self):
        conn = self.replay(("cmd", SERIAL_REPLY))
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(ValueError, "timeout must"):
                await conn.command(1, timeout=timeout)
        with self.assertRaisesRegex(ValueError, "limited to 255"):
            await conn.command(1, b"x" * 256)
        with self.assertRaisesRegex(ValueError, "offset must"):
            await conn.download("recording", lambda _data: None, offset=-1)
        self.assertEqual(await conn.serial(), "C261CF0430")
        conn.client.write_gatt_char.assert_awaited_once()

    async def test_write_failure_preserves_error_and_invalidates_session(self):
        conn = self.replay()
        conn.client.write_gatt_char.side_effect = OSError("GATT write failed")
        with self.assertRaisesRegex(OSError, "GATT write failed"):
            await conn.serial()
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.file_list()
        conn.client.write_gatt_char.assert_awaited_once()

    async def test_fsync_failure_after_protocol_end_leaves_session_usable(self):
        conn = self.replay(("cmd", SIZE_THREE), ("off", b"abc"), ("cmd", DOWNLOAD_END))
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("rcominote.recording_export.os.fsync", side_effect=OSError("fsync failed")),
                self.assertRaisesRegex(OSError, "fsync failed"),
            ):
                await export_recording(conn, "recording", Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])
        conn.queue.put_nowait(("cmd", SERIAL_REPLY))
        self.assertEqual(await conn.serial(), "C261CF0430")

    async def test_unsafe_names_rejected_before_device_write(self):
        for name in ("", "a" * 15, "../secret", "/absolute", "a\\b", ".", "a\0b", "中文"):
            with self.subTest(name=name):
                conn = self.replay()
                with self.assertRaises(ValueError):
                    await conn.download(name, lambda _data: None)
                conn.client.write_gatt_char.assert_not_awaited()

    async def test_atomic_export_hash_matches_known_abc_digest(self):
        conn = self.replay(("cmd", SIZE_THREE), ("off", b"abc"), ("cmd", DOWNLOAD_END))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            result = await export_recording(conn, "recording", out, expected_size=3)
            self.assertEqual(
                result["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
            )
            self.assertEqual((out / "recording.mp3").read_bytes(), b"abc")
            self.assertEqual([path.name for path in out.iterdir()], ["recording.mp3"])

    async def test_failed_or_changed_download_leaves_no_final_or_partial_file(self):
        sequences = [
            ([("cmd", SIZE_THREE), ("off", b"a"), None], None, ConnectionError),
            ([("cmd", SIZE_THREE), ("off", b"abc"), ("cmd", DOWNLOAD_END)], 4, ValueError),
        ]
        for events, expected, error in sequences:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                out = Path(directory)
                with self.assertRaises(error):
                    await export_recording(self.replay(*events), "recording", out, expected_size=expected)
                self.assertEqual(list(out.iterdir()), [])

    async def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            target = out / "recording.mp3"
            target.write_bytes(b"original")
            conn = self.replay()
            with self.assertRaises(FileExistsError):
                await export_recording(conn, "recording", out)
            conn.client.write_gatt_char.assert_not_awaited()
            self.assertEqual(target.read_bytes(), b"original")

    async def test_concurrent_exporter_cannot_be_overwritten_at_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            conn = self.replay(("cmd", SIZE_THREE), ("off", b"abc"), ("cmd", DOWNLOAD_END))
            original_link = __import__("os").link

            def raced_link(source, target):
                Path(target).write_bytes(b"other exporter")
                original_link(source, target)

            with (
                patch("rcominote.recording_export.os.link", side_effect=raced_link),
                self.assertRaises(FileExistsError),
            ):
                await export_recording(conn, "recording", out)
            self.assertEqual((out / "recording.mp3").read_bytes(), b"other exporter")
            self.assertEqual(len(list(out.iterdir())), 1)


class FilenameTests(unittest.TestCase):
    def test_valid_fourteen_byte_device_name(self):
        self.assertEqual(validate_filename("20261012085542"), b"20261012085542")
