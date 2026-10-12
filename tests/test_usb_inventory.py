"""Real IOKit descriptor subset: interfaces repeat IDs; plist includes binary data."""

import unittest
from pathlib import Path

from rcominote.usb_inventory import parse_registry

FIXTURE = Path(__file__).parent / "fixtures/ioreg-hiveton.plist"
EXPECTED = {
    "location": "00120000",
    "vid_pid": "38f4:fffe",
    "product": "Hiveton App Serial",
    "manufacturer": "Hiveton",
    "serial": "HVR_APP_SERIAL4",
    "device_class": 239,
    "interfaces": [
        {"number": 0, "class": 2, "subclass": 2, "protocol": 0},
        {"number": 1, "class": 10, "subclass": 0, "protocol": 0},
    ],
}


class USBTests(unittest.TestCase):
    def test_captured_device_is_not_duplicated_by_interface_ids(self):
        self.assertEqual(parse_registry(FIXTURE.read_bytes()), [EXPECTED])


if __name__ == "__main__":
    unittest.main()
