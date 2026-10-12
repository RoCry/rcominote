"""Single fixed NOR-offset probe followed by a bounded retained-log tail."""

from . import printk_ring
from .range_readback import range_commands

GUARDS = (
    (0x10025348, "2de9f043032985b00546144606d0294a"),
    (0x100BB960, "636b0c10696b0c100000000049530210"),
)
PRODUCER = "dbg fread spi_flash 0"
MARKER = f"dbg mdb {printk_ring.CONTEXT:x} 1c"
INITIAL = (
    range_commands(printk_ring.READS[: len(printk_ring.GUARDS) + 1])
    + range_commands(tuple((a, len(bytes.fromhex(v))) for a, v in GUARDS))
    + [PRODUCER, MARKER]
    + ["kernel version"] * 8
)


def verify(capture: dict) -> None:
    printk_ring.verify(capture, payload=True)
    for address, expected in GUARDS:
        if printk_ring.read(capture, address, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError("NOR fread descriptor/entry differs from fixed firmware profile")


def tail_ranges(capture: dict) -> tuple[tuple[int, int], ...]:
    write = printk_ring.context(capture, 28)["write_index"]
    window = capture.get("ring_window", 0)
    if type(window) is not int or not 0 <= window <= 10:
        raise ValueError("Ring window must be one of 0..10")
    start = (write - (256 + 192 * window)) % printk_ring.CAPACITY
    first = min(256, printk_ring.CAPACITY - start)
    return ((printk_ring.BUFFER + start, first),) + (
        ((printk_ring.BUFFER, 256 - first),) if first < 256 else ()
    )


def flush_due(capture: dict, command: str) -> bool:
    """Eight small version queries flush context without a full help listing."""
    if command == "help":
        return True
    if capture.get("printk_tail") and command == "kernel version":
        capture["tail_flush_queries"] = capture.get("tail_flush_queries", 0) + 1
        return capture["tail_flush_queries"] == 8
    return False


def append_tail(capture: dict) -> None:
    """Called after context's flush, once only; addresses stay in fixed static ring."""
    if (
        capture.get("printk_tail")
        and not capture.get("tail_appended")
        and MARKER in capture["range_frame_spans"]
        and capture["range_frame_spans"][MARKER][1] is not None
    ):
        verify(capture | {"ok": True})
        capture["fixed_text_commands"].extend(range_commands(tail_ranges(capture | {"ok": True})))
        capture["tail_appended"] = True


def inspect(capture: dict) -> dict:
    verify(capture)
    if not capture.get("tail_appended"):
        raise ValueError("Missing dynamically bounded tail reads")
    raw = b"".join(printk_ring.read(capture, a, n) for a, n in tail_ranges(capture))
    return {
        "producer": PRODUCER,
        "window": capture.get("ring_window", 0),
        "context": printk_ring.context(capture, 28),
        "ranges": tail_ranges(capture),
        "bytes": len(raw),
        "hex": raw.hex(),
        "text": raw.decode("ascii", errors="replace"),
        "scope": "Non-atomic 256 B log tail after fixed offset-zero read; no raw-data completeness claim",
    }
