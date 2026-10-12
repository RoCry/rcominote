#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Inventory exact FW010004 CDC worker offline; never execute target code or I/O."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_REG_PC

BASE = 0x10000000
SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
CODE = (
    ("irq callback", 0x1000C3A0, 0x1000C3DA),
    ("tx helper", 0x1000C3E4, 0x1000C452),
    ("command 02 reply", 0x1000C46C, 0x1000C4B8),
    ("test helpers", 0x1000C4C8, 0x1000C4E2),
    ("test helpers", 0x1000C4E8, 0x1000C502),
    ("timer callback", 0x1000C508, 0x1000C696),
    ("worker bind receive dispatch", 0x1000C6D8, 0x1000C8C4),
    ("word dispatch", 0x1000C8CA, 0x1000C8D8),
    ("command 28", 0x1000C91C, 0x1000C94C),
    ("worker command branches", 0x1000C9B4, 0x1000CCD4),
    ("identity dispatch", 0x1000CD2C, 0x1000CD38),
    ("identity branches", 0x1000CD48, 0x1000CF40),
    ("message helper", 0x1005280C, 0x1005287C),
    ("board bit helper", 0x1002DD74, 0x1002DD96),
    ("status helper", 0x100A5F9E, 0x100A5FE0),
)
FOCUS = (
    (0x1000C838, 0x1000C866),
    (0x1000C93E, 0x1000C94C),
    (0x1005286A, 0x1005287C),
    (0x1000C420, 0x1000C430),
)


def main(image_path: Path) -> None:
    image = image_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact verified FW010004 mapped image")

    def chunk(start: int, end: int) -> bytes:
        if not BASE <= start < end <= BASE + len(image):
            raise RuntimeError("Region outside verified image")
        return image[start - BASE : end - BASE]

    def word(address: int) -> int:
        return struct.unpack("<I", chunk(address, address + 4))[0]

    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    decoder.detail = True
    regions = []
    focus = []
    for name, start, end in CODE:
        data = chunk(start, end)
        instructions = list(decoder.disasm(data, start))
        if sum(i.size for i in instructions) != len(data):
            raise RuntimeError(f"Incomplete code region: {start:#x}")
        calls = []
        literals = []
        for instruction in instructions:
            if instruction.mnemonic == "bl":
                if len(instruction.operands) != 1 or instruction.operands[0].type != ARM_OP_IMM:
                    raise RuntimeError("Unexpected direct call encoding")
                calls.append([hex(instruction.address), hex(instruction.operands[0].imm)])
            if instruction.mnemonic in ("ldr", "ldr.w"):
                for operand in instruction.operands:
                    if operand.type == ARM_OP_MEM and operand.mem.base == ARM_REG_PC:
                        address = ((instruction.address + 4) & ~3) + operand.mem.disp
                        value = word(address)
                        literal = {"at": hex(instruction.address), "value": hex(value)}
                        if BASE <= value < BASE + len(image):
                            text = image[value - BASE : value - BASE + 80].split(b"\0")[0]
                            if text and all(32 <= byte < 127 or byte in (10, 13) for byte in text):
                                literal["ascii"] = text.decode("ascii")
                        literals.append(literal)
            if any(left <= instruction.address < right for left, right in FOCUS):
                focus.append(
                    {
                        "at": hex(instruction.address),
                        "bytes": instruction.bytes.hex(),
                        "asm": f"{instruction.mnemonic} {instruction.op_str}",
                    }
                )
        regions.append(
            {
                "name": name,
                "start": hex(start),
                "end_exclusive": hex(end),
                "sha256": hashlib.sha256(data).hexdigest(),
                "instruction_count": len(instructions),
                "calls": calls,
                "literals": literals,
            }
        )

    word_targets = [value & ~1 for value in struct.unpack("<17I", chunk(0x1000C8D8, 0x1000C91C))]
    high_targets = [0x1000C8C4 + 2 * value for value in struct.unpack("<3H", chunk(0x1000C8C4, 0x1000C8CA))]
    identity_targets = [
        0x1000CD38 + 2 * value for value in struct.unpack("<8H", chunk(0x1000CD38, 0x1000CD48))
    ]
    result = {
        "image_sha256": SHA,
        "scope": "Complete worker code intervals, IRQ/tx helpers, timer callback; no device I/O",
        "word_dispatch_02_12": {f"{i + 2:02x}": hex(value) for i, value in enumerate(word_targets)},
        "high_dispatch_81_83": {f"{i + 0x81:02x}": hex(value) for i, value in enumerate(high_targets)},
        "identity_dispatch_0_7": {str(i): hex(value) for i, value in enumerate(identity_targets)},
        "explicit_dispatch": {
            "28": "0x1000c91c",
            "80": "0x1000cb42",
            "90": "0x1000cb72",
            "a0": "0x1000c9ce",
            "b0": "0x1000caf6",
            "f0": "0x1000ca9e",
            "ff": "0x1000ca2c",
            "default": "0x1000c880",
        },
        "focus_instructions": focus,
        "code_regions": regions,
        "limits": [
            "Static evidence; no CDC enumeration or framing observed on hardware",
            "No memory/file/NOR bulk-read request fields in this worker",
            "Async main-message recipients and recording internals not exhaustively followed",
            "Does not cover ROM ADFU, USB MSC, OTA, or alternative firmware",
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    typer.run(main)
