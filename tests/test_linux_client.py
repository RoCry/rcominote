"""Boyi discovery, routing and transactions over literal ATT wire fixtures."""

import asyncio
import socket
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from rcominote import protocol as P
from rcominote.connection import Connection, create_client
from rcominote.linux_att import AttError
from rcominote.linux_client import LinuxClient

DEVICE = SimpleNamespace(address="50:C0:F0:AE:7C:0E", details={"props": {"AddressType": "public"}})
SERIAL_REPLY = bytes.fromhex("d22d01010a4332363143463034333060bb")
SERVICE = bytes.fromhex("110620002b00e0e5")
CHARACTERS = bytes.fromhex("090721000c2200e1e52300102400e2e52600102700e3e52900102a00e4e5")


def pages():
    return [
        SERVICE,
        AttError(bytes.fromhex("01102c000a")),
        CHARACTERS,
        AttError(bytes.fromhex("01082b000a")),
        bytes.fromhex("050125000229"),
        bytes.fromhex("050128000229"),
        bytes.fromhex("05012b000229"),
    ]


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    def client(self, responses=None):
        client = LinuxClient(DEVICE, timeout=20, disconnected_callback=Mock())
        client._link = AsyncMock()
        client._link.request.side_effect = pages() if responses is None else responses
        return client

    async def test_discovery_live_handles_and_notification_cccd_writes(self):
        client = self.client()
        await client._discover()
        self.assertIsNotNone(client.services.get_service(P.SERVICE))
        self.assertIsNone(client.services.get_service("00001800-0000-1000-8000-00805f9b34fb"))
        self.assertEqual(client.services.characteristics[P.NOTIFY_OFFLINE].handle, 0x2A)
        self.assertEqual(
            [call.args[0].hex() for call in client._link.request.await_args_list],
            [
                "100100ffff0028",
                "102c00ffff0028",
                "0820002b000328",
                "082b002b000328",
                "0425002500",
                "0428002800",
                "042b002b00",
            ],
        )
        client._link.request.side_effect = None
        client._link.request.return_value = b"\x13"
        await client.start_notify(P.NOTIFY_CMD, Mock())
        client._link.request.assert_awaited_with(bytes.fromhex("1225000100"), 0x13)
        await client.write_gatt_char(P.WRITE, bytes.fromhex("d22d010100e12e"), response=False)
        client._link.write_command.assert_awaited_once_with(bytes.fromhex("522200d22d010100e12e"))

    async def test_paginates_characteristic_and_descriptor_tables(self):
        responses = pages()
        responses[2:3] = [CHARACTERS[:16], CHARACTERS[:2] + CHARACTERS[16:]]
        client = self.client(responses)
        await client._discover()
        self.assertIn("0825002b000328", [call.args[0].hex() for call in client._link.request.await_args_list])

        client = self.client([bytes.fromhex("050125000129"), bytes.fromhex("050126000229")])
        self.assertEqual(await client._cccd(0x25, 0x26), 0x26)

    async def test_wrong_error_handle_is_not_discovery_eof(self):
        client = self.client([SERVICE, AttError(bytes.fromhex("011000000a"))])
        with self.assertRaises(AttError):
            await client._discover()

    async def test_duplicate_service_and_nonmonotonic_characteristic_rejected(self):
        invalid = [
            [bytes.fromhex("110620002b00e0e52c003700e0e5")],
            [*pages()[:2], bytes.fromhex("090721000c2200e1e52100102400e2e5")],
        ]
        for responses in invalid:
            with self.subTest(responses=responses), self.assertRaises(ValueError):
                await self.client(responses)._discover()

    async def test_missing_cccd_fails_before_subscription(self):
        client = self.client([*pages()[:4], AttError(bytes.fromhex("010425000a"))])
        with self.assertRaisesRegex(ValueError, "no CCCD"):
            await client._discover()
        self.assertFalse(any(call.args[0][0] == 0x12 for call in client._link.request.await_args_list))

    async def test_setup_failure_closes_transport(self):
        client = self.client()
        client._link.__aenter__.side_effect = OSError("connect failed")
        with self.assertRaisesRegex(OSError, "connect failed"):
            await client.__aenter__()
        client._link.__aexit__.assert_awaited_once()

    async def test_subscription_failure_removes_callback(self):
        client = self.client()
        await client._discover()
        client._link.request.side_effect = OSError("CCCD write failed")
        with self.assertRaisesRegex(OSError, "CCCD write failed"):
            await client.start_notify(P.NOTIFY_CMD, Mock())
        self.assertEqual(client._callbacks, {})

    def test_platform_selection_and_address_type(self):
        with patch("rcominote.connection.sys.platform", "linux"):
            self.assertIsInstance(
                create_client(DEVICE, timeout=20, disconnected_callback=Mock()), LinuxClient
            )
        with (
            patch("rcominote.connection.sys.platform", "darwin"),
            patch("rcominote.connection.BleakClient") as bleak,
        ):
            self.assertIs(create_client(DEVICE, timeout=20, disconnected_callback=Mock()), bleak.return_value)
        for address_type in (None, "random"):
            with self.subTest(address_type=address_type), self.assertRaisesRegex(ValueError, "public LE"):
                LinuxClient(
                    SimpleNamespace(address=DEVICE.address, details={"props": {"AddressType": address_type}}),
                    timeout=20,
                    disconnected_callback=Mock(),
                )


@unittest.skipUnless(sys.platform == "linux", "Linux ATT packet-socket lifecycle tests")
class WireTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = LinuxClient(
            DEVICE, timeout=20, disconnected_callback=lambda _: self.conn._dropped(None)
        )
        with patch("rcominote.connection.create_client", return_value=self.client):
            self.conn = Connection(DEVICE)
        local, self.peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        local.setblocking(False)
        self.peer.setblocking(False)
        self.client._link._socket = local
        self.client._link._reader = asyncio.create_task(self.client._link._receive())
        # Replay discovery separately; use the real link for subscription and Boyi traffic.
        with patch.object(self.client._link, "request", side_effect=pages()):
            await self.client._discover()
        self.client._dispatcher = asyncio.create_task(self.client._dispatch())
        self.addAsyncCleanup(self.client.__aexit__, None, None, None)
        self.addCleanup(self.peer.close)

    async def receive(self):
        return await asyncio.wait_for(asyncio.get_running_loop().sock_recv(self.peer, 518), 1)

    async def send(self, packet):
        await asyncio.get_running_loop().sock_sendall(self.peer, packet)

    async def subscribe(self, uuid, source="cmd"):
        task = asyncio.create_task(
            self.client.start_notify(uuid, lambda _c, d: self.conn._received(source, d))
        )
        self.addAsyncCleanup(self.finish, task)
        await self.receive()
        await self.send(b"\x13")
        await task

    async def finish(self, task):
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_serial_response_routed_even_before_cccd_write_response(self):
        callback = lambda _c, d: self.conn._received("cmd", d)
        task = asyncio.create_task(self.client.start_notify(P.NOTIFY_CMD, callback))
        self.addAsyncCleanup(self.finish, task)
        self.assertEqual(await self.receive(), bytes.fromhex("1225000100"))
        await self.send(b"\x1b\x24\x00" + SERIAL_REPLY)
        await self.send(b"\x13")
        await task
        serial = asyncio.create_task(self.conn.serial())
        self.addAsyncCleanup(self.finish, serial)
        self.assertEqual(await self.receive(), bytes.fromhex("522200d22d010100e12e"))
        self.assertEqual(await serial, "C261CF0430")

    async def test_download_routes_offline_and_command_notifications(self):
        self.client._link.mtu = 247
        await self.subscribe(P.NOTIFY_CMD)
        await self.subscribe(P.NOTIFY_OFFLINE, "off")
        received = []
        download = asyncio.create_task(self.conn.download("recording", received.append))
        self.addAsyncCleanup(self.finish, download)
        request = await self.receive()
        self.assertEqual(request[:3], bytes.fromhex("522200"))
        self.assertEqual(P.parse(request[3:]), (11, b"recording\0\0\0\0\0\x00\x00\x00\x00"))
        await self.send(bytes.fromhex("1b2400d22d010b0500000000035f6a"))
        await self.send(bytes.fromhex("1b2a00616263"))
        await self.send(bytes.fromhex("1b2400d22d010b01024e1b"))
        self.assertEqual(await download, 3)
        self.assertEqual(b"".join(received), b"abc")

    async def test_download_request_cannot_exceed_peer_mtu(self):
        with self.assertRaisesRegex(ValueError, "negotiated MTU"):
            await self.conn.download("recording", lambda _: None)
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await self.conn.serial()

    async def test_download_cancellation_stop_uses_same_live_transport(self):
        from rcominote.download_cancel import DownloadCancelled

        self.client._link.mtu = 247
        await self.subscribe(P.NOTIFY_CMD)
        await self.subscribe(P.NOTIFY_OFFLINE, "off")
        accepted = asyncio.Event()
        download = asyncio.create_task(self.conn.download("recording", lambda _: accepted.set()))
        self.addAsyncCleanup(self.finish, download)
        await self.receive()
        await self.send(bytes.fromhex("1b2400d22d010b0500000000035f6a"))
        await self.send(bytes.fromhex("1b2a0061"))
        await asyncio.wait_for(accepted.wait(), 1)
        download.cancel()
        stop = await self.receive()
        self.assertEqual(P.parse(stop[3:]), (12, b""))
        await self.send(bytes.fromhex("1b2a006263"))
        await self.send(bytes.fromhex("1b2400d22d010c01007e1b"))
        with self.assertRaises(DownloadCancelled) as caught:
            await download
        self.assertEqual(caught.exception.received, 1)
        self.assertTrue(caught.exception.stop_result["response_received"])
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await self.conn.serial()

    async def test_remote_close_interrupts_pending_boyi_command(self):
        await self.subscribe(P.NOTIFY_CMD)
        serial = asyncio.create_task(self.conn.serial())
        self.addAsyncCleanup(self.finish, serial)
        await self.receive()
        self.peer.close()
        with self.assertRaisesRegex(ConnectionError, "disconnected"):
            await asyncio.wait_for(serial, 1)

    async def test_callback_failure_terminates_link(self):
        def broken(_characteristic, _data):
            raise OSError("receive sink failed")

        self.client._callbacks[0x24] = self.client.services.characteristics[P.NOTIFY_CMD], broken
        await self.send(b"\x1b\x24\x00" + SERIAL_REPLY)
        await asyncio.wait_for(self.client._dispatcher, 1)
        with self.assertRaisesRegex(ConnectionError, "receive sink failed"):
            await self.client.write_gatt_char(P.WRITE, b"x", response=False)

    async def test_idle_notification_dispatch_has_no_transaction_timeout(self):
        self.client._link.timeout = 0.001
        await asyncio.sleep(0.01)
        self.assertFalse(self.client._dispatcher.done())


if __name__ == "__main__":
    unittest.main()
