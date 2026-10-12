#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["unicorn==2.1.4", "typer>=0.16,<1"]
# ///
"""Execute the owned FW010004 pixel callback against hand-authored golden patterns.

No device I/O. External allocator, free, command and transfer calls are intercepted.
The callback's actual ARM Thumb instructions perform all pixel packing.
"""

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

IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
BASE = 0x10000000
DATA = 0x180056F0
SOURCE = 0x18010000
TEMP = 0x18020000
STOP = 0x100E3000
ENTRY = 0x10027E84
END = 0x10027F8E


def run_case(image: bytes, *, width: int, height: int, x: int, y: int, pixels: list[int]) -> dict:
    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    machine.mem_map(BASE, 0x100000)
    machine.mem_write(BASE, image)
    machine.mem_map(0x18000000, 0x80000)
    machine.mem_write(SOURCE, struct.pack(f"<{len(pixels)}H", *pixels))
    machine.mem_write(DATA + 0x1CB, bytes([x, y, width, height]))
    machine.mem_write(DATA + 0x1D0, struct.pack("<I", SOURCE))
    machine.mem_write(DATA + 0x1C8, b"\x01")
    machine.reg_write(UC_ARM_REG_SP, 0x18070000)
    machine.reg_write(UC_ARM_REG_LR, STOP | 1)
    commands: list[int] = []
    transfers: list[str] = []
    allocations: list[int] = []
    frees: list[int] = []
    finished = False
    instructions = 0

    def hook(cpu: Uc, address: int, size: int, user_data: object) -> None:
        nonlocal finished, instructions
        instructions += 1
        if address == STOP:
            finished = True
            cpu.emu_stop()
            return
        if ENTRY <= address < END:
            return
        match address:
            case 0x100B959C:
                allocations.append(cpu.reg_read(UC_ARM_REG_R0))
                cpu.reg_write(UC_ARM_REG_R0, TEMP)
            case 0x100B958E:
                frees.append(cpu.reg_read(UC_ARM_REG_R0))
                cpu.reg_write(UC_ARM_REG_R0, 0)
            case 0x10027AD0:
                commands.append(cpu.reg_read(UC_ARM_REG_R1))
                cpu.reg_write(UC_ARM_REG_R0, 0)
            case 0x10027DC0:
                length = cpu.reg_read(UC_ARM_REG_R2)
                if not 1 <= length <= 200:
                    raise RuntimeError(f"Unexpected transfer length: {length}")
                transfers.append(bytes(cpu.mem_read(cpu.reg_read(UC_ARM_REG_R1), length)).hex())
                cpu.reg_write(UC_ARM_REG_R0, 0)
            case _:
                raise RuntimeError(f"Unexpected execution outside callback: {address:#x}")
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    machine.hook_add(UC_HOOK_CODE, hook)
    machine.emu_start(ENTRY | 1, STOP + 2, count=100000)
    if not finished:
        raise RuntimeError("Callback did not return within instruction budget")
    result = {
        "commands": commands,
        "transfers": transfers,
        "allocations": allocations,
        "frees": frees,
        "busy": bytes(machine.mem_read(DATA + 0x1C8, 1))[0] & 1,
    }
    return {"observed": result, "instructions": instructions}


def main(image_path: Path) -> None:
    image = image_path.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != IMAGE_SHA:
        raise typer.BadParameter("Requires the exact verified C261CF0430 FW010004 mapped image")
    # Goldens are hand-authored, not calculated with a copy of the pixel algorithm.
    cases = [
        {
            "name": "two_columns_top_bottom_and_second_row",
            "width": 2,
            "height": 8,
            "x": 3,
            "y": 0,
            "pixels": [1, 0, 0, 0xFFFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x8000, 0],
            "commands": [0xAF, 0xB0, 0x11, 0x0F],
            "transfers": ["408102"],
        },
        {
            "name": "second_source_page_and_nonzero_y",
            "width": 1,
            "height": 16,
            "x": 0,
            "y": 8,
            "pixels": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xFFFF],
            "commands": [0xAF, 0xB1, 0x11, 0x0C, 0xB2, 0x11, 0x0C],
            "transfers": ["4001", "4080"],
        },
        {
            "name": "unaligned_window_drops_tail_and_y_remainder",
            "width": 1,
            "height": 9,
            "x": 0,
            "y": 1,
            "pixels": [0, 0, 0, 0, 0, 0, 0, 0, 0xFFFF],
            "commands": [0xAF, 0xB0, 0x11, 0x0C],
            "transfers": ["4000"],
        },
    ]
    reports = []
    for case in cases:
        result = run_case(image, **{key: case[key] for key in ("width", "height", "x", "y", "pixels")})
        expected = {
            "commands": case["commands"],
            "transfers": case["transfers"],
            "allocations": [200],
            "frees": [TEMP],
            "busy": 0,
        }
        if result["observed"] != expected:
            raise RuntimeError(f"{case['name']}: expected {expected}, observed {result}")
        reports.append({"name": case["name"], **result})
    print(
        json.dumps(
            {
                "image_sha256": digest,
                "engine": "Unicorn 2.1.4 Thumb MCLASS",
                "scope": "Actual callback instructions, intercepted external calls; no hardware",
                "cases": reports,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
