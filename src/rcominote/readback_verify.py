"""Require every memory row, independently of transport ACKs."""

from .code_references import FIXED_BLOCKS, read_block
from .range_readback import (
    BODY_PROBE_RANGES,
    HEADER_PROBE_RANGES,
    image_ranges,
    read_range,
    scoped_capture,
    validate_known_header,
)


def verify_readback(result: dict) -> None:
    """Transport completion does not prove shell output survived firmware buffering."""
    result["transport_ok"] = result["ok"]
    reads = [
        block
        for block in FIXED_BLOCKS
        if f"dbg mdb {block[0]:x} {block[1]:x}" in result["fixed_text_commands"]
    ]
    ranges = list(
        dict.fromkeys(
            [
                (a, n)
                for a, n in (
                    *HEADER_PROBE_RANGES,
                    *BODY_PROBE_RANGES,
                    *image_ranges(result.get("image_chunk_indices", [])),
                )
                if f"dbg mdb {a:x} {n:x}" in result["fixed_text_commands"]
            ]
        )
    )
    if not reads and not ranges:
        return
    result["readback_complete"] = False
    if not result["transport_ok"]:
        return
    try:
        for address, length in ranges:
            data = read_range(result, address, length)
            if address == 0x10000000 and length == 512:
                validate_known_header(data)
        for address, length, *_ in reads:
            command = f"dbg mdb {address:x} {length:x}"
            read_block(scoped_capture(result, command), address, length)
    except ValueError as error:
        result["error"] = str(error)
        result["ok"] = False
    else:
        result["readback_complete"] = True
