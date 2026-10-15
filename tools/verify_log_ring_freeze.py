#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6"]
# ///
"""Verify fixed firmware evidence for the CPU/DMA snapshot boundary; offline only."""

import gzip
import hashlib
import json
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/log-ring-freeze-boundary-2026-10-14.json"
EVIDENCE_SHA = "023075733c17e83f67a132b0c50616454d3cf759ac8ddda6c8c2a25b3216a899"
IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
IMAGE_PATH = ROOT / "docs/evidence/minimal-image-2026-10-13/original-system.bin.gz"
BASE = 0x10000000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify() -> dict:
    receipt = EVIDENCE.read_bytes()
    require(sha(receipt) == EVIDENCE_SHA, "Static evidence receipt changed")
    evidence = json.loads(receipt)
    image = gzip.decompress(IMAGE_PATH.read_bytes())
    require(len(image) == 927632 and sha(image) == IMAGE_SHA, "Wrong original firmware image")
    require(evidence["image"]["sha256"] == IMAGE_SHA, "Image identity differs in receipt")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    instructions = {}
    for region in evidence["regions"]:
        address = int(region["address"], 16)
        raw = bytes.fromhex(region["hex"])
        require(len(raw) == region["length"], f"Length changed: {region['name']}")
        require(sha(raw) == region["sha256"], f"Region hash changed: {region['name']}")
        require(image[address - BASE : address - BASE + len(raw)] == raw, "Region differs from image")
        decoded = list(decoder.disasm(raw, address))
        require(sum(row.size for row in decoded) == len(raw), "Incomplete Thumb decoding")
        assembly = "\n".join(f"{row.address:08x}: {row.mnemonic} {row.op_str}".rstrip() for row in decoded)
        require(assembly == region["disassembly"], f"Disassembly changed: {region['name']}")
        instructions.update({row.address: f"{row.mnemonic} {row.op_str}" for row in decoded})
    for row in evidence["data"]:
        address, offset = int(row["address"], 16), int(row["image_offset"], 16)
        raw = bytes.fromhex(row["hex"])
        expected_offset = address - 0x18000000 + 0xDD500 if row["initial_ram_not_live"] else address - BASE
        require(offset == expected_offset, "Data mapping changed")
        require(image[offset : offset + len(raw)] == raw and sha(raw) == row["sha256"], "Data changed")
    for address, expected in {
        0x10024C70: "bl #0x10026f10",
        0x10026E42: "beq #0x10026e3a",
        0x10026E5C: "bne #0x10026e3a",
        0x1002FBEE: "beq #0x1002fbe2",
        0x1002DCAE: "bmi #0x1002dcaa",
        0x10026F2A: "bl #0x10026c70",
        0x10026F2E: "movs r3, #1",
        0x10026F30: "strb r3, [r5, #0x18]",
        0x10026D9C: "bl #0x100a1da6",
        0x100A1F8C: "b.w #0x10026f10",
    }.items():
        require(instructions.get(address) == expected, f"Critical instruction changed: {address:#x}")
    return {
        "scope": "Offline static-byte and Thumb verification; no device access or runtime conclusion",
        "evidence_sha256": EVIDENCE_SHA,
        "image_sha256": IMAGE_SHA,
        "regions_verified": len(evidence["regions"]),
        "data_regions_verified": len(evidence["data"]),
        "conclusion": "CPU/DMA switch does not establish a bounded, exclusive ring freeze contract",
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
