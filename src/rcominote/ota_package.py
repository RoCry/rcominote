"""Offline AOTA container integrity checks; never establishes device compatibility."""

import hashlib
import mmap
import os
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import Annotated

import typer

from .output import emit

HEADER_SIZE = 1024
DIRECTORY_OFFSET = 512
ENTRY_SIZE = 32
MAX_XML_SIZE = 2 * 1024 * 1024


def _name(raw: bytes, *, label: str) -> str:
    name, separator, padding = raw.partition(b"\0")
    if separator and any(padding):
        raise ValueError(f"{label}: nonzero bytes after filename terminator")
    try:
        decoded = name.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label}: filename is not UTF-8") from error
    if not decoded or decoded in (".", "..") or any(c in decoded for c in "/\\"):
        raise ValueError(f"{label}: empty or unsafe filename")
    if not decoded.isprintable():
        raise ValueError(f"{label}: filename contains control characters")
    return decoded


def _xml_metadata(data: bytes) -> dict:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(f"ota.xml: malformed XML: {error}") from error
    if root.tag != "ota_firmware":
        raise ValueError("ota.xml: expected ota_firmware root")
    versions = []
    for tag in ("firmware_version", "old_firmware_version"):
        for element in root.findall(tag):
            versions.append(
                {"tag": tag, "fields": [{"name": child.tag, "text": child.text} for child in element]}
            )
    return {"source": "ota.xml; strings only, no compatibility validation", "versions": versions}


def inspect_package(data: bytes | bytearray | mmap.mmap) -> dict:
    """Check the fixed SDK layout, all CRCs, and file bounds before returning metadata."""
    if data[:4] == b"LZMA":
        raise ValueError("LZMA wrapper is not an AOTA container; decompression is not implemented")
    if data[:4] != b"AOTA":
        raise ValueError("Expected AOTA magic")
    if len(data) < HEADER_SIZE:
        raise ValueError(f"Truncated AOTA header: {len(data)} bytes, need {HEADER_SIZE}")
    if len(data) > 0xFFFFFFFF:
        raise ValueError("AOTA container exceeds the 32-bit size field")
    header_crc, version, header_size, count, flags, directory, body_offset, total_size, data_crc = (
        struct.unpack_from("<IHHHHHHII", data, 4)
    )
    if header_size != HEADER_SIZE or directory != DIRECTORY_OFFSET or body_offset != HEADER_SIZE:
        raise ValueError("Unsupported AOTA layout: expected header/data 1024 and directory 512")
    if count > 16:
        raise ValueError(f"AOTA directory has {count} entries; maximum is 16")
    if total_size < body_offset or total_size != len(data):
        raise ValueError(f"AOTA total size {total_size} does not match file size {len(data)}")
    view = memoryview(data)
    try:
        computed_header_crc = zlib.crc32(view[8:HEADER_SIZE])
        if computed_header_crc == 0xFFFFFFFF:
            raise ValueError("AOTA header CRC32 is the firmware parser's rejected 0xffffffff sentinel")
        if computed_header_crc != header_crc:
            raise ValueError("AOTA header CRC32 mismatch")
        if zlib.crc32(view[body_offset:total_size]) != data_crc:
            raise ValueError("AOTA data CRC32 mismatch (includes padding)")
        entries = []
        names = set()
        extents = []
        xml = None
        for index in range(count):
            position = directory + index * ENTRY_SIZE
            name = _name(bytes(view[position : position + 12]), label=f"Entry {index}")
            if name in names:
                raise ValueError(f"Duplicate AOTA filename: {name}")
            names.add(name)
            offset, size, checksum = struct.unpack_from("<II4xI", data, position + 16)
            end = offset + size
            if end > 0xFFFFFFFF or offset < body_offset or end > total_size:
                raise ValueError(f"AOTA file {name}: extent outside body or 32-bit overflow")
            if size and any(
                offset < previous_end and previous_start < end for previous_start, previous_end in extents
            ):
                raise ValueError(f"AOTA file {name}: overlapping file extents")
            if size:
                extents.append((offset, end))
            if zlib.crc32(view[offset:end]) != checksum:
                raise ValueError(f"AOTA file {name}: CRC32 mismatch (declared unpadded length)")
            entries.append({"name": name, "offset": offset, "size": size, "crc32": f"{checksum:08x}"})
            if name == "ota.xml":
                if size > MAX_XML_SIZE:
                    raise ValueError(f"ota.xml exceeds host metadata limit {MAX_XML_SIZE} bytes")
                xml = bytes(view[offset:end])
        return {
            "scope": "offline AOTA container integrity only; device acceptance and recoverability unverified",
            "sha256": hashlib.sha256(view).hexdigest(),
            "total_size": total_size,
            "header_version": version,
            "header_size": header_size,
            "directory_offset": directory,
            "data_offset": body_offset,
            "flags": flags,
            "header_crc32": f"{header_crc:08x}",
            "data_crc32": f"{data_crc:08x}",
            "header_version_area_hex": bytes(view[0x40:DIRECTORY_OFFSET]).hex(),
            "header_version_area_note": "Raw bytes: SDK packer and C version structures differ",
            "metadata": _xml_metadata(xml) if xml is not None else None,
            "entries": entries,
        }
    finally:
        view.release()


def main(image: Annotated[Path, typer.Argument(help="Local uncompressed AOTA package; offline checks only")]):
    """Inspect AOTA layout, CRC32s and metadata without connecting to a device."""
    with image.open("rb") as handle:
        size = os.fstat(handle.fileno()).st_size
        if not size:
            raise ValueError("Empty file; expected AOTA container")
        if size > 0xFFFFFFFF:
            raise ValueError("AOTA container exceeds the 32-bit size field")
        with mmap.mmap(handle.fileno(), length=0, access=mmap.ACCESS_READ) as data:
            emit(inspect_package(data))
