"""Official-JS request goldens and failure sequences through the real Connection."""

import asyncio
import json
import signal
import unittest
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from rcominote.cli import app
from rcominote.connection import Connection
from rcominote.maintenance import MaintenanceUnverified, Operation, encode_user_id, submit

SERIAL = "C261CF0430"
# Owned-device capture, 2026-10-12 (same independent fixtures as test_comi).
SERIAL_REPLY = bytes.fromhex("d22d01010a4332363143463034333060bb")
IDLE = bytes.fromhex(
    "d22d0105340000e8f20000e8f00164000100040101ff78696e6b5f746573740000000000000000000000000009ff0300010000000000000000b321"
)
# Official JS Bt/ry/ho produced these frames; unknown ff7e payload intentionally
# exercises the distinction between matching response and verified effect.
ACK_BIND = bytes.fromhex("d22d010302ff7ea9e4")
ACK_FORMAT = bytes.fromhex("d22d011002ff7ead60")
ACK_PHONE = bytes.fromhex("d22d011802ff7eaf00")
BUSY = bytes.fromhex(
    "d22d0105340000e8f20000e8f00164010100040101ff78696e6b5f746573740000000000000000000000000009ff03000100000000000000004fe3"
)


def replay(*, info=IDLE, respond=True, on_mutation=None):
    client = AsyncMock()
    client.services.get_service = lambda _uuid: object()
    with patch("rcominote.connection.create_client", return_value=client):
        conn = Connection("maintenance-replay")

    async def on_write(_uuid, packet, **_kwargs):
        opcode = packet[3]
        if opcode == 1:
            reply = SERIAL_REPLY
        elif opcode == 5:
            reply = info
        else:
            if on_mutation:
                await on_mutation()
            reply = {3: ACK_BIND, 16: ACK_FORMAT, 18: None, 24: ACK_PHONE}[opcode] if respond else None
        if reply is not None:
            conn._received("cmd", reply)

    client.write_gatt_char.side_effect = on_write
    return conn, client


def wire(client):
    return [call.args[1] for call in client.write_gatt_char.await_args_list]


def invoke(conn, args):
    with (
        patch("rcominote.maintenance.find_device", new=AsyncMock(return_value="maintenance-replay")),
        patch("rcominote.maintenance.Connection", return_value=conn),
    ):
        return CliRunner().invoke(app, ["maintenance", *args])


class MaintenanceCliTests(unittest.TestCase):
    def test_seven_official_goldens_submit_once_close_and_never_claim_effect(self):
        cases = (
            (
                ["bind", "0123456789abcdef", "--confirm", "bind"],
                "d22d0103113031323334353637383961626364656600d2df",
                True,
            ),
            (["unbind", "--confirm", "unbind"], "d22d0103110000000000000000000000000000000000a95b", False),
            (
                ["unbind", "--confirm", "unbind", "--delete-recordings", "--confirm-delete-all", SERIAL],
                "d22d0103110000000000000000000000000000000001689b",
                False,
            ),
            (["format", "--confirm", "format"], "d22d011000ed7e", True),
            (["factory-reset", "--confirm", "factory-reset"], "d22d011200ec1e", False),
            (["phone-type", "android"], "d22d011801003e1f", True),
            (["phone-type", "ios"], "d22d01180101ffdf", True),
        )
        for args, golden, expects_reply in cases:
            with self.subTest(args=args):
                conn, client = replay()
                result = invoke(conn, [*args, "--serial", SERIAL])
                self.assertEqual(result.exit_code, 3, result.output)
                outcome = json.loads(result.stdout)
                self.assertEqual(outcome["status"], "submitted_unverified")
                self.assertFalse(outcome["ok"])
                self.assertFalse(outcome["device_effect_verified"])
                self.assertEqual(outcome["response_received"], expects_reply)
                self.assertEqual(outcome["reply_hex"], "ff7e" if expects_reply else None)
                self.assertEqual([packet[3] for packet in wire(client)[:2]], [1, 5])
                self.assertEqual(wire(client)[2:], [bytes.fromhex(golden)])
                client.__aexit__.assert_awaited_once()

    def test_validation_prevents_bluetooth_and_id_truncation(self):
        invalid = [
            ["format", "--confirm", "format"],
            ["format", "--serial", SERIAL],
            ["factory-reset", "--serial", SERIAL, "--confirm", "reboot"],
            ["phone-type", "ios", "--serial", ""],
            ["phone-type", "linux", "--serial", SERIAL],
            ["unbind", "--serial", SERIAL, "--confirm", "unbind", "--delete-recordings"],
            ["unbind", "--serial", SERIAL, "--confirm", "unbind", "--confirm-delete-all", SERIAL],
            [
                "unbind",
                "--serial",
                SERIAL,
                "--confirm",
                "unbind",
                "--delete-recordings",
                "--confirm-delete-all",
                "OTHER",
            ],
        ]
        invalid.extend(
            ["bind", user_id, "--serial", SERIAL, "--confirm", "bind"]
            for user_id in ("", "0123456789abcdefX", "用户", "a\0b", "a\nb", "a\x7fb")
        )
        for args in invalid:
            with (
                self.subTest(args=args),
                patch("rcominote.maintenance.find_device", new=AsyncMock()) as find,
            ):
                result = CliRunner().invoke(app, ["maintenance", *args])
                self.assertNotEqual(result.exit_code, 0)
                find.assert_not_awaited()

    def test_short_id_padding_is_not_truncation_or_unbind(self):
        self.assertEqual(encode_user_id("A"), bytes.fromhex("4100000000000000000000000000000000"))

    def test_wrong_connected_identity_and_busy_state_prevent_mutation(self):
        for serial, info, requests in (("OTHER", IDLE, [1]), (SERIAL, BUSY, [1, 5])):
            with self.subTest(serial=serial, busy=info == BUSY):
                conn, client = replay(info=info)
                result = invoke(conn, ["format", "--serial", serial, "--confirm", "format"])
                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual([packet[3] for packet in wire(client)], requests)
                client.__aexit__.assert_awaited_once()

    def test_synchronous_ack_sigint_returns_unknown_and_closes(self):
        async def interrupt_without_suspending():
            signal.raise_signal(signal.SIGINT)

        conn, client = replay(on_mutation=interrupt_without_suspending)
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            result = invoke(conn, ["phone-type", "ios", "--serial", SERIAL])
        finally:
            signal.signal(signal.SIGINT, previous)
        self.assertEqual(result.exit_code, 130, result.output)
        outcome = json.loads(result.stdout)
        self.assertEqual(outcome["status"], "unknown")
        self.assertTrue(outcome["response_received"])
        self.assertFalse(outcome["device_effect_verified"])
        self.assertEqual([packet[3] for packet in wire(client)], [1, 5, 24])
        client.__aexit__.assert_awaited_once()

    def test_disconnect_failure_retains_submission_observations_without_claiming_success(self):
        conn, client = replay()
        client.__aexit__.side_effect = OSError("disconnect failed")
        result = invoke(conn, ["format", "--serial", SERIAL, "--confirm", "format"])
        self.assertEqual(result.exit_code, 1, result.output)
        outcome = json.loads(result.stdout)
        self.assertEqual(outcome["status"], "unknown")
        self.assertTrue(outcome["request_sent"])
        self.assertTrue(outcome["response_received"])
        self.assertEqual(outcome["reply_hex"], "ff7e")
        self.assertFalse(outcome["device_effect_verified"])
        self.assertIn("disconnect failed", outcome["error"])
        self.assertEqual([packet[3] for packet in wire(client)], [1, 5, 16])


class MaintenanceConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_only_retires_session_even_with_late_reply(self):
        conn, client = replay()
        result = await submit(conn, Operation.unbind, bytes.fromhex("0000000000000000000000000000000000"))
        self.assertEqual(result["status"], "submitted_unverified")
        conn._received("cmd", ACK_BIND)
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.serial()
        self.assertEqual([packet[3] for packet in wire(client)], [5, 3])

    async def test_write_or_missing_ack_failure_has_no_retry_and_late_reply_cannot_reuse(self):
        for failure in ("write", "ack"):
            with self.subTest(failure=failure):

                async def broken_write():
                    raise OSError("GATT completion lost")

                conn, client = replay(respond=False, on_mutation=broken_write if failure == "write" else None)
                actual_command = conn.command

                async def bounded_command(cmd, payload=b"", *, timeout=5, actual_command=actual_command):
                    return await actual_command(cmd, payload, timeout=0.01)

                with (
                    patch.object(conn, "command", new=bounded_command),
                    self.assertRaises(MaintenanceUnverified) as caught,
                ):
                    await submit(conn, Operation.format)
                outcome = caught.exception.outcome
                self.assertEqual(outcome["status"], "unknown")
                self.assertFalse(outcome["response_received"])
                self.assertFalse(outcome["device_effect_verified"])
                conn._received("cmd", ACK_FORMAT)
                with self.assertRaisesRegex(ConnectionError, "reconnect"):
                    await conn.serial()
                self.assertEqual([packet[3] for packet in wire(client)], [5, 16])

    async def test_write_only_deadline_aborts_stuck_write_and_retires_session(self):
        async def pending_write():
            await asyncio.Event().wait()

        conn, client = replay(on_mutation=pending_write)
        with self.assertRaises(TimeoutError):
            await conn.send_only(18, timeout=0.01)
        with self.assertRaisesRegex(ConnectionError, "reconnect"):
            await conn.serial()
        self.assertEqual(wire(client), [bytes.fromhex("d22d011200ec1e")])
