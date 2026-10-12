"""Strict multiline mdb parsing; initial fixed probe rereads an already validated header."""

import hashlib

from .code_references import read_block

BODY_PROBE_RANGES = tuple((address, 512) for address in range(0x10000200, 0x10000A00, 512))

HEADER_BATCH_READS = ((0x10000000, 512),)
HEADER_PROBE_RANGES = tuple((0x10000000, size) for size in (64, 256, 512))


def read_range(capture: dict, address: int, length: int) -> bytes:
    if length <= 0 or length > 512 or address % 16:
        raise ValueError("Range must be aligned and contain 1..512 bytes")
    command = f"dbg mdb {address:x} {length:x}"
    if command not in capture.get("fixed_text_commands", []):
        raise ValueError(f"Missing declared range: {command}")
    capture = scoped_capture(capture, command)
    rows = [(address + offset, min(16, length - offset)) for offset in range(0, length, 16)]
    # A single declared command prints many 16-byte rows. Reuse the strict row
    # parser with row declarations derived solely from that command's bounds.
    row_capture = capture | {"fixed_text_commands": [f"dbg mdb {a:x} {n:x}" for a, n in rows]}
    return b"".join(read_block(row_capture, a, n) for a, n in rows)


def validate_known_header(data: bytes) -> None:
    if hashlib.sha256(data).hexdigest() != "911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5":
        raise ValueError("Mapped header differs from independently validated FW010004 header")


def image_ranges(indices: tuple[int, ...] | list[int]) -> tuple[tuple[int, int], ...]:
    """Fixed observed image body only; at most 64 chunks per bounded BLE session."""
    if len(indices) > 64 or len(set(indices)) != len(indices):
        raise ValueError("Image session requires at most 64 distinct chunk indices")
    if any(type(index) is not int or index < 0 or index * 512 >= 927120 for index in indices):
        raise ValueError("Image chunk lies outside the independently validated body")
    return tuple(
        (0x10000200 + index * 512 + offset, min(256, 927120 - index * 512 - offset))
        for index in indices
        for offset in (0, 256)
    )


def range_commands(ranges: tuple[tuple[int, int], ...]) -> list[str]:
    return [command for address, length in ranges for command in (f"dbg mdb {address:x} {length:x}", "help")]


def read_image_chunk(capture: dict, index: int) -> bytes:
    return b"".join(read_range(capture, address, length) for address, length in image_ranges([index]))


def scoped_capture(capture: dict, command: str) -> dict:
    if span := capture.get("range_frame_spans", {}).get(command):
        start, end = span
        if end is None or not 0 <= start < end <= len(capture["frames"]):
            raise ValueError(f"Incomplete frame span for {command}")
        capture = capture | {"frames": capture["frames"][start:end]}
    return capture
