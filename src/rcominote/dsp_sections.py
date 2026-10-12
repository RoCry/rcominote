"""Offline DSP section inventory; never maps or executes DSP destination addresses."""

import hashlib
import struct
from pathlib import Path

from .dsp_header import inspect_header
from .output import emit


def inspect_image(raw: bytes) -> dict:
    header = inspect_header(raw[:540], file_size=len(raw))
    roots = [("code", header["code_offset"]), ("data", header["data_offset"])]
    for bank in header["nonzero_banks"]:
        roots.extend((f"bank{bank['bank']}_{kind}", bank[f"{kind}_offset"]) for kind in ("code", "data"))
    tables = []
    for name, start in roots:
        if not start:
            continue
        cursor = start
        sections = []
        while True:
            if cursor + 4 > len(raw):
                raise ValueError(f"DSP {name}: missing section terminator at {cursor:#x}")
            size = struct.unpack_from("<I", raw, cursor)[0]
            if size == 0:
                break  # Actual loader accepts a four-byte zero size at EOF.
            if cursor + 8 > len(raw):
                raise ValueError(f"DSP {name}: incomplete nonempty section header at {cursor:#x}")
            address = struct.unpack_from("<I", raw, cursor + 4)[0]
            end = cursor + 8 + size
            if end > len(raw):
                raise ValueError(f"DSP {name}: section payload exceeds file at {cursor:#x}")
            sections.append(
                {
                    "header_offset": cursor,
                    "data_offset": cursor + 8,
                    "bytes": size,
                    "dsp_address": hex(address),
                    "sha256": hashlib.sha256(raw[cursor + 8 : end]).hexdigest(),
                }
            )
            cursor = end
        tables.append({"name": name, "offset": start, "terminator_offset": cursor, "sections": sections})
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "header": header,
        "tables": tables,
        "scope": "File section bounds and hashes; no DSP address validity, execution or boot proof",
    }


def main(image: Path):
    """Inventory full DSP file sections offline, rejecting truncation."""
    emit(inspect_image(image.read_bytes()))
