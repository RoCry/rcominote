"""Resumable read-only export of the actual SDFS recording DSP file."""

import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from . import nor_windows
from .ble_target import OWNED_SERIAL
from .dsp_header import inspect_header
from .nor_batch_cli import capture_sector
from .output import emit
from .printk_tail import RECORD_DSP_BYTES, NorTarget, block_offset
from .sdfs_checksum import checksum32

BLOCKS = (RECORD_DSP_BYTES + 511) // 512


def publish(path: Path, raw: bytes) -> None:
    """No-replacement atomic publication; interrupted temporary files are not evidence."""
    descriptor, name = tempfile.mkstemp(prefix=".part-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def verified_block(directory: Path, block: int) -> bytes | None:
    """Revalidate source evidence even on resume; never trust cached success flags."""
    paths = sorted(directory.glob("attempt-*/window-*.json"))
    if not paths:
        return None
    report = nor_windows.analyze(paths)
    if report["target"] != "record-dsp" or report["offset"] != block_offset(NorTarget.record_dsp, block):
        raise ValueError(f"Wrong evidence target/offset for DSP block {block}")
    if report["conflicts"]:
        raise ValueError(f"Conflicting DSP block {block}: {report['conflicts']}")
    if not report["complete"]:
        return None
    raw = bytes.fromhex(report["sector_hex"])
    if (cached := directory / "sector.bin").exists() and cached.read_bytes() != raw:
        raise ValueError(f"Cached DSP block {block} differs from its evidence")
    return raw


async def export(out: Path, *, serial: str, max_new_blocks: int, attempts: int) -> dict:
    if type(max_new_blocks) is not int or not 1 <= max_new_blocks <= BLOCKS:
        raise ValueError(f"max-new-blocks must be1..{BLOCKS}")
    if type(attempts) is not int or not 1 <= attempts <= 5:
        raise ValueError("attempts must be1..5")
    out.mkdir(parents=True, exist_ok=True)
    blocks = []
    new_blocks = 0
    for index in range(BLOCKS):
        directory = out / f"block-{index:03}"
        raw = verified_block(directory, index)
        if raw is None:
            if new_blocks == max_new_blocks:
                break
            directory.mkdir(exist_ok=True)
            for _ in range(attempts):
                number = 0
                while (destination := directory / f"attempt-{number:03}").exists():
                    number += 1
                await capture_sector(destination, NorTarget.record_dsp, serial, index)
                if (raw := verified_block(directory, index)) is not None:
                    break
            if raw is None:
                raise RuntimeError(
                    f"DSP block {index} incomplete after {attempts} attempts; evidence retained"
                )
            if not (directory / "sector.bin").exists():
                publish(directory / "sector.bin", raw)
            new_blocks += 1
        blocks.append(raw)
        emit({"block": index, "verified_blocks": len(blocks), "total_blocks": BLOCKS})
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
        report["header"] = inspect_header(raw[:540], file_size=len(raw))
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
