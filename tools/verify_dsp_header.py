#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["unicorn==2.1.4", "typer>=0.16,<1"]
# ///
"""Verify actual DSP header loader control flow using synthetic headers; no DSP execution."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_MCLASS, UC_MODE_THUMB, Uc
from unicorn.arm_const import (
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_SP,
)

SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
FILE = 0x18010000
ENTRY = 0x18011000
STOP = 0x100E3000


def verify(image: bytes, header: bytes, *, seek_error: bool = False) -> dict:
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x10000000, 0x100000)
    cpu.mem_write(0x10000000, image)
    cpu.mem_map(0x18000000, 0x80000)
    cpu.mem_write(ENTRY, b"\xff" * 4)
    cpu.reg_write(UC_ARM_REG_R0, FILE)
    cpu.reg_write(UC_ARM_REG_R1, ENTRY)
    cpu.reg_write(UC_ARM_REG_SP, 0x18070000)
    cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
    calls = []
    finished = False

    def hook(machine: Uc, address: int, size: int, user_data: object) -> None:
        nonlocal finished
        if address == STOP:
            finished = True
            machine.emu_stop()
            return
        if 0x1003CAF4 <= address < 0x1003CB66:
            return
        args = [machine.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
        match address:
            case 0x1002EBF4:
                if args != [FILE, 0, 0]:
                    raise RuntimeError(f"Unexpected seek arguments: {args}")
                calls.append("seek")
                machine.reg_write(UC_ARM_REG_R0, 0xFFFFFFFB if seek_error else 0)
            case 0x1002EB5C:
                if args[0] != FILE or args[2] != 540 or calls != ["seek"]:
                    raise RuntimeError(f"Unexpected header read: {args}")
                calls.append("read")
                machine.mem_write(args[1], header)
                machine.reg_write(UC_ARM_REG_R0, len(header))
            case 0x1009FF86:
                calls.append("log")
                machine.reg_write(UC_ARM_REG_R0, 0)
            case _:
                raise RuntimeError(f"Unexpected execution: {address:#x}")
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(0x1003CAF5, STOP + 2, count=1000)
    if not finished:
        raise RuntimeError("DSP loader did not return within instruction budget")
    return {
        "return": cpu.reg_read(UC_ARM_REG_R0),
        "entry": struct.unpack("<I", bytes(cpu.mem_read(ENTRY, 4)))[0],
        "calls": calls,
    }


def main(image_path: Path) -> None:
    image = image_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact verified FW010004 mapped image")
    # SDK header layout oracle: 540 bytes, LE magic, entry at +16, zero section pointers.
    header = b"xhqy" + bytes(12) + struct.pack("<I", 0x12345678) + bytes(520)
    results = {}
    for name, data, seek_error, expected in [
        ("empty_sections", header, False, (0, 0x12345678, ["seek", "read"])),
        ("short_header", header[:539], False, (0xFFFFFFEA, 0xFFFFFFFF, ["seek", "read", "log"])),
        ("bad_magic", b"BAD!" + header[4:], False, (0xFFFFFFEA, 0xFFFFFFFF, ["seek", "read", "log"])),
        ("failed_seek_full_read", header, True, (0, 0x12345678, ["seek", "read"])),
    ]:
        result = verify(image, data, seek_error=seek_error)
        if result != dict(zip(("return", "entry", "calls"), expected, strict=True)):
            raise RuntimeError(f"{name} mismatch: {result}")
        results[name] = result
    print(
        json.dumps(
            {
                "image_sha256": SHA,
                "engine": "Unicorn 2.1.4 Thumb MCLASS",
                "scope": "Actual header loader; synthetic empty-section headers; intercepted file I/O and log",
                "limits": "No DSP resource or segment data verified; no hardware or DSP execution",
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
