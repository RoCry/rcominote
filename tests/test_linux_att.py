"""Literal ATT exchanges replayed over real packet sockets; never opens Bluetooth."""

import asyncio
import ctypes
import errno
import socket
import unittest
from unittest.mock import Mock, patch

from rcominote.experiments.linux_att import AttError, AttLink


class AttTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.open_packet_link()

    def open_packet_link(self, *, local_mtu=247):
        self.report = {}
        self.link = AttLink("12:34:56:78:9A:BC", self.report, local_mtu=local_mtu)
        local, self.peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        local.setblocking(False)
        self.peer.setblocking(False)
        self.link._socket = local
        self.link._reader = asyncio.create_task(self.link._receive())
        self.addAsyncCleanup(self.link.__aexit__, None, None, None)
        self.addCleanup(self.peer.close)

    async def send(self, hex_value):
        await asyncio.get_running_loop().sock_sendall(self.peer, bytes.fromhex(hex_value))

    async def recv(self):
        return await asyncio.wait_for(asyncio.get_running_loop().sock_recv(self.peer, 518), 2)

    def task(self, pdu, expected):
        task = asyncio.create_task(self.link.request(bytes.fromhex(pdu), expected))
        self.addAsyncCleanup(self.finish, task)
        return task

    async def finish(self, task):
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_discovery_survives_peer_mtu_notification_and_indication(self):
        request = self.task("100100ffff0028", 0x11)
        self.assertEqual(await self.recv(), bytes.fromhex("100100ffff0028"))
        await self.send("02f700")
        self.assertEqual(await self.recv(), bytes.fromhex("03f700"))
        await self.send("1b1700aabb")
        await self.send("1d1800cc")
        self.assertEqual(await self.recv(), b"\x1e")
        await self.send("1106010005000018")
        self.assertEqual(await request, bytes.fromhex("1106010005000018"))
        self.assertEqual(self.link.mtu, 247)
        self.assertEqual(await self.link.next_notification(), (0x17, b"\xaa\xbb"))
        self.assertEqual(await self.link.next_notification(), (0x18, b"\xcc"))
        self.assertEqual(
            [(item["direction"], item["hex"]) for item in self.report["att_packets"]],
            [
                ("tx", "100100ffff0028"),
                ("rx", "02f700"),
                ("tx", "03f700"),
                ("rx", "1b1700aabb"),
                ("rx", "1d1800cc"),
                ("tx", "1e"),
                ("rx", "1106010005000018"),
            ],
        )

    async def test_our_mtu_exchange_updates_limit_and_discovery_error_retains_bytes(self):
        request = self.task("02f700", 0x03)
        await self.recv()
        await self.send("03b900")
        await request
        self.assertEqual(self.link.mtu, 185)
        request = self.task("101a00ffff0028", 0x11)
        await self.recv()
        await self.send("01101a000a")
        with self.assertRaises(AttError) as caught:
            await request
        self.assertEqual(caught.exception.pdu, bytes.fromhex("01101a000a"))
        # The protocol-defined end of discovery must permit the next ATT operation.
        request = self.task("0a0300", 0x0B)
        await self.recv()
        await self.send("0b436f4d69")
        self.assertEqual(await request, b"\x0bCoMi")

    async def test_local_128_request_caps_large_peer_and_notification_boundary(self):
        self.open_packet_link(local_mtu=128)
        request = self.task("028000", 0x03)
        self.assertEqual(await self.recv(), bytes.fromhex("028000"))
        await self.send("03f700")
        self.assertEqual(await request, bytes.fromhex("03f700"))
        self.assertEqual(self.link.mtu, 128)
        await self.send("1b1700" + "ab" * 125)
        self.assertEqual(await self.link.next_notification(), (0x17, b"\xab" * 125))
        await self.send("1b1700" + "ab" * 126)
        with self.assertRaisesRegex(ConnectionError, "exceeds negotiated MTU: 129 > 128"):
            await self.link.next_notification()

    async def test_local_128_peer_exchange_advertises_local_even_when_peer_is_smaller(self):
        self.open_packet_link(local_mtu=128)
        await self.send("02b900")
        self.assertEqual(await self.recv(), bytes.fromhex("038000"))
        self.assertEqual(self.link.mtu, 128)
        await self.send("025000")
        self.assertEqual(await self.recv(), bytes.fromhex("038000"))
        self.assertEqual(self.link.mtu, 80)

    async def test_mismatched_own_mtu_claim_fails_before_sending_and_preserves_link(self):
        self.open_packet_link(local_mtu=128)
        with self.assertRaisesRegex(ValueError, "configured local ATT MTU"):
            await self.link.request(bytes.fromhex("02f700"), 0x03)
        self.assertEqual(self.report["att_packets"], [])
        request = self.task("028000", 0x03)
        self.assertEqual(await self.recv(), bytes.fromhex("028000"))
        await self.send("038000")
        await request
        self.assertEqual(self.link.mtu, 128)

    def test_local_mtu_validation_precedes_report_mutation(self):
        for value in (True, False, None, "128", 128.0, 0, 22, 248, 517):
            with self.subTest(local_mtu=value):
                report = {}
                with self.assertRaisesRegex(ValueError, "integer from 23 through 247"):
                    AttLink("12:34:56:78:9A:BC", report, local_mtu=value)
                self.assertEqual(report, {})
        for value in (23, 128, 247):
            with self.subTest(local_mtu=value):
                self.assertEqual(AttLink("12:34:56:78:9A:BC", {}, local_mtu=value).local_mtu, value)
        self.assertEqual(AttLink("12:34:56:78:9A:BC", {}).local_mtu, 247)

    async def test_unrelated_error_cannot_complete_pending_request(self):
        request = self.task("100100ffff0028", 0x11)
        await self.recv()
        await self.send("010100000e")  # Device replying to our Error Response, not discovery.
        with self.assertRaisesRegex(ValueError, "Unmatched"):
            await request
        with self.assertRaisesRegex(ConnectionError, "unusable"):
            await self.link.request(b"\x0a\x03\x00", 0x0B)

    async def test_cancelled_request_closes_instead_of_reusing_late_reply(self):
        request = self.task("100100ffff0028", 0x11)
        await self.recv()
        request.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await request
        with self.assertRaisesRegex(ConnectionError, "unusable"):
            await self.link.request(b"\x0a\x03\x00", 0x0B)
        self.assertEqual(self.link._socket.fileno(), -1)

    async def test_timeout_is_bounded_and_invalidates(self):
        self.link.timeout = 0.02
        request = self.task("100100ffff0028", 0x11)
        await self.recv()
        with self.assertRaises(TimeoutError):
            await request
        with self.assertRaisesRegex(ConnectionError, "unusable"):
            await self.link.next_notification()

    async def test_malformed_peer_mtu_fails_without_reply(self):
        request = self.task("100100ffff0028", 0x11)
        await self.recv()
        await self.send("021600")
        with self.assertRaisesRegex(ValueError, "Invalid peer ATT MTU"):
            await request
        self.assertEqual(
            [r["hex"] for r in self.report["att_packets"] if r["direction"] == "tx"], ["100100ffff0028"]
        )

    def test_linux_sockaddr_matches_header_layout(self):
        # BlueZ sockaddr_l2: family, PSM, reversed bdaddr, CID, public, alignment.
        self.assertEqual(self.link._sockaddr().hex(), "1f000000bc9a7856341204000100")
        with self.assertRaisesRegex(ValueError, "MAC"):
            AttLink("not-a-device", {})

    async def test_local_fixed_cid_bind_precedes_connect_with_header_golden_addresses(self):
        calls = []

        def record(name):
            def invoke(fd, address, length):
                calls.append((name, ctypes.string_at(address, length).hex()))
                return 0

            return invoke

        libc = Mock()
        libc.bind.side_effect = record("bind")
        libc.connect.side_effect = record("connect")
        with patch("rcominote.experiments.linux_att.ctypes.CDLL", return_value=libc):
            await self.link._connect()
        # BlueZ btio.c local ANY/public CID4, then remote/public CID4.
        # Missing bind reproduced EINVAL on the real Linux 6.14 host.
        self.assertEqual(
            calls, [("bind", "1f00000000000000000004000100"), ("connect", "1f000000bc9a7856341204000100")]
        )

    async def test_failed_bind_closes_socket_without_connect(self):
        link = AttLink("12:34:56:78:9A:BC", {})
        local, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(local.close)
        self.addCleanup(peer.close)
        libc = Mock()
        libc.bind.return_value = -1
        with (
            patch("rcominote.experiments.linux_att.sys.platform", "linux"),
            patch("rcominote.experiments.linux_att.socket.socket", return_value=local),
            patch("rcominote.experiments.linux_att.ctypes.CDLL", return_value=libc),
            patch("rcominote.experiments.linux_att.ctypes.get_errno", return_value=errno.EADDRINUSE),
            self.assertRaisesRegex(OSError, "local bind failed"),
        ):
            await link.__aenter__()
        libc.connect.assert_not_called()
        self.assertEqual(local.fileno(), -1)
