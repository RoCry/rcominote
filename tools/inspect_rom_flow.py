#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Decode only verified actual ROM condition/save/restore functions offline."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

SHA = "0dda0a4532813627df78b506bfa1f7e5dc8ae4b9886cc32173265592defcaa67"
BASE = 0x1900


def main(image: Path):
    data = image.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA:
        raise ValueError("Requires exact repeated actual ROM336-byte capture")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    regions = []
    for name, start, end in (
        ("exit condition", 0x1908, 0x1930),
        ("entry state save", 0x1934, 0x196E),
        ("restore and return", 0x1980, 0x19B4),
    ):
        raw = data[start - BASE : end - BASE]
        insns = list(decoder.disasm(raw, start))
        if sum(i.size for i in insns) != len(raw):
            raise ValueError(f"Incomplete decode at {start:x}")
        regions.append(
            {
                "name": name,
                "start": hex(start),
                "end_exclusive": hex(end),
                "hex": raw.hex(),
                "instructions": [{"at": hex(i.address), "asm": f"{i.mnemonic} {i.op_str}"} for i in insns],
            }
        )
    literals = {
        hex(a): hex(struct.unpack_from("<I", data, a - BASE)[0])
        for a in (0x1930, 0x1970, 0x1974, 0x1978, 0x197C, 0x19B4, 0x19B8, 0x19BC)
    }
    print(
        json.dumps(
            {
                "scope": "actual readback, offline analysis; no mode entry or exit execution",
                "sha256": SHA,
                "base": hex(BASE),
                "regions": regions,
                "literals": literals,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
