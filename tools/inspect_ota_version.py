#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""SHA-bound actual OTA initialization and version gate; no target execution."""

import hashlib
import json
import re
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

SHA256 = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
BASE = 0x10000000


def main(image: Path):
    data = image.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Expected verified mapped-system image")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    regions = []
    for start, end in ((0x4AE8, 0x4B54), (0x669F8, 0x66A3C), (0x664C2, 0x6655C), (0xCC8, 0xCDC)):
        instructions = []
        cursor = start
        for insn in decoder.disasm(data[start:end], BASE + start):
            cursor += insn.size
            item = {
                "address": hex(insn.address),
                "bytes": insn.bytes.hex(),
                "instruction": f"{insn.mnemonic} {insn.op_str}",
            }
            if insn.mnemonic.startswith("ldr") and "[pc," in insn.op_str:
                match = re.search(r"#(0x[0-9a-f]+|[0-9]+)", insn.op_str)
                if match:
                    address = ((insn.address + 4) & ~3) + int(match[1], 0)
                    value = struct.unpack_from("<I", data, address - BASE)[0]
                    item |= {"literal_address": hex(address), "literal_value": hex(value)}
                    offset = value - BASE
                    if 0 <= offset < len(data):
                        end_string = data.find(b"\0", offset, offset + 160)
                        if end_string >= offset:
                            candidate = data[offset:end_string]
                            if candidate and all(32 <= c < 127 or c in (10, 13) for c in candidate):
                                item["literal_string"] = candidate.decode("ascii")
            instructions.append(item)
        if cursor != end:
            raise ValueError(f"Incomplete instruction range at {cursor:x}")
        regions.append(
            {"start": hex(BASE + start), "end_exclusive": hex(BASE + end), "instructions": instructions}
        )
    print(
        json.dumps(
            {
                "sha256": SHA256,
                "scope": "static initialization and board/version gate, not live OTA acceptance",
                "regions": regions,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
