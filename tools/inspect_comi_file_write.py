#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6"]
# ///
"""Inspect fixed CoMi file-write paths offline; JSON stdout, no device access."""

import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

BASE = 0x10000000
SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
SIZE = 927632
REGIONS = (
    ("dumpbuf_handler", 0x10024A28, 0x10024AAA, "code", "Excludes NOP and literal pool at10024aac."),
    ("fs_write_dispatch", 0x1002EBA8, 0x1002EBE6, "code", "Excludes NOP and literal pool at1002ebe8."),
    ("fatfs_vtable_prefix", 0x100BC09C, 0x100BC0A8, "data", "Three pointer words; never decoded as code."),
    ("fatfs_write", 0x1002F850, 0x1002F894, "code", "Ends before literal word at1002f894."),
    (
        "f_write",
        0x100A714C,
        0x100A732C,
        "code",
        "Complete function; next function starts100a732c; no embedded pool.",
    ),
    ("byte_copy", 0x100A6316, 0x100A6328, "code", "Complete helper; next function starts100a6328."),
)


def inspect(image: bytes) -> dict:
    if len(image) != SIZE or hashlib.sha256(image).hexdigest() != SHA:
        raise ValueError("Requires exact927632-byte verified CoMi FW010004 mapped system image")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    regions = []
    for name, start, end, kind, boundary in REGIONS:
        raw = image[start - BASE : end - BASE]
        entry = {
            "name": name,
            "start": hex(start),
            "end_exclusive": hex(end),
            "size": len(raw),
            "kind": kind,
            "boundary": boundary,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "hex": raw.hex(),
        }
        if kind == "code":
            instructions = list(decoder.disasm(raw, start))
            if sum(instruction.size for instruction in instructions) != len(raw):
                raise RuntimeError(f"Incomplete instruction decode at{start:#x}")
            entry["instructions"] = [
                f"{i.address:#010x} {i.bytes.hex()} {i.mnemonic} {i.op_str}" for i in instructions
            ]
        else:
            entry["u32_le"] = [hex(value) for value in struct.unpack("<3I", raw)]
        regions.append(entry)
    if struct.unpack_from("<I", image, 0x100BC0A4 - BASE)[0] != 0x1002F851:
        raise RuntimeError("Fixed FAT write callback pointer changed")
    return {
        "source": {"device": "C261CF0430", "firmware": "010004", "size": SIZE, "sha256": SHA},
        "method": "Offline Capstone5.0.6 ARM Thumb MCLASS; no target execution, device access or MMIO reads",
        "call_chain": [
            "dumpbuf10024a28 calls fs_write1002eba8 at10024a90; fs_write return ignored",
            "fs_write loads file+4 mount, mount+1c vtable, vtable+8 write callback",
            "Previously observed SD mount vtable100bc09c has write slot100bc0a4=1002f851",
            "fatfs_write1002f850 calls f_write100a714c at1002f864",
        ],
        "static_observations": {
            "source_argument": "f_write100a715a retains caller source r1 in sb; remaining length r2 retained in sl",
            "sector_boundary": "100a71aa masks file position low9bits; nonzero branches100a72f0",
            "direct_sector_path": "At sector boundary100a7242 compares remaining length with512; >=512 passes original source sb in r1 to disk_write10040e28 at100a726a",
            "partial_sector_path": "<512 branches100a72cc;100a72f6..7302 clips copy size to sector remainder and remaining input",
            "cpu_copy": "100a730e..731e passes filesystem+0x50+(fileposition&511), original source sb and clipped count to100a6316; helper uses LDRB/STRB loop",
            "dirty_cache": "After CPU copy100a7328 writes1 to filesystem+3, corresponding to FatFs dirty window",
            "fresh_small_file": "A fresh file at offset0 with positive length<512 avoids the original-source direct-sector write branch; cache flush and metadata operations still access SD",
        },
        "limits": [
            "Vtable runtime selection comes from prior mount evidence; this tool reads only the fixed mapped image.",
            "CPU byte-copy path differs from direct-sector path; this does not establish DMA access restrictions as the cause of earlier4096-byte XIP zero output.",
            "No proof of SD durability, close success or downloaded bytes: each live experiment needs complete session and exact independent source comparison.",
            "Small mapped-XIP exports are mapped representation; not raw physical NOR backup.",
            "Only fixed source windows are inspected; no arbitrary memory or target-function interface.",
        ],
        "regions": regions,
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uv run tools/inspect_comi_file_write.py VERIFIED_SYSTEM.bin")
    print(json.dumps(inspect(Path(sys.argv[1]).read_bytes()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
