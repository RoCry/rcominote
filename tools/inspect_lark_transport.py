#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Compare two pinned LARK transport variants offline; never execute helpers."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

BASE = 0x01010000
SPECS = {
    "adfus.bin": (
        "ee57bd899a2b2623d9e9d3b5d8fa7c970ada8df717e69c122c8ce19be3d6f8d8",
        [
            (0x24B0, 0x251C),
            (0x2540, 0x255C),
            (0x2610, 0x2678),
            (0x3108, 0x3192),
            (0x31D4, 0x3220),
            (0x3224, 0x324C),
            (0x4D38, 0x4D8A),
            (0xA540, 0xA58A),
            (0x4CDC, 0x4D2E),
            (0x47A8, 0x47B6),
            (0xA75C, 0xA7A6),
            (0xA82C, 0xA878),
        ],
        [(0, 0x20), (0x240, 0x258), (0x2678, 0x2684), (0x740, 0x800), (0x3194, 0x31A8)],
    ),
    "adfus_u.bin": (
        "0aefabef3c09374b170d9a784bc5983ab6a1c904e945556de27e1fcb31b8847d",
        [(0x25C0, 0x25D8), (0x26F0, 0x2772), (0x47E0, 0x481E), (0x483C, 0x4850), (0x4930, 0x4934)],
        [(0, 0x20), (0x240, 0x258), (0x2774, 0x2784), (0x4820, 0x483C), (0xD84, 0xDE4)],
    ),
}


def main(directory: Path, usb_storage: bool = False, handshake: bool = False):
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    files = []
    specs = SPECS
    if usb_storage and handshake:
        raise typer.BadParameter("Choose one audit mode")
    if usb_storage:
        specs = {
            "adfus_u.bin": (
                SPECS["adfus_u.bin"][0],
                [
                    (0x25E0, 0x2612),
                    (0x3E9C, 0x3EB6),
                    (0x3E2C, 0x3E86),
                    (0x4200, 0x445C),
                    (0x3F70, 0x3FAE),
                    (0x3FB0, 0x3FD4),
                    (0x5634, 0x5640),
                    (0x53B4, 0x55C6),
                    (0x55E0, 0x55FC),
                    (0x4C5C, 0x4CBA),
                    (0x500C, 0x505E),
                    (0x25C0, 0x25D8),
                    (0x26F0, 0x2772),
                    (0x483C, 0x4850),
                    (0x265C, 0x2674),
                    (0x4A3C, 0x4A50),
                    (0x4A6C, 0x4A7A),
                    (0x3110, 0x3118),
                ],
                [(0xA24, 0xA40), (0xB50, 0xB78), (0x3EB8, 0x3ED0), (0xE06, 0xE68)],
            )
        }
    if handshake:
        specs = {
            "adfus_u.bin": (
                SPECS["adfus_u.bin"][0],
                [
                    (0x26F0, 0x2772),
                    (0x5068, 0x50BA),
                    (0xA9B8, 0xAA02),
                    (0xAA14, 0xAA56),
                    (0xAA56, 0xAAA6),
                    (0xAB72, 0xAB98),
                    (0xACF0, 0xAD20),
                    (0xAD32, 0xADCA),
                ],
                [(0xAD20, 0xAD31)],
            )
        }
    for name, (sha, regions, tables) in specs.items():
        data = (directory / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError(f"Wrong pinned zephyr LARK artifact: {name}")
        code = []
        for start, end in regions:
            raw = data[start:end]
            insns = list(decoder.disasm(raw, BASE + start))
            if sum(i.size for i in insns) != len(raw):
                raise ValueError(f"Incomplete decode: {name} {start:x}")
            code.append(
                {
                    "offset": hex(start),
                    "hex": raw.hex(),
                    "instructions": [
                        {"at": hex(i.address), "asm": f"{i.mnemonic} {i.op_str}"} for i in insns
                    ],
                }
            )
        files.append(
            {
                "name": name,
                "sha256": sha,
                "size": len(data),
                "code": code,
                "tables": [{"offset": hex(a), "hex": data[a:b].hex()} for a, b in tables],
            }
        )
    usb = (directory / "adfus_u.bin").read_bytes()
    vid, pid = struct.unpack_from("<HH", usb, 0xD84 + 8)
    print(
        json.dumps(
            {
                "scope": "offline configured transports/descriptors; not observed CoMi USB or recovery",
                "source_commit": "26f51e584940d5b141cd1d09d2629d69b595f579",
                "source_directory": "action_technology_sdk/zephyr/tools/prebuilt/lark/common/bin",
                "configured_base": hex(BASE),
                "usb_descriptor_vid": hex(vid),
                "usb_descriptor_pid": hex(pid),
                "files": files,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
