"""Offline verification of the fixed, instruction-derived CoMi read set."""

import hashlib
import json
import re
from pathlib import Path
from typing import Annotated

import typer
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

from .output import emit, new_output

# Lengths are hexadecimal in the device's mdb commands; decimal here.
BLOCKS = (
    (0x1000BF20, 16, "logsrv entry", True),
    (0x1000C0AC, 8, "two PC-relative literals", False),
    (0x100C26BA, 13, "r1 string candidate", False),
    (0x100AD486, 16, "BL target and adjacent instructions", True),
    (0x1000BF30, 16, "BL return and subsequent instructions", True),
)


def read_block(capture: dict, address: int, length: int) -> bytes:
    command = f"dbg mdb {address:x} {length:x}"
    if capture.get("serial") != "C261CF0430" or not capture.get("ok"):
        raise ValueError("Expected completed owned-device capture")
    if command not in capture.get("fixed_text_commands", []):
        raise ValueError(f"Missing declared read: {command}")
    text = "".join(frame.get("text", "") for frame in capture["frames"])
    rows = re.findall(rf"(?m)^{address:08x}:([^\r\n]*)", text)
    match = (
        re.fullmatch(rf" ((?:[0-9a-f]{{2}} ){{{length - 1}}}[0-9a-f]{{2}}) {{2,}}.*", rows[0])
        if len(rows) == 1
        else None
    )
    if match is None:
        raise ValueError(f"Missing, duplicate, or incomplete {length}-byte row at {address:#x}")
    return bytes.fromhex(match[1])


def inspect_references(first: Path, second: Path) -> dict:
    captures = [json.loads(path.read_text()) for path in (first, second)]
    stamps = [capture.get("captured_at") for capture in captures]
    if not all(stamps) or stamps[0] == stamps[1]:
        raise ValueError("Two distinct capture records are required")
    blocks = []
    for address, length, reason, code in BLOCKS:
        data = read_block(captures[0], address, length)
        if data != read_block(captures[1], address, length):
            raise ValueError(f"Independent reads differ at {address:#x}")
        row = {
            "address": hex(address),
            "length": length,
            "reason": reason,
            "hex": data.hex(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if code:
            insns = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(data, address))
            row["instructions"] = [
                {
                    "address": hex(ins.address),
                    "bytes": ins.bytes.hex(),
                    "mnemonic": ins.mnemonic,
                    "operands": ins.op_str,
                }
                for ins in insns
            ]
            decoded = sum(ins.size for ins in insns)
            row["undecoded_tail_hex"] = data[decoded:].hex()
        elif address == 0x1000C0AC:
            row["little_endian_words"] = [hex(int.from_bytes(data[i : i + 4], "little")) for i in (0, 4)]
        else:
            row["ascii"] = data.decode("ascii")
        blocks.append(row)
    return {
        "scope": "69 noncontiguous mapped bytes, not a physical flash backup",
        "independent_reads_match": True,
        "captures": [
            {"captured_at": capture["captured_at"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for capture, path in zip(captures, (first, second), strict=True)
        ],
        "blocks": blocks,
        "limitations": [
            "No code executed by decoder",
            "No physical offsets or image boundaries established",
            "Adjacent decoded bytes need not belong to the same function",
            "A trailing partial instruction is retained without interpreting missing bytes",
        ],
    }


def main(first: Path, second: Path, out: Annotated[Path, typer.Option()]):
    """Compare two code-references captures offline; require all five exact rows."""
    new_output(out)
    report = inspect_references(first, second)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    emit(report)
