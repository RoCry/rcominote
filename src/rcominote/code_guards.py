"""Live prerequisites for fixed instruction-derived memory reads."""

import re

from .ble_target import OWNED_SERIAL
from .code_references import (
    INFO_STORAGE_CALLBACK,
    INFO_STORAGE_CALLBACK_TAIL,
    INFO_STORAGE_MORE,
    INFO_STORAGE_MOUNT,
    INFO_STORAGE_TABLE,
    INFO_STORAGE_VOLUME,
    INFO_STORAGE_VTABLE,
    read_block,
)


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


def observed_capacity_entries(frames: list[dict]) -> bool:
    return all(
        observed_code(frames, address, expected, "capacity getter")
        for address, expected in (
            (0x100549C0, "1fb50446fff79afe002812db69462046"),
            (0x100549D0, "daf73cfc104a114b9b1a5b0103f47f43"),
            (0x10054A28, "1fb50446fff766fe002812db69462046"),
            (0x10054A38, "daf708fc104a114b9b1a5b0103f47f43"),
        )
    )


def observed_storage_entries(frames: list[dict]) -> bool:
    return all(
        observed_code(frames, address, expected, "storage-query entry/branch")
        for address, expected in (
            (0x100546FC, "70b50e4e0546002456f8041b2846acf7"),
            (0x1005470C, "ddfa28b10134052cf6d16ff015040ae0"),
            (0x1002F24C, "73b50e46054688b9214b22482249c01a"),
        )
    )


def observed_storage_reference(frames: list[dict], command: str) -> bool:
    """Fail before dereferencing a stale mount or following changed code."""
    prerequisites = (
        (
            INFO_STORAGE_CALLBACK_TAIL,
            (
                (0x100A42D6, "13b5c068144604f10c0101aa013003f0", "SD callback entry"),
                (0x100A42E6, "33fb58b9019a4ff40073236053895b02", "SD callback branch"),
            ),
        ),
        (INFO_STORAGE_CALLBACK, ((0x100BC0E0, "d7420a10", "SD statvfs callback pointer"),)),
        (INFO_STORAGE_TABLE, ((0x10054738, "24ce0b10b07b0118", "volume-table literals"),)),
        (
            INFO_STORAGE_VOLUME,
            (
                (0x1005471C, "074b03ebc4031b79da07f6d513f0020f", "volume stride and flags"),
                (0x100BCE34, "43120c10", "SD volume index"),
                (0x10054738, "24ce0b10b07b0118", "volume array literal"),
            ),
        ),
        (INFO_STORAGE_MOUNT, ((0x18017BD0, "640a011803000000", "SD mount pointer and flags"),)),
        (
            INFO_STORAGE_VTABLE,
            (
                (0x18010A64, "e40c0118f8f700180000000043120c10", "SD mount identity"),
                (0x18010A74, "8c0a011800000000040000009cc00b10", "SD mount vtable"),
                (0x1002F2AC, "0198c3695b6c002bddd0324629469847", "statvfs indirect call"),
            ),
        ),
    )
    if command in {f"dbg mdb {a:x} {n:x}" for a, n, _, _ in INFO_STORAGE_MORE}:
        return observed_storage_entries(frames)
    for blocks, checks in prerequisites:
        if command in {f"dbg mdb {a:x} {n:x}" for a, n, _, _ in blocks}:
            return all(observed_code(frames, address, value, name) for address, value, name in checks)
    return True


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
