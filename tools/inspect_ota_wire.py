#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Inspect exact CoMi OTA dispatcher offline; never contact a device."""

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
    ("connection callback", 0x100638E4, 0x10063974),
    ("receive exact bytes", 0x10063990, 0x100639D6),
    ("receive TLV header", 0x100639E4, 0x10063A3C),
    ("negotiation result 09", 0x10063B58, 0x10063C1C),
    ("send service header", 0x10063C80, 0x10063CC4),
    ("upgrade request 01", 0x10063CD0, 0x10063E18),
    ("connection negotiation 02", 0x10063E4C, 0x10063EF0),
    ("require image bytes 03", 0x10063F10, 0x10063FA0),
    ("receive image data 04 or 0b", 0x10064018, 0x1006416C),
    ("report image valid 06", 0x1006419C, 0x10064208),
    ("ioctl cases 10001 through 10004", 0x10064220, 0x1006424E),
    ("ioctl case bodies", 0x10064252, 0x100642B0),
    ("process command dispatcher", 0x100642C8, 0x100643B0),
    ("backend read", 0x100643E0, 0x100644A8),
    ("TLV pack and data wrappers", 0x100B147E, 0x100B14A8),
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

    def word(address: int) -> int:
        return struct.unpack("<I", chunk(address, address + 4))[0]

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
                    value = word(address)
                    literal = {"at": hex(instruction.address), "address": hex(address), "value": hex(value)}
                    if BASE <= value < BASE + len(data):
                        text = data[value - BASE : value - BASE + 100].split(b"\0")[0]
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

    table_image = 0x100DF1CC
    table_ram = 0x18001CCC
    commands = []
    for index in range(5):
        address = table_image + index * 8
        raw = chunk(address, address + 8)
        commands.append(
            {
                "opcode": f"{raw[0]:02x}",
                "image_address": hex(address),
                "bytes": raw.hex(),
                "handler_thumb": hex(word(address + 4)),
            }
        )
    result = {
        "image_sha256": SHA,
        "image_bytes": len(data),
        "method": "Offline Capstone 5.0.6 ARM Thumb MCLASS; manually bounded code intervals exclude literal pools; no target execution or device I/O",
        "command_table": {"image": hex(table_image), "ram": hex(table_ram), "entries": commands},
        "backend_api": {
            "image": "0x100df1ac",
            "ram": "0x18001cac",
            "bytes": chunk(0x100DF1AC, 0x100DF1CC).hex(),
            "thumb_pointers": [hex(word(0x100DF1AC + index * 4)) for index in range(8)],
        },
        "regions": regions,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    typer.run(main)
