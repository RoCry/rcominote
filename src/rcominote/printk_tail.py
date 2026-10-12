"""Named fixed NOR-offset probe followed by a bounded retained-log tail."""

import re
from enum import StrEnum

from . import printk_ring
from .range_readback import range_commands

GUARDS = (
    (0x10025348, "2de9f043032985b00546144606d0294a"),
    (0x100BB960, "636b0c10696b0c100000000049530210"),
)


class NorTarget(StrEnum):
    boot = "boot"
    backup_boot = "backup-boot"
    recovery = "recovery"
    system = "system"
    dsp = "dsp"
    record_dsp = "record-dsp"
    record_dsp_header_end = "record-dsp-header-end"


TARGET_OFFSETS = {
    NorTarget.boot: 0,
    NorTarget.backup_boot: 0x2000,
    NorTarget.recovery: 0x4000,
    NorTarget.system: 0x24000,
    NorTarget.dsp: 0x240000,
    NorTarget.record_dsp: 0x24D400,
    NorTarget.record_dsp_header_end: 0x24D600,
}
MARKER = f"dbg mdb {printk_ring.CONTEXT:x} 1c"
RECORD_DSP_BYTES = 110148  # Double-read SDFS directory, actual aerecord.dsp.


def block_offset(value: NorTarget, block: int = 0) -> int:
    if type(block) is not int or block < 0:
        raise ValueError("NOR block must be a nonnegative integer")
    if block and (value != NorTarget.record_dsp or block * 512 >= RECORD_DSP_BYTES):
        raise ValueError("Additional NOR blocks are limited to the known recording DSP file")
    return TARGET_OFFSETS[value] + block * 512


def validate_options(value: NorTarget, window: int, enabled: bool) -> NorTarget:
    if type(window) is not int or not 0 <= window <= 10 or (window and not enabled):
        raise ValueError("Ring window 0..10 is only available with printk-nor-tail")
    value = NorTarget(value)
    if value != NorTarget.boot and not enabled:
        raise ValueError("NOR target is only available with printk-nor-tail")
    return value


def target(capture: dict) -> NorTarget:
    value = NorTarget(capture.get("nor_target", NorTarget.boot))
    expected = block_offset(value, capture.get("nor_block", 0))
    offset = capture.get("nor_offset", expected)
    if type(offset) is not int or offset != expected:
        raise ValueError("NOR target and offset do not match fixed firmware profile")
    return value


def producer(value: NorTarget = NorTarget.boot, block: int = 0) -> str:
    offset = block_offset(value, block)
    return f"dbg fread spi_flash {hex(offset) if offset else '0'}"


PRODUCER = producer()


def initial(value: NorTarget, block: int = 0) -> list[str]:
    return (
        range_commands(printk_ring.READS[: len(printk_ring.GUARDS) + 1])
        + range_commands(tuple((a, len(bytes.fromhex(v))) for a, v in GUARDS))
        + [producer(value, block), MARKER]
        + ["kernel version"] * 8
    )


def verify_producer(capture: dict) -> NorTarget:
    value = target(capture)
    expected = producer(value, capture.get("nor_block", 0))
    commands = capture["fixed_text_commands"]
    if not isinstance(commands, list) or not all(isinstance(command, str) for command in commands):
        raise ValueError("Invalid fixed producer command list")
    if commands.count(expected) != 1 or any(
        command.startswith("dbg fread ") and command != expected for command in commands
    ):
        description = "offset-zero" if value == NorTarget.boot else value.value
        raise ValueError(f"Expected exactly one fixed {description} NOR producer")
    return value


def verify(capture: dict) -> None:
    verify_producer(capture)
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
        capture["fixed_text_commands"].extend(
            [f"dbg mdb {address:x} {length:x}" for address, length in tail_ranges(capture | {"ok": True})]
            + ["help"]
        )
        capture["tail_appended"] = True


def verify_producer_output(capture: dict, value: NorTarget) -> None:
    last_guard = f"dbg mdb {GUARDS[-1][0]:x} {len(bytes.fromhex(GUARDS[-1][1])):x}"
    spans = capture["range_frame_spans"]
    start, end = spans[last_guard][1], spans[MARKER][1]
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(capture["frames"]):
        raise ValueError("Invalid NOR producer output frame interval")
    text = "".join(frame.get("text", "") for frame in capture["frames"][start:end])
    block = capture.get("nor_block", 0)
    command = producer(value, block)
    status = re.search(rf"\r\nfread 512b: offset=0x{block_offset(value, block):x}, buf=0x[0-9a-f]+\r\n", text)
    echo = f"logsrv: cmd({len(command)}) {command}\r\n"
    if status is None or text.find(echo, status.end()) < 0:
        raise ValueError("Captured NOR producer status/echo does not match declared target")


def inspect(capture: dict) -> dict:
    verify(capture)
    if not capture.get("tail_appended"):
        raise ValueError("Missing dynamically bounded tail reads")
    value = target(capture)
    verify_producer_output(capture, value)
    raw = b"".join(printk_ring.read(capture, a, n) for a, n in tail_ranges(capture))
    return {
        "producer": producer(value, capture.get("nor_block", 0)),
        "target": value.value,
        "offset": block_offset(value, capture.get("nor_block", 0)),
        "window": capture.get("ring_window", 0),
        "context": printk_ring.context(capture, 28),
        "ranges": tail_ranges(capture),
        "bytes": len(raw),
        "hex": raw.hex(),
        "text": raw.decode("ascii", errors="replace"),
        "scope": "Non-atomic 256 B log tail after fixed named NOR read; no raw-data completeness claim",
    }
