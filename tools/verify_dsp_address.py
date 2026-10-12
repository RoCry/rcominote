#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["unicorn==2.1.4", "typer>=0.16,<1"]
# ///
"""Execute the actual ARM section loader with intercepted file I/O; no DSP execution."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from unicorn import (
    UC_ARCH_ARM,
    UC_HOOK_CODE,
    UC_HOOK_MEM_INVALID,
    UC_HOOK_MEM_READ,
    UC_HOOK_MEM_WRITE,
    UC_MEM_WRITE,
    UC_MODE_MCLASS,
    UC_MODE_THUMB,
    Uc,
)
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
STOP = 0x100E3000
MMIO = 0x400010C0


def verify(image: bytes, dsp: int, kind: int, length: int) -> dict:
    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    cpu.mem_map(0x10000000, 0x100000)
    cpu.mem_write(0x10000000, image)
    # Stub intercepted functions with BX LR, preserving normal Thumb return handling.
    for address in (0x1002EBF4, 0x1002EB5C, 0x1002EC40, 0x1009FF86):
        cpu.mem_write(address, b"\x70\x47")
    cpu.mem_map(0x18000000, 0x80000)
    cpu.mem_map(0x40001000, 0x1000)
    cpu.mem_write(MMIO, struct.pack("<I", 0xA5FF5A5A))
    for register, value in (
        (UC_ARM_REG_R0, FILE),
        (UC_ARM_REG_R1, 0x21C),
        (UC_ARM_REG_R2, kind),
        (UC_ARM_REG_SP, 0x18070000),
        (UC_ARM_REG_LR, STOP | 1),
    ):
        cpu.reg_write(register, value)
    reads = []
    accesses = []
    finished = False
    headers = 0
    instructions = 0
    faults = []
    trace = []

    def memory(machine: Uc, access: int, address: int, size: int, value: int, _: object) -> None:
        if address != MMIO or size != 4:
            raise RuntimeError(f"Unexpected MMIO access: {address:#x}/{size}")
        # Unicorn passes a value for writes only; record actual pre-read contents.
        observed = value if access == UC_MEM_WRITE else struct.unpack("<I", machine.mem_read(address, 4))[0]
        accesses.append(
            {"operation": "write" if access == UC_MEM_WRITE else "read", "value": f"0x{observed:08x}"}
        )

    def code(machine: Uc, address: int, size: int, _: object) -> None:
        nonlocal finished, headers, instructions
        instructions += 1
        trace.append(f"{address:#x}/{size} LR={machine.reg_read(UC_ARM_REG_LR):#x}")
        if address == STOP:
            finished = True
            machine.emu_stop()
            return
        if address == 0x1003C9CE:
            reads.append(
                {
                    "destination": f"0x{machine.reg_read(UC_ARM_REG_R1):08x}",
                    "bytes": machine.reg_read(UC_ARM_REG_R2),
                }
            )
            finished = True
            machine.emu_stop()
            return
        if 0x1003C914 <= address < 0x1003CA36:
            return
        args = [machine.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
        match address:
            case 0x1002EBF4:
                if args != [FILE, 0x21C, 0]:
                    raise RuntimeError(f"Unexpected seek: {args}")
                returned = 0
            case 0x1002EB5C:
                if args[0] != FILE:
                    raise RuntimeError(f"Unexpected file: {args}")
                if args[1] >= 0x18060000:
                    if args[2] != 8 or headers > 1:
                        raise RuntimeError(f"Unexpected header read: {args}")
                    machine.mem_write(args[1], struct.pack("<II", length, dsp) if headers == 0 else bytes(8))
                    headers += 1
                else:
                    raise RuntimeError("Payload read call site should stop execution")
                returned = args[2]
            case 0x1002EC40:
                returned = 0x224
            case 0x1009FF86:
                returned = 0
            case _:
                raise RuntimeError(f"Unexpected execution: {address:#x}")
        machine.reg_write(UC_ARM_REG_R0, returned)

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, memory, begin=0x40001000, end=0x40001FFF)

    def invalid(machine: Uc, access: int, address: int, size: int, value: int, _: object) -> bool:
        faults.append(
            f"Unexpected memory at DSP {dsp:#x}: {address:#x}/{size}, PC {machine.reg_read(UC_ARM_REG_PC):#x}"
        )
        return False

    cpu.hook_add(UC_HOOK_MEM_INVALID, invalid)
    try:
        cpu.emu_start(0x1003C915, STOP + 2, count=500)
    except Exception as error:
        raise RuntimeError(f"Section emulation failed: {faults}, {trace[-16:]}") from error
    if not finished:
        raise RuntimeError("Section loader failed to return within instruction budget")
    return {
        "dsp_address": f"0x{dsp:08x}",
        "kind": "code" if kind else "data",
        "section_bytes": length,
        "return": None if reads else cpu.reg_read(UC_ARM_REG_R0),
        "stop_reason": "intercepted payload read" if reads else "section loader returned",
        "payload_reads": reads,
        "mmio_address": f"0x{MMIO:08x}",
        "mmio_accesses": accesses,
        "instructions": instructions,
    }


def main(image_path: Path) -> None:
    image = image_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != SHA:
        raise typer.BadParameter("Requires exact verified FW010004 mapped image")
    # Literal hand-derived address/boundary oracles from actual instruction immediates.
    # They deliberately do not reuse an address-conversion implementation.
    cases = [
        ("actual_first_code", 0, 1, 5312, 0x01140000),
        ("actual_second_code", 0x40000000, 1, 8944, 0x01040000),
        ("ptcm_last", 0x1FFF, 1, 2, 0x01143FFE),
        ("ownership_last", 0xBFFF, 1, 2, 0x01057FFE),
        ("dtcm_first", 0, 0, 2, 0x01100000),
        ("data_c000_bank_fallback", 0xC000, 0, 2, 0x01058000),
        ("ext_last", 0x40017FFF, 1, 2, 0x0106FFFE),
        ("ext_end_rejected", 0x40018000, 1, 2, None),
        ("start_only_no_section_end_check", 0x1FFF, 1, 0x4000, 0x01143FFE),
    ]
    results = {}
    for name, dsp, kind, length, destination in cases:
        result = verify(image, dsp, kind, length)
        expected_reads = (
            [] if destination is None else [{"destination": f"0x{destination:08x}", "bytes": length}]
        )
        mmio_cases = {"actual_second_code", "ownership_last"}
        expected_mmio = (
            []
            if name not in mmio_cases
            else [
                {"operation": "read", "value": "0xa5ff5a5a"},
                {"operation": "write", "value": "0xa4af5a5a"},
            ]
        )
        expected_return = 0xFFFFFFF2 if destination is None else None
        if (
            result["payload_reads"] != expected_reads
            or result["return"] != expected_return
            or result["mmio_accesses"] != expected_mmio
        ):
            raise RuntimeError(f"{name} differs from literal oracle: {result}")
        results[name] = result
    print(
        json.dumps(
            {
                "image_sha256": SHA,
                "engine": "Unicorn 2.1.4 Thumb MCLASS",
                "executed_region": "0x1003c914..0x1003ca36",
                "scope": "Actual ARM section loader, synthetic section headers, intercepted seek/read/tell/log; MMIO backed by synthetic memory; success cases stop at first payload read",
                "limits": [
                    "No physical RAM capacity or ownership behavior measured",
                    "Payload read destinations observed; DSP payload bytes neither copied nor executed",
                    "Post-read MMIO restoration statically inspected only",
                    "No firmware write or device I/O",
                ],
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
