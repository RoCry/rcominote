#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["unicorn==2.1.4", "typer>=0.16,<1"]
# ///
"""Run original CDC init and string registrar; stub file/string helpers and USB calls; never touch hardware."""

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
STOP = 0x100E3000


def main(image_path: Path) -> None:
    image = image_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact verified FW010004 mapped image")
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x10000000, 0x100000)
    cpu.mem_write(0x10000000, image)
    cpu.mem_map(0x18000000, 0x80000)
    # Synthetic device object with RAM data, no hardware or real device pointers.
    cpu.mem_write(0x18010010, struct.pack("<I", 0x18020000))
    cpu.reg_write(UC_ARM_REG_R0, 0x18010000)
    cpu.reg_write(UC_ARM_REG_SP, 0x18070000)
    cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
    registrations = []
    operations = []
    finished = False

    def hook(machine: Uc, address: int, size: int, user_data: object) -> None:
        nonlocal finished
        if address == STOP:
            finished = True
            machine.emu_stop()
            return
        if address == 0x1009A20C:
            ptr = machine.reg_read(UC_ARM_REG_R1)
            registrations.append(
                {
                    "index": machine.reg_read(UC_ARM_REG_R0),
                    "string": bytes(machine.mem_read(ptr, 20)).split(b"\0")[0].decode("ascii"),
                    "length": machine.reg_read(UC_ARM_REG_R2),
                }
            )
        if address == 0x1009A200:
            operations.append(
                {"descriptors": [machine.reg_read(UC_ARM_REG_R0), machine.reg_read(UC_ARM_REG_R1)]}
            )
        if (
            0x1009A5E0 <= address < 0x1009A6F2
            or 0x1009A200 <= address < 0x1009A208
            or 0x1009A20C <= address < 0x1009A2A6
        ):
            return
        if address == 0x10000CDC:
            ptr = machine.reg_read(UC_ARM_REG_R0)
            value = bytes(machine.mem_read(ptr, 20)).split(b"\0")[0]
            if value not in (b"Actions", b"CDC-ACM-DEV", b"0123456789A"):
                raise RuntimeError(f"Unexpected strlen input: {value!r}")
            machine.reg_write(UC_ARM_REG_R0, len(value))
        elif address == 0x100B966E:
            dest = machine.reg_read(UC_ARM_REG_R0)
            source = machine.reg_read(UC_ARM_REG_R1)
            length = machine.reg_read(UC_ARM_REG_R2)
            if not 0 < length <= 20:
                raise RuntimeError("Unexpected checked-copy length")
            machine.mem_write(dest, bytes(machine.mem_read(source, length)))
        elif address == 0x10036A88:
            key = bytes(machine.mem_read(machine.reg_read(UC_ARM_REG_R0), 7))
            if key != b"BT_MAC\0" or machine.reg_read(UC_ARM_REG_R2) != 20:
                raise RuntimeError("Unexpected NVRAM request")
            machine.reg_write(UC_ARM_REG_R0, 0xFFFFFFFE)
        elif address in (0x1009A2D0, 0x1009A324):
            operations.append({"stub": hex(address), "config": machine.reg_read(UC_ARM_REG_R0)})
            machine.reg_write(UC_ARM_REG_R0, 0)
        elif address == 0x100B8C8E or address == 0x10055F90:
            machine.reg_write(UC_ARM_REG_R0, 0)
        else:
            raise RuntimeError(f"Unexpected execution (USB operations forbidden): {address:#x}")
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(0x1009A5E1, STOP + 2, count=1000)
    if not finished:
        raise RuntimeError("CDC init did not return within instruction budget")
    result = {"return": cpu.reg_read(UC_ARM_REG_R0), "registrations": registrations}
    # Independent descriptor/API oracle: manufacturer=1, product=2, serial=3.
    expected = [
        {"index": 1, "string": "Actions", "length": 7},
        {"index": 2, "string": "CDC-ACM-DEV", "length": 11},
        {"index": 3, "string": "0123456789A", "length": 11},
    ]
    if result != {"return": 0, "registrations": expected}:
        raise RuntimeError(f"Unexpected CDC init result: {result}")
    if operations != [
        {"descriptors": [0x100DCD4A, 0x100DCDA7]},
        {"stub": "0x1009a2d0", "config": 0x100BF968},
        {"stub": "0x1009a324", "config": 0x100BF968},
    ]:
        raise RuntimeError(f"Unexpected registration/enable order: {operations}")
    print(
        json.dumps(
            {
                "image_sha256": SHA,
                "engine": "Unicorn 2.1.4 Thumb MCLASS",
                "scope": "Actual CDC init/registrar; synthetic state; missing BT_MAC; helper and USB results stubbed",
                "limits": "No USB/MMIO execution; does not prove this path was invoked on the connected device",
                "result": result,
                "operations": operations,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
