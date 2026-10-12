#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Reproduce the bounded recovery handoff evidence offline; never execute firmware."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

VERIFIED_SHA = "19625b7b70eb8e4a91c889792c0ca383f51ea205629e67565b59c47d15e09906"
IMAGE_SOURCE = 0xE098
RAM_BASE = 0x18000000
# Runtime code boundaries and separately identified literal pools.
MODULES = (
    ("unmap", 0xB8, 0xC8, 0xC8, 0xCC),
    ("sum32", 0xE8, 0x100, 0, 0),
    ("image_check", 0x100, 0x20C, 0x20C, 0x218),
    ("jump", 0x218, 0x21E, 0, 0),
    ("map", 0x21E, 0x22E, 0x230, 0x234),
    ("handoff", 0x450, 0x4B0, 0x4B0, 0x4C0),
)


def main(image: Path):
    data = image.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != 63288 or digest != VERIFIED_SHA:
        raise ValueError("Requires the exact complete checksum-verified decoded CoMi recovery")
    header_size = struct.unpack_from("<H", data, 0x24)[0]
    body_size, stored = struct.unpack_from("<II", data, 0x18)
    header_sum = sum(word for (word,) in struct.iter_unpack("<I", data[:header_size])) & 0xFFFFFFFF
    body_sum = sum(word for (word,) in struct.iter_unpack("<I", data[header_size:])) & 0xFFFFFFFF
    if (
        header_size != 512
        or body_size != len(data) - 512
        or header_sum != 0xFFFFFFFF
        or (body_sum + stored) & 0xFFFFFFFF != 0xFFFFFFFF
    ):
        raise ValueError("Complete recovery header/body checksum differs")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    modules = []
    for name, start, end, literal_start, literal_end in MODULES:
        raw = data[IMAGE_SOURCE + start : IMAGE_SOURCE + end]
        instructions = [
            {
                "runtime_address": hex(instruction.address),
                "image_address": hex(0x11000000 + IMAGE_SOURCE + instruction.address - RAM_BASE),
                "bytes": instruction.bytes.hex(),
                "instruction": f"{instruction.mnemonic} {instruction.op_str}",
            }
            for instruction in decoder.disasm(raw, RAM_BASE + start)
        ]
        if sum(len(bytes.fromhex(item["bytes"])) for item in instructions) != len(raw):
            raise ValueError(f"Incomplete instruction decoding in {name}")
        literals = data[IMAGE_SOURCE + literal_start : IMAGE_SOURCE + literal_end] if literal_start else b""
        modules.append(
            {
                "name": name,
                "runtime_start": hex(RAM_BASE + start),
                "runtime_end_exclusive": hex(RAM_BASE + end),
                "image_start": hex(0x11000000 + IMAGE_SOURCE + start),
                "bytes": raw.hex(),
                "instructions": instructions,
                "literals": {
                    "runtime_start": hex(RAM_BASE + literal_start) if literals else None,
                    "bytes": literals.hex(),
                    "words": [hex(word) for (word,) in struct.iter_unpack("<I", literals)],
                },
            }
        )
    print(
        json.dumps(
            {
                "decoded_sha256": digest,
                "image_bytes": len(data),
                "header_checksum_valid": True,
                "body_checksum_valid": True,
                "relocation_basis": "Startup copy-shaped arguments: image1100e098 to RAM18000000; static interpretation, not observed execution",
                "scope": "Complete selected handoff/check/sum/map/unmap/jump interfaces; preparation, cache invalidation and earlier authorization not expanded",
                "modules": modules,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
