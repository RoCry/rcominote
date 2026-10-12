"""Fixed static UART log ring; snapshots are non-atomic, never a Flash backup."""

import hashlib
import json
import struct
from pathlib import Path

from .code_references import read_block
from .output import emit
from .printk_state import inspect_state, verify_guards
from .range_readback import scoped_capture

GUARDS = (
    (0x10026CD4, "0f494ff48052281d7bf09af8"),
    (0x10026D0C, "04e00018"),
    (0x10026D14, "09ee0318"),
)
CONTEXT = 0x1800E008
BUFFER = 0x1803EE09
CAPACITY = 4096
PAYLOAD_READS = (
    ((BUFFER, 7),)
    + tuple((address, min(64, 0x1803FE00 - address)) for address in range(0x1803EE10, 0x1803FE00, 64))
    + ((0x1803FE00, 9),)
)
READS = (
    tuple((a, len(bytes.fromhex(v))) for a, v in GUARDS) + ((CONTEXT, 20),) + PAYLOAD_READS + ((CONTEXT, 24),)
)


def read(capture: dict, address: int, length: int) -> bytes:
    command = f"dbg mdb {address:x} {length:x}"
    if command not in capture["fixed_text_commands"]:
        raise ValueError(f"Missing ring read: {command}")
    scoped = scoped_capture(capture, command)
    rows = [(address + offset, min(16, length - offset)) for offset in range(0, length, 16)]
    scoped = scoped | {"fixed_text_commands": [f"dbg mdb {a:x} {n:x}" for a, n in rows]}
    return b"".join(read_block(scoped, a, n) for a, n in rows)


def context(capture: dict, length: int) -> dict:
    r, w, used, capacity, buffer = struct.unpack("<5I", read(capture, CONTEXT, length)[:20])
    if capacity != CAPACITY or buffer != BUFFER:
        raise ValueError("Printk ring address/capacity differs from fixed firmware profile")
    if r > CAPACITY or w > CAPACITY or used > CAPACITY:
        raise ValueError("Printk ring indices invalid or changed during non-atomic capture")
    return {"read_index": r, "write_index": w, "used": used, "capacity": capacity, "buffer": hex(buffer)}


def verify(capture: dict, *, payload: bool = False) -> None:
    verify_guards(capture)
    for address, expected in GUARDS:
        if read(capture, address, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f"Printk ring instruction/literal changed at {address:#x}")
    if payload:
        if inspect_state(capture)["branch_from_flags"] != "dma_buffer":
            raise ValueError("Printk DMA ring is not the observed active backend")
        context(capture, 20)


def inspect(capture: dict) -> dict:
    verify(capture, payload=True)
    raw = b"".join(read(capture, a, n) for a, n in PAYLOAD_READS)
    return {
        "before": context(capture, 20),
        "after": context(capture, 24),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "physical_order_hex": raw.hex(),
        "scope": "Non-atomic static RAM snapshot; may contain stale or overwritten logs; not Flash data proof",
    }


def main(capture: Path):
    """Inspect a fixed ring capture offline; never follows a device pointer."""
    emit(inspect(json.loads(capture.read_text())))
