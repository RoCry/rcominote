"""Offline verification of the fixed, instruction-derived CoMi read set."""

import hashlib
import json
import re
from pathlib import Path
from typing import Annotated

import typer
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

from .boot_readback import BOOT_BLOCKS, BOOT_NAME_POINTERS
from .card_readback import CARD_BLOCKS
from .output import emit, new_output
from .read_sets import BLOCKS, DISK_BLOCKS, HANDLER_BLOCKS, INFO_BLOCKS, INFO_STORAGE, VENDOR_BLOCKS
from .vendor_dispatch import BASE, TABLE, TABLE_END, inspect_dispatch

FIXED_BLOCKS = tuple(
    dict.fromkeys(
        (
            *BLOCKS,
            *VENDOR_BLOCKS,
            *HANDLER_BLOCKS,
            *INFO_BLOCKS,
            *INFO_STORAGE,
            *DISK_BLOCKS,
            *CARD_BLOCKS,
            *BOOT_BLOCKS,
        )
    )
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


def disk_metadata(capture: dict) -> dict:
    """Interpret only instruction-evidenced fields; values are cached logical metadata."""
    header = read_block(capture, 0x18010A8C, 16)
    node = read_block(capture, 0x1800195C, 16) + read_block(capture, 0x1800196C, 16)
    sector_size = int.from_bytes(node[12:14], "little")
    cluster_size = int.from_bytes(header[10:12], "little") * sector_size
    entries = int.from_bytes(read_block(capture, 0x18010AC0, 4), "little")
    free = int.from_bytes(read_block(capture, 0x18010AA8, 4), "little")
    if sector_size != 512 or entries < 2 or not cluster_size or free > entries - 2:
        raise ValueError("Captured filesystem metadata is inconsistent with the decoded capacity path")
    total = entries - 2
    return {
        "scope": "cached filesystem data clusters and registered logical disk, not raw flash geometry",
        "filesystem_type_value": header[0],
        "drive_number": header[1],
        "sector_bytes": sector_size,
        "cluster_bytes": cluster_size,
        "data_clusters": total,
        "cached_free_clusters": free,
        "data_capacity_bytes": total * cluster_size,
        "cached_free_bytes": free * cluster_size,
        "reported_total_mib": (((cluster_size >> 10) * total) & 0xFFFFFFFF) >> 10,
        "reported_free_mib": (((cluster_size >> 10) * free) & 0xFFFFFFFF) >> 10,
        "disk_sector_offset": int.from_bytes(node[16:20], "little"),
        "disk_sector_count": int.from_bytes(node[20:24], "little"),
    }


def card_metadata(capture: dict) -> dict:
    """Decode cached fields located by actual loads; type names use pinned SDK enum."""
    state = read_block(capture, 0x18005D58, 16)
    return {
        "scope": "cached SD/MMC driver state, not package identity or firmware storage",
        "type_value": state[0],
        "type_inferred_from_sdk": {0: "SD", 1: "MMC"}.get(state[0], "unknown"),
        "initialized_value": state[1],
        "force_plug_out_value": state[2],
        "low_power_value": state[3],
        "rca": int.from_bytes(state[4:8], "little"),
        "ccs_value": state[8],
        "sector_count": int.from_bytes(state[12:16], "little"),
        "sector_bytes": int.from_bytes(read_block(capture, 0x18005D68, 4), "little"),
    }


def device_names(capture: dict) -> list[dict]:
    """Report the bounded observed table; names alone do not establish readiness."""
    entries = [(parent, name, 16) for parent, name in BOOT_NAME_POINTERS]
    entries.extend(((0x100BA100, 0x100CAEE9, 10), (0x100BA160, 0x100CAEF3, 3)))
    devices = []
    for parent, name, length in sorted(entries):
        raw = read_block(capture, name, length)
        prefix, separator, _ = raw.partition(b"\0")
        devices.append(
            {
                "device_address": hex(parent),
                "name_address": hex(name),
                "name_prefix": prefix.decode("ascii"),
                "name_complete": bool(separator),
            }
        )
    return devices


def flash_configuration(capture: dict) -> dict:
    """Configuration/state only: no chip-ID command or physical-capacity verification."""
    config = read_block(capture, 0x100BC258, 16)
    state = int.from_bytes(read_block(capture, 0x18002E70, 2), "little")
    return {
        "scope": "registered spi_flash configuration, not chip-ID or boot-medium proof",
        "device_state_halfword": hex(state),
        "ready_by_decoded_helper": state & 0x1FF == 0x100,
        "layout_page_count": int.from_bytes(config[:4], "little"),
        "layout_page_bytes": int.from_bytes(config[4:8], "little"),
        "sdk_config_chip_bytes": int.from_bytes(config[8:12], "little"),
        "sdk_config_page_bytes": int.from_bytes(config[12:16], "little"),
        "data_prefix_hex": read_block(capture, 0x18001A7C, 16).hex(),
    }


def inspect_references(
    first: Path,
    second: Path,
    *,
    vendor: bool = False,
    handler: bool = False,
    info: bool = False,
    storage: bool = False,
    disk: bool = False,
    card: bool = False,
    boot: bool = False,
) -> dict:
    captures = [json.loads(path.read_text()) for path in (first, second)]
    stamps = [capture.get("captured_at") for capture in captures]
    if not all(stamps) or stamps[0] == stamps[1]:
        raise ValueError("Two distinct capture records are required")
    blocks = []
    card = card or boot
    disk = disk or card
    storage = storage or disk
    info = info or storage
    vendor = vendor or handler or info
    selected = INFO_BLOCKS if info else HANDLER_BLOCKS if handler else VENDOR_BLOCKS if vendor else BLOCKS
    if storage:
        selected = (*selected, *INFO_STORAGE)
    if disk:
        selected = (*selected, *DISK_BLOCKS)
    if card:
        selected = (*selected, *CARD_BLOCKS)
    if boot:
        selected = (*selected, *BOOT_BLOCKS)
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
    read_bytes = sum(block[1] for block in selected)
    unique_bytes = len({address + offset for address, length, *_ in selected for offset in range(length)})
    report = {
        "scope": f"{unique_bytes} distinct mapped bytes from {read_bytes} fixed-read bytes, not a physical flash backup",
        "read_bytes": read_bytes,
        "unique_mapped_bytes": unique_bytes,
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
    if disk:
        report["disk_metadata"] = disk_metadata(captures[0])
    if card:
        report["card_metadata"] = card_metadata(captures[0])
    if boot:
        report["device_names"] = device_names(captures[0])
        report["flash_configuration"] = flash_configuration(captures[0])
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
    info: bool = False,
    storage: bool = False,
    disk: bool = False,
    card: bool = False,
    boot: bool = False,
):
    """Compare fixed --vendor, --handler, --info, --storage, --disk, --card or --boot reads."""
    new_output(out)
    report = inspect_references(
        first,
        second,
        vendor=vendor,
        handler=handler,
        info=info,
        storage=storage,
        disk=disk,
        card=card,
        boot=boot,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    emit(report)
