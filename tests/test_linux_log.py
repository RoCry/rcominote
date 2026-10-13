"""ATT tables from CoMi HCI service discovery and hand-encoded characteristic oracles."""

import unittest
from unittest.mock import AsyncMock

from rcominote.experiments.linux_att import AttError
from rcominote.experiments.linux_log import discover, short_read, table_rows
from rcominote.log_stream import Stream

# CoMi ranges observed in 2026-10-13 near-PC btmon: GAP/GATT/battery, Actions, Boyi.
SERVICES = [
    bytes.fromhex("110601000800011809000f000018100013000f18"),
    bytes.fromhex("111414001900d19f1b1f80f2b28ee8119af601309ae4"),
    bytes.fromhex("11061a001f00f0f520002b00e0e5"),
]
# Mac 2026-10-12 GATT discovery independently records declarations21/23, CCCD25.
CHARACTERS = bytes.fromhex(
    "091515000c1600d19f1b1f80f2b28ee8119af602309ae41700101800d19f1b1f80f2b28ee8119af603309ae4"
)


class LinuxLogTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_read_rejects_changed_code_row(self):
        stream = Stream()
        # Independent image row at1000ab40 begins5e; simulate a changed first byte.
        text = "1000ab40: 00 34 8d f8 12 30 94 f8 70 34 bd f8 00 20 8d f8    .4...0..p4... ..\r\n"
        payload = b"\x00" + len(text).to_bytes(2, "little") + text.encode()

        async def send(_packet):
            stream.feed(b"\x1d\xf0\x81" + len(payload).to_bytes(2, "little") + payload)

        with self.assertRaisesRegex(ValueError, "differs from independent image"):
            await short_read(send, stream, {})

    async def test_short_read_missing_output_stops_at_bounded_fillers(self):
        packets = []
        stream = Stream()

        async def send(packet):
            packets.append(packet)
            # Captured Actions ACK; command success alone is not readback proof.
            stream.feed(bytes.fromhex("1d108107007f0400a0860100"))

        with self.assertRaisesRegex(ValueError, "not received within eight"):
            await short_read(send, stream, {})
        self.assertEqual(len(packets), 9)  # One fixed read plus the explicit eight-query budget.

    async def test_complete_discovery_uses_verified_values_and_cccd(self):
        link = AsyncMock()
        link.request.side_effect = [
            *SERVICES,
            AttError(bytes.fromhex("01102c000a")),
            CHARACTERS,
            bytes.fromhex("050119000229"),
        ]
        result = await discover(link, {})
        self.assertEqual(result, (22, 24, 25))

    async def test_wrong_end_handle_is_not_successful_discovery(self):
        link = AsyncMock()
        link.request.side_effect = [*SERVICES, AttError(bytes.fromhex("011000000a"))]
        with self.assertRaises(AttError):
            await discover(link, {})

    async def test_changed_cccd_is_rejected_before_subscription(self):
        link = AsyncMock()
        link.request.side_effect = [
            *SERVICES,
            AttError(bytes.fromhex("01102c000a")),
            CHARACTERS,
            bytes.fromhex("050119000129"),
        ]
        with self.assertRaisesRegex(ValueError, "not the expected CCCD"):
            await discover(link, {})
        self.assertTrue(all(call.args[0][0] != 0x12 for call in link.request.await_args_list))

    def test_partial_table_row_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "Malformed GATT table"):
            table_rows(SERVICES[0][:-1], (6, 20))
