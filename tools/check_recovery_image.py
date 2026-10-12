#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["unicorn==2.1.4", "typer>=0.16,<1"]
# ///
"""Run CoMi's actual recovery checker offline, with no hardware or candidate execution."""

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
    UC_MEM_READ,
    UC_MODE_MCLASS,
    UC_MODE_THUMB,
    UC_PROT_EXEC,
    UC_PROT_READ,
    UC_PROT_WRITE,
    Uc,
    UcError,
)
from unicorn.arm_const import (
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_SP,
)

RECOVERY_SHA = "19625b7b70eb8e4a91c889792c0ca383f51ea205629e67565b59c47d15e09906"
IMAGE_BASE = 0x10000000
RAM_BASE = 0x18000000
IMAGE_SOURCE = 0xE098
CODE_START = RAM_BASE + 0xE8
CODE_END = RAM_BASE + 0x20C
POOL_END = RAM_BASE + 0x218
CHECKER = RAM_BASE + 0x100
DIAGNOSTIC = RAM_BASE + 0x78
GLOBAL_SP = RAM_BASE + 0x18DC
# Synthetic oracle workspace, not proposed device RAM allocations.
STACK_TOP = 0x20001000
STACK_BOTTOM = STACK_TOP - 256
ENTRY_OUT = 0x20001000
RETURN_TRAP = 0x20002000
INITIAL_ENTRY_OUT = 0x1100000F  # Old mapping-shaped sentinel; not live register state.
MAX_IMAGE_BYTES = 2 * 1024 * 1024
INSTRUCTION_BUDGET = 4_000_000
TIMEOUT_US = 15_000_000


class ModelError(RuntimeError):
    """The bounded model cannot represent this execution; not a checker rejection."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contained(address: int, size: int, start: int, end: int) -> bool:
    return size > 0 and start <= address and address + size <= end


def check_image(recovery: bytes, candidate: bytes) -> dict:
    """Return actual r0/output values; model errors raise instead of inventing a result."""
    if len(recovery) != 63288 or digest(recovery) != RECOVERY_SHA:
        raise ValueError("Requires the exact complete checksum-verified decoded CoMi recovery")
    if not 0 < len(candidate) <= MAX_IMAGE_BYTES:
        raise ValueError("Candidate must contain 1..2097152 bytes (offline model bound)")

    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    candidate_pages = (len(candidate) + 4095) & ~4095
    cpu.mem_map(IMAGE_BASE, candidate_pages, UC_PROT_READ)
    cpu.mem_write(IMAGE_BASE, candidate)
    cpu.mem_map(RAM_BASE, 4096, UC_PROT_READ | UC_PROT_EXEC)
    cpu.mem_write(CODE_START, recovery[IMAGE_SOURCE + 0xE8 : IMAGE_SOURCE + 0x218])
    cpu.mem_map(RAM_BASE + 0x1000, 4096, UC_PROT_READ | UC_PROT_WRITE)
    cpu.mem_map(0x20000000, 8192, UC_PROT_READ | UC_PROT_WRITE)
    cpu.mem_map(RETURN_TRAP, 4096, UC_PROT_READ | UC_PROT_EXEC)
    cpu.mem_write(RETURN_TRAP, b"\x00\xbf")  # Stopped by hook before execution.
    cpu.mem_write(ENTRY_OUT, struct.pack("<I", INITIAL_ENTRY_OUT))
    for register, value in (
        (UC_ARM_REG_SP, STACK_TOP),
        (UC_ARM_REG_LR, RETURN_TRAP | 1),
        (UC_ARM_REG_R0, IMAGE_BASE),
        (UC_ARM_REG_R1, ENTRY_OUT),
        (UC_ARM_REG_R2, 0),  # Exact observed handoff caller; no invented size limit.
    ):
        cpu.reg_write(register, value)

    instructions = 0
    returned = False
    diagnostics = []
    input_read_end = IMAGE_BASE

    def code(machine: Uc, address: int, size: int, _data: object) -> None:
        nonlocal instructions, returned
        if address == RETURN_TRAP:
            if machine.reg_read(UC_ARM_REG_SP) != STACK_TOP:
                raise ModelError("Checker returned without restoring its synthetic stack")
            returned = True
            machine.emu_stop()
            return
        instructions += 1
        if instructions > INSTRUCTION_BUDGET:
            raise ModelError("Checker instruction budget exhausted")
        if address == DIAGNOSTIC:
            diagnostics.append(machine.reg_read(UC_ARM_REG_R0))
            target = machine.reg_read(UC_ARM_REG_LR)
            if not target & 1 or not CODE_START <= (target & ~1) < CODE_END:
                raise ModelError(f"Unexpected diagnostic return target {target:#x}")
            machine.reg_write(UC_ARM_REG_PC, target)
        elif address & 1 or not contained(address, size, CODE_START, CODE_END):
            raise ModelError(f"Execution outside checker/sum whitelist: {address:#x}+{size}")

    def memory(machine: Uc, access: int, address: int, size: int, value: int, _data: object) -> None:
        nonlocal input_read_end
        writable = any(
            contained(address, size, start, end)
            for start, end in (
                (STACK_BOTTOM, STACK_TOP),
                (ENTRY_OUT, ENTRY_OUT + 4),
                (GLOBAL_SP, GLOBAL_SP + 4),
            )
        )
        if access == UC_MEM_READ:
            if contained(address, size, IMAGE_BASE, IMAGE_BASE + len(candidate)):
                input_read_end = max(input_read_end, address + size)
                return
            if contained(address, size, CODE_END, POOL_END):
                return
        if not writable:
            kind = "read" if access == UC_MEM_READ else "write"
            raise ModelError(
                f"Out-of-contract {kind} at {address:#x}+{size}, pc={machine.reg_read(UC_ARM_REG_PC):#x}"
            )

    def invalid(machine: Uc, access: int, address: int, size: int, value: int, _data: object) -> bool:
        raise ModelError(
            f"Unmapped/protected access {access} at {address:#x}+{size}, "
            f"pc={machine.reg_read(UC_ARM_REG_PC):#x}"
        )

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, memory)
    cpu.hook_add(UC_HOOK_MEM_INVALID, invalid)
    try:
        cpu.emu_start(CHECKER | 1, RETURN_TRAP + 2, timeout=TIMEOUT_US, count=INSTRUCTION_BUDGET + 1)
    except UcError as error:
        raise ModelError(f"Unicorn could not execute the bounded checker: {error}") from error
    if not returned:
        raise ModelError("Checker did not return within instruction/time budget")
    unsigned_rc = cpu.reg_read(UC_ARM_REG_R0)
    rc = unsigned_rc if unsigned_rc < 0x80000000 else unsigned_rc - 0x100000000
    return {
        "recovery_decoded_sha256": RECOVERY_SHA,
        "candidate_sha256": digest(candidate),
        "candidate_bytes": len(candidate),
        "rc": rc,
        "accepted_by_local_checker": rc == 0,
        "entry_out_initial": hex(INITIAL_ENTRY_OUT),
        "entry_out": hex(struct.unpack("<I", bytes(cpu.mem_read(ENTRY_OUT, 4)))[0]),
        "global_sp": hex(struct.unpack("<I", bytes(cpu.mem_read(GLOBAL_SP, 4)))[0]),
        "diagnostic_args": [hex(value) for value in diagnostics],
        "instructions": instructions,
        "input_read_end_exclusive": hex(input_read_end),
        "model": {
            "engine": "Unicorn 2.1.4 ARM Thumb MCLASS",
            "entry": hex(CHECKER | 1),
            "size_limit_argument": 0,
            "code_range": [hex(CODE_START), hex(CODE_END)],
            "literal_range": [hex(CODE_END), hex(POOL_END)],
            "input": "Read-only, exact file extent; mapped-page padding inaccessible",
            "workspace": "Synthetic 256-byte stack, four-byte entry_out and global180018dc only",
            "only_interception": "18000078: record r0, return to LR; actual helper formats a hex diagnostic",
            "instruction_budget": INSTRUCTION_BUDGET,
            "timeout_us": TIMEOUT_US,
            "limits": "No candidate execution, mapping/preparation helpers, ROM, MMIO, UART or hardware state; "
            "local acceptance does not establish boot authorization, usable stack, execution or recovery",
        },
    }


def main(recovery: Path, candidate: Path) -> None:
    """Inspect DECODED recovery against CANDIDATE CPU-visible bytes, entirely offline.

    Rejections emit JSON and exit 1; model/input errors emit stderr and exit 2.
    """
    try:
        report = check_image(recovery.read_bytes(), candidate.read_bytes())
    except (OSError, ValueError, ModelError) as error:
        typer.echo(f"Oracle error: {error}", err=True)
        raise typer.Exit(code=2) from error
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["accepted_by_local_checker"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
