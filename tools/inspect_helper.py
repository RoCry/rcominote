#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Inspect the pinned public LEOPARD ADFU helper without executing it."""

import hashlib
import json
import struct
from pathlib import Path
from typing import Annotated

import typer
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

EXPECTED_SHA256 = "470827c527a7111cebeb74e60dd32c007390df34453bce519998963db3ad5953"
LOAD_ADDRESS = 0x2FF70000
TOKENS = b"gfrirmwmisicsircrswsescfrrsfrxaf"
TOKEN_OFFSET = 0xC2A
POINTER_OFFSET = 0xC4C
# Independently transcribed from the pinned artifact; reject a different layout.
HANDLER_OFFSETS = (
    0x4784,
    0x47A4,
    0x481C,
    0x47C4,
    0x48AC,
    0x4948,
    0x4A5C,
    0x491C,
    0x4BCC,
    0x4B0C,
    0x4C38,
    0x4C84,
    0x4880,
    0x4CAC,
    0x4970,
    0x4CCC,
)


def disassemble(data: bytes, start: int, end: int) -> dict:
    """Decode only selected code, excluding adjacent literal pools."""
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    instructions = [
        {
            "address": f"0x{item.address:08x}",
            "file_offset": f"0x{item.address - LOAD_ADDRESS:x}",
            "bytes": item.bytes.hex(),
            "mnemonic": item.mnemonic,
            "operands": item.op_str,
        }
        for item in decoder.disasm(data[start:end], LOAD_ADDRESS + start)
    ]
    if sum(len(bytes.fromhex(item["bytes"])) for item in instructions) != end - start:
        raise ValueError(f"incomplete Thumb decode at file range {start:#x}..{end:#x}")
    return {
        "file_start": f"0x{start:x}",
        "file_end_exclusive": f"0x{end:x}",
        "instructions": instructions,
    }


def inspect(path: Path) -> dict:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"unsupported helper SHA-256 {digest}; expected pinned LEOPARD {EXPECTED_SHA256}")
    if data[TOKEN_OFFSET : TOKEN_OFFSET + len(TOKENS)] != TOKENS:
        raise ValueError("command tokens differ from independently recorded artifact")
    pointers = struct.unpack_from("<16I", data, POINTER_OFFSET)
    expected = tuple(LOAD_ADDRESS + offset + 1 for offset in HANDLER_OFFSETS)
    if pointers != expected:
        raise ValueError("handler table differs from independently recorded artifact")
    storage_tables = []
    for kind, offset, entries in (
        ("nor", 0x958, (0x3C09, 0x3E49, 0x3DDD, 0x3AF5, 0x3D6D, 0x3AF1, 0x3B9D)),
        ("sd", 0x530, (0x2C29, 0x2D31, 0x2E6D, 0x2F21, 0x2EE9, 0x2575, 0x2579)),
        ("nand", 0x87C, (0x37D1, 0x325D, 0x3369, 0x3495, 0x32D5, 0x3249, 0x3329)),
    ):
        actual = struct.unpack_from("<7I", data, offset)
        if actual != tuple(LOAD_ADDRESS + entry for entry in entries):
            raise ValueError(f"{kind} storage table differs from recorded artifact")
        post_init = entries[5] - 1
        if data[post_init : post_init + 4] != b"\x00\x20\x70\x47":
            raise ValueError(f"{kind} post-init callback is no longer a no-op")
        storage_tables.append(
            {
                "kind": kind,
                "table_file_offset": f"0x{offset:x}",
                "thumb_pointers": [f"0x{item:08x}" for item in actual],
                "post_init_slot": "0x14",
                "post_init_code": disassemble(data, post_init, post_init + 4),
            }
        )
    return {
        "scope": "static offline analysis; no device I/O or target execution",
        "source_commit": "26f51e584940d5b141cd1d09d2629d69b595f579",
        "source_path": "action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/adfus.bin",
        "sha256": digest,
        "size": len(data),
        "load_address": f"0x{LOAD_ADDRESS:08x}",
        "address_basis": "matching fw_product.cfg ADFUS download/run addresses",
        "token_file_offset": f"0x{TOKEN_OFFSET:x}",
        "token_bytes": TOKENS.hex(),
        "pointer_file_offset": f"0x{POINTER_OFFSET:x}",
        "pointer_bytes": data[POINTER_OFFSET : POINTER_OFFSET + 64].hex(),
        "commands": [
            {
                "index": index,
                "token": TOKENS[index * 2 : index * 2 + 2].decode("ascii"),
                "thumb_pointer": f"0x{pointer:08x}",
                "code_file_offset": f"0x{pointer - LOAD_ADDRESS - 1:x}",
            }
            for index, pointer in enumerate(pointers)
        ],
        "storage_tables": storage_tables,
        "code": {
            "dispatcher": disassemble(data, 0x467C, 0x46BE),
            "rm": disassemble(data, 0x481C, 0x4878),
            "rs": disassemble(data, 0x4BCC, 0x4C28),
            "is": disassemble(data, 0x48AC, 0x490A),
            "nand_read": disassemble(data, 0x325C, 0x32C0),
        },
        "limitations": [
            "Public SDK helper; not recovered from CoMi.",
            "Load address is configuration-derived, not observed execution.",
            "Command semantics inferred from static data flow, not hardware testing.",
            "ROM transport, authentication and compatible CoMi storage driver remain unknown.",
            "Post-init callback is a no-op; initializers and NAND lazy init may have side effects.",
        ],
    }


def main(
    helper: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Print verified command table and bounded Thumb disassembly as JSON."""
    try:
        report = inspect(helper)
    except (OSError, ValueError, struct.error) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    typer.run(main)
