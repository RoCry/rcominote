"""Offline Actions DSP header bounds, independent of successful DSP execution."""

import hashlib
import struct
from pathlib import Path

from .output import emit


def inspect_header(raw: bytes, *, file_size: int) -> dict:
    """Require the full 540-byte header; validate pointers, not section bodies."""
    if len(raw) != 540:
        raise ValueError("DSP header requires exactly 540 bytes")
    if raw[:4] != b"xhqy":
        raise ValueError("DSP header magic differs from xhqy")
    if type(file_size) is not int or file_size < 540:
        raise ValueError("DSP file size must include its complete header")
    words = struct.unpack("<135I", raw)
    pointers = {"code": words[5], "data": words[6]}
    banks = []
    for bank in range(64):
        code, data = words[7 + bank * 2 : 9 + bank * 2]
        pointers[f"bank_{bank}_code"] = code
        pointers[f"bank_{bank}_data"] = data
        if code or data:
            banks.append({"bank": bank, "code_offset": code, "data_offset": data})
    for name, offset in pointers.items():
        if offset and not 540 <= offset <= file_size - 8:
            raise ValueError(f"DSP {name} section header outside file bounds: {offset:#x}")
    return {
        "header_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "file_bytes": file_size,
        "tool_version_word": hex(words[1]),
        "file_type": raw[8],
        "file_subtype": raw[9],
        "algorithm_version_word": hex(words[3]),
        "entry_point": hex(words[4]),
        "code_offset": words[5],
        "data_offset": words[6],
        "nonzero_banks": banks,
        "scope": "Complete header and pointer bounds only; section bodies/checksums not validated",
    }


def main(header: Path, file_size: int):
    """Inspect an extracted 540-byte header against the known full file size."""
    emit(inspect_header(header.read_bytes(), file_size=file_size))
