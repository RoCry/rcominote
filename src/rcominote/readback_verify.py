"""Require every memory row, independently of transport ACKs."""

import hashlib

from .code_references import FIXED_BLOCKS, read_block
from .range_readback import HEADER_PROBE_RANGES, read_range


def verify_readback(result: dict) -> None:
    """Transport completion does not prove shell output survived firmware buffering."""
    result["transport_ok"] = result["ok"]
    reads = [
        block
        for block in FIXED_BLOCKS
        if f"dbg mdb {block[0]:x} {block[1]:x}" in result["fixed_text_commands"]
    ]
    ranges = [
        (a, n) for a, n in HEADER_PROBE_RANGES if f"dbg mdb {a:x} {n:x}" in result["fixed_text_commands"]
    ]
    if not reads and not ranges:
        return
    result["readback_complete"] = False
    if not result["transport_ok"]:
        return
    try:
        for address, length in ranges:
            data = read_range(result, address, length)
            if length == 512 and hashlib.sha256(data).hexdigest() != (
                "911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5"
            ):
                raise ValueError("Mapped header differs from independently validated FW010004 header")
        for address, length, *_ in reads:
            read_block(result, address, length)
    except ValueError as error:
        result["error"] = str(error)
        result["ok"] = False
    else:
        result["readback_complete"] = True
