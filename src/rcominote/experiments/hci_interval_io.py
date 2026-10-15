"""Narrow hci0 capture and one explicit per-connection update; no global settings."""

import asyncio
import ctypes
import getpass
import os
import signal
import struct
import subprocess
import sys
from pathlib import Path

from rcominote.experiments import hci_interval as H
from rcominote.linux_client import LinuxClient


def authorize(*, password_stdin: bool) -> None:
    if not password_stdin:
        cached = subprocess.run(["sudo", "-n", "-v"], capture_output=True, timeout=5, check=False)
        if cached.returncode == 0:
            return
    password = (
        sys.stdin.readline(1025).removesuffix("\n") if password_stdin else getpass.getpass("sudo password: ")
    )
    if not password or len(password) > 1024 or "\n" in password or "\r" in password:
        raise ValueError("Expected one nonempty password line")
    try:
        result = subprocess.run(
            ["sudo", "-S", "-p", "", "-v"],
            input=(password + "\n").encode(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        if result.returncode:
            raise PermissionError("sudo credential validation failed")
    finally:
        password = None


def socket_address(fd: int, *, peer: bool) -> str:
    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.getpeername if peer else libc.getsockname
    function.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    function.restype = ctypes.c_int
    address = ctypes.create_string_buffer(14)
    length = ctypes.c_uint(14)
    if function(fd, address, ctypes.byref(length)) != 0:
        raise OSError(ctypes.get_errno(), "Cannot verify active ATT socket address")
    family, psm, raw, cid, kind = struct.unpack("<HH6sHBx", address.raw)
    if length.value != 14 or (family, psm, cid, kind) != (31, 0, 4, 1):
        raise ValueError("Requires Linux public LE fixed ATT socket")
    return H.mac(raw)


def active_link(conn) -> dict:
    # ABI from local Linux6.14 bluetooth.h/l2cap.h: SOL_L2CAP6/CONNINFO2,
    # struct {u16 hci_handle; u8 dev_class[3]; padding}; little endian Linux only.
    if sys.platform != "linux" or sys.byteorder != "little" or not isinstance(conn.client, LinuxClient):
        raise ValueError("Requires existing direct LinuxClient")
    conn._check_failure()
    link = conn.client._link
    link._check()
    sock = link._socket
    fd = sock.fileno()
    peer = socket_address(fd, peer=True)
    local = socket_address(fd, peer=False)
    raw = sock.getsockopt(6, 2, 6)
    if len(raw) != 6:
        raise ValueError("Unexpected L2CAP_CONNINFO ABI")
    handle = struct.unpack_from("<H", raw)[0]
    if peer != H.PEER or link.address.upper() != H.PEER or not 0 <= handle < 0x0F00:
        raise ValueError("Active socket is not fixed owned peer/valid HCI handle")
    return {"handle": handle, "local": local, "peer": peer, "controller": "hci0"}


class Monitor:
    def __init__(self, out: Path, *, snoop=None, seconds: int = 55):
        if type(seconds) is not int or seconds not in (55, 70):
            raise ValueError("Monitor deadline must be fixed55 or70 seconds")
        self.seconds = seconds
        self.path = out / "session.btsnoop"
        self.errors = out / "btmon.stderr"
        self.snoop = H.Snoop() if snoop is None else snoop
        self.offset = 0
        self.process = None
        self.error_file = None
        self.stop = {"signal": "SIGINT", "requested": False, "delivery": "not-running"}

    def poll(self, *, final: bool = False) -> list[dict]:
        if self.path.exists():
            size = self.path.stat().st_size
            if size < self.offset or size > H.LIMIT:
                raise ValueError("HCI capture changed/truncated or exceeded bound")
            with self.path.open("rb") as handle:
                handle.seek(self.offset)
                raw = handle.read(H.LIMIT + 1 - self.offset)
            self.offset += len(raw)
            self.snoop.feed(raw, final=final)
        elif final:
            raise ValueError("Missing HCI capture")
        return self.snoop.events

    async def start(self) -> None:
        # BlueZ btsnoop_create uses O_WRONLY|O_CREAT|O_TRUNC. Precreate only
        # this new empty artifact so privileged btmon preserves user ownership.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        self.error_file = self.errors.open("xb")
        self.process = await asyncio.create_subprocess_exec(
            "sudo",
            "-n",
            "timeout",
            "--signal=INT",
            "--kill-after=2s",
            f"{self.seconds}s",
            "btmon",
            "-i",
            "0",
            "-w",
            str(self.path.resolve()),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=self.error_file,
        )
        async with asyncio.timeout(3):
            while not any(e["kind"] == "controller" for e in self.poll()):
                if self.process.returncode is not None:
                    raise RuntimeError("Bounded btmon exited before controller capture was ready")
                await asyncio.sleep(0.05)

    async def close(self) -> int | None:
        # Signal only our held sudo child. sudo(8) forwards user-sent SIGINT;
        # kill(2) permits the caller's UID matching sudo's real UID. Original
        # timeout still bounds cleanup if delivery/forwarding fails.
        try:
            if self.process is not None:
                if self.process.returncode is None:
                    try:
                        self.process.send_signal(signal.SIGINT)
                        self.stop.update(requested=True, delivery="sent")
                    except ProcessLookupError:
                        self.stop["delivery"] = "exited-race"
                    except PermissionError:
                        self.stop["delivery"] = "permission-denied-timeout-fallback"
                else:
                    self.stop["delivery"] = "already-exited"
                await self.process.wait()
                self.poll(final=True)
                allowed = (0, 124, 137, 130) if self.stop["requested"] else (0, 124, 137)
                if self.process.returncode not in allowed:
                    raise RuntimeError(f"Bounded btmon failed: exit {self.process.returncode}")
                return self.process.returncode
        finally:
            if self.error_file is not None:
                self.error_file.close()
        return None


async def request_once(handle: int, timeout: int) -> None:
    if (
        type(handle) is not int
        or not 0 <= handle < 0x0F00
        or type(timeout) is not int
        or not 10 <= timeout <= 3200
    ):
        raise ValueError("Invalid bounded HCI handle/current supervision timeout")
    process = await asyncio.create_subprocess_exec(
        "sudo",
        "-n",
        "timeout",
        "--kill-after=1s",
        "6s",
        "hcitool",
        "-i",
        "hci0",
        "lecup",
        f"--handle={handle}",
        "--min=6",
        "--max=6",
        "--latency=0",
        f"--timeout={timeout}",
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        result = await process.wait()
    finally:
        # Cancellation must still reap this bounded root child.
        if process.returncode is None:
            await process.wait()
    if result:
        raise RuntimeError(f"Single per-link hcitool update failed: exit {result}")
