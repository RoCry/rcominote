"""Fail-closed boundaries for the one-file RAM bootstrap experiment."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import typer

from rcominote import protocol as P
from rcominote.experiments import sd_bootstrap as B
from rcominote.experiments.sd_bridge import console_packet


def identity(free: int = 100) -> dict:
    payload = bytearray(52)
    payload[:4] = (200).to_bytes(4, "big")
    payload[4:8] = free.to_bytes(4, "big")
    payload[11:14] = bytes.fromhex("010004")
    payload[15] = 1
    return {"serial": B.OWNED_SERIAL, "bound": False, "device": P.parse_device_info(bytes(payload))}


class BootstrapTests(unittest.IsolatedAsyncioTestCase):
    def test_tail_size_is_a_fixed_profile_before_file_or_device_access(self):
        for size, parent in ((127, Path("parent")), (513, Path("parent")), (512, None)):
            with (
                self.subTest(size=size, parent=parent),
                self.assertRaisesRegex(typer.BadParameter, "tail-size"),
            ):
                B.main(
                    Path("missing-image"),
                    Path("unused"),
                    tail_report=parent,
                    tail_size=size,
                    create_sd_file=parent is None,
                )

    def test_sd_capacity_boundary_is_explicit_and_bounded(self):
        state = B.verify_state(identity(100), identity(99), sd_write=True)
        self.assertEqual(state["free_capacity_decrease"], 1)
        for free, write in ((99, False), (98, True), (101, True)):
            with (
                self.subTest(free=free, write=write),
                self.assertRaisesRegex(ValueError, "Unexpected state change"),
            ):
                B.verify_state(identity(100), identity(free), sd_write=write)

    def test_capacity_policy_does_not_mask_settings_or_raw_changes(self):
        before = identity()
        after = identity(99)
        raw = bytearray.fromhex(after["device"]["raw"])
        raw[39] = 1
        after["device"] = P.parse_device_info(bytes(raw))
        with self.assertRaisesRegex(ValueError, "Unexpected state change"):
            B.verify_state(before, after, sd_write=True)
        after["device"]["noise_reduction"] = 0
        with self.assertRaisesRegex(ValueError, "consistent52-byte"):
            B.verify_state(before, after, sd_write=True)

    async def test_unexpected_producer_is_rejected_before_device_access(self):
        with patch.object(B, "find_device", AsyncMock()) as find:
            with self.assertRaisesRegex(ValueError, "fixed boot0"):
                await B.write_file({"producer": "dbg fread spi_flash 1"})
            find.assert_not_awaited()

    async def test_existing_file_does_not_write_and_retains_short_download(self):
        info = identity()
        payload = b"observed but incomplete"
        conn = AsyncMock()
        conn.__aenter__.return_value = conn

        async def download(_name, sink, *, offset):
            self.assertEqual(offset, 0)
            sink(payload)
            raise RuntimeError("Short download")

        conn.download.side_effect = download
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(B, "identity", AsyncMock(return_value=(info, []))),
            patch.object(B, "find_device", AsyncMock(return_value=SimpleNamespace())),
            patch.object(B, "Connection", return_value=conn),
            patch.object(B, "read_info", AsyncMock(return_value=info)),
            patch.object(B, "write_file", AsyncMock()) as write,
        ):
            report = {"name": "rc0123456789", "download_only": True}
            with self.assertRaisesRegex(RuntimeError, "Short download"):
                await B.capture(report, b"x" * 160, Path(directory))
            write.assert_not_awaited()
            self.assertEqual(report["received_bytes"], len(payload))
            self.assertEqual((Path(directory) / "download.bin").read_bytes(), payload)

    async def test_after_failure_does_not_hide_original_failure(self):
        info = identity()
        with (
            patch.object(B, "identity", AsyncMock(side_effect=[(info, []), OSError("postcheck failed")])),
            patch.object(B, "write_file", AsyncMock(side_effect=ValueError("primary framing error"))),
        ):
            report = {"name": "rc0123456789"}
            with self.assertRaisesRegex(ValueError, "primary framing error"):
                await B.capture(report, b"", Path("unused"))
            self.assertEqual(report["after_error"], "OSError: postcheck failed")

    async def test_incomplete_actions_session_prevents_download(self):
        info = identity()
        report = {"name": "rc0123456789"}
        with (
            patch.object(B, "identity", AsyncMock(return_value=(info, []))) as identity_read,
            patch.object(B, "write_file", AsyncMock(side_effect=ValueError("Incomplete Actions session"))),
            patch.object(B, "find_device", AsyncMock()) as find,
        ):
            with self.assertRaisesRegex(ValueError, "Incomplete Actions session"):
                await B.capture(report, b"", Path("unused"))
            find.assert_not_awaited()
            self.assertEqual(identity_read.await_count, 2)
            self.assertEqual(report["before"], report["after"])

    async def test_existing_visible_name_prevents_sd_command(self):
        with (
            patch.object(B, "identity", AsyncMock(return_value=({}, [{"name": "rc0123456789"}]))),
            patch.object(B, "write_file", AsyncMock()) as write,
        ):
            with self.assertRaises(FileExistsError):
                await B.capture({"name": "rc0123456789"}, b"", Path("unused"))
            write.assert_not_awaited()

    def test_wrong_image_fails_before_output_or_device_access(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "wrong.bin"
            image.write_bytes(b"wrong")
            with patch.object(B, "capture", AsyncMock()) as capture:
                with self.assertRaisesRegex(ValueError, "Wrong independent"):
                    B.main(image, root / "out", create_sd_file=True)
                capture.assert_not_awaited()
                self.assertFalse((root / "out").exists())

    def test_fixed_command_fits_and_uses_base0_safe_address(self):
        for source, (address, size, _) in B.SOURCES.items():
            with self.subTest(source=source):
                command = f"dbg dumpbuf {address} {size} /SD:/RECORDER/Call-rc0123456789.mp3"
                encoded = console_packet(command)[8:]
                self.assertLessEqual(len(encoded), 63)
                self.assertEqual(int(command.split()[2], 0), address)
                self.assertTrue(encoded.endswith(b".mp3\n"))
