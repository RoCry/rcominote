#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""SHA-bound OTA selection, payload writes and commit ordering; offline only."""

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
    ("upgrade entry through first literal pool", 0x1006635C, 0x100665E8),
    ("upgrade entry continuation and success commit", 0x10066670, 0x1006691C),
    ("payload selection and breakpoint state switch", 0x1006586C, 0x100659CA),
    ("payload breakpoint switch targets before literal pool", 0x100659D2, 0x10065A90),
    ("payload writer before second literal pool", 0x10065B00, 0x10065E24),
    ("payload writes and verification before third literal pool", 0x10065E68, 0x10066140),
    ("partition current lookup", 0x1002766C, 0x100276AC),
    ("partition mirror lookup", 0x100276B0, 0x1002770E),
    ("maximum file size", 0x100A1F96, 0x100A1FAA),
    ("current file id and mirror predicate and type predicates", 0x100A1FCE, 0x100A2012),
    ("actual storage write dispatcher and NOR loop", 0x10064BDC, 0x10064D54),
    ("actual storage read dispatcher and NOR loop", 0x10064D74, 0x10064E00),
    ("breakpoint file state update and conditional store", 0x100B15D8, 0x100B1648),
    ("breakpoint overall state update", 0x10067B00, 0x10067B3C),
    ("breakpoint save before literal pool", 0x1006792C, 0x10067968),
    ("breakpoint storage lookup", 0x10066B14, 0x10066B1A),
    ("storage sync handles only types two and four", 0x100B14DA, 0x100B14F8),
    ("OTA state callback dispatch", 0x100654CC, 0x10065500),
    ("application callback after OTA state changes", 0x1000478C, 0x10004828),
    ("validity ioctl wrapper", 0x100B1510, 0x100B151E),
    ("Bluetooth validity message sender", 0x1006419C, 0x10064208),
    ("Bluetooth ioctl before switch table", 0x10064220, 0x1006424E),
    ("Bluetooth ioctl after switch table", 0x10064252, 0x100642B0),
)
TABLES = (
    ("file state switch: states one through seven", 0x100659CA, 0x100659D1),
    ("Bluetooth ioctl switch", 0x1006424E, 0x10064252),
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
                "scope": "selected actual application payload selection/write/CRC/commit paths; no live OTA, recovery execution or power-cut proof",
                "regions": regions,
                "switch_tables": [
                    {
                        "name": name,
                        "start": hex(start),
                        "end_exclusive": hex(end),
                        "bytes": chunk(start, end).hex(),
                        "targets": [hex(start + 2 * value) for value in chunk(start, end)],
                    }
                    for name, start, end in TABLES
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    typer.run(main)
