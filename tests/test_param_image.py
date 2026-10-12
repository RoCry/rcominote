"""Parameter checks against independent captured SRAM CRCs, not generated checksums."""

import hashlib
import json
import unittest
from pathlib import Path

from rcominote.param_image import inspect_slots

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"


def captured_metadata() -> bytes:
    analysis = json.loads((EVIDENCE / "partition-analysis-2026-10-12.json").read_text())
    blocks = {
        int(block["address"], 16): bytes.fromhex(block["hex"])
        for block in analysis["blocks"]
        if 0x01000040 <= int(block["address"], 16) < 0x01000328
    }
    acpt = b"".join(blocks[address] for address in range(0x01000040, 0x01000328, 16))
    versions = [
        bytes.fromhex(
            json.loads((EVIDENCE / f"firmware-identity-{run}-2026-10-12.json").read_text())[
                "parameter_version_hex"
            ]
        )
        for run in ("first", "second")
    ]
    if hashlib.sha256(acpt).hexdigest() != "a071b0cdafad355eb05a71e96fc2cb6a5348ec8b5e11d0ac4dfe54d83671a144":
        raise AssertionError("Independent ACPT capture changed")
    if versions[0] != versions[1] or hashlib.sha256(versions[0]).hexdigest() != (
        "4e9d0059884cd1294c258d7f5bc43e5975641963d043c4d41eba420af0d22dc1"
    ):
        raise AssertionError("Independent FVER capture changed")
    return acpt + versions[0]


class ParameterImageTests(unittest.TestCase):
    def setUp(self):
        # Synthetic plain slot carrying actual cached metadata. It is not a
        # captured physical slot, and its padding has no checksum oracle.
        self.prefix = captured_metadata() + bytes(148) + b"part"

    def test_actual_paired_raw_slots_select_reset32_and_reject_blank_backup_as_valid(self):
        primary = (EVIDENCE / "param-slots-2026-10-13/param0-raw.bin").read_bytes()
        backup = (EVIDENCE / "param-slots-2026-10-13/param1-raw.bin").read_bytes()
        self.assertEqual(
            hashlib.sha256(primary).hexdigest(),
            "4a374a53ace6a201a23f43ff2a8ac137ec6379a2ad2c842a8b045694142875a1",
        )
        self.assertEqual(backup, b"\xff" * 4096)
        report = inspect_slots(primary, backup)
        self.assertTrue(report["complete"])
        self.assertEqual(report["primary"]["profile"], "reset32")
        self.assertEqual(
            report["primary"]["decoded_prefix_1024_sha256"], hashlib.sha256(self.prefix).hexdigest()
        )
        self.assertTrue(report["primary"]["acpt"]["matches_cached_sram"])
        self.assertTrue(report["primary"]["fver"]["matches_cached_sram"])
        self.assertEqual(report["backup"]["classification"], "uniform_slot")
        self.assertFalse(report["backup"]["boot_metadata_crc_valid"])
        self.assertEqual(primary[1024:], b"\xff" * 3072)
        self.assertNotIn("decoded_sha256", report["primary"])

    def test_captured_crc_and_identity_with_blank_backup_prefix(self):
        report = inspect_slots(self.prefix, b"\xff" * 1024)
        self.assertFalse(report["complete"])
        primary = report["primary"]
        self.assertEqual(primary["profile"], "plain")
        self.assertEqual(primary["acpt"]["crc32"], "0x703f5674")
        self.assertEqual(primary["fver"]["crc32"], "0xc06bda1e")
        self.assertEqual(primary["fver"]["board_name"], "ats3085l_dvb_watch_ext_nor_max")
        self.assertEqual(primary["fver"]["version_name"], "1.04_2602030950")
        self.assertTrue(primary["acpt"]["matches_cached_sram"])
        self.assertTrue(primary["fver"]["matches_cached_sram"])
        self.assertEqual(report["backup"]["classification"], "uniform_prefix")
        self.assertFalse(report["backup"]["complete_slot"])
        self.assertFalse(report["backup"]["valid_parameter"])
        self.assertIsNone(report["comparison"]["decoded_metadata_equal"])

    def test_full_capture_does_not_expand_crc_coverage_to_tail_or_verify_pairing(self):
        first = self.prefix + bytes(3072)
        second = first[:-1] + b"\x01"
        report = inspect_slots(first, second)
        self.assertTrue(report["complete"])
        self.assertEqual(report["comparison"]["raw_different_bytes"], 1)
        self.assertTrue(report["comparison"]["decoded_metadata_equal"])
        self.assertEqual(report["primary"]["crc_covered_bytes"], 872)
        self.assertEqual(report["primary"]["bytes_outside_crc_coverage"], 3224)
        self.assertFalse(report["primary"]["decoded_tail_semantics_verified"])
        self.assertEqual(report["pairing_scope"], "caller must independently verify repeated physical reads")

    def test_corrupted_acpt_or_fver_stops_even_with_valid_other_slot(self):
        # Realistic damaged field or stored checksum; do not regenerate CRCs.
        for index in (20, 740, 760, 868):
            with self.subTest(index=index):
                damaged = bytearray(self.prefix)
                damaged[index] ^= 1
                with self.assertRaisesRegex(ValueError, "0x3000.*interpretable"):
                    inspect_slots(self.prefix, bytes(damaged))

    def test_part_marker_is_observed_not_a_boot_checksum_requirement(self):
        report = inspect_slots(self.prefix[:-4] + b"xxxx", self.prefix)
        self.assertFalse(report["primary"]["part_marker_at_1020"])
        self.assertTrue(report["primary"]["boot_metadata_crc_valid"])

    def test_two_uniform_regions_are_not_valid_parameter_slots(self):
        for size in (1024, 4096):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "Neither parameter"):
                inspect_slots(b"\xff" * size, bytes(size))

    def test_unbounded_or_mismatched_input_is_rejected(self):
        for first, second in (
            (b"", b""),
            (self.prefix[:872], self.prefix[:872]),
            (self.prefix, self.prefix * 4),
            (self.prefix * 8, self.prefix * 8),
        ):
            with (
                self.subTest(lengths=(len(first), len(second))),
                self.assertRaisesRegex(ValueError, "equal lengths"),
            ):
                inspect_slots(first, second)
