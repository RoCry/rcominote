"""Fixed recovery image export; raw and decoded output only after image checksums."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from ..ble_target import OWNED_SERIAL
from ..output import emit
from ..printk_tail import RECOVERY_BYTES, NorTarget
from ..recovery_image import verify
from .nor_export import collect, publish

BLOCKS = (RECOVERY_BYTES + 511) // 512


async def export(out: Path, *, serial: str, max_new_blocks: int, attempts: int) -> dict:
    blocks = await collect(
        out,
        target=NorTarget.recovery,
        total_blocks=BLOCKS,
        serial=serial,
        max_new_blocks=max_new_blocks,
        attempts=attempts,
    )
    report = {
        "target": "recovery",
        "image_bytes": RECOVERY_BYTES,
        "verified_blocks": len(blocks),
        "total_blocks": BLOCKS,
        "complete": len(blocks) == BLOCKS,
        "scope": "Readback and offline checksum only; no execution, write or recovery proof",
    }
    if report["complete"]:
        raw = b"".join(blocks)[:RECOVERY_BYTES]
        plain, verification = verify(raw)
        report.update(verification)
        outputs = ((out / "recovery-raw.bin", raw), (out / "recovery-decoded.bin", plain))
        for path, data in outputs:
            if path.exists() and path.read_bytes() != data:
                raise ValueError(f"Existing output differs from verified recovery: {path}")
        for path, data in outputs:
            if not path.exists():
                publish(path, data)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main(
    out: Annotated[Path, typer.Option()],
    serial: str = OWNED_SERIAL,
    max_new_blocks: int = BLOCKS,
    attempts: int = 3,
):
    """Resume reads of the fixed recovery image, publishing only after full validation."""
    emit(asyncio.run(export(out, serial=serial, max_new_blocks=max_new_blocks, attempts=attempts)))
