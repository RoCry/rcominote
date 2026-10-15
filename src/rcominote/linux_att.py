"""Linux public-LE ATT transport; one request in flight and bounded notifications.

Linux ABI: BlueZ 5.72 lib/{bluetooth,l2cap}.h (commit 770ad5614e7e8074133e6f563495ce4822f63fe4).
AF_BLUETOOTH=31, BTPROTO_L2CAP=0, BDADDR_LE_PUBLIC=1; fixed ATT CID=4.
The ctypes connect avoids Python builds which omit AF_BLUETOOTH address conversion.
"""

import asyncio
import ctypes
import errno
import math
import re
import socket
import struct
import sys
from collections import deque
from collections.abc import Callable


class AttError(ValueError):
    """Peer ATT Error Response, retained verbatim for narrowly checked discovery EOF."""

    def __init__(self, pdu: bytes):
        self.pdu = pdu
        super().__init__(f"ATT Error Response: {pdu.hex()}")


class AttLink:
    local_mtu = 247
    timeout = 10.0

    def __init__(
        self,
        address: str,
        *,
        disconnected_callback: Callable[[Exception], None] | None = None,
        notification_limit: int = 256,
        timeout: float = 10.0,
        trace: Callable[[str, bytes], None] | None = None,
    ):
        if not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", address):
            raise ValueError("Expected six colon-separated MAC octets")
        self.address = address
        if type(notification_limit) is not int or notification_limit <= 0:
            raise ValueError("Notification limit must be a positive integer")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("ATT timeout must be finite and positive")
        self.timeout = timeout
        self.notification_limit = notification_limit
        self._disconnected_callback = disconnected_callback
        self.mtu = 23
        self.notifications: deque[tuple[int, bytes]] = deque()
        self._available = asyncio.Event()
        self._request_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._socket: socket.socket | None = None
        self._reader: asyncio.Task | None = None
        self._pending: asyncio.Future | None = None
        self._expected: int | None = None
        self._request_opcode: int | None = None
        self._failure: BaseException | None = None
        self._entered = False
        self._trace_callback = trace

    def _sockaddr(self, *, local: bool = False) -> bytes:
        # Native Linux little-endian sockaddr_l2, including ABI trailing alignment byte.
        address = bytes(6) if local else bytes.fromhex(self.address.replace(":", ""))[::-1]
        return struct.pack("<HH6sHBx", 31, 0, address, 4, 1)

    async def __aenter__(self):
        if self._entered:
            raise RuntimeError("ATT link cannot be re-entered")
        self._entered = True
        if sys.platform != "linux" or sys.byteorder != "little":
            raise RuntimeError("Direct ATT requires little-endian Linux")
        try:
            self._socket = socket.socket(31, socket.SOCK_SEQPACKET, 0)
            self._socket.setblocking(False)
            async with asyncio.timeout(self.timeout):
                await self._connect()
            self._reader = asyncio.create_task(self._receive())
            return self
        except BaseException:
            if self._socket is not None:
                self._socket.close()
            raise

    async def _connect(self):
        assert self._socket is not None
        libc = ctypes.CDLL(None, use_errno=True)
        bind = libc.bind
        bind.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        bind.restype = ctypes.c_int
        # Match BlueZ 5.72 btio.c:1955: bind ANY/public with CID4 first.
        # Linux 6.14 l2cap_add_scid changes CONN_ORIENTED to FIXED;
        # otherwise l2cap_chan_connect rejects PSM0 with EINVAL.
        local = ctypes.create_string_buffer(self._sockaddr(local=True))
        if bind(self._socket.fileno(), local, 14) < 0:
            raise OSError(ctypes.get_errno(), "LE ATT local bind failed")
        connect = libc.connect
        connect.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        connect.restype = ctypes.c_int
        address = ctypes.create_string_buffer(self._sockaddr())
        if connect(self._socket.fileno(), address, 14) == 0:
            return
        error = ctypes.get_errno()
        if error not in (errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY):
            raise OSError(error, "LE ATT connect failed")
        loop = asyncio.get_running_loop()
        ready = loop.create_future()
        fd = self._socket.fileno()

        def writable():
            if not ready.done():
                ready.set_result(None)

        loop.add_writer(fd, writable)
        try:
            await ready
            if error := self._socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR):
                raise OSError(error, "LE ATT connect failed")
        finally:
            loop.remove_writer(fd)

    async def __aexit__(self, *_args):
        self._fail(ConnectionError("ATT link closed"), notify=False)
        if self._reader is not None:
            self._reader.cancel()
            await asyncio.gather(self._reader, return_exceptions=True)

    def _check(self):
        if self._failure is not None:
            raise ConnectionError(f"ATT link unusable: {self._failure}") from self._failure
        if self._socket is None or self._socket.fileno() < 0:
            raise ConnectionError("ATT link not connected")

    def _fail(self, error: BaseException, *, notify: bool = True):
        if self._failure is not None:
            return
        self._failure = error
        if self._socket is not None:
            self._socket.close()
        self._available.set()
        if self._pending is not None and not self._pending.done():
            self._pending.set_exception(error)
        if notify and self._disconnected_callback is not None:
            failure = error if isinstance(error, Exception) else ConnectionError("ATT operation cancelled")
            try:
                self._disconnected_callback(failure)
            except Exception as callback_error:  # noqa: BLE001 - retain transport failure
                asyncio.get_running_loop().call_exception_handler(
                    {"message": "ATT disconnect callback failed", "exception": callback_error}
                )

    def abort(self, error: Exception) -> None:
        """Terminate transport after an upper-layer receive/dispatch failure."""
        self._fail(error)

    async def _send(self, pdu: bytes):
        async with self._write_lock:
            self._check()
            assert self._socket is not None
            async with asyncio.timeout(self.timeout):
                await asyncio.get_running_loop().sock_sendall(self._socket, pdu)
            self._trace("tx", pdu)

    def _trace(self, direction: str, pdu: bytes) -> None:
        if self._trace_callback is not None:
            try:
                self._trace_callback(direction, pdu)
            except Exception as error:
                failure = RuntimeError("ATT trace callback failed")
                self._fail(failure)
                raise failure from error

    def _exchange_mtu(self, pdu: bytes):
        if len(pdu) != 3:
            raise ValueError(f"Malformed ATT MTU PDU: {pdu.hex()}")
        peer = int.from_bytes(pdu[1:], "little")
        if not 23 <= peer <= 517:
            raise ValueError(f"Invalid peer ATT MTU: {peer}")
        self.mtu = min(self.local_mtu, peer)

    async def _receive(self):
        try:
            assert self._socket is not None
            while True:
                pdu = await asyncio.get_running_loop().sock_recv(self._socket, 518)
                if not pdu:
                    raise ConnectionError("ATT socket closed by peer")
                self._trace("rx", pdu)
                if len(pdu) > self.mtu:
                    raise ValueError(f"ATT PDU exceeds negotiated MTU: {len(pdu)} > {self.mtu}")
                opcode = pdu[0]
                if opcode == 0x02:
                    self._exchange_mtu(pdu)
                    await self._send(b"\x03\xf7\x00")
                elif opcode in (0x1B, 0x1D):
                    if len(pdu) < 3 or pdu[1:3] == b"\0\0":
                        raise ValueError(f"Malformed ATT notification/indication: {pdu.hex()}")
                    if len(self.notifications) >= self.notification_limit:
                        raise RuntimeError(
                            f"ATT notification buffer exceeded {self.notification_limit} packets"
                        )
                    if opcode == 0x1D:
                        await self._send(b"\x1e")
                    self.notifications.append((int.from_bytes(pdu[1:3], "little"), pdu[3:]))
                    self._available.set()
                elif self._pending is None or self._pending.done():
                    raise ValueError(f"Unsolicited ATT response: {pdu.hex()}")
                elif opcode == 0x01:
                    if len(pdu) != 5 or pdu[1] != self._request_opcode or pdu[4] == 0:
                        raise ValueError(f"Unmatched/malformed ATT error: {pdu.hex()}")
                    # An ATT error completes this request. Caller decides whether it
                    # is the protocol-defined discovery terminator or a failure.
                    self._pending.set_exception(AttError(pdu))
                elif opcode == self._expected:
                    if opcode == 0x03:
                        self._exchange_mtu(pdu)
                    elif opcode == 0x13 and len(pdu) != 1:
                        raise ValueError(f"Malformed ATT write response: {pdu.hex()}")
                    elif opcode in (0x05, 0x09, 0x11):
                        self._validate_table(pdu)
                    self._pending.set_result(pdu)
                else:
                    raise ValueError(f"Unexpected ATT response: {pdu.hex()}")
        except asyncio.CancelledError:
            raise
        except (OSError, ValueError, RuntimeError) as error:
            self._fail(error)

    @staticmethod
    def _validate_table(pdu: bytes) -> None:
        if len(pdu) <= 2:
            raise ValueError(f"Truncated ATT discovery response: {pdu.hex()}")
        width = {1: 4, 2: 18}.get(pdu[1], 0) if pdu[0] == 0x05 else pdu[1]
        minimum = 4 if pdu[0] in (0x05, 0x11) else 2
        if width < minimum or (len(pdu) - 2) % width:
            raise ValueError(f"Malformed ATT discovery response: {pdu.hex()}")

    async def request(self, pdu: bytes, expected: int) -> bytes:
        if not isinstance(pdu, bytes) or not pdu or len(pdu) > self.mtu:
            raise ValueError("ATT request must be nonempty bytes within negotiated MTU")
        if type(expected) is not int or not 0 <= expected <= 0xFF:
            raise ValueError("Expected ATT opcode must be a byte")
        async with self._request_lock:
            self._check()
            self._pending = asyncio.get_running_loop().create_future()
            self._expected, self._request_opcode = expected, pdu[0]
            try:
                async with asyncio.timeout(self.timeout):
                    await self._send(pdu)
                    return await self._pending
            except AttError:
                raise
            except BaseException as error:
                self._fail(error)
                # The send may have failed before anyone awaited this future.
                if self._pending.done() and not self._pending.cancelled():
                    self._pending.exception()
                raise
            finally:
                self._pending = None
                self._expected = self._request_opcode = None

    async def write_command(self, pdu: bytes) -> None:
        """Send one complete ATT Write Command, without a response transaction."""
        if (
            not isinstance(pdu, bytes)
            or not 3 <= len(pdu) <= self.mtu
            or pdu[0] != 0x52
            or pdu[1:3] == b"\0\0"
        ):
            raise ValueError("Expected ATT Write Command with nonzero handle within negotiated MTU")
        try:
            await self._send(pdu)
        except BaseException as error:
            self._fail(error)
            raise

    async def next_notification(self) -> tuple[int, bytes]:
        """Wait without an idle deadline; cancelling this wait does not close ATT."""
        while True:
            self._check()
            if self.notifications:
                return self.notifications.popleft()
            self._available.clear()
            await self._available.wait()
