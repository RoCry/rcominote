"""Actual first SD bridge failure + independently decoded64-byte TLV boundary."""

import unittest
from pathlib import Path

from rcominote.experiments.sd_bridge import console_packet, sector_from_ring


class ConsoleLengthTests(unittest.TestCase):
    def test_captured_oversize_command_is_rejected_before_transport(self):
        # First live attempt:68 B including newline; firmware truncates path
        # then waits for another TLV instead of acknowledging this request.
        command = "dbg dumpbuf 0x10000000 0x1000 /SD:/RECORDER/Call-rcf24b45143596.mp3"
        with self.assertRaisesRegex(ValueError, "exceeds64 bytes"):
            console_packet(command)

    def test_exact_limit_preserves_command_and_replaces_only_newline_with_nul(self):
        # Actual parser has64-byte buffer, NUL at index63. Final newline may
        # occupy that slot; all63 command bytes must precede it.
        packet = console_packet("a" * 63)
        self.assertEqual(packet, bytes.fromhex("1d10814300014000") + b"a" * 63 + b"\n")


class CircularSectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Independent real NOR boot0 golden; wire grammar from actual fread
        # printf("%8x: "), sixteen printf("%2x "), printf("\r\n").
        cls.sector = Path("docs/evidence/boot-complete-2026-10-12/raw.bin").read_bytes()[:512]
        cls.lines = [
            f"{offset:8x}: " + "".join(f"{byte:2x} " for byte in cls.sector[offset : offset + 16]) + "\r\n"
            for offset in range(0, 512, 16)
        ]

    def test_complete_run_across_physical_boundary_matches_real_boot(self):
        logical = ("\r\n" + "".join(self.lines)).encode().ljust(4096, b"x")
        for cut in (1, 2, 1000):
            with self.subTest(cut=cut):
                self.assertEqual(sector_from_ring(logical[cut:] + logical[:cut]), self.sector)

    def test_old_rows_and_separate_new_row_cannot_be_assembled(self):
        mixed = ("\r\n" + "".join(self.lines[:31]) + "unrelated log\r\n" + self.lines[31]).encode()
        with self.assertRaisesRegex(ValueError, "found 0"):
            sector_from_ring(mixed.ljust(4096, b"x"))

    def test_two_complete_generations_are_ambiguous_even_if_equal(self):
        duplicate = ("\r\n" + "".join(self.lines) * 2).encode()
        with self.assertRaisesRegex(ValueError, "found 2"):
            sector_from_ring(duplicate.ljust(4096, b"x"))

    def test_real_capture_binds_status_rows_and_current_dump_marker(self):
        raw = Path("docs/evidence/sd-bridge-2026-10-13/boot-ring-download.bin").read_bytes()
        commands = {
            "producer_command": "dbg fread spi_flash 0",
            "dump_command": "dbg dumpbuf 402910729 4096 /SD:/RECORDER/Call-rcb61b078de5.mp3",
        }
        self.assertEqual(sector_from_ring(raw, nor_offset=0, **commands), self.sector)
        with self.assertRaisesRegex(ValueError, "found 0"):
            sector_from_ring(raw, nor_offset=0xFA00, **commands)
        with self.assertRaisesRegex(ValueError, "found 0"):
            sector_from_ring(raw, nor_offset=0, **(commands | {"dump_command": "different live marker"}))
