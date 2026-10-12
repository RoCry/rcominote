"""Offline verification of the fixed, instruction-derived CoMi read set."""

import hashlib
import json
import re
from pathlib import Path
from typing import Annotated

import typer
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

from .output import emit, new_output
from .vendor_dispatch import BASE, TABLE, TABLE_END, inspect_dispatch

# Lengths are hexadecimal in the device's mdb commands; decimal here.
BLOCKS = (
    (0x1000BF20, 16, "logsrv entry", True),
    (0x1000C0AC, 8, "two PC-relative literals", False),
    (0x100C26BA, 13, "r1 string candidate", False),
    (0x100AD486, 16, "BL target and adjacent instructions", True),
    (0x1000BF30, 16, "BL return and subsequent instructions", True),
)

VENDOR_BLOCKS = (
    (0x1000A01C, 16, "vendor_read observed thread entry", True),
    (0x10009E9C, 16, "vendor observed thread entry", True),
    (0x1000A170, 16, "vendor_read first four PC-relative literals", False),
    (0x1000A180, 4, "vendor_read r7 PC-relative literal", False),
    (0x1000A1AC, 4, "vendor_read r8 PC-relative literal", False),
    # Contiguous executable span from observed entry up to its first evidenced
    # literal pool. Function boundaries within the span remain inferred.
    *(
        (address, min(16, 0x1000A170 - address), "vendor_read code before literal pool", True)
        for address in range(0x1000A02C, 0x1000A170, 16)
    ),
)

HANDLER_CORE_BLOCKS = (
    (0x1000A01C, 16, "vendor_read entry prerequisite", True),
    (0x1000A14C, 16, "direct BL to packet-processing callee", True),
    (0x1000B3B4, 16, "packet-processing callee entry", True),
    (0x1000B3C4, 16, "packet-processing callee continuation", True),
    *(
        (address, min(16, 0x1000B558 - address), "callee span before evidenced literal pool", True)
        for address in range(0x1000B3D4, 0x1000B558, 16)
    ),
    (0x1000B558, 12, "three callee PC-relative literals", False),
)
SPECIAL_BLOCKS = (
    (0x1000B0C0, 16, "command 0x3a direct callee entry", True),
    (0x1000B0D0, 16, "command 0x3a callee continuation", True),
    (0x1000B0E0, 16, "command 0x3a after observed BL return", True),
    (0x1000B0F0, 16, "command 0x3a continuation", True),
    (0x1000B100, 16, "command 0x3a final branch targets", True),
    (0x1000B110, 4, "command 0x3a r0 PC-relative literal", False),
    (0x100C22BB, 16, "command 0x3a r0 literal target prefix", False),
    (0x100AD3D6, 16, "command 0x3a direct helper callee", True),
)
HANDLER_BLOCKS = (*HANDLER_CORE_BLOCKS, *SPECIAL_BLOCKS)


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


def inspect_references(first: Path, second: Path, *, vendor: bool = False, handler: bool = False) -> dict:
    captures = [json.loads(path.read_text()) for path in (first, second)]
    stamps = [capture.get("captured_at") for capture in captures]
    if not all(stamps) or stamps[0] == stamps[1]:
        raise ValueError("Two distinct capture records are required")
    blocks = []
    vendor = vendor or handler
    selected = HANDLER_BLOCKS if handler else VENDOR_BLOCKS if vendor else BLOCKS
    for address, length, reason, code in selected:
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
        if code and not vendor:
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
        elif not code and address != 0x100C26BA:
            row["little_endian_words"] = [
                hex(int.from_bytes(data[i : i + 4], "little")) for i in range(0, len(data), 4)
            ]
        elif not code:
            row["ascii"] = data.decode("ascii")
        blocks.append(row)
    report = {
        "scope": f"{sum(block[1] for block in selected)} noncontiguous mapped bytes, not a physical flash backup",
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
    if vendor:
        # Decode contiguous bytes together: 32-bit Thumb instructions can cross
        # 16-byte transport rows. Never resume decoding in their second half.
        regions = []
        for address, length, _, code in sorted(selected):
            if not code:
                continue
            data = read_block(captures[0], address, length)
            if regions and regions[-1][0] + len(regions[-1][1]) == address:
                regions[-1][1].extend(data)
            else:
                regions.append((address, bytearray(data)))
        report["code_regions"] = []
        if handler:
            # Actual TBB embeds 58 data bytes inside executable address space.
            # Do not decode its offsets as Thumb instructions or stop there.
            split_regions = []
            for address, data in regions:
                if address == BASE:
                    report["dispatch"] = inspect_dispatch(bytes(data))
                    report["data_regions"] = [
                        {
                            "address": hex(TABLE),
                            "kind": "TBB byte offsets",
                            "hex": data[TABLE - BASE : TABLE_END - BASE].hex(),
                        }
                    ]
                    split_regions.extend(
                        [
                            (address, data[: TABLE - BASE]),
                            (TABLE_END, data[TABLE_END - BASE :]),
                        ]
                    )
                else:
                    split_regions.append((address, data))
            regions = split_regions
        for address, data in regions:
            insns = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(data, address))
            report["code_regions"].append(
                {
                    "address": hex(address),
                    "length": len(data),
                    "instructions": [
                        {
                            "address": hex(ins.address),
                            "bytes": ins.bytes.hex(),
                            "mnemonic": ins.mnemonic,
                            "operands": ins.op_str,
                        }
                        for ins in insns
                    ],
                    "undecoded_tail_hex": data[sum(ins.size for ins in insns) :].hex(),
                }
            )
    return report


def main(
    first: Path,
    second: Path,
    out: Annotated[Path, typer.Option()],
    vendor: bool = False,
    handler: bool = False,
):
    """Compare fixed references; --vendor selects receive loop, --handler its dispatcher."""
    new_output(out)
    report = inspect_references(first, second, vendor=vendor, handler=handler)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    emit(report)
