#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Inspect a SHA-bound partial decoded recovery; never execute or read a device."""

import hashlib
import json
import re
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

SHA256 = "cff7225f49d502a3e6cf52a8d2df12cbee44625cc2120c3c7a03a96d77e577b7"
BASE = 0x11000000


def main(image: Path, entry: bool = False):
    data = image.read_bytes()
    if len(data) != 48128 or hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Expected the revalidated94-block decoded recovery prefix")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    regions = []
    ranges = ((0x23D4, 0x23FA), (0x1FF8, 0x2040), (0x8AAC, 0x8AD2), (0x999A, 0x99A2))
    if entry:
        ranges = (
            (0x634, 0x6D8),
            (0x7A4, 0x7DC),
            (0x7EC, 0x86C),
            (0x884, 0x8D0),
            (0x8E0, 0x908),
            (0x910, 0x99C),
            (0x1348, 0x13AC),
            (0x13B8, 0x13E8),
            (0x24B8, 0x24E8),
            (0x99AA, 0x99BC),
            (0xA122, 0xA144),
            (0xA20A, 0xA20E),
        )
    for start, end in ranges:
        instructions = []
        cursor = start
        for instruction in decoder.disasm(data[start:end], BASE + start):
            cursor += instruction.size
            item = {
                "address": hex(instruction.address),
                "bytes": instruction.bytes.hex(),
                "instruction": f"{instruction.mnemonic} {instruction.op_str}",
            }
            if instruction.mnemonic.startswith("ldr") and "[pc," in instruction.op_str:
                match = re.search(r"#(0x[0-9a-f]+|[0-9]+)", instruction.op_str)
                if match:
                    address = ((instruction.address + 4) & ~3) + int(match[1], 0)
                    item["literal_address"] = hex(address)
                    value = struct.unpack_from("<I", data, address - BASE)[0]
                    item["literal_value"] = hex(value)
                    if entry and BASE <= value < BASE + len(data):
                        raw = data[value - BASE : value - BASE + 160].split(b"\0")[0]
                        if raw and all(32 <= byte < 127 or byte in (10, 13) for byte in raw):
                            item["literal_text"] = raw.decode("ascii")
            instructions.append(item)
        if cursor != end:
            raise ValueError(f"Incomplete instruction range at {cursor:x}, expected {end:x}")
        regions.append(
            {"start": hex(BASE + start), "end_exclusive": hex(BASE + end), "instructions": instructions}
        )
    print(
        json.dumps(
            {
                "sha256": SHA256,
                "bytes": len(data),
                "complete_image": False,
                "body_checksum_verified": False,
                "scope": "Provisional32-byte decoding; original windows revalidated, full body unavailable",
                "vector_sp": hex(struct.unpack_from("<I", data, 0x200)[0]),
                "vector_reset": hex(struct.unpack_from("<I", data, 0x204)[0]),
                "regions": regions,
                "copy_sources": [
                    {
                        "source": "0x1100f5a0",
                        "destination": "0x18001508",
                        "bytes": 0x198,
                        "source_in_prefix": False,
                    },
                    {
                        "source": "0x1100e098",
                        "destination": "0x18000000",
                        "bytes": 0x1508,
                        "source_in_prefix": False,
                    },
                    {
                        "source": "0x1100f738",
                        "destination": "0x01000400",
                        "bytes": 0,
                        "source_in_prefix": False,
                    },
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
