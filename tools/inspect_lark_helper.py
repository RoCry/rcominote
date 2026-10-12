#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Inspect pinned LARK helper command and NOR paths without executing target code."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_MEM, ARM_REG_PC

BASE = 0x01010000
SHA = "ee57bd899a2b2623d9e9d3b5d8fa7c970ada8df717e69c122c8ce19be3d6f8d8"
REGIONS = (
    ("complete command dispatcher", 0x4758, 0x479A),
    ("memory read handler", 0x489C, 0x48F8),
    ("storage read handler", 0x4BDC, 0x4C38),
    ("storage selector initializer", 0x492C, 0x498A),
    ("selector0 constructor dispatch", 0x2564, 0x2596),
    ("NOR constructor selects in-image driver", 0x3E2C, 0x3E46),
    ("NOR initializer", 0x3DBC, 0x3E16),
    ("NOR read wrapper", 0x3C34, 0x3C4C),
    ("NOR read driver", 0x402C, 0x4066),
    ("NOR post-init no-op", 0x3CFC, 0x3D00),
)


def main(path: Path) -> None:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact pinned zephyr LARK common adfus.bin")

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
                "scope": "LARK helper command/read paths; nested initialization not fully audited; no CoMi compatibility proof",
                "source_commit": "26f51e584940d5b141cd1d09d2629d69b595f579",
                "source_path": "action_technology_sdk/zephyr/tools/prebuilt/lark/common/bin/adfus.bin",
                "sha256": SHA,
                "size": len(data),
                "configured_load_base": hex(BASE),
                "regions": regions,
                "command_tokens_hex": chunk(0xD88, 0xDA8).hex(),
                "command_pointers": [hex(x) for x in struct.unpack("<16I", chunk(0xDAC, 0xDEC))],
                "nor_table": {"file_start": "0xa28", "bytes": chunk(0xA28, 0xA44).hex()},
                "nor_driver_table": {"file_start": "0xb54", "bytes": chunk(0xB54, 0xB7C).hex()},
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    typer.run(main)
