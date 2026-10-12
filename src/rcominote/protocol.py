"""CoMi Note (Boyi branch) wire format, from the official app's JS (CoMi 1.1.2)."""

import struct
from dataclasses import dataclass

SERVICE = "0000e5e0-0000-1000-8000-00805f9b34fb"
WRITE = "0000e5e1-0000-1000-8000-00805f9b34fb"
NOTIFY_CMD = "0000e5e2-0000-1000-8000-00805f9b34fb"
NOTIFY_REALTIME = "0000e5e3-0000-1000-8000-00805f9b34fb"
NOTIFY_OFFLINE = "0000e5e4-0000-1000-8000-00805f9b34fb"
COMPANY_ID = 14172
HEAD = 0xD22D
VERSION = 1

GET_SERIAL = 1
GET_BIND_INFO = 2
BIND = 3
SET_TIME = 4
GET_DEVICE_INFO = 5
START_RECORDING = 6
STOP_RECORDING = 7
PAUSE_RECORDING = 8
RESUME_RECORDING = 9
GET_FILE_LIST = 10
GET_FILE_DATA = 11
STOP_GET_FILE = 12
DELETE_FILE = 13
DEVICE_STATUS_CHANGE = 15
GET_RECORDING_INFO = 21
VOICE_CONTROL_CHANGE = 25


def crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def frame(cmd: int, payload: bytes = b"") -> bytes:
    if len(payload) > 255:
        raise ValueError("Boyi payload is limited to 255 bytes")
    body = struct.pack(">HBBB", HEAD, VERSION, cmd, len(payload)) + payload
    return body + struct.pack("<H", crc16(body))


def parse(packet: bytes) -> tuple[int, bytes]:
    if len(packet) < 7:
        raise ValueError(f"Short Boyi frame: {packet.hex()}")
    head, version, cmd, length = struct.unpack_from(">HBBB", packet)
    if head != HEAD or version != VERSION:
        raise ValueError(f"Not a Boyi v1 frame: {packet.hex()}")
    if len(packet) != 5 + length + 2:
        raise ValueError(f"Boyi length {length} disagrees with frame: {packet.hex()}")
    (crc,) = struct.unpack_from("<H", packet, 5 + length)
    if crc != crc16(packet[: 5 + length]):
        raise ValueError(f"Boyi CRC mismatch: {packet.hex()}")
    return cmd, packet[5 : 5 + length]


def text(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii")


@dataclass(slots=True, frozen=True)
class FileEntry:
    name: str
    size: int
    kind: str  # "call" (byte 0) or "note"


def parse_file_entry(payload: bytes) -> FileEntry:
    if len(payload) < 20 or payload[0] != 0:
        raise ValueError(f"Bad file entry: {payload.hex()}")
    (size,) = struct.unpack_from(">I", payload, 15)
    return FileEntry(name=text(payload[1:15]), size=size, kind="call" if payload[19] == 0 else "note")


def parse_device_info(payload: bytes) -> dict:
    if len(payload) < 44:
        raise ValueError(f"Device info is {len(payload)} bytes, app expects >= 44: {payload.hex()}")
    total, free = struct.unpack_from(">II", payload)

    def tri(byte: int) -> bool | None:
        return None if byte == 255 else byte == 1

    return {
        "total_capacity": total,
        "free_capacity": free,
        "charging": payload[8] != 0,
        "battery": payload[9],
        "recording_state": {0: "idle", 1: "recording"}.get(payload[10], "paused"),
        "version": payload[11:14].hex(),
        "usb_mode": payload[14] == 1,
        "mode": "call" if payload[15] == 1 else "memo",
        "indicator_light": tri(payload[16]),
        "noise_reduction": payload[39],
        "voice_control": tri(payload[40]),
        "segment_duration": payload[41],
        "screen_backlight": tri(payload[42]),
        "raw": payload.hex(),
    }


def parse_event(cmd: int, payload: bytes) -> dict:
    """Official CoMi 1.1.2 Y8/Z8 layouts; retain uninterpreted bytes as raw."""
    match cmd:
        case 15:
            if len(payload) < 20:
                raise ValueError(f"Device-status event needs >=20 bytes: {payload.hex()}")

            def tri(value: int) -> bool | None:
                return None if value == 255 else value == 1

            fields = {
                "event": "device_status",
                "charging": payload[0] != 0,
                "battery": payload[1],
                "usb_mode": payload[2] == 1,
                "mode": "call" if payload[3] == 1 else "memo",
                "power_off_duration": payload[4],
                "noise_reduction": payload[5],
                "voice_control": tri(payload[6]),
                "indicator_light": tri(payload[7]),
                "segment_duration": payload[8],
                "screen_backlight": tri(payload[9]),
                "usb_connected": payload[10] == 1,
            }
        case 25:
            if len(payload) < 5:
                raise ValueError(f"Voice-control event needs >=5 bytes: {payload.hex()}")
            fields = {
                "event": "voice_control",
                "enabled": payload[0] == 1,
                "file_size": struct.unpack_from(">I", payload, 1)[0],
            }
        case _:
            raise ValueError(f"Not a known unsolicited event opcode: {cmd:#x}")
    return fields | {"opcode": cmd, "raw": payload.hex()}
