#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""SHA-bound OTA initialization preparation audit; offline, no device traffic."""

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
    ("startup wrapper calling application initializer", 0x10001C98, 0x10001D18),
    ("BLE callback attaches existing OTA object", 0x100048BA, 0x10004952),
    ("application initialization argument", 0x10004AE8, 0x10004B54),
    ("complete initializer before literal pool", 0x100669F8, 0x10066ADC),
    ("complete partition preparation before literal pool", 0x100655BC, 0x100657B4),
    ("partition erase alignment and clean check", 0x1006550C, 0x100655A4),
    ("storage clean check before literal pool", 0x10064E0C, 0x10064EC0),
    ("storage erase dispatcher before literal pool", 0x1006503C, 0x100650A8),
    ("NOR erase loop through driver API", 0x10064FD0, 0x1006502C),
    ("storage initializer including NOR type and id zero", 0x100650B8, 0x10065178),
    ("storage id getter", 0x100B1500, 0x100B1504),
    ("partition by index", 0x10027650, 0x10027668),
    ("breakpoint initializer before literal pool", 0x10067B48, 0x10067B90),
    ("breakpoint load before literal pool", 0x10067978, 0x100679C0),
    ("breakpoint defaults", 0x100B1648, 0x100B166E),
    ("breakpoint save before literal pool", 0x1006792C, 0x10067968),
    ("breakpoint file state set before literal pool", 0x100679D4, 0x10067A34),
    ("breakpoint file state lookup before literal pool", 0x10067A40, 0x10067A84),
    ("NVRAM set wrapper", 0x10036A10, 0x10036A3C),
    ("NVRAM set implementation before literal pool", 0x100364F4, 0x1003673C),
    ("NVRAM storage write bounds and dispatch", 0x10035E24, 0x10035E6C),
    ("NVRAM driver write loop", 0x10036C38, 0x10036C9C),
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
    print(
        json.dumps(
            {
                "sha256": SHA,
                "size": len(data),
                "scope": "initialization preparation, conditional erase and breakpoint store paths; no runtime state or live OTA",
                "regions": regions,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    typer.run(main)
