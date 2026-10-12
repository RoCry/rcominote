#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Inspect pinned public helper NOR initialization without executing target code."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_MEM, ARM_REG_PC

BASE = 0x2FF70000
SHA = "470827c527a7111cebeb74e60dd32c007390df34453bce519998963db3ad5953"
REGIONS = (
    ("system storage constructor selection", 0x2424, 0x2458),
    ("complete is selector/init/postinit", 0x48AC, 0x490C),
    ("NOR constructor loads ROM API", 0x3EB4, 0x3ECC),
    ("complete NOR initializer before literal pool", 0x3C08, 0x3D30),
    ("GPIO configuration helper", 0x2FE8, 0x3004),
    ("GPIO output helper before literal pool", 0x3004, 0x3024),
    ("secondary chip select callback", 0x3BAA, 0x3BC4),
    ("delay helper before literal pool", 0x3F50, 0x3F78),
    ("select secondary chip info flags and callback", 0x3BC4, 0x3BE0),
    ("restore primary chip info flags and callback", 0x3BE8, 0x3C04),
    ("complete NOR read before literal pool", 0x3E48, 0x3EB0),
    ("ROM read wrapper before literal pool", 0x3A28, 0x3A40),
    ("postinit no-op", 0x3AF0, 0x3AF4),
    ("NOR previous-storage exit", 0x3B9C, 0x3BAA),
    ("NOR ioctl before embedded switch table", 0x3AF4, 0x3B1E),
    ("NOR ioctl after embedded switch table", 0x3B22, 0x3B90),
)


def main(path: Path) -> None:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact pinned LEOPARD common adfus.bin")

    def chunk(start: int, end: int) -> bytes:
        if not 0 <= start < end <= len(data):
            raise RuntimeError("Region outside helper")
        return data[start:end]

    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    decoder.detail = True
    regions = []
    for name, start, end in REGIONS:
        raw = chunk(start, end)
        instructions = list(decoder.disasm(raw, BASE + start))
        if sum(i.size for i in instructions) != len(raw):
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
                    offset = address - BASE
                    value = struct.unpack("<I", chunk(offset, offset + 4))[0]
                    literals.append(
                        {"at": hex(instruction.address), "address": hex(address), "value": hex(value)}
                    )
        regions.append(
            {
                "name": name,
                "file_start": hex(start),
                "file_end_exclusive": hex(end),
                "bytes": raw.hex(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "instructions": [
                    {"at": hex(i.address), "asm": f"{i.mnemonic} {i.op_str}"} for i in instructions
                ],
                "literals": literals,
            }
        )
    print(
        json.dumps(
            {
                "scope": "public helper NOR initialization/read side-effect boundaries; not CoMi execution or compatibility",
                "sha256": SHA,
                "size": len(data),
                "configured_load_base": hex(BASE),
                "regions": regions,
                "nor_table": {"file_start": "0x958", "bytes": chunk(0x958, 0x974).hex()},
                "primary_spinor_info": {"file_start": "0xdaec", "bytes": chunk(0xDAEC, 0xDB14).hex()},
                "ioctl_switch": {
                    "file_start": "0x3b1e",
                    "bytes": chunk(0x3B1E, 0x3B21).hex(),
                    "targets": [hex(BASE + 0x3B1E + 2 * b) for b in chunk(0x3B1E, 0x3B21)],
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    typer.run(main)
