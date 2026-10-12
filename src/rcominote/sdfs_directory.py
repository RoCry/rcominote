"""Offline SDFS directory from guarded, repeated fixed DSP-partition reads."""

import hashlib
import struct
from itertools import pairwise
from pathlib import Path

from . import nor_windows
from .output import emit

PARTITION_OFFSET = 0x240000
PARTITION_BYTES = 0xB0000
ENTRY_BYTES = 32
PREFIX_BYTES = 512


def _name(raw: bytes) -> str:
    name, separator, padding = raw.partition(b"\0")
    if not name or any(byte < 0x20 or byte > 0x7E for byte in name):
        raise ValueError("SDFS filename must contain printable ASCII")
    if separator and any(padding):
        raise ValueError("SDFS filename has nonzero bytes after its NUL terminator")
    return name.decode("ascii")


def parse_directory(raw: bytes) -> dict:
    """Parse only the bounded directory; no file bodies or checksum validation."""
    if len(raw) < ENTRY_BYTES:
        raise ValueError("Truncated SDFS header: need 32 bytes")
    if raw[:12] != b"sdfs.bin\0\0\0\0":
        raise ValueError("SDFS header magic differs from sdfs.bin")
    count, total_size, reserved0, reserved1, checksum = struct.unpack_from("<5I", raw, 12)
    directory_bytes = (count + 1) * ENTRY_BYTES
    if directory_bytes > PREFIX_BYTES:
        raise ValueError("SDFS directory exceeds the fixed 512-byte read prefix")
    if len(raw) < directory_bytes:
        raise ValueError(f"Truncated SDFS directory: need {directory_bytes} bytes, got {len(raw)}")
    if not directory_bytes <= total_size <= PARTITION_BYTES:
        raise ValueError("SDFS total size lies outside directory/partition bounds")
    files = []
    names = set()
    for index in range(1, count + 1):
        start = index * ENTRY_BYTES
        name = _name(raw[start : start + 12])
        offset, size, r0, r1, word = struct.unpack_from("<5I", raw, start + 12)
        if name.casefold() in names:
            raise ValueError(f"Duplicate case-insensitive SDFS filename: {name}")
        names.add(name.casefold())
        end = offset + size
        if offset < directory_bytes or end > PARTITION_BYTES or end > total_size:
            raise ValueError(f"SDFS file extent outside directory/volume/partition bounds: {name}")
        files.append(
            {
                "name": name,
                "relative_offset": offset,
                "absolute_offset": PARTITION_OFFSET + offset,
                "size": size,
                "relative_end": end,
                "absolute_end": PARTITION_OFFSET + end,
                "reserved": [r0, r1],
                "checksum_word": hex(word),
            }
        )
    occupied = sorted((file for file in files if file["size"]), key=lambda file: file["relative_offset"])
    for previous, current in pairwise(occupied):
        if current["relative_offset"] < previous["relative_end"]:
            raise ValueError(f"Overlapping SDFS file extents: {previous['name']}, {current['name']}")
    directory = raw[:directory_bytes]
    return {
        "scope": "Directory metadata only; file bodies and checksum algorithm not verified",
        "partition_offset": PARTITION_OFFSET,
        "partition_bytes": PARTITION_BYTES,
        "file_count": count,
        "volume_bytes": total_size,
        "directory_bytes": directory_bytes,
        "directory_sha256": hashlib.sha256(directory).hexdigest(),
        "header_reserved": [reserved0, reserved1],
        "header_checksum_word": hex(checksum),
        "checksum_verified": False,
        "files": files,
    }


def inspect(captures: list[Path]) -> dict:
    """Require double coverage of every directory row from the fixed DSP target."""
    coverage = nor_windows.analyze(captures)
    if coverage["target"] != "dsp" or coverage["offset"] != PARTITION_OFFSET:
        raise ValueError("SDFS directory requires fixed DSP target at NOR offset 0x240000")
    if coverage["conflicts"]:
        raise ValueError(f"Conflicting SDFS prefix rows: {coverage['conflicts']}")
    rows = {int(row["offset"], 16): row["variants"][0] for row in coverage["rows"]}

    def read(length: int) -> bytes:
        required = range(0, length, 16)
        missing = [hex(offset) for offset in required if offset not in rows or rows[offset]["sources"] < 2]
        if missing:
            raise ValueError(f"SDFS directory rows lack independent double coverage: {missing}")
        return b"".join(bytes.fromhex(rows[offset]["hex"]) for offset in required)

    header = read(32)
    count = struct.unpack_from("<I", header, 12)[0]
    length = (count + 1) * ENTRY_BYTES
    if length > PREFIX_BYTES:
        raise ValueError("SDFS directory exceeds the fixed 512-byte read prefix")
    report = parse_directory(read(length))
    report["input_files"] = coverage["input_files"]
    report["distinct_sources"] = coverage["distinct_sources"]
    return report


def main(captures: list[Path]):
    """Inspect the actual fixed DSP SDFS directory offline; no device connection."""
    emit(inspect(captures))
