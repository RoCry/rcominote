"""Experiment-only Boyi/Actions client: one socket, one inherited dispatcher."""

import asyncio
import time
from uuid import UUID

from rcominote.connection import Connection
from rcominote.experiments.sd_bridge import console_packet
from rcominote.linux_att import AttLink
from rcominote.linux_client import Characteristic, LinuxClient
from rcominote.log_capture import START, STOP
from rcominote.log_probe import NOTIFY, PREPARE, SERVICE, WRITE
from rcominote.log_stream import Stream

ACTION_SERVICE = b"\x11\x14\x14\x00\x19\x00" + UUID(SERVICE).bytes[::-1]
ACTION_CHARS = bytes.fromhex(
    "091515000c1600d19f1b1f80f2b28ee8119af602309ae41700101800d19f1b1f80f2b28ee8119af603309ae4"
)
ACTION_DESCRIPTOR = bytes.fromhex("050119000229")


class DualClient(LinuxClient):
    def __init__(self, device, report, **kwargs):
        super().__init__(device, **kwargs)
        self.report = report
        self.receive_guard = None
        self.receive_observer = None
        report["att_packets"] = []
        self._link = AttLink(device.address, disconnected_callback=self._failed, trace=self.record)

    def record(self, direction, pdu):
        rows = self.report["att_packets"]
        if len(rows) >= 4096:
            raise RuntimeError("Dual session ATT evidence bound exceeded")
        rows.append({"direction": direction, "hex": pdu.hex(), "monotonic_ns": time.monotonic_ns()})
        if self.receive_observer is not None:
            self.receive_observer(len(rows) - 1, rows[-1])
        if direction == "rx" and self.receive_guard is not None:
            self.receive_guard(pdu)

    async def _discover(self):
        await super()._discover()
        for request, response in (
            (bytes.fromhex("10140019000028"), ACTION_SERVICE),
            (bytes.fromhex("08140019000328"), ACTION_CHARS),
            (bytes.fromhex("0419001900"), ACTION_DESCRIPTOR),
        ):
            actual = await self._link.request(request, response[0])
            if actual != response:
                raise ValueError("Actions GATT differs from fixed FW010004 session profile")
        self.services.characteristics[WRITE] = Characteristic(WRITE, 21, 22, 12)
        self.services.characteristics[NOTIFY] = Characteristic(NOTIFY, 23, 24, 16, 25)

    async def action_write(self, packet):
        self._check()
        if await self._link.request(b"\x12\x16\0" + packet, 0x13) != b"\x13":
            raise ValueError("Actions Write Request lacks exact response")


class DualConnection(Connection):
    def __init__(self, device, report):
        super().__init__(device)  # Neither constructor opens a socket.
        self.client = DualClient(device, report, timeout=20, disconnected_callback=self._dropped)
        self.offline_allowed = False

    def _received(self, source, packet):
        if source == "off" and not self.offline_allowed:
            raise ValueError("Offline Boyi bytes outside the sole active download")
        super()._received(source, packet)


class Actions:
    """Synchronous callback decoder; never competes with the single dispatcher."""

    def __init__(self, conn, session):
        self.conn, self.session = conn, session
        self.operation = None
        self.changed = asyncio.Event()
        self.failure = None
        self.expected = 0
        self.total_expected = 5
        self.stream = None
        conn.client.receive_guard = self.guard_received

    def guard_received(self, pdu):
        # Check at actual socket RX time, before the dispatcher queue can defer
        # an old packet until a later transaction. No queue drain/discard.
        if pdu[:3] == b"\x1b\x18\0" and self.operation is None:
            raise ValueError("Late Actions at socket receive outside operation")
        if pdu[:3] == b"\x1b\x2a\0" and not self.conn.offline_allowed:
            raise ValueError("Offline bytes at socket receive outside download")

    def receive(self, _characteristic, data):
        if self.operation is None:
            raise ValueError("Late Actions notification outside active operation")
        rows = self.operation["notifications"]
        if len(rows) >= 1024 or sum(len(r) // 2 for r in rows) + len(data) > 65536:
            raise RuntimeError("Actions evidence bound exceeded")
        rows.append(bytes(data).hex())
        if self.failure is None:
            try:
                if self.stream.ended:
                    raise ValueError("Actions data after F1")
                self.stream.feed(bytes(data))
                if self.stream.acks > self.expected or (
                    self.stream.ended and self.expected != self.total_expected
                ):
                    raise ValueError("Actions ACK/end precedes its exact request")
            except ValueError as error:
                self.failure = error
        self.changed.set()

    async def wait(self, predicate):
        async with asyncio.timeout(5):
            while True:
                self.conn._check_failure()
                if self.failure is not None:
                    raise self.failure
                if predicate():
                    return
                self.changed.clear()
                await self.changed.wait()

    async def run(self, op):
        await self.run_commands(
            op,
            [console_packet(op["producer"]), console_packet(op["dump_command"])],
            sd_write_command_index=1,
        )

    async def run_commands(self, op, commands: list[bytes], *, sd_write_command_index: int | None):
        if (
            not isinstance(commands, list)
            or len(commands) > 3
            or any(not isinstance(packet, bytes) or not packet for packet in commands)
            or (
                sd_write_command_index is not None
                and (
                    type(sd_write_command_index) is not int or not 0 <= sd_write_command_index < len(commands)
                )
            )
        ):
            raise ValueError(
                "Actions body requires at most three packets and an explicit valid SD-write index"
            )
        if self.operation is not None or not self.conn.queue.empty() or self.conn.client._link.notifications:
            raise ValueError("Actions operation overlaps another transaction/queued Boyi bytes")
        self.operation, self.stream, self.failure, self.expected = op, Stream(), None, 0
        self.total_expected = 3 + len(commands)
        op.update(
            notifications=[],
            writes=[],
            frames=self.stream.frames,
            sd_write_attempted=False,
            log_session_complete=False,
        )
        op["actions_start"] = len(self.session["att_packets"])
        attempted = False
        failure = None

        async def send(packet, *, cleanup=False):
            self.expected += 1
            row = {"hex": packet.hex(), "att_write_confirmed": False}
            op["writes"].append(row)
            if cleanup and len(commands) in (0, 1, 3):
                # Fixed empty/one/three-body controls bound failed cleanup to two seconds.
                async with asyncio.timeout(2):
                    await self.conn.client.action_write(packet)
            else:
                await self.conn.client.action_write(packet)
            row["att_write_confirmed"] = True
            if not cleanup:
                await self.wait(lambda: self.stream.acks >= self.expected)

        async with self.conn._transaction:
            try:
                await send(PREPARE)
                attempted = True  # START may take effect even if its response fails.
                await send(START)
                for index, packet in enumerate(commands):
                    if index == sd_write_command_index:
                        op["sd_write_attempted"] = True
                    await send(packet)
            except BaseException as error:
                failure = error
                raise
            finally:
                try:
                    if attempted:
                        await send(STOP, cleanup=failure is not None)
                        if failure is None:
                            await self.wait(lambda: self.stream.ended)
                            if self.stream.pending or self.stream.acks != self.total_expected:
                                raise ValueError("Incomplete Actions operation")
                            op["log_session_complete"] = True
                except BaseException as error:
                    op["cleanup_error"] = f"{type(error).__name__}: {error}"
                    if failure is None:
                        raise
                finally:
                    op.update(
                        actions_end=len(self.session["att_packets"]),
                        ack_count=self.stream.acks,
                        end_received=self.stream.ended,
                        pending_hex=self.stream.pending.hex(),
                    )
                    self.operation = None
                    if failure is not None or op.get("cleanup_error"):
                        self.conn._fail(RuntimeError("Actions operation failed; session retired"))
