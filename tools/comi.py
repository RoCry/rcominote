#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["bleak>=1.1,<2", "typer>=0.16,<1"]
# ///
"""Seeyon CoMi Note research: discovery, status, remote control and recording export.

Speaks the device's own "Boyi" BLE protocol (company id 14172, service e5e0),
reverse-engineered from the official CoMi app (1.1.2). Read and download paths
need no binding; the device answers an unbound client. No bind/delete/format/
reset/unbind command is implemented. Record and set-time are explicit mutations.
Connection targets the selected advertised serial rather than the first Boyi unit."""

import asyncio
import json
import struct
import sys
import time
from pathlib import Path
from typing import Annotated

import typer
from bleak import BleakClient, BleakScanner

sys.path.insert(0, str(Path(__file__).resolve().parent))
import protocol as P  # noqa: E402
from ble_target import OWNED_SERIAL, find_device  # noqa: E402

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
DEFAULT_OUT = Path.home() / ".local/share/comi-research"


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


class Connection:
    """One BLE session. Command replies and offline (file) data arrive on
    separate notify characteristics; we fan both into one queue tagged by
    source so the download loop can interleave them deterministically."""

    def __init__(self, device):
        self.queue: asyncio.Queue[tuple[str, bytes] | None] = asyncio.Queue()
        self.client = BleakClient(device, timeout=20, disconnected_callback=self._dropped)

    def _dropped(self, _client):
        self.queue.put_nowait(None)

    async def __aenter__(self):
        await self.client.__aenter__()
        if self.client.services.get_service(P.SERVICE) is None:
            raise ValueError("Target does not expose the Boyi control service")
        await self.client.start_notify(P.NOTIFY_CMD, lambda _c, d: self.queue.put_nowait(("cmd", bytes(d))))
        await self.client.start_notify(P.NOTIFY_OFFLINE, lambda _c, d: self.queue.put_nowait(("off", bytes(d))))
        return self

    async def __aexit__(self, *exc):
        await self.client.__aexit__(*exc)

    async def _write(self, cmd: int, payload: bytes = b"") -> None:
        await self.client.write_gatt_char(P.WRITE, P.frame(cmd, payload), response=False)

    async def _next(self, deadline: float) -> tuple[str, bytes]:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("CoMi response deadline exceeded")
        item = await asyncio.wait_for(self.queue.get(), timeout=remaining)
        if item is None:
            raise ConnectionError("CoMi disconnected before completing the request")
        return item

    async def command(self, cmd: int, payload: bytes = b"", timeout: float = 5.0) -> bytes:
        """Send one command and return the data of its single matching reply."""
        await self._write(cmd, payload)
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            source, packet = await self._next(deadline)
            if source != "cmd":
                continue
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
        """GET_FILE_LIST streams one reply per file, then a status-2 terminator."""
        await self._write(P.GET_FILE_LIST)
        entries: list[P.FileEntry] = []
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            source, packet = await self._next(deadline)
            if source != "cmd":
                continue
            cmd, data = P.parse(packet)
            if cmd != P.GET_FILE_LIST or not data:
                continue
            status = data[0]
            if status == 2:  # end of list
                return entries
            if status == 1:  # device-reported failure
                raise RuntimeError("Device returned GET_FILE_LIST failure")
            entries.append(P.parse_file_entry(data))

    async def download(self, name: str, sink, timeout: float = 15.0) -> int:
        """GET_FILE_DATA: first cmd reply carries the size, then offline-data
        packets carry the bytes, and a cmd reply with status 2 ends it."""
        payload = name.encode("ascii").ljust(14, b"\0") + struct.pack(">I", 0)
        await self._write(P.GET_FILE_DATA, payload)
        received = 0
        declared: int | None = None
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            source, packet = await self._next(deadline)
            deadline = asyncio.get_running_loop().time() + timeout
            if source == "off":
                sink(packet)
                received += len(packet)
                continue
            cmd, data = P.parse(packet)
            if cmd != P.GET_FILE_DATA or not data:
                continue
            status = data[0]
            if status == 2:
                if declared is not None and received != declared:
                    raise RuntimeError(f"Short download: {received}/{declared} bytes")
                return received
            if status == 1:
                raise RuntimeError(f"Device reports no such file: {name}")
            if status == 0 and len(data) >= 5:
                (declared,) = struct.unpack_from(">I", data, 1)


@app.command()
def scan(seconds: float = 12.0):
    """List nearby CoMi Note units and decode the advertised MAC + serial."""

    async def run():
        found = await BleakScanner.discover(timeout=seconds, return_adv=True)
        out = []
        for device, adv in found.values():
            raw = adv.manufacturer_data.get(P.COMPANY_ID)
            if raw is None:
                continue
            mac = ":".join(f"{b:02X}" for b in raw[:6]) if len(raw) >= 6 else None
            serial = raw[6:16].split(b"\0", 1)[0].decode("ascii", "replace") if len(raw) >= 16 else None
            out.append(
                {"address": device.address, "name": adv.local_name, "rssi": adv.rssi, "mac": mac, "serial": serial}
            )
        emit(out)

    asyncio.run(run())


@app.command()
def info(seconds: float = 12.0, serial: str = OWNED_SERIAL):
    """Serial, bind state, battery, capacity, firmware version and settings."""

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            emit(
                {
                    "serial": await conn.serial(),
                    "bound": await conn.bound(),
                    "device": await conn.device_info(),
                }
            )

    asyncio.run(run())


@app.command()
def files(seconds: float = 12.0, serial: str = OWNED_SERIAL):
    """List the recordings held on the device."""

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            emit([{"name": e.name, "size": e.size, "kind": e.kind} for e in await conn.file_list()])

    asyncio.run(run())


@app.command()
def download(
    name: str,
    out: Annotated[Path, typer.Option()] = DEFAULT_OUT,
    seconds: float = 12.0,
    serial: str = OWNED_SERIAL,
):
    """Export one recording by filename into OUT (bytes are raw as stored, MP3)."""

    async def run():
        out.mkdir(parents=True, exist_ok=True)
        target = out / f"{name}.mp3"
        with target.open("wb") as handle:
            async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
                start = time.time()
                received = await conn.download(name, handle.write)
        emit({"name": name, "bytes": received, "path": str(target), "seconds": round(time.time() - start, 2)})

    asyncio.run(run())


@app.command()
def sync(
    out: Annotated[Path, typer.Option()] = DEFAULT_OUT,
    seconds: float = 12.0,
    serial: str = OWNED_SERIAL,
):
    """Download every recording not already present in OUT."""

    async def run():
        out.mkdir(parents=True, exist_ok=True)
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            entries = await conn.file_list()
            results = []
            for entry in entries:
                target = out / f"{entry.name}.mp3"
                if target.exists() and target.stat().st_size == entry.size:
                    results.append({"name": entry.name, "status": "skip"})
                    continue
                with target.open("wb") as handle:
                    received = await conn.download(entry.name, handle.write)
                results.append({"name": entry.name, "status": "ok", "bytes": received})
        emit(results)

    asyncio.run(run())


@app.command()
def record(
    action: Annotated[str, typer.Argument(help="start | stop | pause | resume")],
    seconds: float = 12.0,
    serial: str = OWNED_SERIAL,
):
    """Remotely drive the recorder (the physical button still works too)."""
    cmd = {
        "start": P.START_RECORDING,
        "stop": P.STOP_RECORDING,
        "pause": P.PAUSE_RECORDING,
        "resume": P.RESUME_RECORDING,
    }.get(action)
    if cmd is None:
        raise typer.BadParameter("action must be start|stop|pause|resume")

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            reply = await conn.command(cmd)
            ok = bool(reply) and reply[0] == 0
            result = {"action": action, "ok": ok, "name": P.text(reply[1:15]) if ok and len(reply) >= 15 else None}
            if action == "stop" and ok and len(reply) >= 21:
                (size,) = struct.unpack_from(">I", reply, 15)
                result |= {"size": size, "need_sync": reply[20] == 1}
            emit(result)

    asyncio.run(run())


@app.command("set-time")
def set_time(seconds: float = 12.0, serial: str = OWNED_SERIAL):
    """Push the host clock to the device (year-2000, month, day, h, m, s)."""

    async def run():
        now = time.localtime()
        payload = bytes((now.tm_year - 2000, now.tm_mon, now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec))
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            reply = await conn.command(P.SET_TIME, payload)
        emit({"set_time": time.strftime("%Y-%m-%d %H:%M:%S", now), "ok": bool(reply) and reply[0] == 0})

    asyncio.run(run())


if __name__ == "__main__":
    app()
