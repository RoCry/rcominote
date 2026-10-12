"""Fixed recovery image export; raw and decoded output only after image checksums."""

import asyncio
import hashlib
import json
import struct
from pathlib import Path
from typing import Annotated

import typer

from ..ble_target import OWNED_SERIAL
from ..nor_codec import decode
from ..output import emit
from ..printk_tail import RECOVERY_BYTES, NorTarget
from ..sdfs_checksum import checksum32
from .nor_export import collect, publish

BLOCKS = (RECOVERY_BYTES + 511) // 512
HEADER_SHA = "121a4b6beb56293ded54630fb33cfc871cfc64cbfaf23454e7f3e1d7763374b9"


def verify(raw: bytes) -> tuple[bytes, dict]:
    if len(raw) != RECOVERY_BYTES:
        raise ValueError("Recovery image must contain exactly63288 raw bytes")
    plain = decode(raw, block_bytes=32)
    if hashlib.sha256(plain[:512]).hexdigest() != HEADER_SHA:
        raise ValueError("Recovery header differs from independently verified device header")
    body_size, body_checksum = struct.unpack_from("<II", plain, 24)
    if body_size != len(plain) - 512 or checksum32(plain[:512]) != 0xFFFFFFFF:
        raise ValueError("Recovery header size/checksum failed")
    if (checksum32(plain[512:]) + body_checksum) & 0xFFFFFFFF != 0xFFFFFFFF:
        raise ValueError("Recovery body checksum failed; decode profile or readback requires investigation")
    return plain, {
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "decoded_sha256": hashlib.sha256(plain).hexdigest(),
        "header_checksum_valid": True,
        "body_checksum_valid": True,
        "decode_reset_bytes": 32,
    }


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
