#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["unicorn==2.1.4", "typer>=0.16,<1"]
# ///
"""Verify original audio adapter instructions against hand-authored ABI fixtures; offline only."""

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
INPUT = 0x18010000
STOP = 0x100E3000
HANDLE = 0x18030000


def verify(image: bytes, *, channel: int) -> dict:
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x10000000, 0x100000)
    cpu.mem_write(0x10000000, image)
    cpu.mem_map(0x18000000, 0x80000)
    # Input oracle: 48 kHz enum, ADC key4000, gain -12, buffer2048, known callbacks.
    fixture = bytearray(28)
    fixture[2:4] = bytes([48, channel])
    struct.pack_into("<H", fixture, 4, 0x4000)
    struct.pack_into("<h", fixture, 10, -12)
    struct.pack_into("<HIII", fixture, 14, 2048, 0x18020000, 0x10001001, 0x18021000)
    cpu.mem_write(INPUT, bytes(fixture))
    cpu.mem_write(0x1800F728, struct.pack("<I", 0x100BA200))
    cpu.reg_write(UC_ARM_REG_R0, INPUT)
    cpu.reg_write(UC_ARM_REG_SP, 0x18070000)
    cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
    observed = []
    finished = False

    def hook(machine: Uc, address: int, size: int, user_data: object) -> None:
        nonlocal finished
        if address == STOP:
            finished = True
            machine.emu_stop()
            return
        if 0x1002ABB4 <= address < 0x1002AC30:
            return
        match address:
            case 0x100B96C8:
                start = machine.reg_read(UC_ARM_REG_R0)
                count = machine.reg_read(UC_ARM_REG_R2)
                if count != 20 or machine.reg_read(UC_ARM_REG_R1) != 0:
                    raise RuntimeError("Unexpected memset call")
                machine.mem_write(start, bytes(count))
            case 0x10038694:
                param = machine.reg_read(UC_ARM_REG_R1)
                raw = bytes(machine.mem_read(param, 36))
                adc = struct.unpack_from("<I", raw, 8)[0]
                observed.append(
                    {
                        "device": machine.reg_read(UC_ARM_REG_R0),
                        "rate": raw[0],
                        "channel": struct.unpack_from("<H", raw, 2)[0],
                        "width": struct.unpack_from("<I", raw, 4)[0],
                        "adc": list(struct.unpack("<H4h", bytes(machine.mem_read(adc, 10)))),
                        "callback": struct.unpack_from("<I", raw, 20)[0],
                        "context": struct.unpack_from("<I", raw, 24)[0],
                        "buffer": struct.unpack_from("<I", raw, 28)[0],
                        "length": struct.unpack_from("<I", raw, 32)[0],
                    }
                )
                machine.reg_write(UC_ARM_REG_R0, HANDLE)
            case 0x10055F90:
                machine.reg_write(UC_ARM_REG_R0, 0)
            case _:
                raise RuntimeError(f"Unexpected execution: {address:#x}")
        machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(0x1002ABB5, STOP + 2, count=10000)
    if not finished:
        raise RuntimeError("Adapter did not return within instruction budget")
    return {"open_calls": observed, "return": cpu.reg_read(UC_ARM_REG_R0)}


def main(image_path: Path) -> None:
    image = image_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact verified FW010004 mapped image")
    accepted = verify(image, channel=8)
    # Hand-authored ABI values; offsets are not used to derive this expected record.
    expected = {
        "open_calls": [
            {
                "device": 0x100BA200,
                "rate": 48,
                "channel": 8,
                "width": 0,
                "adc": [0x4000, -12, -12, -12, -12],
                "callback": 0x10001001,
                "context": 0x18021000,
                "buffer": 0x18020000,
                "length": 2048,
            }
        ],
        "return": HANDLE,
    }
    if accepted != expected:
        raise RuntimeError(f"ADC ABI mismatch: {accepted}")
    rejected = verify(image, channel=0x20)
    if rejected != {"open_calls": [], "return": 0}:
        raise RuntimeError(f"Unsupported channel reached open: {rejected}")
    print(
        json.dumps(
            {
                "image_sha256": SHA,
                "engine": "Unicorn 2.1.4 Thumb MCLASS",
                "scope": "Actual adapter; intercepted memset, log, ADC open; no hardware",
                "adc_fixture": accepted,
                "unsupported_fixture": rejected,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
