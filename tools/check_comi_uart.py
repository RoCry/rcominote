#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["unicorn==2.1.4", "pyelftools==0.32", "typer>=0.16,<1"]
# ///
"""Compile an owned UART fragment and compare MMIO traces with actual firmware offline."""

import hashlib
import json
import struct
import subprocess
from pathlib import Path

import typer
from elftools.elf.elffile import ELFFile
from unicorn import UC_ARCH_ARM, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MODE_MCLASS, UC_MODE_THUMB, Uc
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parents[1]
IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
OWN_BASE, RETURN, OUTPUT = 0x01020000, 0x01021000, 0x01022000
UART, DEVICE = 0x40038000, 0x100B9F60


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def emulate(
    image: bytes,
    own: bytes,
    entry: int,
    args: tuple[int, int],
    *,
    receive: bool,
    ready_after: int | None,
    received_word: int = 0x1234ABCD,
):
    engine = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    engine.mem_map(0x10000000, 0x100000)
    engine.mem_write(0x10000000, image)
    engine.mem_map(OWN_BASE, 0x4000)
    engine.mem_write(OWN_BASE, own)
    engine.mem_write(OUTPUT, b"\xee")
    engine.mem_map(UART, 0x1000)
    engine.mem_write(UART + 4, struct.pack("<I", received_word))
    reads, writes = [], []

    def read_hook(cpu, _access, address, size, _value, _context):
        if address == UART + 12:
            blocked = ready_after is None or len(reads) < ready_after
            status = (32 if receive else 64) if blocked else 0
            cpu.mem_write(address, struct.pack("<I", status))
            reads.append(status)
        elif UART <= address < UART + 0x1000 and address != UART + 4:
            raise ValueError(f"Unexpected MMIO read: {address:x}/{size}")

    def write_hook(_cpu, _access, address, size, value, _context):
        if UART <= address < UART + 0x1000:
            if address != UART + 8 or size != 4:
                raise ValueError(f"Unexpected MMIO write: {address:x}/{size}")
            writes.append(value)

    engine.hook_add(UC_HOOK_MEM_READ, read_hook)
    engine.hook_add(UC_HOOK_MEM_WRITE, write_hook)
    for register, value in (
        (UC_ARM_REG_R0, args[0]),
        (UC_ARM_REG_R1, args[1]),
        (UC_ARM_REG_SP, OWN_BASE + 0x3FF0),
        (UC_ARM_REG_LR, RETURN | 1),
    ):
        engine.reg_write(register, value)
    engine.emu_start(entry | 1, RETURN, count=1000)
    return {
        "returned": engine.reg_read(UC_ARM_REG_PC) == RETURN,
        "r0": engine.reg_read(UC_ARM_REG_R0),
        "status_reads": reads,
        "tx_writes": writes,
        "output": bytes(engine.mem_read(OUTPUT, 1)).hex(),
    }


def main(toolchain: Path, image: Path, output: Path):
    raw = image.read_bytes()
    if digest(raw) != IMAGE_SHA:
        raise ValueError("Wrong actual CoMi system image")
    if struct.unpack_from("<2I", raw, DEVICE + 4 - 0x10000000) != (0x100BC0F0, 0x100BC128):
        raise ValueError("UART0 descriptor changed")
    if (
        struct.unpack_from("<I", raw, 0xBC0F4)[0] != UART
        or struct.unpack_from("<I", raw, 0xBC104)[0] != 2000000
    ):
        raise ValueError("UART0 base/default baud changed")
    if struct.unpack_from("<2I", raw, 0xBC128) != (0x100A4317, 0x100A4329):
        raise ValueError("Actual polling API changed")
    compiler = toolchain.resolve() / "bin/arm-none-eabi-gcc"
    version = subprocess.check_output([str(compiler), "--version"], text=True).splitlines()[0]
    if "10.3.1" not in version:
        raise ValueError("Expected previously verified Arm GNU10.3.1 compiler")
    output.mkdir(parents=True, exist_ok=False)
    elf = output / "comi_uart.elf"
    command = [
        str(compiler),
        "-mcpu=cortex-m4",
        "-mthumb",
        "-mfloat-abi=soft",
        "-ffreestanding",
        "-fno-builtin",
        "-Os",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wpedantic",
        "-nostdlib",
        "-Wl,--build-id=none,-Ttext=0x01020000,-e,comi_uart0_putc",
        str(ROOT / "firmware/board/comi_uart.c"),
        "-o",
        str(elf),
    ]
    subprocess.run(command, check=True, capture_output=True)
    with elf.open("rb") as stream:
        parsed = ELFFile(stream)
        section = parsed.get_section_by_name(".text")
        if section["sh_addr"] != OWN_BASE:
            raise ValueError("Unexpected owned code placement")
        own = section.data()
        symbols = {s.name: s["st_value"] for s in parsed.get_section_by_name(".symtab").iter_symbols()}
    cases = []
    for receive in (False, True):
        for delay in (0, 1, 7):
            for value in (0, 1, 127, 128, 255):
                original_args = (DEVICE, OUTPUT if receive else value)
                owned_args = (OUTPUT if receive else value, 8)
                original = emulate(
                    raw,
                    own,
                    0x100A4316 if receive else 0x100A4328,
                    original_args,
                    receive=receive,
                    ready_after=delay,
                    received_word=0x12340000 | value,
                )
                owned = emulate(
                    raw,
                    own,
                    symbols["comi_uart0_getc" if receive else "comi_uart0_putc"],
                    owned_args,
                    receive=receive,
                    ready_after=delay,
                    received_word=0x12340000 | value,
                )
                if not original["returned"] or not owned["returned"] or owned["r0"] != 0:
                    raise ValueError("Ready UART path failed to return success")
                if any(original[k] != owned[k] for k in ("status_reads", "tx_writes", "output")):
                    raise ValueError("Owned UART behavior differs from independent actual-code oracle")
                cases.append({"receive": receive, "ready_after": delay, "value": value, "trace": owned})
    for receive in (False, True):
        entry = symbols["comi_uart0_getc" if receive else "comi_uart0_putc"]
        args = (OUTPUT if receive else 0xA5, 8)
        result = emulate(raw, own, entry, args, receive=receive, ready_after=None)
        if not result["returned"] or result["r0"] != 0xFFFFFFFF or len(result["status_reads"]) != 8:
            raise ValueError("Owned timeout did not terminate at exact poll budget")
        if result["tx_writes"] or result["output"] != "ee":
            raise ValueError("Timeout changed data")
        cases.append({"receive": receive, "case": "blocked-timeout", "trace": result})
        invalid = emulate(raw, own, entry, (args[0], 0), receive=receive, ready_after=0)
        if not invalid["returned"] or invalid["r0"] != 0xFFFFFFFE or invalid["status_reads"]:
            raise ValueError("Invalid budget must fail before MMIO")
        cases.append({"receive": receive, "case": "invalid-budget", "trace": invalid})
    invalid_pointer = emulate(raw, own, symbols["comi_uart0_getc"], (0, 8), receive=True, ready_after=0)
    if (
        not invalid_pointer["returned"]
        or invalid_pointer["r0"] != 0xFFFFFFFE
        or invalid_pointer["status_reads"]
    ):
        raise ValueError("Null RX output must fail before MMIO")
    cases.append({"receive": True, "case": "null-output", "trace": invalid_pointer})
    report = {
        "scope": "Offline M4 CPU model and synthetic MMIO only; no device or board bring-up",
        "image_sha256": IMAGE_SHA,
        "compiler": version,
        "command": command,
        "source_sha256": {
            n: digest((ROOT / "firmware/board" / n).read_bytes()) for n in ("comi_uart.c", "comi_uart.h")
        },
        "own_elf_sha256": digest(elf.read_bytes()),
        "own_text_hex": own.hex(),
        "raw_regions": [
            {"address": hex(a), "bytes": raw[a - 0x10000000 : b - 0x10000000].hex()}
            for a, b in (
                (0x100A4316, 0x100A4328),
                (0x100A4328, 0x100A4336),
                (0x100BC0F0, 0x100BC10C),
                (0x100BC128, 0x100BC130),
                (0x1002FB84, 0x1002FBD0),
                (0x100BBF2C, 0x100BBF3C),
            )
        ],
        "cases": cases,
        "limits": [
            "UART clock/mux/baud/CTRL initialization not implemented or modeled",
            "No assumption about CoMi accessible pads/voltage",
            "Poll budget is not elapsed time",
            "Owned fragment not linked into minimal fixture or uploaded",
        ],
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    (output / "report.json").write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    typer.run(main)
