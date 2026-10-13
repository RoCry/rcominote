"""Boyi-only Linux GATT client over an explicitly LE/public ATT connection.

Discovery validates live handles; it never assumes the historical handle table.
Application transactions, framing and download validation remain in Connection.
"""

import asyncio
import struct
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from . import protocol as P
from .linux_att import AttError, AttLink


def uuid_string(raw: bytes) -> str:
    if len(raw) == 2:
        return f"0000{int.from_bytes(raw, 'little'):04x}-0000-1000-8000-00805f9b34fb"
    if len(raw) == 16:
        return str(UUID(bytes=raw[::-1]))
    raise ValueError("GATT UUID must contain 2 or 16 bytes")


def table_rows(pdu: bytes, widths: tuple[int, ...]) -> list[bytes]:
    if len(pdu) < 2 or pdu[1] not in widths or len(pdu) == 2 or (len(pdu) - 2) % pdu[1]:
        raise ValueError(f"Malformed GATT discovery table: {pdu.hex()}")
    return [pdu[offset : offset + pdu[1]] for offset in range(2, len(pdu), pdu[1])]


@dataclass(frozen=True, slots=True)
class Characteristic:
    uuid: str
    declaration: int
    handle: int
    properties: int
    cccd: int | None = None


class BoyiService:
    def __init__(self):
        self.start = 0
        self.end = 0
        self.characteristics: dict[str, Characteristic] = {}

    def get_service(self, uuid: str):
        return self if self.start and uuid.lower() == P.SERVICE else None


class LinuxClient:
    """Small transport adapter for Connection; no Actions shell or OTA support."""

    def __init__(self, device, *, timeout: float, disconnected_callback: Callable):
        if device.details.get("props", {}).get("AddressType") != "public":
            raise ValueError("Direct Linux CoMi transport requires a scanned public LE address")
        self.services = BoyiService()
        self._timeout = timeout
        self._disconnected_callback = disconnected_callback
        self._failure: Exception | None = None
        self._closing = False
        self._callbacks: dict[int, tuple[Characteristic, Callable]] = {}
        self._dispatcher: asyncio.Task | None = None
        self._link = AttLink(device.address, disconnected_callback=self._failed)

    def _failed(self, error: Exception):
        if self._failure is None:
            self._failure = error
            if not self._closing:
                self._disconnected_callback(self)

    def _check(self):
        if self._failure is not None:
            raise ConnectionError(f"Linux CoMi transport failed: {self._failure}") from self._failure
        if self._closing:
            raise ConnectionError("Linux CoMi transport closed")

    async def __aenter__(self):
        try:
            async with asyncio.timeout(self._timeout):
                await self._link.__aenter__()
                await self._link.request(b"\x02\xf7\x00", 0x03)
                await self._discover()
            self._dispatcher = asyncio.create_task(self._dispatch())
            return self
        except BaseException:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self, *_exc):
        self._closing = True
        if self._dispatcher is not None:
            self._dispatcher.cancel()
            await asyncio.gather(self._dispatcher, return_exceptions=True)
        await self._link.__aexit__(None, None, None)

    async def _page(self, request: bytes, expected: int) -> bytes | None:
        try:
            return await self._link.request(request, expected)
        except AttError as error:
            # Only Attribute Not Found for this exact opcode/start terminates a table.
            if error.pdu == b"\x01" + request[:3] + b"\x0a":
                return None
            raise

    async def _discover(self):
        start = 1
        while start <= 0xFFFF:
            request = b"\x10" + struct.pack("<HHH", start, 0xFFFF, 0x2800)
            if (pdu := await self._page(request, 0x11)) is None:
                break
            for row in table_rows(pdu, (6, 20)):
                first, last = struct.unpack_from("<HH", row)
                if not start <= first <= last:
                    raise ValueError("Nonmonotonic GATT service handles")
                if uuid_string(row[4:]) == P.SERVICE:
                    if self.services.start:
                        raise ValueError("Duplicate Boyi control service")
                    self.services.start, self.services.end = first, last
                start = last + 1
        if not self.services.start:
            raise ValueError("Target does not expose the Boyi control service")

        characters = []
        start = self.services.start
        while start <= self.services.end:
            request = b"\x08" + struct.pack("<HHH", start, self.services.end, 0x2803)
            if (pdu := await self._page(request, 0x09)) is None:
                break
            for row in table_rows(pdu, (7, 21)):
                declaration, properties, value = struct.unpack_from("<HBH", row)
                if not start <= declaration < value <= self.services.end:
                    raise ValueError("Invalid/nonmonotonic GATT characteristic handles")
                characters.append(Characteristic(uuid_string(row[5:]), declaration, value, properties))
                start = value + 1
        if len({char.uuid for char in characters}) != len(characters):
            raise ValueError("Duplicate Boyi characteristic UUID")

        for index, char in enumerate(characters):
            end = characters[index + 1].declaration - 1 if index + 1 < len(characters) else self.services.end
            if char.handle > end:
                raise ValueError("Overlapping GATT characteristic handles")
            cccd = await self._cccd(char.handle + 1, end) if char.properties & 0x10 else None
            self.services.characteristics[char.uuid] = Characteristic(
                char.uuid, char.declaration, char.handle, char.properties, cccd
            )
        for uuid, required_property in (
            (P.WRITE, 0x04),
            (P.NOTIFY_CMD, 0x10),
            (P.NOTIFY_OFFLINE, 0x10),
            (P.NOTIFY_REALTIME, 0x10),
        ):
            char = self._characteristic(uuid)
            if not char.properties & required_property:
                raise ValueError(f"Boyi characteristic {uuid} lacks required GATT property")

    async def _cccd(self, start: int, end: int) -> int:
        cccd = None
        while start <= end:
            request = b"\x04" + struct.pack("<HH", start, end)
            if (pdu := await self._page(request, 0x05)) is None:
                break
            if len(pdu) < 2 or pdu[1] not in (1, 2):
                raise ValueError("Invalid GATT descriptor format")
            width = 4 if pdu[1] == 1 else 18
            rows = table_rows(bytes((pdu[0], width)) + pdu[2:], (width,))
            for row in rows:
                handle = int.from_bytes(row[:2], "little")
                if not start <= handle <= end:
                    raise ValueError("Nonmonotonic GATT descriptor handles")
                if uuid_string(row[2:]) == "00002902-0000-1000-8000-00805f9b34fb":
                    if cccd is not None:
                        raise ValueError("Duplicate GATT CCCD")
                    cccd = handle
                start = handle + 1
        if cccd is None:
            raise ValueError("Boyi notification characteristic has no CCCD")
        return cccd

    def _characteristic(self, uuid: str) -> Characteristic:
        try:
            return self.services.characteristics[uuid.lower()]
        except KeyError as error:
            raise ValueError(f"Missing Boyi characteristic: {uuid}") from error

    async def start_notify(self, uuid: str, callback: Callable):
        self._check()
        char = self._characteristic(uuid)
        if not char.properties & 0x10 or char.cccd is None:
            raise ValueError(f"Characteristic cannot notify: {uuid}")
        if char.handle in self._callbacks:
            raise ValueError(f"Already subscribed: {uuid}")
        self._callbacks[char.handle] = char, callback
        try:
            response = await self._link.request(b"\x12" + struct.pack("<HH", char.cccd, 1), 0x13)
            if response != b"\x13":
                raise ValueError("Malformed GATT CCCD write response")
        except BaseException:
            self._callbacks.pop(char.handle, None)
            raise

    async def write_gatt_char(self, uuid: str, data: bytes, *, response: bool):
        self._check()
        char = self._characteristic(uuid)
        if response or not char.properties & 0x04:
            raise ValueError("Boyi transport requires a Write Without Response characteristic")
        await self._link.write_command(b"\x52" + struct.pack("<H", char.handle) + data)

    async def _dispatch(self):
        try:
            while True:
                handle, data = await self._link.next_notification()
                if handle not in self._callbacks:
                    raise ValueError(f"Unsubscribed GATT notification: {handle:#06x}")
                char, callback = self._callbacks[handle]
                callback(char, bytearray(data))
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - callback failures invalidate the transport
            self._link.abort(error)
            self._failed(error)
