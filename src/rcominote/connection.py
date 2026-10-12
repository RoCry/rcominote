"""Boyi BLE transactions with explicit transfer and cancellation boundaries."""

from __future__ import annotations

import asyncio
import math
import struct
import sys
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from bleak import BleakClient

from . import protocol as P
from .download_cancel import DownloadCancelled

BUFFER_LIMIT = 256
REALTIME_BYTE_LIMIT = 16 * 1024 * 1024
CANCEL_TIMEOUT = 1.0


@dataclass(slots=True)
class RealtimeCapture:
    """Local capture accounting; sink failure must not prevent recording cleanup."""

    connection: Connection
    sink: Callable[[bytes], int]
    bytes: int = 0
    packets: int = 0
    error: Exception | None = None

    def receive(self, data: bytes) -> None:
        if self.error is not None:
            return
        try:
            if self.bytes + len(data) > REALTIME_BYTE_LIMIT:
                raise RuntimeError("Realtime capture exceeded 16 MiB")
            if self.sink(data) != len(data):
                raise OSError("Short write while saving realtime audio")
            self.bytes += len(data)
            self.packets += 1
        except Exception as error:  # noqa: BLE001 - propagate callback failure to capture owner
            self.error = error

    def check(self) -> None:
        self.connection._check_failure()
        if self.error is not None:
            raise self.error

    async def wait(self, duration: float) -> None:
        if not math.isfinite(duration) or not 0 < duration <= 300:
            raise ValueError("Realtime duration must be finite, >0 and <=300 seconds")
        deadline = asyncio.get_running_loop().time() + duration
        while True:
            self.check()
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return
            await asyncio.sleep(min(remaining, 0.1))


def validate_filename(name: str) -> bytes:
    """Validate the protocol's 14-byte name before using it on wire or disk."""
    try:
        raw = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("Recording name must be ASCII") from exc
    if not 1 <= len(raw) <= 14:
        raise ValueError("Recording name must contain 1..14 ASCII bytes")
    if (
        any(byte < 0x20 or byte == 0x7F for byte in raw)
        or any(item in name for item in ("/", "\\", ".."))
        or name == "."
    ):
        raise ValueError("Recording name must not contain paths or control characters")
    return raw


def recording_output_name(name: str, offset: int = 0) -> str:
    validate_filename(name)
    if type(offset) is not int or not 0 <= offset <= 0xFFFFFFFF:
        raise ValueError("Recording offset must be an integer in 0..4294967295")
    return f"{name}.offset-{offset}.bin" if offset else f"{name}.mp3"


class Connection:
    """One transaction at a time; failed exchanges permanently invalidate the session."""

    def __init__(self, device):
        self.queue: asyncio.Queue[tuple[str, bytes] | None] = asyncio.Queue(maxsize=BUFFER_LIMIT)
        self.events: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=BUFFER_LIMIT)
        self._failure: Exception | None = None
        self.client = BleakClient(device, timeout=20, disconnected_callback=self._dropped)
        self._transaction = asyncio.Lock()
        self._realtime_enabled = False
        self._realtime_capture: RealtimeCapture | None = None
        self._discard_offline = False

    def _received_realtime(self, _characteristic, data: bytearray) -> None:
        if self._realtime_capture is not None:
            self._realtime_capture.receive(bytes(data))

    @asynccontextmanager
    async def realtime_capture(self, sink: Callable[[bytes], int]):
        """Capture raw chunks; retain CCC subscription until disconnect (FW010004)."""
        self._check_failure()
        if self._realtime_capture is not None:
            raise RuntimeError("A realtime capture is already active on this connection")
        capture = RealtimeCapture(self, sink)
        self._realtime_capture = capture
        try:
            if not self._realtime_enabled:
                await self.client.start_notify(P.NOTIFY_REALTIME, self._received_realtime)
                self._realtime_enabled = True
            yield capture
            capture.check()
        finally:
            self._realtime_capture = None

    def _dropped(self, _client):
        self._fail(ConnectionError("CoMi disconnected before completing the request"))

    def _fail(self, error: Exception) -> None:
        if self._failure is None:
            self._failure = error
            for queue in (self.queue, self.events):
                if not queue.full():
                    queue.put_nowait(None)

    def _check_failure(self) -> None:
        if self._failure is not None:
            raise self._failure

    def _received(self, source: str, packet: bytes) -> None:
        """Route at notification time, including when no transaction is waiting."""
        if self._failure is not None:
            return
        if source == "off" and self._discard_offline:
            return
        try:
            if source == "cmd":
                cmd, payload = P.parse(packet)
                if cmd in (P.DEVICE_STATUS_CHANGE, P.VOICE_CONTROL_CHANGE):
                    self.events.put_nowait(P.parse_event(cmd, payload) | {"frame": packet.hex()})
                    return
            self.queue.put_nowait((source, packet))
        except asyncio.QueueFull:
            self._fail(RuntimeError(f"CoMi notification buffer exceeded {BUFFER_LIMIT} packets"))
        except ValueError as error:
            self._fail(error)

    async def __aenter__(self):
        await self.client.__aenter__()
        try:
            if self.client.services.get_service(P.SERVICE) is None:
                raise ValueError("Target does not expose the Boyi control service")
            await self.client.start_notify(P.NOTIFY_CMD, lambda _c, d: self._received("cmd", bytes(d)))
            await self.client.start_notify(P.NOTIFY_OFFLINE, lambda _c, d: self._received("off", bytes(d)))
        except BaseException as error:
            try:
                await self.client.__aexit__(*sys.exc_info())
            except BaseException as cleanup_error:  # noqa: BLE001 - retain original cancellation/setup error
                error.add_note(f"Disconnect after setup failure also failed: {cleanup_error}")
            raise
        return self

    async def __aexit__(self, *exc):
        await self.client.__aexit__(*exc)

    async def _write(self, cmd: int, payload: bytes = b"") -> None:
        self._check_failure()
        await self.client.write_gatt_char(P.WRITE, P.frame(cmd, payload), response=False)

    @asynccontextmanager
    async def _request(self, cmd: int, payload: bytes = b"", *, timeout: float):
        # Pure validation and cancellation while waiting for the lock cannot
        # leave a remote request in flight. A failed GATT write attempt can.
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("CoMi request timeout must be finite and greater than zero")
        packet = P.frame(cmd, payload)
        async with self._transaction:
            self._check_failure()
            try:
                await self.client.write_gatt_char(P.WRITE, packet, response=False)
                yield
            except BaseException:
                # Replies and offline chunks carry no transaction identity.
                # Clearing queued packets cannot isolate late notifications.
                self._fail(ConnectionError("CoMi request did not finish; reconnect before another request"))
                raise

    async def _take[T](self, queue: asyncio.Queue[T | None], deadline: float) -> T:
        self._check_failure()
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("CoMi response deadline exceeded")
        try:
            item = await asyncio.wait_for(queue.get(), timeout=remaining)
        except TimeoutError as exc:
            self._check_failure()
            raise TimeoutError("CoMi response deadline exceeded") from exc
        self._check_failure()
        if item is None:
            raise ConnectionError("CoMi disconnected before completing the request")
        return item

    async def _next(self, deadline: float) -> tuple[str, bytes]:
        return await self._take(self.queue, deadline)

    async def watch(self, duration: float) -> list[dict]:
        """Collect events from connection setup through a fixed watch deadline."""
        if not 0 < duration <= 300:
            raise ValueError("Watch duration must be >0 and <=300 seconds")
        deadline = asyncio.get_running_loop().time() + duration
        collected = []
        while True:
            try:
                event = await self._take(self.events, deadline)
            except TimeoutError:
                return collected
            if len(collected) == BUFFER_LIMIT:
                raise RuntimeError(f"CoMi watch exceeded {BUFFER_LIMIT} events; choose a shorter duration")
            collected.append(event)

    async def command(self, cmd: int, payload: bytes = b"", timeout: float = 5.0) -> bytes:
        async with self._request(cmd, payload, timeout=timeout):
            deadline = asyncio.get_running_loop().time() + timeout
            while True:
                source, packet = await self._next(deadline)
                if source == "cmd":
                    reply_cmd, data = P.parse(packet)
                    if reply_cmd == cmd:
                        return data

    async def serial(self) -> str:
        return P.text(await self.command(P.GET_SERIAL))

    async def bound(self) -> bool:
        return any(await self.command(P.GET_BIND_INFO))

    async def device_info(self) -> dict:
        return P.parse_device_info(await self.command(P.GET_DEVICE_INFO))

    async def file_list(self, timeout: float = 20.0) -> list[P.FileEntry]:
        async with self._request(P.GET_FILE_LIST, timeout=timeout):
            entries: list[P.FileEntry] = []
            names: set[str] = set()
            deadline = asyncio.get_running_loop().time() + timeout
            while True:
                source, packet = await self._next(deadline)
                if source != "cmd":
                    continue
                cmd, data = P.parse(packet)
                if cmd != P.GET_FILE_LIST:
                    continue
                if not data:
                    raise ValueError("Empty GET_FILE_LIST reply")
                status = data[0]
                if status == 2 and len(data) == 1:
                    return entries
                if status == 1:
                    raise RuntimeError("Device returned GET_FILE_LIST failure")
                if status != 0 or len(data) != 20:
                    raise ValueError(f"Malformed GET_FILE_LIST reply: {data.hex()}")
                entry = P.parse_file_entry(data)
                validate_filename(entry.name)
                if entry.name in names:
                    raise ValueError(f"Duplicate recording in file list: {entry.name}")
                names.add(entry.name)
                entries.append(entry)

    async def download(
        self, name: str, sink: Callable[[bytes], int | None], timeout: float = 15.0, *, offset: int = 0
    ) -> int:
        """Require full-size declaration, exact suffix bytes and explicit terminator.

        Timeout measures inactivity of this transfer. Unrelated command traffic
        cannot keep an incomplete download alive. Offline bytes have no file ID,
        so they are accepted only after this request's declaration.
        """
        recording_output_name(name, offset)
        payload = validate_filename(name).ljust(14, b"\0") + struct.pack(">I", offset)
        async with self._request(P.GET_FILE_DATA, payload, timeout=timeout):
            received = 0
            declared: int | None = None
            deadline = asyncio.get_running_loop().time() + timeout
            try:
                while True:
                    source, packet = await self._next(deadline)
                    if source == "off":
                        if declared is None:
                            raise ValueError("Recording data arrived before its size declaration")
                        if not packet:
                            continue
                        if received + len(packet) > declared - offset:
                            raise ValueError(f"Download exceeds declared remaining size {declared - offset}")
                        written = sink(packet)
                        if written is not None and written != len(packet):
                            raise OSError("Recording output accepted a partial write")
                        received += len(packet)
                        deadline = asyncio.get_running_loop().time() + timeout
                        continue
                    cmd, data = P.parse(packet)
                    if cmd != P.GET_FILE_DATA:
                        continue
                    if not data:
                        raise ValueError("Empty GET_FILE_DATA reply")
                    match data[0]:
                        case 0:
                            if len(data) != 5 or declared is not None:
                                raise ValueError("Malformed or duplicate recording size declaration")
                            (declared,) = struct.unpack_from(">I", data, 1)
                            if offset > declared:
                                raise ValueError(f"Recording offset {offset} exceeds file size {declared}")
                            deadline = asyncio.get_running_loop().time() + timeout
                        case 1:
                            raise RuntimeError(f"Device reports recording download failure: {name}")
                        case 2:
                            if len(data) != 1 or declared is None:
                                raise ValueError("Recording ended without a valid size declaration")
                            if received != declared - offset:
                                raise RuntimeError(f"Short download: {received}/{declared - offset} bytes")
                            return received
                        case _:
                            raise ValueError(f"Unknown GET_FILE_DATA status: {data[0]}")
            except asyncio.CancelledError as error:
                self._discard_offline = True
                stop_result = {
                    "request_attempted": False,
                    "request_sent": False,
                    "response_received": False,
                    "error": None,
                    "worker_exit_verified": False,
                }
                # Worker startup clears the stop flag. Before the first data,
                # disconnect instead of claiming an effective device cancel.
                if received:
                    stop_result = await self._stop_cancelled_download()
                raise DownloadCancelled(
                    name=name,
                    offset=offset,
                    received=received,
                    declared_size=declared,
                    stop_result=stop_result,
                ) from error

    async def _stop_cancelled_download(self) -> dict:
        """One best-effort explicit stop, while still owning the download transaction."""
        result = {
            "request_attempted": True,
            "request_sent": False,
            "response_received": False,
            "error": None,
            "worker_exit_verified": False,
        }
        try:
            deadline = asyncio.get_running_loop().time() + CANCEL_TIMEOUT
            async with asyncio.timeout(CANCEL_TIMEOUT):
                await self._write(P.STOP_GET_FILE)
                result["request_sent"] = True
                while True:
                    source, packet = await self._next(deadline)
                    if source != "cmd":
                        continue
                    cmd, data = P.parse(packet)
                    if cmd != P.STOP_GET_FILE:
                        continue
                    if data != b"\0":
                        raise ValueError(f"Malformed STOP_GET_FILE reply: {data.hex()}")
                    result["response_received"] = True
                    break
        except asyncio.CancelledError:
            result["error"] = "Stop cleanup interrupted by another cancellation"
        except Exception as error:  # noqa: BLE001 - cancellation remains the primary outcome
            result["error"] = f"{type(error).__name__}: {error}"
        return result
