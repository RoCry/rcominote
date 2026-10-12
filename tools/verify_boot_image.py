#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer>=0.16,<1"]
# ///
"""Verify the captured boot partition offline; never writes or executes firmware."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from verify_raw_codec import transform


def main(raw_path: Path):
    raw = raw_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != "782c26c3ba9bee07a8b0b464898fb963a76eb35a2916586b854f8f45993f4166":
        raise ValueError("Input differs from captured4096-byte boot partition")
    candidates = {}
    for size in (32, 64, 128, 256, 512, 1024, 2048, 4096):
        data = transform(raw, 0x0A15A191, decrypt=True, block_bytes=size)
        candidates[str(size)] = hex((sum(struct.unpack("<904I", data[56:3672])) + 0x1264AA7D) & 0xFFFFFFFF)
    decoded = transform(raw, 0x0A15A191, decrypt=True, block_bytes=512)[:3672]
    if sum(struct.unpack("<14I", decoded[:56])) & 0xFFFFFFFF != 0xFFFFFFFF:
        raise ValueError("Boot header checksum failed")
    if candidates["512"] != "0xffffffff":
        raise ValueError("Boot body checksum failed")
    print(
        json.dumps(
            {
                "candidate_body_checksums": candidates,
                "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
                "header_checksum_valid": True,
                "body_checksum_valid": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
