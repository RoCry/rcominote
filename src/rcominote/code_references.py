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

INFO_BODY_BLOCKS = (
    *(
        (address, 16, "previously decoded call/table prerequisite", False)
        for address in (
            0x1000A01C,
            0x1000A14C,
            0x1000B3B4,
            0x1000B3C4,
            0x1000B404,
            0x1000B414,
            0x1000B474,
        )
    ),
    (0x1000AAD0, 16, "GET_DEVICE_INFO callee entry", True),
    (0x1000AAE0, 16, "GET_DEVICE_INFO callee continuation", True),
    *(
        (address, min(16, 0x1000ABE4 - address), "GET_DEVICE_INFO code before literal pool", True)
        for address in range(0x1000AAF0, 0x1000ABE4, 16)
    ),
    (0x1000ABE4, 16, "GET_DEVICE_INFO literal pool", False),
)
INFO_REFERENCES = (
    (0x100BA780, 3, "version bytes referenced by GET_DEVICE_INFO", False),
    (0x100C1243, 8, "capacity getter r0 literal prefix", False),
    (0x100C21E8, 10, "model string referenced by GET_DEVICE_INFO", False),
    (0x100549C0, 16, "first capacity getter entry", True),
    (0x100549D0, 16, "first capacity getter continuation", True),
    (0x10054A28, 16, "second capacity getter entry", True),
    (0x10054A38, 16, "second capacity getter continuation", True),
)
INFO_CAPACITY = (
    *(
        (address, min(16, 0x10054A18 - address), "free-capacity getter continuation", True)
        for address in range(0x100549E0, 0x10054A18, 16)
    ),
    *(
        (address, min(16, 0x10054A80 - address), "total-capacity getter continuation", True)
        for address in range(0x10054A48, 0x10054A80, 16)
    ),
)
INFO_STORAGE_ENTRY = (
    (0x100546FC, 16, "capacity getter volume-check BL target", True),
    (0x1005470C, 16, "volume-check callee continuation", True),
    (0x1002F24C, 16, "capacity getter stat-query BL target", True),
    (0x1002F25C, 16, "stat-query callee continuation", True),
)
INFO_STORAGE_MORE = (
    (0x1005471C, 16, "volume-check taken branch", True),
    (0x1005472C, 12, "volume-check return before referenced literals", True),
    (0x10054738, 8, "volume-check PC-relative literals", False),
    (0x1002F26C, 16, "stat-query branch continuation", True),
    (0x1002F27C, 16, "stat-query path checks", True),
    *(
        (address, 16, "stat-query continuation before literal pool", True)
        for address in range(0x1002F28C, 0x1002F2DC, 16)
    ),
    (0x1002F2DC, 12, "stat-query first three PC-relative literals", False),
)
INFO_STORAGE_TABLE = (
    (0x100BCE24, 16, "volume-name pointer table first four entries", False),
    (0x100BCE34, 4, "volume-name pointer table fifth entry", False),
)
INFO_STORAGE_VOLUME = (
    (0x18017BD0, 8, "SD volume entry: code-proven base plus index four times stride eight", False),
)
INFO_STORAGE_MOUNT = (
    (0x18010A64, 16, "SD mount candidate first fields", False),
    (0x18010A74, 16, "SD mount candidate through code-proven vtable offset", False),
)
INFO_STORAGE_VTABLE = ((0x100BC0E0, 4, "mounted SD statvfs callback pointer", False),)
INFO_STORAGE_CALLBACK = (
    (0x100A42D6, 16, "SD statvfs callback Thumb entry", True),
    (0x100A42E6, 16, "SD statvfs callback entry continuation", True),
)
INFO_STORAGE_CALLBACK_TAIL = ((0x100A42F6, 16, "SD statvfs success continuation and error branch", True),)
INFO_STORAGE = (
    *INFO_STORAGE_ENTRY,
    *INFO_STORAGE_MORE,
    *INFO_STORAGE_TABLE,
    *INFO_STORAGE_VOLUME,
    *INFO_STORAGE_MOUNT,
    *INFO_STORAGE_VTABLE,
    *INFO_STORAGE_CALLBACK,
    *INFO_STORAGE_CALLBACK_TAIL,
)
INFO_BLOCKS = (*INFO_BODY_BLOCKS, *INFO_REFERENCES, *INFO_CAPACITY)
DISK_ENTRY = (
    (0x100A4306, 2, "statvfs error-path return branch", True),
    (0x100A794E, 16, "statvfs direct free-cluster callee", True),
    (0x100A795E, 16, "free-cluster callee continuation", True),
)
DISK_MORE = (
    (0x100A796E, 16, "free-cluster cached-count checks", True),
    (0x1003F684, 16, "free-cluster volume lookup direct callee", True),
    (0x1003F694, 16, "volume lookup callee continuation", True),
)
DISK_VOLUME_BODY = (
    *(
        (address, 16, "volume lookup mounted-drive path", True)
        for address in range(0x1003F6A4, 0x1003F6E4, 16)
    ),
    (0x1003F864, 4, "volume lookup indexed filesystem-table literal", False),
)
DISK_STATUS_ENTRY = (
    (0x10040D9C, 16, "mounted-drive status direct callee", True),
    (0x10040DAC, 16, "disk status continuation", True),
)
DISK_STATUS_MORE = (
    (0x10040DBC, 4, "disk-status final return before literals", True),
    (0x10040DC0, 8, "disk-name table and status-translation literals", False),
    (0x100A1998, 16, "named-disk status direct callee", True),
    (0x100A19A8, 16, "named-disk status continuation", True),
)
DISK_REGISTRY_ENTRY = (
    (0x10025870, 16, "named-disk registry lookup callee", True),
    (0x10025880, 16, "registry lookup continuation", True),
)
DISK_TABLES = (
    (0x100BC768, 16, "disk-status name table first four entries", False),
    (0x100BC778, 4, "disk-status name table fifth entry", False),
    (0x1800FD4C, 16, "FatFs pointer table first four candidate entries", False),
    (0x1800FD5C, 4, "FatFs pointer table fifth candidate entry", False),
)
DISK_REGISTRY_BODY = (
    *(
        (address, min(16, 0x100258C4 - address), "registry lookup remaining branches", True)
        for address in range(0x10025890, 0x100258C4, 16)
    ),
    (0x100258C4, 8, "registry list-head and mutex literals", False),
)
DISK_FS = (
    (0x100C6F54, 3, "disk-name table fifth string", False),
    (0x18010A8C, 16, "active FatFs prefix: type drive and cluster size", False),
    (0x18010AA8, 4, "active FatFs cached free-cluster count", False),
    (0x18010AC0, 4, "active FatFs FAT entry count", False),
)
DISK_LIST = ((0x1800C3D4, 8, "disk registry list head next and previous pointers", False),)
DISK_NODE = (
    (0x1800195C, 16, "sole registered disk node identity fields", False),
    (0x1800196C, 16, "sole registered disk geometry and ops pointer", False),
)
DISK_OPS = (
    (0x1800197C, 16, "SD disk operations init/status/read/write pointers", False),
    (0x1800198C, 4, "SD disk operations ioctl pointer", False),
)
DISK_DRIVER_ENTRY = ((0x10025950, 16, "registered SD status callback entry", True),)
DISK_DRIVER_LITERAL = ((0x10025960, 4, "SD status callback global-device pointer literal", False),)
DISK_DRIVER_GLOBAL = ((0x1800C3F0, 4, "SD status callback referenced device pointer", False),)
DISK_DEVICE = (
    (0x100BA160, 16, "SD backend device candidate name/config/API/state fields", False),
    (0x100BA170, 4, "SD backend device candidate data field", False),
)
DISK_DEVICE_REFS = (
    (0x100CAEF3, 3, "SD backend device name prefix", False),
    (0x100BC398, 8, "SD backend config candidate", False),
    (0x18005BE8, 4, "SD backend data first word: controller candidate", False),
    (0x100BC3A0, 16, "SD backend API first four function pointers", False),
)
DISK_CONTROLLER = (
    (0x100CAEE9, 10, "SD config referenced controller-name prefix", False),
    (0x100BA100, 16, "SD data referenced controller device prefix", False),
    (0x100BA110, 4, "controller device data candidate", False),
)
DISK_PHASES = (
    DISK_ENTRY,
    DISK_MORE,
    DISK_VOLUME_BODY,
    DISK_STATUS_ENTRY,
    DISK_STATUS_MORE,
    DISK_REGISTRY_ENTRY,
    DISK_TABLES,
    DISK_REGISTRY_BODY,
    DISK_FS,
    DISK_LIST,
    DISK_NODE,
    DISK_OPS,
    DISK_DRIVER_ENTRY,
    DISK_DRIVER_LITERAL,
    DISK_DRIVER_GLOBAL,
    DISK_DEVICE,
    DISK_DEVICE_REFS,
    DISK_CONTROLLER,
)
DISK_BLOCKS = tuple(block for phase in DISK_PHASES for block in phase)


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


def inspect_references(
    first: Path,
    second: Path,
    *,
    vendor: bool = False,
    handler: bool = False,
    info: bool = False,
    storage: bool = False,
    disk: bool = False,
) -> dict:
    captures = [json.loads(path.read_text()) for path in (first, second)]
    stamps = [capture.get("captured_at") for capture in captures]
    if not all(stamps) or stamps[0] == stamps[1]:
        raise ValueError("Two distinct capture records are required")
    blocks = []
    storage = storage or disk
    info = info or storage
    vendor = vendor or handler or info
    selected = INFO_BLOCKS if info else HANDLER_BLOCKS if handler else VENDOR_BLOCKS if vendor else BLOCKS
    if storage:
        selected = (*selected, *INFO_STORAGE)
    if disk:
        selected = (*selected, *DISK_BLOCKS)
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
    if disk:
        report["disk_metadata"] = disk_metadata(captures[0])
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
):
    """Compare fixed reads: --vendor, --handler, --info, --storage or --disk paths."""
    new_output(out)
    report = inspect_references(
        first, second, vendor=vendor, handler=handler, info=info, storage=storage, disk=disk
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    emit(report)
