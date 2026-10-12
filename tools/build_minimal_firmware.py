#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["pyelftools==0.32", "typer>=0.16,<1"]
# ///
"""Build an offline M4/ACTH image fixture. No SDK, device, encoding or flash I/O."""

import hashlib
import json
import struct
import subprocess
from pathlib import Path

import typer
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "firmware/minimal"
BASE = 0x10000000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Build tool failed ({error.returncode}): {command[0]}\n{error.output}") from error


def wrap(body: bytes, entry: int) -> bytes:
    if len(body) % 4:
        raise ValueError("Compiler body must be word aligned")
    header = bytearray(512)
    body_sum = sum(word for (word,) in struct.iter_unpack("<I", body)) & 0xFFFFFFFF
    struct.pack_into(
        "<III8sIIIIHHHHI7sB",
        header,
        0,
        0x48544341,
        0x41435448,
        BASE,
        b"RCOMI4",
        entry,
        len(body),
        0xFFFFFFFF - body_sum,
        0,
        512,
        0,
        0,
        1,
        0,
        b"",
        0,
    )
    header_sum = sum(word for (word,) in struct.iter_unpack("<I", header)) & 0xFFFFFFFF
    struct.pack_into("<I", header, 0x20, 0xFFFFFFFF - header_sum)
    return bytes(header) + body


def main(toolchain: Path, out: Path):
    compiler = toolchain.resolve() / "bin/arm-none-eabi-gcc"
    version = run([str(compiler), "--version"]).splitlines()[0]
    if "10.3.1" not in version:
        raise ValueError(f"Requires the previously verified GNU Arm10.3.1 toolchain, got {version}")
    out.mkdir(parents=True, exist_ok=False)
    out = out.resolve()
    elf = out / "minimal.elf"
    command = [
        str(compiler),
        "-mcpu=cortex-m4",
        "-mthumb",
        "-mfloat-abi=soft",
        "-ffreestanding",
        "-fno-builtin",
        "-fno-common",
        "-fno-unwind-tables",
        "-fno-asynchronous-unwind-tables",
        "-ffunction-sections",
        "-fdata-sections",
        "-Os",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-nostdlib",
        "-Wl,--build-id=none,--gc-sections",
        f"-Wl,-Map={out / 'minimal.map'}",
        f"-T{SOURCE / 'linker.ld'}",
        str(SOURCE / "startup.S"),
        str(SOURCE / "main.c"),
        "-o",
        str(elf),
    ]
    log = run(command)
    (out / "build.log").write_text(log)
    attributes = run([str(compiler.with_name("arm-none-eabi-readelf")), "-A", str(elf)])
    if "Tag_CPU_arch: v7E-M" not in attributes or "Tag_ABI_VFP_args: VFP registers" in attributes:
        raise ValueError("Unexpected compiler CPU/float ABI attributes")
    (out / "attributes.txt").write_text(attributes)
    (out / "disassembly.txt").write_text(
        run([str(compiler.with_name("arm-none-eabi-objdump")), "-d", str(elf)])
    )
    body_path = out / "minimal-body.bin"
    run([str(compiler.with_name("arm-none-eabi-objcopy")), "-O", "binary", str(elf), str(body_path)])
    body = body_path.read_bytes()
    with elf.open("rb") as handle:
        parsed = ELFFile(handle)
        entry = parsed.header["e_entry"]
        symbols = {
            symbol.name: symbol.entry["st_value"]
            for symbol in parsed.get_section_by_name(".symtab").iter_symbols()
        }
        vectors = parsed.get_section_by_name(".vectors")
        if vectors.header["sh_addr"] != BASE + 512 or len(vectors.data()) != 320:
            raise ValueError("Unexpected vector placement")
        sp, vector_entry = struct.unpack_from("<II", body)
        if (sp, vector_entry) != (0x01002B40, entry) or not entry & 1:
            raise ValueError("ELF entry and independent observed vector/SP contract differ")
        if not BASE + 512 <= entry < BASE + 512 + len(body) <= BASE + 0x1200:
            raise ValueError("Fixture body/entry outside bounded link region")
    image = wrap(body, entry)
    (out / "minimal-acth.bin").write_bytes(image)
    report = {
        "scope": "Offline M4 ELF + ACTH fixture; not a CoMi BSP, raw NOR image, OTA package or hardware execution proof",
        "compiler": version,
        "command": command,
        "source_sha256": {
            name: sha((SOURCE / name).read_bytes()) for name in ("startup.S", "main.c", "linker.ld")
        },
        "cpu": "Cortex-M4 / ARMv7E-M",
        "float_abi": "soft; no media/BLE vendor libraries",
        "addresses": {
            key: hex(symbols[key])
            for key in (
                "Reset_Handler",
                "vector_table",
                "__stack_top",
                "__stack_bottom",
                "__data_load",
                "__data_start",
                "__data_end",
                "__bss_start",
                "__bss_end",
                "fixture_marker",
            )
        },
        "memory_basis": "Original app uses01001b40..01002340 init stack and01002b40 vector SP; fixture layout only, not free live RAM",
        "artifacts": {
            name: {"bytes": len(data), "sha256": sha(data)}
            for name, data in (
                ("minimal.elf", elf.read_bytes()),
                ("minimal-body.bin", body),
                ("minimal-acth.bin", image),
            )
        },
    }
    (out / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    typer.run(main)
