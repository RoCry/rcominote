#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Audit actual OTA NVRAM spare-segment preerase; no target execution."""

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
    ("OTA writer call to NVRAM preerase", 0x10065C32, 0x10065C54),
    ("clear and erase API thunks", 0x100A52D2, 0x100A52DC),
    ("complete fixed user-region clear", 0x10035FC4, 0x10036028),
    ("complete region erase", 0x10035EC4, 0x10035F34),
    ("complete blank check", 0x10035DD0, 0x10035E20),
    ("complete NVRAM driver read loop", 0x10036CA8, 0x10036D0C),
    ("NVRAM partition selection and base size assignment", 0x10036B10, 0x10036B94),
    ("NVRAM storage assignment and region scan caller", 0x10036BC0, 0x10036C1C),
    ("storage lookup spi_flash", 0x10036D1C, 0x10036D50),
    ("selected region scan header loop", 0x10036780, 0x10036790),
    ("selected region scan current segment assignment", 0x10036800, 0x10036860),
    ("startup initialized data copy", 0x1009C1D0, 0x1009C1F8),
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
                        text = data[value - BASE : value - BASE + 160].split(b"\0")[0]
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
    initializer = chunk(0x100DF0AC, 0x100DF0E4)
    print(
        json.dumps(
            {
                "sha256": SHA,
                "scope": "actual OTA fixed user-region spare-segment preerase; no live segment pointer or erase observation",
                "regions": regions,
                "user_region_initializer": {
                    "image_address": "0x100df0ac",
                    "startup_ram_address": "0x18001bac",
                    "bytes": initializer.hex(),
                    "sha256": hashlib.sha256(initializer).hexdigest(),
                    "name": initializer[4:20].split(b"\0")[0].decode("ascii"),
                    "base_initial": hex(struct.unpack_from("<I", initializer, 0x18)[0]),
                    "total_size_initial": struct.unpack_from("<I", initializer, 0x1C)[0],
                    "segment_size_initial": struct.unpack_from("<I", initializer, 0x20)[0],
                    "segment_offset_initial": struct.unpack_from("<I", initializer, 0x24)[0],
                    "note": "startup initializer only; partition init and scan replace base, total size and current segment",
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    typer.run(main)
