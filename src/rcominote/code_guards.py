"""Live prerequisites for fixed instruction-derived memory reads."""

import re

from .ble_target import OWNED_SERIAL
from .code_references import read_block


def observed_logsrv_entry(frames: list[dict]) -> bool:
    text = "".join(frame.get("text", "") for frame in frames)
    match = re.search(r"(?m)^\*0x[0-9a-f]+ logsrv[ \t]*\r?\n[^\n]*\n[^\n]*entry: (0x[0-9a-f]+)", text)
    if match and match[1] != "0x1000bf21":
        raise ValueError(f"Live logsrv entry changed: {match[1]}; fixed sample is not applicable")
    return match is not None


def observed_vendor_entries(frames: list[dict]) -> bool:
    """Both exact live thread names/entries must precede fixed vendor code reads."""
    text = "".join(frame.get("text", "") for frame in frames)
    complete = True
    for name, expected in (("vendor_read", "0x1000a01d"), ("vendor", "0x10009e9d")):
        entries = re.findall(
            rf"(?m)^[ *]0x[0-9a-f]+ {name}[ \t]*\r?\n[^\n]*\n[^\n]*entry: (0x[0-9a-f]+)",
            text,
        )
        if entries and entries != [expected]:
            raise ValueError(f"Live {name} entry changed or repeated: {entries}")
        complete = complete and bool(entries)
    return complete


def observed_block(frames: list[dict], address: int, length: int) -> bytes | None:
    text = "".join(frame.get("text", "") for frame in frames)
    if not re.search(rf"(?m)^{address:08x}:[^\r\n]*\r?\n", text):
        return None
    capture = {
        "serial": OWNED_SERIAL,
        "ok": True,
        "fixed_text_commands": [f"dbg mdb {address:x} {length:x}"],
        "frames": frames,
    }
    return read_block(capture, address, length)


def observed_code(frames: list[dict], address: int, expected: str, name: str) -> bool:
    data = observed_block(frames, address, len(bytes.fromhex(expected)))
    if data is None:
        return False
    if data.hex() != expected:
        raise ValueError(f"Live {name} code changed; fixed references are not applicable")
    return True


def observed_vendor_code(frames: list[dict]) -> bool:
    return observed_code(frames, 0x1000A01C, "8fb5544c544b55485549564fdff88081", "vendor_read")


def observed_vendor_call(frames: list[dict]) -> bool:
    return observed_code(frames, 0x1000A14C, "01f032f905460020a3f027fd002d05da", "vendor call")


def observed_handler_entry(frames: list[dict]) -> bool:
    return observed_code(
        frames, 0x1000B3B4, "f7b5684b684d0778ed1a6d0105f47f45", "handler entry"
    ) and observed_code(frames, 0x1000B3C4, "064645f43c003a4640f031000c466349", "handler continuation")


def observed_logsrv_code(frames: list[dict]) -> bool:
    text = "".join(frame.get("text", "") for frame in frames)
    rows = re.findall(r"(?m)^1000bf20: ((?:[0-9a-f]{2} ){15}[0-9a-f]{2}) {2,}", text)
    if rows and rows != ["2d e9 f0 47 61 49 62 4e 86 b0 50 20 a1 f0 ab fa"]:
        raise ValueError("Live logsrv code changed or repeated; literal addresses are not applicable")
    return bool(rows)


def observed_logsrv_literals(frames: list[dict]) -> bool:
    text = "".join(frame.get("text", "") for frame in frames)
    rows = re.findall(r"(?m)^1000c0ac: ((?:[0-9a-f]{2} ){7}[0-9a-f]{2}) {2,}", text)
    if rows and rows != ["ba 26 0c 10 1c a5 0b 10"]:
        raise ValueError("Live logsrv literals changed or repeated; references are not applicable")
    return bool(rows)
