#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Static bounded boot instruction evidence; never executes the image."""

import hashlib
import json
import re
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs


def main(image: Path):
    raw = image.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != "73a199d17490d5ae9e35e466b4ad8fafaa0757fb4a1ae7e79b5c90f90e4cb054":
        raise ValueError("Input differs from verified3672-byte actual boot image")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    ranges = [
        (0x38, 0x52),
        (0x56, 0x5E),
        (0x22C, 0x25C),
        (0x264, 0x298),
        (0x298, 0x4C4),
        (0x500, 0x504),
        (0x6A8, 0x6EC),
        (0x6F8, 0x702),
        (0x708, 0x712),
        (0xC70, 0xC8C),
        (0xD90, 0xDB4),
    ]
    regions = []
    for start, end in ranges:
        instructions = []
        for insn in decoder.disasm(raw[start:end], 0x01010000 + start):
            item = {
                "address": hex(insn.address),
                "bytes": insn.bytes.hex(),
                "instruction": f"{insn.mnemonic} {insn.op_str}",
            }
            if insn.mnemonic.startswith("ldr") and "[pc," in insn.op_str:
                match = re.search(r"#(0x[0-9a-f]+|[0-9]+)", insn.op_str)
                if match:
                    address = ((insn.address + 4) & ~3) + int(match[1], 0)
                    item["literal_address"] = hex(address)
                    item["literal_value"] = hex(struct.unpack_from("<I", raw, address - 0x01010000)[0])
            instructions.append(item)
        if sum(len(bytes.fromhex(i["bytes"])) for i in instructions) != end - start:
            raise ValueError(f"Incomplete instruction decoding at {start:#x}")
        regions.append(
            {
                "start": hex(0x01010000 + start),
                "end_exclusive": hex(0x01010000 + end),
                "instructions": instructions,
            }
        )
    print(
        json.dumps(
            {
                "sha256": digest,
                "base": "0x01010000",
                "scope": "Selected actual boot instructions; static only, indirect ROM targets unresolved",
                "regions": regions,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
