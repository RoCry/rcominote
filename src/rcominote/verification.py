"""Reproducible read-only hardware verification with retained intermediate evidence."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from bleak.exc import BleakError

from . import code_sample, gatt
from .ble_target import OWNED_SERIAL, find_device
from .connection import Connection
from .device_commands import read_info
from .diagnostics import Profile, capture_profile
from .output import emit


async def verify_device(out: Path, serial: str, code: bool) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "captured_at": datetime.now(UTC).isoformat(),
        "serial": serial,
        "scope": "read-only queries and temporary log sessions; no recording/setter/reboot/flash",
        "steps": [],
        "ok": False,
    }

    def save(name: str, value: dict):
        with (out / f"{name}.json").open("x") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        report["steps"].append({"name": name, "file": f"{name}.json"})

    async def status():
        async with Connection(await find_device(serial=serial, seconds=12)) as conn:
            return await read_info(conn, serial)

    async def capture(name: str, profile: Profile):
        result = await capture_profile(profile, serial, 2)
        save(name, result)
        if not result["ok"]:
            raise RuntimeError(f"{name} log transport did not complete; see retained capture")
        return result

    try:
        before = await status()
        save("info-before", before)
        if before["device"]["recording_state"] != "idle":
            raise ValueError("Verification requires idle device; existing recording left unchanged")
        save("gatt", await gatt.snapshot(serial=serial))
        await capture("platform", Profile.platform)
        if code:
            if before["device"]["version"] != "010004":
                raise ValueError("Code sample currently validated only on FW1.0.4")
            await capture("code-first", Profile.code)
            await capture("code-second", Profile.code)
            analysis = code_sample.inspect_samples(out / "code-first.json", out / "code-second.json")
            save("code-analysis", analysis)
            if analysis["decoded_bytes"] != 16:
                raise ValueError("Code sample did not decode completely")
        after = await status()
        save("info-after", after)
        for field in ("version", "recording_state"):
            if before["device"][field] != after["device"][field]:
                raise ValueError(f"Device {field} changed during verification")
        report["ok"] = True
        report["limits"] = [
            "Diagnostic ok means transport completion, not complete shell output",
            "No complete firmware backup or recovery validation",
            "No new recording tested",
        ]
    except (ValueError, RuntimeError, OSError, BleakError) as error:
        report["error"] = str(error) or type(error).__name__
    with (out / "manifest.json").open("x") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main(
    out: Annotated[Path, typer.Option(help="New evidence directory")],
    serial: str = OWNED_SERIAL,
    code: Annotated[bool, typer.Option(help="Also read/compare two guarded 16-byte code samples")] = False,
):
    """Run info/GATT/platform diagnostics and final status; retain evidence at each step."""
    result = asyncio.run(verify_device(out, serial, code))
    emit(result | {"directory": str(out)})
    if not result["ok"]:
        raise typer.Exit(1)
