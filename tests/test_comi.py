"""Oracles: frames captured live from the owned CoMi Note (serial C261CF0430,
macOS, 2026-10-12) and the app's documented layout. Expected values are decoded
by hand, never by replaying protocol.py's own output."""

import unittest

from rcominote import protocol as P

# Captured 2026-10-12 off the real device (see research note).
SERIAL_REPLY = bytes.fromhex("d22d01010a4332363143463034333060bb")
FILE_ENTRY = bytes.fromhex("d22d010a1400323032363130313230383535343200001e7c01e12f")
LIST_END = bytes.fromhex("d22d010a01021fdb")
DEVICE_INFO = bytes.fromhex(
    "d22d0105340000e8f20000e8f00164000100040101ff78696e6b5f746573740000000000000000000000000009ff0300010000000000000000b321"
)


class WireTests(unittest.TestCase):
    def test_crc16_matches_captured_serial_reply(self):
        # Trailer 60 bb is little-endian, so the frame's CRC is 0xbb60 over the
        # first 15 bytes. Hand-checked against the captured packet.
        self.assertEqual(P.crc16(SERIAL_REPLY[:-2]), 0xBB60)

    def test_frame_reproduces_captured_get_serial_request(self):
        # The device answered this exact request on the wire.
        self.assertEqual(P.frame(P.GET_SERIAL).hex(), "d22d010100e12e")

    def test_parse_rejects_corrupted_crc(self):
        with self.assertRaisesRegex(ValueError, "CRC"):
            P.parse(SERIAL_REPLY[:-1] + b"\x00")

    def test_parse_extracts_serial_text(self):
        cmd, data = P.parse(SERIAL_REPLY)
        self.assertEqual(cmd, P.GET_SERIAL)
        self.assertEqual(P.text(data), "C261CF0430")

    def test_file_entry_decodes_name_size_kind(self):
        _, data = P.parse(FILE_ENTRY)
        entry = P.parse_file_entry(data)
        # 00 00 1e 7c big-endian = 7804; trailing kind byte 0x01 is "note".
        self.assertEqual((entry.name, entry.size, entry.kind), ("20261012085542", 7804, "note"))

    def test_list_terminator_is_status_two(self):
        _, data = P.parse(LIST_END)
        self.assertEqual(data[0], 2)

    def test_device_info_capacity_and_version(self):
        _, data = P.parse(DEVICE_INFO)
        info = P.parse_device_info(data)
        # 0000e8f2 = 59634 (total), 0000e8f0 = 59632 (free), charging byte 0x01,
        # battery 0x64 = 100, version bytes 01 00 04.
        self.assertEqual(info["total_capacity"], 59634)
        self.assertEqual(info["free_capacity"], 59632)
        self.assertTrue(info["charging"])
        self.assertEqual(info["battery"], 100)
        self.assertEqual(info["version"], "010004")
        self.assertEqual(info["recording_state"], "idle")


if __name__ == "__main__":
    unittest.main()
