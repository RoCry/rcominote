"""Production ATT lifecycle and packet-boundary tests; never opens Bluetooth."""

import asyncio
import socket
import sys
import unittest
from unittest.mock import Mock

from rcominote.linux_att import AttError, AttLink


@unittest.skipUnless(sys.platform == "linux", "Linux ATT packet-socket lifecycle tests")
class AttTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dropped = Mock()
        self.link = AttLink("12:34:56:78:9A:BC", disconnected_callback=self.dropped)
        local, self.peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        local.setblocking(False)
        self.peer.setblocking(False)
        self.link._socket = local
        self.link._reader = asyncio.create_task(self.link._receive())
        self.addAsyncCleanup(self.link.__aexit__, None, None, None)
        self.addCleanup(self.peer.close)

    async def send(self, pdu):
        await asyncio.get_running_loop().sock_sendall(self.peer, pdu)

    async def recv(self):
        return await asyncio.wait_for(asyncio.get_running_loop().sock_recv(self.peer, 518), 2)

    def task(self, awaitable):
        task = asyncio.create_task(awaitable)
        self.addAsyncCleanup(self.finish, task)
        return task

    async def finish(self, task):
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def reader_finished(self):
        await asyncio.wait_for(asyncio.shield(self.link._reader), 2)

    async def test_peer_mtu_notification_and_indication_during_request(self):
        request = self.task(self.link.request(bytes.fromhex("100100ffff0028"), 0x11))
        self.assertEqual(await self.recv(), bytes.fromhex("100100ffff0028"))
        await self.send(bytes.fromhex("02f700"))
        self.assertEqual(await self.recv(), bytes.fromhex("03f700"))
        await self.send(bytes.fromhex("1b1700aabb"))
        await self.send(bytes.fromhex("1d1800cc"))
        self.assertEqual(await self.recv(), b"\x1e")
        await self.send(bytes.fromhex("1106010005000018"))
        self.assertEqual(await request, bytes.fromhex("1106010005000018"))
        self.assertEqual(self.link.mtu, 247)
        self.assertEqual(await self.link.next_notification(), (0x17, b"\xaa\xbb"))
        self.assertEqual(await self.link.next_notification(), (0x18, b"\xcc"))
        self.dropped.assert_not_called()

    async def test_our_mtu_exchange_and_recoverable_att_error(self):
        request = self.task(self.link.request(bytes.fromhex("02f700"), 0x03))
        await self.recv()
        await self.send(bytes.fromhex("03b900"))
        await request
        self.assertEqual(self.link.mtu, 185)
        request = self.task(self.link.request(bytes.fromhex("101a00ffff0028"), 0x11))
        await self.recv()
        await self.send(bytes.fromhex("01101a000a"))
        with self.assertRaises(AttError) as caught:
            await request
        self.assertEqual(caught.exception.pdu, bytes.fromhex("01101a000a"))
        await self.link.write_command(bytes.fromhex("520300ab"))
        self.assertEqual(await self.recv(), bytes.fromhex("520300ab"))
        self.dropped.assert_not_called()

    async def test_request_timeout_aborts_and_notifies_once(self):
        self.link.timeout = 0.02
        request = self.task(self.link.request(bytes.fromhex("0a0300"), 0x0B))
        await self.recv()
        with self.assertRaises(TimeoutError):
            await request
        with self.assertRaisesRegex(ConnectionError, "unusable"):
            await self.link.next_notification()
        await self.link.__aexit__()
        self.dropped.assert_called_once()
        self.assertEqual(self.link._socket.fileno(), -1)

    async def test_cancelled_request_aborts_but_waiting_for_request_lock_does_not(self):
        first = self.task(self.link.request(bytes.fromhex("0a0300"), 0x0B))
        await self.recv()
        second = self.task(self.link.request(bytes.fromhex("0a0400"), 0x0B))
        await asyncio.sleep(0)
        second.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await second
        self.dropped.assert_not_called()
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        self.dropped.assert_called_once()
        self.assertEqual(self.link._socket.fileno(), -1)

    async def test_idle_wait_cancellation_preserves_transport(self):
        self.link.timeout = 0.01
        waiter = self.task(self.link.next_notification())
        await asyncio.sleep(0.04)
        self.assertFalse(waiter.done())
        waiter.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiter
        await self.send(bytes.fromhex("1b1700aa"))
        self.assertEqual(await self.link.next_notification(), (0x17, b"\xaa"))
        self.dropped.assert_not_called()

    async def test_remote_close_unblocks_request_and_notification_waiters(self):
        request = self.task(self.link.request(bytes.fromhex("0a0300"), 0x0B))
        await self.recv()
        waiter = self.task(self.link.next_notification())
        self.peer.close()
        with self.assertRaises(ConnectionError):
            await request
        with self.assertRaises(ConnectionError):
            await waiter
        await self.reader_finished()
        self.dropped.assert_called_once()

    async def test_explicit_close_suppresses_callback(self):
        waiter = self.task(self.link.next_notification())
        await asyncio.sleep(0)
        await self.link.__aexit__()
        with self.assertRaises(ConnectionError):
            await waiter
        self.dropped.assert_not_called()

    async def test_dispatch_abort_unblocks_waiter_and_preserves_first_failure(self):
        waiter = self.task(self.link.next_notification())
        await asyncio.sleep(0)
        failure = ValueError("Boyi callback failed")
        self.link.abort(failure)
        self.link.abort(RuntimeError("later failure"))
        with self.assertRaisesRegex(ConnectionError, "Boyi callback failed"):
            await waiter
        self.dropped.assert_called_once_with(failure)

    async def test_queue_overrun_is_terminal_and_bounded(self):
        self.link.notification_limit = 2
        for _ in range(3):
            await self.send(bytes.fromhex("1b1700aa"))
        await self.reader_finished()
        self.assertEqual(len(self.link.notifications), 2)
        with self.assertRaisesRegex(ConnectionError, "buffer exceeded"):
            await self.link.next_notification()
        self.dropped.assert_called_once()

    async def test_commands_can_overlap_a_request_but_requests_serialize(self):
        first = self.task(self.link.request(bytes.fromhex("0a0300"), 0x0B))
        self.assertEqual(await self.recv(), bytes.fromhex("0a0300"))
        second = self.task(self.link.request(bytes.fromhex("0a0400"), 0x0B))
        await self.link.write_command(bytes.fromhex("520500ab"))
        self.assertEqual(await self.recv(), bytes.fromhex("520500ab"))
        await self.send(b"\x0bfirst")
        self.assertEqual(await first, b"\x0bfirst")
        self.assertEqual(await self.recv(), bytes.fromhex("0a0400"))
        await self.send(b"\x0bsecond")
        self.assertEqual(await second, b"\x0bsecond")

    async def test_large_transfer_has_no_trace_or_lifetime_packet_cap(self):
        self.link.mtu = 247
        pdu = bytes.fromhex("1b1700") + b"x" * 244
        for _ in range(4200):
            await self.send(pdu)
            self.assertEqual(await self.link.next_notification(), (0x17, b"x" * 244))
        self.assertFalse(hasattr(self.link, "report"))
        self.dropped.assert_not_called()

    async def test_invalid_command_is_rejected_before_send_without_poisoning(self):
        for pdu in (b"", b"\x52\x00\x00", b"\x12\x03\x00", b"\x52\x03\x00" + b"x" * 21):
            with self.subTest(pdu=pdu), self.assertRaises(ValueError):
                await self.link.write_command(pdu)
        self.link._check()
        self.dropped.assert_not_called()

    async def test_oversized_packet_is_terminal_even_if_socket_receive_truncates(self):
        await self.send(b"\x1b\x17\x00" + b"x" * 1024)
        await self.reader_finished()
        self.assertIsInstance(self.link._failure, ValueError)
        self.assertIn("exceeds negotiated MTU", str(self.link._failure))
        self.dropped.assert_called_once()

    async def test_malformed_peer_mtu_is_terminal(self):
        await self.send(bytes.fromhex("021600"))
        await self.reader_finished()
        self.assertIsInstance(self.link._failure, ValueError)
        self.dropped.assert_called_once()

    async def test_truncated_discovery_response_fails_request(self):
        request = self.task(self.link.request(bytes.fromhex("040100ffff"), 0x05))
        await self.recv()
        await self.send(bytes.fromhex("0501010002"))
        with self.assertRaisesRegex(ValueError, "Malformed ATT discovery"):
            await request
        self.dropped.assert_called_once()

    def test_linux_sockaddr_and_constructor_validation(self):
        self.assertEqual(self.link._sockaddr().hex(), "1f000000bc9a7856341204000100")
        self.assertEqual(self.link._sockaddr(local=True).hex(), "1f00000000000000000004000100")
        for options in ({"notification_limit": 0}, {"timeout": 0}, {"timeout": float("inf")}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                AttLink("12:34:56:78:9A:BC", **options)
        with self.assertRaises(ValueError):
            AttLink("wrong")
