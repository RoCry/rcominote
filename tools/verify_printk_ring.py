#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["unicorn==2.1.4", "typer>=0.16,<1"]
# ///
"""Execute original printk cbuf functions against retention/wrap oracles; no hardware."""

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
CBUF = 0x1800E008
DMA = 0x1800E024
BUFFER = 0x1803EE09
SOURCE = 0x18020000
STOP = 0x100E3000


def verify(image: bytes, *, wrap: bool) -> dict:
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x10000000, 0x100000)
    cpu.mem_write(0x10000000, image)
    cpu.mem_map(0x18000000, 0x80000)
    cpu.mem_write(BUFFER, b"?" * 4096)
    cpu.mem_write(SOURCE, b"ABCDEF")
    finished = False
    instructions = 0
    copies = []

    def hook(machine: Uc, address: int, size: int, user_data: object) -> None:
        nonlocal finished, instructions
        instructions += 1
        if address == STOP:
            finished = True
            machine.emu_stop()
        elif 0x100A1D3C <= address < 0x100A1E30:
            pass
        elif address == 0x100B9652:
            dst = machine.reg_read(UC_ARM_REG_R0)
            src = machine.reg_read(UC_ARM_REG_R1)
            length = machine.reg_read(UC_ARM_REG_R2)
            if not (SOURCE <= src < SOURCE + 6 and src + length <= SOURCE + 6):
                raise RuntimeError(f"Unexpected memcpy source: {src:#x}, {length}")
            if not (BUFFER <= dst < BUFFER + 4096 and dst + length <= BUFFER + 4096):
                raise RuntimeError(f"Unexpected memcpy destination: {dst:#x}, {length}")
            copies.append({"destination": dst, "source": src, "length": length})
            machine.mem_write(dst, bytes(machine.mem_read(src, length)))
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))
        else:
            raise RuntimeError(f"Unexpected execution: {address:#x}")

    cpu.hook_add(UC_HOOK_CODE, hook)

    def call(address: int, r0: int, r1: int, r2: int = 0) -> int:
        nonlocal finished
        finished = False
        cpu.reg_write(UC_ARM_REG_R0, r0)
        cpu.reg_write(UC_ARM_REG_R1, r1)
        cpu.reg_write(UC_ARM_REG_R2, r2)
        cpu.reg_write(UC_ARM_REG_SP, 0x18070000)
        cpu.reg_write(UC_ARM_REG_LR, STOP | 1)
        cpu.emu_start(address | 1, STOP + 2, count=1000)
        if not finished:
            raise RuntimeError(f"Function {address:#x} exceeded instruction budget")
        return cpu.reg_read(UC_ARM_REG_R0)

    def state() -> list[int]:
        return list(struct.unpack("<5I", bytes(cpu.mem_read(CBUF, 20))))

    call(0x100A1E14, CBUF, BUFFER, 4096)
    initial = state()
    if initial != [0, 0, 0, 4096, BUFFER]:
        raise RuntimeError(f"Initialization mismatch: {initial}")
    if wrap:
        # Empty ring positioned two bytes before its physical end, hand-authored.
        cpu.mem_write(CBUF, struct.pack("<3I", 4094, 4094, 0))
    written = call(0x100A1DA6, CBUF, SOURCE, 6)
    after_write = state()
    preserved = bytes(cpu.mem_read(BUFFER, 4096))
    dma_steps = []
    for length in [6, 4] if wrap else [6]:
        returned = call(0x100A1D58, CBUF, DMA, length)
        pointer, dma_length = struct.unpack("<2I", bytes(cpu.mem_read(DMA, 8)))
        data = bytes(cpu.mem_read(pointer, dma_length)).decode("ascii")
        call(0x100A1D8A, CBUF, dma_length)
        dma_steps.append(
            {"return": returned, "source": pointer, "length": dma_length, "text": data, "state": state()}
        )
    if bytes(cpu.mem_read(BUFFER, 4096)) != preserved:
        raise RuntimeError("DMA selection/consumption changed ring payload")
    return {
        "initial": initial,
        "write_return": written,
        "after_write": after_write,
        "head": preserved[:6].decode("ascii"),
        "tail": preserved[-2:].decode("ascii"),
        "dma_steps": dma_steps,
        "payload_preserved": True,
        "memcpy_calls": copies,
        "instructions": instructions,
    }


def main(image_path: Path) -> None:
    image = image_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact verified FW010004 mapped image")
    normal = verify(image, wrap=False)
    wrapped = verify(image, wrap=True)
    # Hand-computed six-byte sequence in a 4096-byte ring; no production formula
    # generates expected indexes, split lengths, or retained byte strings.
    normal_expected = {
        "initial": [0, 0, 0, 4096, BUFFER],
        "write_return": 6,
        "after_write": [0, 6, 6, 4096, BUFFER],
        "head": "ABCDEF",
        "tail": "??",
        "dma_steps": [
            {"return": 6, "source": BUFFER, "length": 6, "text": "ABCDEF", "state": [6, 6, 0, 4096, BUFFER]}
        ],
        "payload_preserved": True,
        "memcpy_calls": [{"destination": BUFFER, "source": SOURCE, "length": 6}],
    }
    wrapped_expected = {
        "initial": [0, 0, 0, 4096, BUFFER],
        "write_return": 6,
        "after_write": [4094, 4, 6, 4096, BUFFER],
        "head": "CDEF??",
        "tail": "AB",
        "dma_steps": [
            {
                "return": 6,
                "source": 0x1803FE07,
                "length": 2,
                "text": "AB",
                "state": [4096, 4, 4, 4096, BUFFER],
            },
            {"return": 4, "source": BUFFER, "length": 4, "text": "CDEF", "state": [4, 4, 0, 4096, BUFFER]},
        ],
        "payload_preserved": True,
        "memcpy_calls": [
            {"destination": 0x1803FE07, "source": SOURCE, "length": 2},
            {"destination": BUFFER, "source": 0x18020002, "length": 4},
        ],
    }
    for name, actual, expected in [("normal", normal, normal_expected), ("wrap", wrapped, wrapped_expected)]:
        if {key: value for key, value in actual.items() if key != "instructions"} != expected:
            raise RuntimeError(f"{name} oracle mismatch: {actual}")
    print(
        json.dumps(
            {
                "image_sha256": SHA,
                "engine": "Unicorn 2.1.4 Thumb MCLASS",
                "scope": "Actual cbuf init/write/DMA-read/consume; memcpy intercepted; no UART, flash, or hardware",
                "normal": normal,
                "wrap": wrapped,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
