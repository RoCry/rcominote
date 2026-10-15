"""Single dispatcher and optional evidence hook on local packet sockets only."""

import asyncio
import socket
import sys
import unittest
from unittest.mock import AsyncMock, patch

from test_dual_probe import operation, setup
from test_linux_client import DEVICE, SERIAL_REPLY, pages
from test_sd_nor_probe import END

from rcominote import protocol as P
from rcominote.experiments import dual_audit as audit
from rcominote.experiments.dual_client import (
    ACTION_CHARS,
    ACTION_DESCRIPTOR,
    ACTION_SERVICE,
    Actions,
    DualConnection,
)
from rcominote.log_capture import STOP
from rcominote.log_probe import ACK, NOTIFY


@unittest.skipUnless(sys.platform == "linux", "AF_UNIX SOCK_SEQPACKET pairs exist only on Linux")
class DualWireTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.report = {"att_packets": []}
        self.conn = DualConnection(DEVICE, self.report)
        self.client = self.conn.client
        self.link = self.client._link
        self.link.mtu = 247
        local, self.peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        local.setblocking(False)
        self.peer.setblocking(False)
        self.link._socket = local
        self.link._reader = asyncio.create_task(self.link._receive())
        with patch.object(
            self.link, "request", side_effect=pages() + [ACTION_SERVICE, ACTION_CHARS, ACTION_DESCRIPTOR]
        ):
            await self.client._discover()
        self.actions = Actions(self.conn, self.report)
        self.client._callbacks[24] = self.client.services.characteristics[NOTIFY], self.actions.receive
        self.client._callbacks[36] = (
            self.client.services.characteristics[P.NOTIFY_CMD],
            lambda _c, p: self.conn._received("cmd", p),
        )
        self.client._callbacks[42] = (
            self.client.services.characteristics[P.NOTIFY_OFFLINE],
            lambda _c, p: self.conn._received("off", p),
        )
        self.client._dispatcher = asyncio.create_task(self.client._dispatch())
        self.addAsyncCleanup(self.client.__aexit__, None, None, None)
        self.addCleanup(self.peer.close)

    async def recv(self):
        return await asyncio.wait_for(asyncio.get_running_loop().sock_recv(self.peer, 518), 1)

    async def send(self, pdu):
        await asyncio.get_running_loop().sock_sendall(self.peer, pdu)

    async def finish(self, task):
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    def task(self, awaitable):
        value = asyncio.create_task(awaitable)
        self.addAsyncCleanup(self.finish, value)
        return value

    async def test_one_dispatcher_demultiplexes_interleaved_handles_and_exposes_contamination(self):
        # Inject an unrelated Boyi response while Actions is active. It is routed
        # to Boyi, never misdecoded as an ACK; next Actions rejects the queue.
        op = operation()
        task = self.task(self.actions.run(op))
        for index in range(5):
            request = await self.recv()
            self.assertEqual(request[:3], b"\x12\x16\0")
            if index == 1:
                await self.send(b"\x1b\x24\0" + SERIAL_REPLY)
            await self.send(b"\x13")
            await self.send(b"\x1b\x18\0" + ACK)
            if request[3:] == STOP:
                await self.send(b"\x1b\x18\0" + END)
        await task
        self.assertEqual(op["ack_count"], 5)
        self.assertFalse(self.conn.queue.empty())
        # The evidence audit rejects cross-protocol traffic in exclusive span.
        s = setup()
        start = len(s["att_packets"])
        s["att_packets"] += self.report["att_packets"]
        op.update(actions_start=start, actions_end=len(s["att_packets"]))
        with self.assertRaisesRegex(ValueError, "Unexpected traffic"):
            audit.actions(s, op)
        with self.assertRaisesRegex(ValueError, "overlaps"):
            await self.actions.run(operation())

    async def test_late_actions_at_socket_receive_retires_transport(self):
        await self.send(b"\x1b\x18\0" + ACK)
        await asyncio.wait_for(self.link._reader, 1)
        self.assertEqual(self.report["att_packets"][0]["hex"], (b"\x1b\x18\0" + ACK).hex())
        self.assertIsNotNone(self.conn._failure)
        with self.assertRaises(ConnectionError):
            self.link._check()

    async def test_incomplete_stop_end_fails_session_and_never_downloads(self):
        op = operation()
        original = self.actions.wait

        async def bounded(predicate):
            async with asyncio.timeout(0.1):
                await original(predicate)

        self.actions.wait = bounded
        task = self.task(self.actions.run(op))
        for _ in range(5):
            await self.recv()
            await self.send(b"\x13")
            await self.send(b"\x1b\x18\0" + ACK)
        with self.assertRaises(TimeoutError):
            await task
        self.assertFalse(op["log_session_complete"])
        self.assertIsNotNone(self.conn._failure)
        writes = [r for r in self.report["att_packets"] if r["direction"] == "tx"]
        self.assertEqual(len(writes), 5)
        self.assertEqual(writes[-1]["hex"], "121600" + STOP.hex())

    async def test_trace_callback_failure_is_not_silently_dropped(self):
        def broken(_direction, _pdu):
            raise OSError("evidence sink failed")

        self.link._trace_callback = broken
        task = self.task(self.link.request(b"\x0a\x03\0", 0x0B))
        self.assertEqual(await self.recv(), b"\x0a\x03\0")
        with self.assertRaisesRegex(RuntimeError, "trace callback"):
            await task
        self.assertIsNotNone(self.conn._failure)

    async def test_failed_send_is_not_recorded(self):
        with (
            patch.object(
                asyncio.get_running_loop(), "sock_sendall", AsyncMock(side_effect=OSError("send failed"))
            ),
            self.assertRaises(OSError),
        ):
            await self.link.request(b"\x0a\x03\0", 0x0B)
        self.assertEqual(self.report["att_packets"], [])

    async def test_successful_send_return_race_preserves_actual_observation_order(self):
        loop = asyncio.get_running_loop()
        original = loop.sock_sendall

        async def delayed_return(sock, pdu):
            await original(sock, pdu)
            await asyncio.sleep(0.02)

        with patch.object(loop, "sock_sendall", side_effect=delayed_return):
            task = self.task(self.link.request(b"\x0a\x03\0", 0x0B))
            await self.recv()
            await original(self.peer, b"\x0bok")
            self.assertEqual(await task, b"\x0bok")
        self.assertEqual([r["direction"] for r in self.report["att_packets"]], ["rx", "tx"])
        # No fabricated reorder; strict operation proof conservatively refuses
        # response-before-request. Full HCI binding compares within directions.
