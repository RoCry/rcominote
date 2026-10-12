"""Require every memory row, independently of transport ACKs."""

from . import printk_ring
from .code_references import FIXED_BLOCKS, read_block
from .printk_state import inspect_state
from .range_readback import (
    BODY_PROBE_RANGES,
    HEADER_IMAGE_READS,
    HEADER_PROBE_RANGES,
    image_ranges,
    read_header,
    read_range,
    scoped_capture,
    validate_known_header,
)


def verify_readback(result: dict) -> None:
    """Transport completion does not prove shell output survived firmware buffering."""
    result["transport_ok"] = result["ok"]
    result.pop("console_ring", None)
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
                    *HEADER_IMAGE_READS,
                    *BODY_PROBE_RANGES,
                    *image_ranges(result.get("image_chunk_indices", [])),
                )
                if f"dbg mdb {a:x} {n:x}" in result["fixed_text_commands"]
            ]
        )
    )
    if result.get("printk_state"):
        result.pop("console_state", None)
    if not reads and not ranges and not result.get("printk_state"):
        return
    result["readback_complete"] = False
    if not result["transport_ok"]:
        return
    state = None
    ring = None
    try:
        if result.get("printk_state"):
            state = inspect_state(result)
        if result.get("printk_buffer"):
            ring = printk_ring.inspect(result)
        if result.get("image_header"):
            read_header(result)
        for address, length in image_ranges(result.get("image_chunk_indices", [])):
            if f"dbg mdb {address:x} {length:x}" not in result["fixed_text_commands"]:
                raise ValueError("Image session is missing a declared bounded read")
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
        if ring is not None:
            result["console_ring"] = ring
        if state is not None:
            result["console_state"] = state
