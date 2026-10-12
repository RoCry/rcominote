#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer>=0.16,<1"]
# ///
"""Compare captured raw/mapped system headers; does not infer a cipher or decrypt."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import typer


def main(raw_path: Path, mapped_path: Path):
    raw, mapped = raw_path.read_bytes(), mapped_path.read_bytes()
    expected = (
        "28b2e50ba95630f6485bd5e3ccfbd8ebe5f1406ffa36d6c0c4e35c4c71af0678",
        "911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5",
    )
    for data, digest in zip((raw, mapped), expected, strict=True):
        if len(data) != 512 or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Input differs from captured 512-byte raw/mapped system header")
    mask = bytes(a ^ b for a, b in zip(raw, mapped, strict=True))
    report = {
        "raw_sha256": expected[0],
        "mapped_header_sha256": expected[1],
        "xor_prefix": mask[:32].hex(),
        "repeating_xor_periods": [
            n for n in (1, 2, 4, 8, 16, 32, 64, 128, 256) if all(v == mask[i % n] for i, v in enumerate(mask))
        ],
        "equal_byte_count": sum(a == b for a, b in zip(raw, mapped, strict=True)),
    }
    for width in (8, 16, 32):
        groups = defaultdict(list)
        for offset in range(0, 512, width):
            groups[mapped[offset : offset + width]].append(offset)
        report[f"equal_plaintext_groups_{width}"] = [
            {
                "offsets": offsets,
                "distinct_raw_blocks": len({raw[i : i + width] for i in offsets}),
            }
            for offsets in groups.values()
            if len(offsets) > 1
        ]
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    typer.run(main)
