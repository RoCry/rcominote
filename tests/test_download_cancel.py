"""Explicit cancellation against actual reply bytes and realistic late-notification sequences."""

import asyncio
import json
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from rcominote.cli import app
from rcominote.connection import Connection
from rcominote.download_cancel import DownloadCancelled
from rcominote.protocol import FileEntry
from rcominote.recording_export import export_recording

# Existing independent download fixtures; no protocol framing code constructs inputs.
SIZE_THREE = bytes.fromhex("d22d010b0500000000035f6a")
DOWNLOAD_END = bytes.fromhex("d22d010b01024e1b")
# Owned-device cancel trace, 2026-10-12: both immediate and worker replies used these bytes.
STOP_ACK = bytes.fromhex("d22d010c01007e1b")


class DownloadCancelTests(unittest.IsolatedAsyncioTestCase):
    def connection(self):
        client = AsyncMock()
        with patch("rcominote.connection.create_client", return_value=client):
            conn = Connection("captured-cancel-sequence")
        return conn, client

    def notify(self, conn, source, packet):
        conn._received(source, packet)

    async def started_download(self, conn, *, offset=0):
        accepted = asyncio.Event()
        chunks = []

        def sink(data):
            chunks.append(data)
            accepted.set()
            return len(data)

        self.notify(conn, "cmd", SIZE_THREE)
        self.notify(conn, "off", b"a")
        task = asyncio.create_task(conn.download("recording", sink, offset=offset))
        self.addAsyncCleanup(self.finish_task, task)
        await asyncio.wait_for(accepted.wait(), timeout=2)
        return task, chunks

    async def finish_task(self, task):
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_late_data_eof_and_duplicate_ack_cannot_complete_or_reuse_session(self):
        conn, client = self.connection()

        def on_write(_uuid, packet, **_kwargs):
            if packet[3] == 0x0C:
                # An already queued worker write and normal EOF may race with stop.
                self.notify(conn, "off", b"bc")
                self.notify(conn, "cmd", DOWNLOAD_END)
                self.notify(conn, "cmd", STOP_ACK)
                self.notify(conn, "cmd", STOP_ACK)

        client.write_gatt_char.side_effect = on_write
        task, chunks = await self.started_download(conn)
        task.cancel()
        with self.assertRaises(DownloadCancelled) as caught:
            await task
        error = caught.exception
        self.assertEqual(chunks, [b"a"])
        self.assertEqual(
            (error.name, error.offset, error.received, error.declared_size), ("recording", 0, 1, 3)
        )
        self.assertEqual(
            [call.args[1][:5] for call in client.write_gatt_char.await_args_list],
            [bytes.fromhex("d22d010b12"), bytes.fromhex("d22d010c00")],
        )
        self.assertTrue(error.stop_result["request_sent"])
        self.assertTrue(error.stop_result["response_received"])
        self.assertFalse(error.stop_result["worker_exit_verified"])
        # Receiving a late, plausible new-file stream still cannot allow another request.
        self.notify(conn, "cmd", SIZE_THREE)
        self.notify(conn, "off", b"abc")
        self.notify(conn, "cmd", DOWNLOAD_END)
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.download("next", lambda _data: self.fail("Late bytes reached next output"))
        self.assertEqual(client.write_gatt_char.await_count, 2)

    async def test_no_ack_finishes_bounded_cleanup_as_cancellation(self):
        conn, client = self.connection()
        task, chunks = await self.started_download(conn, offset=1)
        task.cancel()
        # The real one-second cleanup deadline catches a stuck cancellation path.
        with self.assertRaises(DownloadCancelled) as caught:
            await asyncio.wait_for(task, timeout=3)
        error = caught.exception
        self.assertEqual((error.offset, error.received, error.declared_size), (1, 1, 3))
        self.assertEqual(chunks, [b"a"])
        self.assertTrue(error.stop_result["request_sent"])
        self.assertFalse(error.stop_result["response_received"])
        self.assertTrue(error.stop_result["error"])
        self.assertFalse(error.stop_result["worker_exit_verified"])
        self.assertEqual(client.write_gatt_char.await_count, 2)

    async def test_stop_write_failure_preserves_cancel_outcome(self):
        conn, client = self.connection()

        def on_write(_uuid, packet, **_kwargs):
            if packet[3] == 0x0C:
                raise OSError("captured transport failure")

        client.write_gatt_char.side_effect = on_write
        task, _chunks = await self.started_download(conn)
        task.cancel()
        with self.assertRaises(DownloadCancelled) as caught:
            await task
        self.assertIn("captured transport failure", str(caught.exception.stop_result["error"]))
        self.assertFalse(caught.exception.stop_result["response_received"])
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.serial()
        self.assertEqual(client.write_gatt_char.await_count, 2)

    async def test_second_cancellation_during_ack_wait_keeps_prefix_outcome(self):
        conn, client = self.connection()
        stop_written = asyncio.Event()

        def on_write(_uuid, packet, **_kwargs):
            if packet[3] == 0x0C:
                stop_written.set()

        client.write_gatt_char.side_effect = on_write
        task, chunks = await self.started_download(conn)
        task.cancel()
        await asyncio.wait_for(stop_written.wait(), timeout=2)
        task.cancel()
        with self.assertRaises(DownloadCancelled) as caught:
            await task
        self.assertEqual((caught.exception.received, chunks), (1, [b"a"]))
        self.assertFalse(caught.exception.stop_result["response_received"])
        self.assertTrue(caught.exception.stop_result["error"])
        self.assertEqual(client.write_gatt_char.await_count, 2)

    async def test_export_keeps_only_delivered_prefix_and_incomplete_manifest(self):
        conn, client = self.connection()
        accepted = asyncio.Event()
        actual_download = conn.download

        async def observed_download(name, sink, **kwargs):
            def observed_sink(data):
                count = sink(data)
                accepted.set()
                return count

            return await actual_download(name, observed_sink, **kwargs)

        def on_write(_uuid, packet, **_kwargs):
            if packet[3] == 0x0C:
                self.notify(conn, "off", b"b")
                self.notify(conn, "cmd", DOWNLOAD_END)
                self.notify(conn, "cmd", STOP_ACK)

        client.write_gatt_char.side_effect = on_write
        self.notify(conn, "cmd", SIZE_THREE)
        self.notify(conn, "off", b"a")
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(conn, "download", new=observed_download),
        ):
            out = Path(directory)
            progress = []
            task = asyncio.create_task(
                export_recording(
                    conn, "recording", out, expected_size=3, offset=1, on_progress=progress.append
                )
            )
            self.addAsyncCleanup(self.finish_task, task)
            await asyncio.wait_for(accepted.wait(), timeout=2)
            task.cancel()
            with self.assertRaises(DownloadCancelled) as caught:
                await task
            report = caught.exception.export_result
            self.assertEqual(progress, [1])
            partial = Path(report["partial_path"])
            manifest = Path(report["manifest_path"])
            self.assertEqual(partial.read_bytes(), b"a")
            self.assertTrue(partial.name.startswith("recording.offset-1."))
            self.assertTrue(partial.name.endswith(".partial.bin"))
            self.assertEqual(set(out.iterdir()), {partial, manifest})
            saved = json.loads(manifest.read_text())
            self.assertEqual(
                (saved["status"], saved["scope"], saved["offset"], saved["bytes"], saved["declared_size"]),
                ("cancelled", "incomplete_recording_suffix", 1, 1, 3),
            )
            self.assertEqual(
                saved["sha256"], "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"
            )
            self.assertFalse(saved["automatic_resume"])

    async def test_manifest_fsync_failure_reports_preserved_prefix_without_complete_output(self):
        conn, client = self.connection()
        accepted = asyncio.Event()
        actual_download = conn.download

        async def observed_download(name, sink, **kwargs):
            def observed_sink(data):
                count = sink(data)
                accepted.set()
                return count

            return await actual_download(name, observed_sink, **kwargs)

        def on_write(_uuid, packet, **_kwargs):
            if packet[3] == 0x0C:
                self.notify(conn, "cmd", STOP_ACK)

        client.write_gatt_char.side_effect = on_write
        self.notify(conn, "cmd", SIZE_THREE)
        self.notify(conn, "off", b"a")
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(conn, "download", new=observed_download),
            patch(
                "rcominote.recording_export.os.fsync",
                side_effect=[None, OSError("metadata disk failure")],
            ),
        ):
            out = Path(directory)
            task = asyncio.create_task(export_recording(conn, "recording", out, expected_size=3))
            self.addAsyncCleanup(self.finish_task, task)
            await asyncio.wait_for(accepted.wait(), timeout=2)
            task.cancel()
            with self.assertRaises(OSError) as caught:
                await task
            partials = list(out.glob("*.partial.bin"))
            self.assertEqual(len(partials), 1)
            partial = partials[0]
            self.assertEqual(partial.read_bytes(), b"a")
            manifest = partial.with_suffix(".json")
            self.assertIn(f"preserved partial={partial}", str(caught.exception))
            self.assertIn(f"metadata={manifest} may be incomplete", str(caught.exception))
            self.assertEqual(set(out.iterdir()), {partial, manifest})

    async def test_export_cancel_during_initial_write_reports_no_bytes_without_stop(self):
        conn, client = self.connection()
        write_entered = asyncio.Event()
        release_write = asyncio.Event()

        async def blocked_write(*_args, **_kwargs):
            write_entered.set()
            await release_write.wait()

        client.write_gatt_char.side_effect = blocked_write
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            task = asyncio.create_task(export_recording(conn, "recording", out, expected_size=3))
            self.addAsyncCleanup(self.finish_task, task)
            await asyncio.wait_for(write_entered.wait(), timeout=2)
            task.cancel()
            with self.assertRaises(DownloadCancelled) as caught:
                await task
            report = caught.exception.export_result
            self.assertEqual((report["status"], report["bytes"]), ("cancelled", 0))
            self.assertIsNone(report["declared_size"])
            self.assertIsNone(report["partial_path"])
            self.assertIsNone(report["manifest_path"])
            self.assertFalse(report["stop"]["request_attempted"])
            self.assertEqual(list(out.iterdir()), [])
            client.write_gatt_char.assert_awaited_once()
            self.assertEqual(client.write_gatt_char.await_args.args[1][:5], bytes.fromhex("d22d010b12"))
            with self.assertRaisesRegex(ConnectionError, "reconnect"):
                await conn.serial()
            client.write_gatt_char.assert_awaited_once()

    async def test_cancel_before_first_data_never_sends_stop(self):
        conn, client = self.connection()
        written = asyncio.Event()
        client.write_gatt_char.side_effect = lambda *_args, **_kwargs: written.set()
        task = asyncio.create_task(conn.download("recording", lambda _data: self.fail("Unexpected data")))
        self.addAsyncCleanup(self.finish_task, task)
        await asyncio.wait_for(written.wait(), timeout=2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        client.write_gatt_char.assert_awaited_once()
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.serial()

    async def test_timeout_and_sink_failure_do_not_send_stop(self):
        for failure in ("timeout", "disk"):
            with self.subTest(failure=failure):
                conn, client = self.connection()
                self.notify(conn, "cmd", SIZE_THREE)

                def sink(_data):
                    raise OSError("disk full")

                if failure == "disk":
                    self.notify(conn, "off", b"a")
                with self.assertRaises(TimeoutError if failure == "timeout" else OSError):
                    await conn.download("recording", sink, timeout=0.01)
                client.write_gatt_char.assert_awaited_once()

    async def test_cancelled_lock_waiter_does_not_stop_another_download(self):
        conn, client = self.connection()
        entered = asyncio.Event()
        async with conn._transaction:

            async def waiting_download():
                entered.set()
                await conn.download("waiting", lambda _data: self.fail("Unexpected data"))

            task = asyncio.create_task(waiting_download())
            self.addAsyncCleanup(self.finish_task, task)
            await asyncio.wait_for(entered.wait(), timeout=2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        client.write_gatt_char.assert_not_awaited()
        self.notify(conn, "cmd", SIZE_THREE)
        self.notify(conn, "off", b"abc")
        self.notify(conn, "cmd", DOWNLOAD_END)
        self.assertEqual(await conn.download("usable", lambda _data: 3), 3)


class DownloadCancelCliTests(unittest.TestCase):
    def test_cli_reports_cancelled_and_disconnects_before_exit_130(self):
        previous_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            for command in ("download", "sync"):
                with self.subTest(command=command):
                    self.assert_cancelled_cli(command)
        finally:
            signal.signal(signal.SIGINT, previous_handler)

    def assert_cancelled_cli(self, command):
        client = AsyncMock()
        client.services.get_service = lambda _uuid: object()
        with patch("rcominote.connection.create_client", return_value=client):
            conn = Connection("cli-replay")
        actual_download = conn.download

        async def cancel_after_delivery(name, sink, **kwargs):
            def observed_sink(data):
                count = sink(data)
                # Exercise asyncio.run's first real SIGINT handler, not only Task.cancel.
                signal.raise_signal(signal.SIGINT)
                return count

            return await actual_download(name, observed_sink, **kwargs)

        def on_write(_uuid, packet, **_kwargs):
            if packet[3] == 0x0B:
                conn._received("cmd", SIZE_THREE)
                conn._received("off", b"a")
            elif packet[3] == 0x0C:
                conn._received("cmd", STOP_ACK)

        client.write_gatt_char.side_effect = on_write
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("rcominote.device_commands.find_device", new=AsyncMock(return_value="cli-replay")),
            patch("rcominote.device_commands.read_info", new=AsyncMock()),
            patch("rcominote.device_commands.Connection", return_value=conn),
            patch.object(
                conn,
                "file_list",
                new=AsyncMock(return_value=[FileEntry("recording", 3, "note"), FileEntry("next", 3, "note")]),
            ),
            patch.object(conn, "download", new=cancel_after_delivery),
        ):
            arguments = [command, "--out", directory]
            if command == "download":
                arguments.insert(1, "recording")
            result = CliRunner().invoke(app, arguments)
            self.assertEqual(result.exit_code, 130, result.output)
            report = json.loads(result.stdout)
            if command == "sync":
                self.assertEqual(len(report), 1)
                report = report[0]
            self.assertEqual(report["status"], "cancelled")
            client.__aexit__.assert_awaited_once()
            self.assertEqual(client.write_gatt_char.await_count, 2)
