"""Boyi BLE transactions and complete, atomic recording export."""

import asyncio
import hashlib
import os
import struct
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bleak import BleakClient

from . import protocol as P


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


class Connection:
    """One session, one transaction at a time; disconnect interrupts waiters."""

    def __init__(self, device):
        self.queue: asyncio.Queue[tuple[str, bytes] | None] = asyncio.Queue()
        self.client = BleakClient(device, timeout=20, disconnected_callback=self._dropped)
        self._transaction = asyncio.Lock()

    def _dropped(self, _client):
        self.queue.put_nowait(None)

    async def __aenter__(self):
        await self.client.__aenter__()
        try:
            if self.client.services.get_service(P.SERVICE) is None:
                raise ValueError("Target does not expose the Boyi control service")
            await self.client.start_notify(
                P.NOTIFY_CMD, lambda _c, d: self.queue.put_nowait(("cmd", bytes(d)))
            )
            await self.client.start_notify(
                P.NOTIFY_OFFLINE, lambda _c, d: self.queue.put_nowait(("off", bytes(d)))
            )
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
        await self.client.write_gatt_char(P.WRITE, P.frame(cmd, payload), response=False)

    async def _next(self, deadline: float) -> tuple[str, bytes]:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("CoMi response deadline exceeded")
        try:
            item = await asyncio.wait_for(self.queue.get(), timeout=remaining)
        except TimeoutError as exc:
            raise TimeoutError("CoMi response deadline exceeded") from exc
        if item is None:
            raise ConnectionError("CoMi disconnected before completing the request")
        return item

    async def command(self, cmd: int, payload: bytes = b"", timeout: float = 5.0) -> bytes:
        async with self._transaction:
            await self._write(cmd, payload)
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
        async with self._transaction:
            await self._write(P.GET_FILE_LIST)
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

    async def download(self, name: str, sink: Callable[[bytes], int | None], timeout: float = 15.0) -> int:
        """Require size declaration, exact bytes and explicit transfer terminator.

        Timeout measures inactivity of this transfer. Unrelated command traffic
        cannot keep an incomplete download alive. Offline bytes have no file ID,
        so they are accepted only after this request's declaration.
        """
        payload = validate_filename(name).ljust(14, b"\0") + struct.pack(">I", 0)
        async with self._transaction:
            await self._write(P.GET_FILE_DATA, payload)
            received = 0
            declared: int | None = None
            deadline = asyncio.get_running_loop().time() + timeout
            while True:
                source, packet = await self._next(deadline)
                if source == "off":
                    if declared is None:
                        raise ValueError("Recording data arrived before its size declaration")
                    if not packet:
                        continue
                    if received + len(packet) > declared:
                        raise ValueError(f"Download exceeds declared size {declared}")
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
                        deadline = asyncio.get_running_loop().time() + timeout
                    case 1:
                        raise RuntimeError(f"Device reports recording download failure: {name}")
                    case 2:
                        if len(data) != 1 or declared is None:
                            raise ValueError("Recording ended without a valid size declaration")
                        if received != declared:
                            raise RuntimeError(f"Short download: {received}/{declared} bytes")
                        return received
                    case _:
                        raise ValueError(f"Unknown GET_FILE_DATA status: {data[0]}")


async def export_recording(conn: Connection, name: str, out: Path, expected_size: int | None = None) -> dict:
    """Publish a verified complete transfer without replacing an existing file.

    SHA-256 identifies downloaded bytes; the device supplies no hash oracle.
    Sync may skip existing same-size files, but must describe that as size-only
    matching, not verified identical content. This helper never skips a file.
    """
    validate_filename(name)
    if expected_size is not None and expected_size < 0:
        raise ValueError("Expected recording size must be nonnegative")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{name}.mp3"
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Recording output already exists: {target}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{name}.", suffix=".part", dir=out)
    part = Path(temporary)
    digest = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "wb") as handle:

            def write(data: bytes) -> int:
                count = handle.write(data)
                digest.update(data[:count])
                return count

            received = await conn.download(name, write)
            if expected_size is not None and received != expected_size:
                raise ValueError(f"File-list size changed: expected {expected_size}, received {received}")
            handle.flush()
            os.fsync(handle.fileno())
        # Both names are on one filesystem. link() atomically fails if another
        # exporter creates target; replace()/rename() could overwrite its work.
        os.link(part, target)
        return {"name": name, "path": str(target), "bytes": received, "sha256": digest.hexdigest()}
    finally:
        part.unlink(missing_ok=True)
