"""Explicit diagnostic profiles, separate from recorder controls."""

import asyncio
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from . import code_references, code_sample, log_capture, log_probe
from .ble_target import OWNED_SERIAL
from .output import emit, new_output

app = typer.Typer(no_args_is_help=True)


class Profile(StrEnum):
    logs = "logs"
    version = "version"
    commands = "commands"
    platform = "platform"
    kernel = "kernel"
    threads = "threads"
    stacks = "stacks"
    code = "code"
    code_literals = "code-literals"
    code_references = "code-references"
    vendor_code = "vendor-code"
    vendor_handler = "vendor-handler"
    device_info_code = "device-info-code"
    storage_code = "storage-code"
    disk_code = "disk-code"
    card_code = "card-code"
    nor_header = "nor-header"


PROFILE_FLAGS = {
    "version": "device_info",
    "commands": "commands",
    "platform": "platform_info",
    "kernel": "kernel_info",
    "threads": "threads",
    "stacks": "stacks",
    "code": "code_sample",
    "code-literals": "code_literals",
    "code-references": "code_references",
    "vendor-code": "vendor_code",
    "vendor-handler": "vendor_handler",
    "device-info-code": "device_info_code",
    "storage-code": "storage_code",
    "disk-code": "disk_code",
    "card-code": "card_code",
    "nor-header": "flash_header",
}


async def capture_profile(profile: Profile, serial: str, duration: float) -> dict:
    flags = {PROFILE_FLAGS[profile.value]: True} if profile.value in PROFILE_FLAGS else {}
    return await log_capture.capture(serial=serial, duration=duration, **flags)


@app.command("capture")
def capture(
    profile: Profile,
    out: Annotated[Path, typer.Option()],
    serial: str = OWNED_SERIAL,
    duration: Annotated[float, typer.Option(min=1, max=30)] = 5,
):
    """Capture fixed diagnostics; code profiles validate exact bytes, nor-header may lack data."""
    new_output(out)
    result = asyncio.run(capture_profile(profile, serial, duration))
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as handle:
        handle.write(encoded)
    emit(
        {key: value for key, value in result.items() if key not in {"frames", "notifications"}}
        | {"path": str(out)}
    )
    if not result["ok"]:
        raise typer.Exit(1)


@app.command("text")
def text(capture: Path):
    """Print already captured diagnostic text offline; never connects."""
    value = json.loads(capture.read_text())
    print("".join(frame.get("text", "") for frame in value["frames"]), end="")


app.command("probe")(log_probe.main)
app.command("compare-code")(code_sample.main)
app.command("compare-references")(code_references.main)
