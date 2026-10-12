"""Fixed Boyi setters traced to CoMi 1.1.2; readback, not ACK, establishes result."""

import asyncio
from enum import StrEnum

import typer

from .ble_target import OWNED_SERIAL, find_device
from .connection import Connection
from .device_commands import ScanSeconds, read_info
from .output import emit

app = typer.Typer(no_args_is_help=True)


class Setting(StrEnum):
    usb = "usb"
    indicator = "indicator"
    voice = "voice"
    noise = "noise"
    segment = "segment"
    backlight = "backlight"


# One-byte payload. Domains intentionally narrower than generic JS numeric setters.
SETTINGS = {
    "usb": (0x13, "usb_mode"),
    "indicator": (0x11, "indicator_light"),
    "voice": (0x14, "voice_control"),
    "noise": (0x17, "noise_reduction"),
    "segment": (0x16, "segment_duration"),
    "backlight": (0x1A, "screen_backlight"),
}


def encode_setting(setting: str, value: str) -> tuple[bytes, bool | int]:
    if setting in {"usb", "indicator", "voice", "backlight"}:
        if value not in {"on", "off"}:
            raise ValueError(f"{setting} expects on|off")
        expected = value == "on"
        return bytes([int(expected)]), expected
    if setting == "noise":
        if not value.isascii() or not value.isdecimal() or not 0 <= int(value) <= 16:
            raise ValueError("noise expects integer 0..16")
        return bytes([int(value)]), int(value)
    if setting == "segment":
        durations = {"30m": 0, "1h": 1, "2h": 2, "3h": 3}
        if value not in durations:
            raise ValueError("segment expects 30m|1h|2h|3h (app-derived labels)")
        return bytes([durations[value]]), durations[value]
    raise ValueError(f"Unknown setting: {setting}")


@app.command("show")
def show(serial: str = OWNED_SERIAL, seconds: ScanSeconds = 12):
    """Read all exposed settings; null means unavailable/unknown."""

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            result = await read_info(conn, serial)
        return {
            "serial": result["serial"],
            "settings": {key: result["device"][field] for key, (_, field) in SETTINGS.items()},
        }

    emit(asyncio.run(run()))


@app.command("set")
def set_value(setting: Setting, value: str, serial: str = OWNED_SERIAL, seconds: ScanSeconds = 12):
    """Explicitly change one setting, then require matching device readback."""
    payload, expected = encode_setting(setting.value, value)
    opcode, field = SETTINGS[setting.value]

    async def run():
        async with Connection(await find_device(serial=serial, seconds=seconds)) as conn:
            before = (await read_info(conn, serial))["device"][field]
            if before is None:
                raise ValueError(f"{setting.value} reports unavailable; no setter sent")
            if before == expected:
                return {
                    "setting": setting.value,
                    "value": before,
                    "changed": False,
                    "verification": "already_matches",
                }
            reply = await conn.command(opcode, payload)
            deadline = asyncio.get_running_loop().time() + 3
            while True:
                actual = (await conn.device_info())[field]
                if actual == expected:
                    return {
                        "setting": setting.value,
                        "before": before,
                        "value": actual,
                        "changed": True,
                        "reply_hex": reply.hex(),
                        "verification": "device_readback",
                    }
                if asyncio.get_running_loop().time() >= deadline:
                    raise RuntimeError(
                        f"{setting.value} response {reply.hex()} received but readback {actual!r} != {expected!r}"
                    )
                await asyncio.sleep(0.2)

    emit(asyncio.run(run()))
