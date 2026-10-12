"""Additional fixed NOR windows within one already guarded Actions log session."""

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import UTC, datetime

from . import printk_ring, printk_tail
from .code_guards import observed_block
from .log_stream import Stream

Request = Callable[[bytes], Awaitable[None]]
Pump = Callable[..., Awaitable[None]]
MAX_WINDOW_FRAMES = 8192


def guard_prefix(seed: dict) -> dict:
    """Retain same-session guards, excluding the preceding NOR read and its RAM rows."""
    if not seed.get("printk_tail"):
        raise ValueError("Warm NOR windows require a guarded printk-nor-tail seed")
    printk_tail.verify(seed | {"ok": True})
    command = printk_tail.producer(printk_tail.target(seed), seed.get("nor_block", 0))
    commands = seed["fixed_text_commands"]
    last_guard = f"dbg mdb {printk_tail.GUARDS[-1][0]:x} {len(bytes.fromhex(printk_tail.GUARDS[-1][1])):x}"
    end = seed["range_frame_spans"][last_guard][1]
    if type(end) is not int or not 0 < end <= len(seed["frames"]):
        raise ValueError("Incomplete shared NOR guard prefix")
    keys = (
        "serial",
        "duration_seconds",
        "image_chunk_indices",
        "image_header",
        "printk_state",
        "printk_buffer",
        "printk_tail",
        "nor_target",
        "nor_offset",
        "nor_block",
        "scope",
    )
    prefix = deepcopy({key: seed[key] for key in keys if key in seed})
    prefix.update(
        frames=deepcopy(seed["frames"][:end]),
        fixed_text_commands=commands[: commands.index(command)],
        range_frame_spans={
            name: list(span)
            for name, span in seed["range_frame_spans"].items()
            if type(span[1]) is int and 0 <= span[0] < span[1] <= end
        },
        shared_session_started_at=seed["captured_at"],
        ok=False,
    )
    return prefix


async def capture_remaining(
    seed: dict,
    stream: Stream,
    request: Request,
    pump: Pump,
    windows: tuple[int, ...],
) -> list[dict]:
    """Abort on any missing/invalid row; caller owns transport and final STOP proof."""
    if (
        not isinstance(windows, tuple)
        or len(windows) > 22
        or any(type(window) is not int or not 0 <= window <= 10 for window in windows)
    ):
        raise ValueError("Warm NOR batch requires at most22 windows in0..10")
    prefix = guard_prefix(seed)
    value = printk_tail.target(seed)
    return [await _capture_window(prefix, value, stream, request, pump, window) for window in windows]


async def _capture_window(
    prefix: dict, value: printk_tail.NorTarget, stream: Stream, request: Request, pump: Pump, window: int
) -> dict:
    record = deepcopy(prefix)
    record.update(captured_at=datetime.now(UTC).isoformat(), ring_window=window, context_flush_queries=0)
    iteration_start = len(stream.frames)
    prefix_length = len(record["frames"])

    def refresh() -> None:
        frames = stream.frames[iteration_start:]
        if len(frames) > MAX_WINDOW_FRAMES:
            raise RuntimeError("Warm NOR window frame limit exceeded")
        record["frames"] = prefix["frames"] + frames

    def position() -> int:
        return prefix_length + len(stream.frames) - iteration_start

    async def send(command: str) -> None:
        record["fixed_text_commands"].append(command)
        encoded = command.encode("ascii")
        tlv = b"\x01" + len(encoded).to_bytes(2, "little") + encoded
        await request(b"\x1d\x10\x81" + len(tlv).to_bytes(2, "little") + tlv)
        refresh()

    def rows_ready(start: int, address: int, length: int) -> bool:
        return all(
            observed_block(stream.frames[start:], address + offset, min(16, length - offset)) is not None
            for offset in range(0, length, 16)
        )

    async def wait_rows(start: int, address: int, length: int) -> None:
        async with asyncio.timeout(5):
            while not rows_ready(start, address, length):
                await pump(timeout=5)
                refresh()

    await send(printk_tail.producer(value, record.get("nor_block", 0)))
    context_start = len(stream.frames)
    record["range_frame_spans"][printk_tail.MARKER] = [position(), None]
    await send(printk_tail.MARKER)
    for _ in range(8):
        if rows_ready(context_start, printk_ring.CONTEXT, 28):
            break
        await send("kernel version")
        record["context_flush_queries"] += 1
    await wait_rows(context_start, printk_ring.CONTEXT, 28)
    refresh()
    record["range_frame_spans"][printk_tail.MARKER][1] = position()
    current = record | {"ok": True}
    printk_ring.context(current, 28)
    if printk_ring.read(current, printk_ring.CONTEXT, 28)[20:22] != b"\x01\x00":
        raise ValueError("Current printk DMA ring init/panic flags must be1/0")
    pending = []
    for address, length in printk_tail.tail_ranges(current):
        command = f"dbg mdb {address:x} {length:x}"
        start = len(stream.frames)
        record["range_frame_spans"][command] = [position(), None]
        await send(command)
        pending.append((command, start, address, length))
    # A real wrapped window lost its last row when help printed between halves.
    # Read both physical slices before generating the large flush listing.
    await send("help")
    for command, start, address, length in pending:
        await wait_rows(start, address, length)
        refresh()
        record["range_frame_spans"][command][1] = position()
    record["tail_appended"] = True
    record["console_tail"] = printk_tail.inspect(record | {"ok": True})
    return record
