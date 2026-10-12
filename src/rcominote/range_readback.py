"""Strict multiline mdb parsing; initial fixed probe rereads an already validated header."""

from .code_references import read_block

HEADER_BATCH_READS = ((0x10000000, 512),)
HEADER_PROBE_RANGES = tuple((0x10000000, size) for size in (64, 256, 512))


def read_range(capture: dict, address: int, length: int) -> bytes:
    if length <= 0 or length > 512 or address % 16:
        raise ValueError("Range must be aligned and contain 1..512 bytes")
    command = f"dbg mdb {address:x} {length:x}"
    if command not in capture.get("fixed_text_commands", []):
        raise ValueError(f"Missing declared range: {command}")
    rows = [(address + offset, min(16, length - offset)) for offset in range(0, length, 16)]
    # A single declared command prints many 16-byte rows. Reuse the strict row
    # parser with row declarations derived solely from that command's bounds.
    row_capture = capture | {"fixed_text_commands": [f"dbg mdb {a:x} {n:x}" for a, n in rows]}
    return b"".join(read_block(row_capture, a, n) for a, n in rows)
