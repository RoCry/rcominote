"""Bounded resumable NOR collection, derived exclusively from retained source windows."""

import os
import tempfile
from pathlib import Path

from . import nor_windows
from .nor_batch_cli import capture_sector
from .output import emit
from .printk_tail import NorTarget, block_offset


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


def verified_block(directory: Path, block: int, target: NorTarget = NorTarget.record_dsp) -> bytes | None:
    """Revalidate source evidence even on resume; never trust cached success flags."""
    paths = sorted(directory.glob("attempt-*/window-*.json"))
    if not paths:
        return None
    report = nor_windows.analyze(paths)
    if report["target"] != target.value or report["offset"] != block_offset(target, block):
        raise ValueError(f"Wrong evidence target/offset for {target.value} block {block}")
    if report["conflicts"]:
        raise ValueError(f"Conflicting {target.value} block {block}: {report['conflicts']}")
    if not report["complete"]:
        return None
    raw = bytes.fromhex(report["sector_hex"])
    if (cached := directory / "sector.bin").exists() and cached.read_bytes() != raw:
        raise ValueError(f"Cached {target.value} block {block} differs from its evidence")
    return raw


async def collect(
    out: Path,
    *,
    target: NorTarget,
    total_blocks: int,
    serial: str,
    max_new_blocks: int,
    attempts: int,
) -> list[bytes]:
    """Read only an allowed target extent; resume after rechecking every source window."""
    target = NorTarget(target)
    if type(total_blocks) is not int or total_blocks < 1:
        raise ValueError("total-blocks must be a positive integer")
    block_offset(target, total_blocks - 1)
    if type(max_new_blocks) is not int or not 1 <= max_new_blocks <= total_blocks:
        raise ValueError(f"max-new-blocks must be1..{total_blocks}")
    if type(attempts) is not int or not 1 <= attempts <= 5:
        raise ValueError("attempts must be1..5")
    out.mkdir(parents=True, exist_ok=True)
    blocks = []
    new_blocks = 0
    for index in range(total_blocks):
        directory = out / f"block-{index:03}"
        raw = verified_block(directory, index, target)
        if raw is None:
            if new_blocks == max_new_blocks:
                break
            directory.mkdir(exist_ok=True)
            for _ in range(attempts):
                number = 0
                while (destination := directory / f"attempt-{number:03}").exists():
                    number += 1
                await capture_sector(destination, target, serial, index)
                if (raw := verified_block(directory, index, target)) is not None:
                    break
            if raw is None:
                raise RuntimeError(
                    f"{target.value} block {index} incomplete after {attempts} attempts; evidence retained"
                )
            if not (directory / "sector.bin").exists():
                publish(directory / "sector.bin", raw)
            new_blocks += 1
        blocks.append(raw)
        emit({"block": index, "verified_blocks": len(blocks), "total_blocks": total_blocks})
    return blocks
