#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["unicorn==2.1.4", "typer>=0.16,<1"]
# ///
"""Execute original sd_fread against short-file and read-failure oracles; no hardware."""

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
    UC_ARM_REG_R3,
    UC_ARM_REG_SP,
)

SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
FILE = 0x18010000
BUFFER = 0x18020000
DEVICE = 0x18030000
STOP = 0x100E3000


def verify(image: bytes, *, failure: bool) -> list[dict]:
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x10000000, 0x100000)
    cpu.mem_write(0x10000000, image)
    cpu.mem_map(0x18000000, 0x80000)
    # Hand-authored file: start 0x240100, length 5, cursor two bytes into file,
    # storage NOR=0, explicit partition K=10. No directory or flash emulated.
    cpu.mem_write(FILE, struct.pack("<III4B", 0x240100, 5, 0x240102, 0, 10, 0, 0))
    cpu.mem_write(0x1800E000, struct.pack("<I", DEVICE))
    cpu.mem_write(BUFFER, b"????????")
    calls: list[dict] = []
    finished = False

    def hook(machine: Uc, address: int, size: int, user_data: object) -> None:
        nonlocal finished
        if address == STOP:
            finished = True
            machine.emu_stop()
            return
        if 0x100267EC <= address < 0x10026848:
            return
        if address == 0x100A1B94:
            call = {
                "device": machine.reg_read(UC_ARM_REG_R0),
                "offset": machine.reg_read(UC_ARM_REG_R1),
                "buffer": machine.reg_read(UC_ARM_REG_R2),
                "length": machine.reg_read(UC_ARM_REG_R3),
            }
            # Oracle is the independently specified five-byte file and cursor.
            if call != {"device": DEVICE, "offset": 0x240102, "buffer": BUFFER, "length": 3}:
                raise RuntimeError(f"Unexpected flash request: {call}")
            calls.append(call)
            if not failure:
                machine.mem_write(BUFFER, b"XYZ")
            machine.reg_write(UC_ARM_REG_R0, 0xFFFFFFFB if failure else 0)
        elif address == 0x1009FF86:
            if not failure:
                raise RuntimeError("Unexpected error log on successful read")
            machine.reg_write(UC_ARM_REG_R0, 0)
        else:
            raise RuntimeError(f"Unexpected execution: {address:#x}")
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    results = []
    # The second call reuses the actual cursor written by the first call.
    for _ in range(2):
        finished = False
        before = len(calls)
        cpu.reg_write(UC_ARM_REG_R0, FILE)
        cpu.reg_write(UC_ARM_REG_R1, BUFFER)
        cpu.reg_write(UC_ARM_REG_R2, 8)
        cpu.reg_write(UC_ARM_REG_SP, 0x18070000)
        cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
        cpu.emu_start(0x100267ED, STOP + 2, count=1000)
        if not finished:
            raise RuntimeError("sd_fread did not return within instruction budget")
        results.append(
            {
                "return": cpu.reg_read(UC_ARM_REG_R0),
                "cursor": struct.unpack("<I", bytes(cpu.mem_read(FILE + 8, 4)))[0],
                "buffer": bytes(cpu.mem_read(BUFFER, 8)).decode("ascii"),
                "flash_calls": len(calls) - before,
            }
        )
    return results


def main(image_path: Path) -> None:
    image = image_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact verified FW010004 mapped image")
    success = verify(image, failure=False)
    expected = [
        {"return": 3, "cursor": 0x240105, "buffer": "XYZ?????", "flash_calls": 1},
        {"return": 0, "cursor": 0x240105, "buffer": "XYZ?????", "flash_calls": 0},
    ]
    if success != expected:
        raise RuntimeError(f"Short-file/EOF mismatch: {success}")
    failure = verify(image, failure=True)
    expected_failure = [
        {"return": 0, "cursor": 0x240102, "buffer": "????????", "flash_calls": 1},
        {"return": 0, "cursor": 0x240102, "buffer": "????????", "flash_calls": 1},
    ]
    if failure != expected_failure:
        raise RuntimeError(f"Read-failure/retry mismatch: {failure}")
    print(
        json.dumps(
            {
                "image_sha256": SHA,
                "engine": "Unicorn 2.1.4 Thumb MCLASS",
                "scope": "Actual sd_fread; flash and logging intercepted; no hardware or DSP data",
                "short_file_then_eof": success,
                "failed_read_then_retry": failure,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
