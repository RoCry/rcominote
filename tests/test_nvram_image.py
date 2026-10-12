"""Independent unmodified SDK packer oracle; synthetic values, no unit secrets.

Source zephyr/tools/build_nvram_bin.py at26f51e584940d5b141cd1d09d2629d69b595f579,
SHA23bca206c213eb579bc46a54f95a351b352dec5592fbfc9eb3c5956fb67bc36f.
Executed build_nvram_region with PropFile lines SERIAL_TEST=example-unit,
BT_TEST=001122AABBCC, BLOB_TEST= followed by600 ASCII Z characters. The literal
compressed result below is the entire1024-byte packer output, not this parser's
encoder. Remaining physical bytes are an explicit erased-flash fixture.
"""

import base64
import hashlib
import json
import unittest
import zlib

from rcominote.nvram_image import inspect_headers, inspect_region

PACKED = zlib.decompress(
    base64.b64decode(
        "eJzzCwsO+u/JyMAgAIRA4Pl/3S8GHl6GYNcgT0ef+BDX4BCG1IrE3IKcVN3SvMwShv+owPO/+wQG"
        "Dl4GpxCIWgMDQ0MjI0dHJydnZwawfJg0A1ckk5OPvxNERdQoGAU0AOgpcxQQAwAddzKy"
    )
)
REGION = PACKED + b"\xff" * (8192 - len(PACKED))


class NvramImageTests(unittest.TestCase):
    def test_official_packer_header_and_cross_prefix_item(self):
        self.assertEqual(
            hashlib.sha256(PACKED).hexdigest(),
            "5a2a73eaf59b2ebfc688500323869f60cf19cf7aa7eb9675f96ac89470b07f1d",
        )
        gate = inspect_headers(REGION[:512], REGION[4096:4608])
        self.assertFalse(gate["complete"])
        self.assertEqual(gate["segments"][1]["classification"], "erased_prefix")
        report = inspect_region(REGION)
        self.assertTrue(report["complete"])
        self.assertEqual(report["segments"][0]["header_crc8"], "0x49")
        self.assertEqual(
            [(i["key"], i["region_offset"], i["value_bytes"]) for i in report["segments"][0]["items"]],
            [("SERIAL_TEST", 16, 13), ("BT_TEST", 64, 13), ("BLOB_TEST", 96, 601)],
        )
        self.assertEqual(
            [item["value_sha256"] for item in report["segments"][0]["items"]],
            [
                "c4d4dc11112ea804645fda94ba16fdf74e4594bc5a1719aab4943e2ee6f612f0",
                "1ff74d1bd5b9362a43e60a4ed1366611e04722cdb4948cabee0c0e7cc541b341",
                "427f356e496b57f651d3b550a1fa4511569c1529f7f63492498c1c2c783d8dba",
            ],
        )
        self.assertEqual(report["segments"][1]["classification"], "erased_segment")
        self.assertIsNone(report["active_segment"])
        self.assertFalse(report["runtime_selection_verified"])
        serialized = json.dumps(report)
        for secret in ("example-unit", "001122AABBCC", "Z" * 20):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, serialized)

    def test_state_markers_do_not_select_segment_or_discard_obsolete_record(self):
        # Source state bytes are deliberately excluded from both CRCs.
        raw = bytearray(REGION[:4096] * 2)
        raw[4] = 0x5A
        raw[17] = 0x5A
        report = inspect_region(bytes(raw))
        self.assertEqual(report["segments"][0]["state"], "obsolete_marker")
        self.assertEqual(report["segments"][0]["items"][0]["state"], "obsolete_marker")
        self.assertIsNone(report["active_segment"])
        self.assertEqual([s["item_count"] for s in report["segments"]], [3, 3])

    def test_header_crc_damage_and_unknown_header_stop_gate(self):
        for offset in (0, 5, 8):
            with self.subTest(offset=offset):
                raw = bytearray(REGION[:512])
                raw[offset] ^= 1
                with self.assertRaises(ValueError):
                    inspect_headers(bytes(raw), b"\xff" * 512)
        with self.assertRaisesRegex(ValueError, "unknown non-erased"):
            inspect_headers(REGION[:512], b"\0" * 512)
        with self.assertRaisesRegex(ValueError, "No interpretable"):
            inspect_headers(b"\xff" * 512, b"\xff" * 512)

    def test_item_data_crc_failure_is_not_hidden_by_header_gate(self):
        raw = bytearray(REGION)
        raw[600] ^= 1  # Actual body byte in the packer's601-byte third value.
        self.assertFalse(inspect_headers(bytes(raw[:512]), bytes(raw[4096:4608]))["complete"])
        with self.assertRaisesRegex(ValueError, "item CRC mismatch"):
            inspect_region(bytes(raw))
        raw[97] = 0x5A
        with self.assertRaisesRegex(ValueError, "including obsolete"):
            inspect_region(bytes(raw))

    def test_name_hash_padding_and_late_dirty_tail_reject_without_values(self):
        for offset, message in ((19, "name hash"), (49, "alignment padding"), (1500, "empty item")):
            with self.subTest(offset=offset):
                raw = bytearray(REGION)
                raw[offset] ^= 1
                with self.assertRaisesRegex(ValueError, message) as error:
                    inspect_region(bytes(raw))
                self.assertNotIn("example-unit", str(error.exception))
        # Erased prefix must not allow an unobserved later chunk to be labelled erased.
        raw = bytearray(REGION)
        raw[4096 + 700] = 0
        with self.assertRaisesRegex(ValueError, "unknown non-erased"):
            inspect_region(bytes(raw))

    def test_item_span_cannot_cross_segment(self):
        raw = bytearray(REGION)
        raw[22:24] = b"\xff\xff"  # Corrupted uint16 length, caught before slicing/CRC.
        with self.assertRaisesRegex(ValueError, "span exceeds"):
            inspect_region(bytes(raw))

    def test_exact_capture_boundaries(self):
        for length in (0, 511, 513, 4096):
            with self.subTest(prefix_length=length), self.assertRaises(ValueError):
                inspect_headers(REGION[:length], REGION[4096:4608])
        for length in (0, 512, 4096, 8191):
            with self.subTest(region_length=length), self.assertRaises(ValueError):
                inspect_region(REGION[:length])
        with self.assertRaises(ValueError):
            inspect_region(REGION + b"\xff")
