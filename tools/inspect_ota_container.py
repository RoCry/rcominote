#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""SHA-bound actual OTA container gates; offline, no device traffic."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_MEM, ARM_REG_PC

BASE = 0x10000000
SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
REGIONS = (
    ("application initialization flags", 0x10004B2E, 0x10004B54),
    ("initializer state reset and version bit", 0x100669F8, 0x10066A3C),
    ("initializer recovery flag copies", 0x10066A68, 0x10066A98),
    ("directory lookup", 0x10066B20, 0x10066B98),
    ("file or image length", 0x10066BA8, 0x10066BFC),
    ("file or image offset", 0x10066C0C, 0x10066C5C),
    ("buffer file CRC check", 0x10066DC4, 0x10066E28),
    ("body CRC check including streamed calculation", 0x10066E3C, 0x10066EF6),
    ("complete image header check", 0x10066F1C, 0x10066FC8),
    ("complete image open", 0x10066FFC, 0x100670E8),
    ("upgrade header and conditional body checks", 0x10066398, 0x10066410),
    ("manifest prefix and CRC check", 0x10067700, 0x10067768),
    ("manifest file lengths", 0x1006777C, 0x100677D4),
    ("manifest read and checks", 0x100677E0, 0x100678E6),
    ("read wrapper through backend", 0x100B155C, 0x100B157A),
    ("CRC32 implementation", 0x1002DB10, 0x1002DB48),
)


def main(image_path: Path) -> None:
    data = image_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact verified FW010004 mapped image")

    def chunk(start: int, end: int) -> bytes:
        if not BASE <= start < end <= BASE + len(data):
            raise RuntimeError("Region outside verified image")
        return data[start - BASE : end - BASE]

    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    decoder.detail = True
    regions = []
    for name, start, end in REGIONS:
        raw = chunk(start, end)
        instructions = list(decoder.disasm(raw, start))
        if sum(instruction.size for instruction in instructions) != len(raw):
            raise RuntimeError(f"Incomplete decoding at {start:#x}")
        literals = []
        for instruction in instructions:
            for operand in instruction.operands:
                if (
                    instruction.mnemonic in ("ldr", "ldr.w")
                    and operand.type == ARM_OP_MEM
                    and operand.mem.base == ARM_REG_PC
                ):
                    address = ((instruction.address + 4) & ~3) + operand.mem.disp
                    value = struct.unpack("<I", chunk(address, address + 4))[0]
                    literal = {"at": hex(instruction.address), "address": hex(address), "value": hex(value)}
                    if BASE <= value < BASE + len(data):
                        text = data[value - BASE : value - BASE + 120].split(b"\0")[0]
                        if text and all(32 <= byte < 127 or byte in (10, 13) for byte in text):
                            literal["ascii"] = text.decode("ascii")
                    literals.append(literal)
        regions.append(
            {
                "name": name,
                "start": hex(start),
                "end_exclusive": hex(end),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "instructions": [
                    {"at": hex(i.address), "bytes": i.bytes.hex(), "asm": f"{i.mnemonic} {i.op_str}"}
                    for i in instructions
                ],
                "literals": literals,
            }
        )
    print(
        json.dumps(
            {
                "sha256": SHA,
                "size": len(data),
                "scope": "actual container and manifest prechecks; no live package acceptance or storage write audit",
                "regions": regions,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    typer.run(main)
