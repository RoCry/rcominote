#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6"]
# ///
"""Inspect fixed CoMi deletion bytes offline; never sends a device command."""

import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

BASE = 0x10000000
SIZE = 927632
IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
REGIONS = (
    ("delete_dispatch", 0x1009EE42, 0x1009EE84, "code"),
    ("delete_paths", 0x1000BA28, 0x1000BAE8, "code"),
    ("delete_literals", 0x1000BAE8, 0x1000BB0C, "data"),
    ("allocation_wrapper", 0x100017EC, 0x100017F8, "code"),
    ("allocation_literal", 0x100017F8, 0x100017FC, "data"),
    ("heap_allocation_wrapper", 0x100B8930, 0x100B8944, "code"),
    ("copy_exact_length", 0x100B9652, 0x100B966E, "code"),
    ("pre_unlink_wrappers", 0x100ADBA0, 0x100ADBAC, "code"),
)
STRINGS = {
    "directory": (0x100C1689, b"/SD:/RECORDER\0"),
    "call_prefix": (0x100C2244, b"Call-\0"),
    "note_prefix": (0x100C223E, b"Note-\0"),
    "path_format": (0x100C235A, b"%s/%s%s.mp3\0"),
    "failure_text": (0x100C244A, b"del file %s fail!!\n\0"),
}


def inspect(image: bytes) -> dict:
    if len(image) != SIZE or hashlib.sha256(image).hexdigest() != IMAGE_SHA:
        raise ValueError("Requires exact verified CoMi FW010004 mapped system image")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    regions = []
    for name, start, end, kind in REGIONS:
        raw = image[start - BASE : end - BASE]
        entry = {
            "name": name,
            "start": hex(start),
            "end_exclusive": hex(end),
            "kind": kind,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "hex": raw.hex(),
        }
        if kind == "code":
            instructions = list(decoder.disasm(raw, start))
            if sum(instruction.size for instruction in instructions) != len(raw):
                raise RuntimeError(f"Incomplete instruction decode at {start:#x}")
            entry["instructions"] = [
                f"{i.address:#010x} {i.bytes.hex()} {i.mnemonic} {i.op_str}" for i in instructions
            ]
        else:
            entry["u32_le"] = [hex(v[0]) for v in struct.iter_unpack("<I", raw)]
        regions.append(entry)
    strings = []
    for name, (address, expected) in STRINGS.items():
        raw = image[address - BASE : address - BASE + len(expected)]
        if raw != expected:
            raise RuntimeError(f"Fixed path/string changed at {address:#x}")
        strings.append(
            {
                "name": name,
                "address": hex(address),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "hex": raw.hex(),
                "text": raw[:-1].decode("ascii"),
            }
        )
    return {
        "kind": "owned-scratch-delete-static-lead",
        "image": {"bytes": SIZE, "sha256": IMAGE_SHA, "cpu_base": hex(BASE)},
        "method": "Offline Capstone5.0.6 Thumb MCLASS; explicit code/literal boundaries; no device I/O",
        "observations": [
            "DELETE0d dispatch1009ee42 calls1000ba28 only for nonzero payload length.",
            "Zero-length branch passes byte00/length1 to response builder1000b114, then returns-1.",
            "Path routine uses /SD:/RECORDER and %s/%s%s.mp3; Call- first, Note- only if first unlink returns negative.",
            "Both unlink calls target1002f0e0; no normal recording-list token check appears in these bounded bodies.",
            "Name allocation receives exactly payload length;100b9652 copies exactly that length without appending NUL.",
            "The bounded path routine contains no explicit filename terminator store before its %s formatting calls.",
            "Pre-unlink helpers100adba0/100adba6 forward arguments1,5 to10053034/100530b8; their effects remain unresolved.",
        ],
        "limits": [
            "Static observations only; not proof that a hidden scratch name is accepted or safely deleted.",
            "Allocator padding/initial contents and firmware filename termination assumptions remain unknown.",
            "No live delete, missing-file response, recreated size, truncation or durability verification.",
            "Production delete requires a complete visible list containing the target; hidden scratch cannot satisfy it.",
            "A new file growing0→4096 could remove an old logical tail, but that protocol and its authorization are unestablished.",
            "No permission for deleting reserved scratch, other files, format, reset or unbind is inferred.",
        ],
        "regions": regions,
        "strings": strings,
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uv run tools/inspect_owned_scratch_delete.py VERIFIED_SYSTEM.bin")
    print(json.dumps(inspect(Path(sys.argv[1]).read_bytes()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
