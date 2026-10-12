"""Require every memory row, independently of transport ACKs."""

from . import printk_ring, printk_tail
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
    result.pop("console_tail", None)
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
    tail = None
    try:
        if result.get("printk_state"):
            state = inspect_state(result)
        if result.get("printk_buffer"):
            ring = printk_ring.inspect(result)
        if result.get("printk_tail"):
            tail = printk_tail.inspect(result)
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
        if tail is not None:
            result["console_tail"] = tail
        if ring is not None:
            result["console_ring"] = ring
        if state is not None:
            result["console_state"] = state


def finish_capture(result: dict, stream, expected_acks: int) -> None:
    """Finalize the physical stream once; only then accept its logical windows."""
    result |= {
        "ack_count": stream.acks,
        "expected_ack_count": expected_acks,
        "end_received": stream.ended,
        "pending_hex": stream.pending.hex(),
        "text_bytes": sum(
            len(bytes.fromhex(row["hex"])) - 8 for row in stream.frames if row["command"] == 0xF0
        ),
    }
    result["ok"] = (
        "error" not in result
        and "stop_error" not in result
        and stream.acks == expected_acks
        and stream.ended
        and not stream.pending
    )
    verify_readback(result)
    seed_ok = result["ok"]
    batch_ok = True
    for record in result.get("batch_records", []):
        record["ok"] = seed_ok
        record["shared_transport"] = {
            "ack_count": stream.acks,
            "expected_ack_count": expected_acks,
            "end_received": stream.ended,
            "pending_hex": stream.pending.hex(),
        }
        record["end_received"] = stream.ended
        if stream.ended:
            record["session_end_frame"] = next(
                row for row in reversed(stream.frames) if row["command"] == 0xF1
            )
        verify_readback(record)
        if not record["ok"]:
            batch_ok = False
            result.setdefault("batch_error", record.get("error", "Shared NOR batch transport failed"))
    result["ok"] = seed_ok and batch_ok and "batch_error" not in result
