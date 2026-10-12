"""Decode cached ACPT metadata; never treats entry offsets as a verified flash map."""

import hashlib
import struct
import zlib


def inspect_acpt(data: bytes) -> dict:
    """Layout: pinned SDK partition.c/partition.h; CRC matches utils_crc32(0,...)."""
    if len(data) != 744:
        raise ValueError("ACPT requires exactly 744 bytes")
    magic, version, size, count, entry_size = struct.unpack_from("<4s4H", data)
    if magic != b"ACPT" or size != len(data) or entry_size != 24 or count > 30:
        raise ValueError("ACPT header magic, size, count, or entry size is invalid")
    stored_crc = int.from_bytes(data[-4:], "little")
    if zlib.crc32(data[:-4]) != stored_crc:
        raise ValueError("ACPT CRC mismatch")
    entries = []
    for index in range(count):
        name, kind, file_id, storage_mirror, flags, offset, size, file_offset = struct.unpack_from(
            "<8s4B3I", data, 16 + index * 24
        )
        entries.append(
            {
                "index": index,
                "name": name.split(b"\0", 1)[0].decode("ascii"),
                "type": kind,
                "file_id": file_id,
                "storage_id": storage_mirror >> 4,
                "mirror_id": storage_mirror & 15,
                "flags": flags,
                "offset": hex(offset),
                "size_bytes": size,
                "end_exclusive": hex(offset + size),
                "file_offset": hex(file_offset),
            }
        )
    return {
        "scope": "runtime cached ACPT table; offsets are configured storage-relative values, not verified flash reads",
        "sha256": hashlib.sha256(data).hexdigest(),
        "version": hex(version),
        "table_bytes": len(data),
        "partition_count": count,
        "entry_bytes": entry_size,
        "crc32": hex(stored_crc),
        "crc_valid": True,
        "entries": entries,
        "unused_entry_bytes_zero": not any(data[16 + count * 24 : 736]),
    }
