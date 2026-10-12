"""Resumable read-only export of the actual SDFS recording DSP file."""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Annotated

import typer

from .ble_target import OWNED_SERIAL
from .dsp_sections import inspect_image
from .nor_export import collect, publish
from .output import emit
from .printk_tail import RECORD_DSP_BYTES, NorTarget
from .sdfs_checksum import checksum32

BLOCKS = (RECORD_DSP_BYTES + 511) // 512


async def export(out: Path, *, serial: str, max_new_blocks: int, attempts: int) -> dict:
    blocks = await collect(
        out,
        target=NorTarget.record_dsp,
        total_blocks=BLOCKS,
        serial=serial,
        max_new_blocks=max_new_blocks,
        attempts=attempts,
    )
    report = {
        "file": "aerecord.dsp",
        "file_bytes": RECORD_DSP_BYTES,
        "verified_blocks": len(blocks),
        "total_blocks": BLOCKS,
        "complete": len(blocks) == BLOCKS,
        "scope": "Raw file readback; no flash write, boot or recovery proof",
    }
    if report["complete"]:
        raw = b"".join(blocks)[:RECORD_DSP_BYTES]
        report["image"] = inspect_image(raw)
        checksum = checksum32(raw)
        if checksum != 0x96D685BB:
            raise ValueError(f"Recording DSP checksum differs from captured SDFS directory: {checksum:#x}")
        report["sdfs_checksum"] = hex(checksum)
        report["sha256"] = hashlib.sha256(raw).hexdigest()
        output = out / "aerecord.dsp"
        if output.exists():
            if output.read_bytes() != raw:
                raise ValueError("Existing DSP output differs from verified evidence")
        else:
            publish(output, raw)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main(
    out: Annotated[Path, typer.Option()],
    serial: str = OWNED_SERIAL,
    max_new_blocks: int = BLOCKS,
    attempts: int = 3,
):
    """Resume bounded recording DSP reads, rechecking retained source evidence."""
    emit(asyncio.run(export(out, serial=serial, max_new_blocks=max_new_blocks, attempts=attempts)))
