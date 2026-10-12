"""Live prerequisites for fixed instruction-derived memory reads."""

import re

from .ble_target import OWNED_SERIAL
from .card_readback import CARD_GUARDS
from .code_references import read_block
from .read_sets import (
    DISK_CONTROLLER,
    DISK_DEVICE,
    DISK_DEVICE_REFS,
    DISK_DRIVER_ENTRY,
    DISK_DRIVER_GLOBAL,
    DISK_DRIVER_LITERAL,
    DISK_ENTRY,
    DISK_FS,
    DISK_LIST,
    DISK_MORE,
    DISK_NODE,
    DISK_OPS,
    DISK_REGISTRY_BODY,
    DISK_REGISTRY_ENTRY,
    DISK_STATUS_ENTRY,
    DISK_STATUS_MORE,
    DISK_TABLES,
    DISK_VOLUME_BODY,
    INFO_STORAGE_CALLBACK,
    INFO_STORAGE_CALLBACK_TAIL,
    INFO_STORAGE_MORE,
    INFO_STORAGE_MOUNT,
    INFO_STORAGE_TABLE,
    INFO_STORAGE_VOLUME,
    INFO_STORAGE_VTABLE,
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
        *CARD_GUARDS,
        (
            DISK_CONTROLLER,
            (
                (0x100BC398, "e9ae0c1000400c00", "SD config controller-name pointer"),
                (0x18005BE8, "00a10b10", "SD data controller pointer"),
            ),
        ),
        (
            DISK_DEVICE_REFS,
            (
                (0x100BA160, "f3ae0c1098c30b10a0c30b1010300018", "SD device identity/config/API"),
                (0x100BA170, "e85b0018", "SD device data pointer"),
            ),
        ),
        (DISK_DEVICE, ((0x1800C3F0, "60a10b10", "SD backend device pointer"),)),
        (DISK_DRIVER_GLOBAL, ((0x10025960, "f0c30018", "SD device global literal"),)),
        (
            DISK_DRIVER_LITERAL,
            ((0x10025950, "034b1b68002b0cbf02200020704700bf", "SD status global-pointer load"),),
        ),
        (DISK_DRIVER_ENTRY, ((0x1800197C, "b55a02105159021065590210a1590210", "SD status callback"),)),
        (
            DISK_OPS,
            (
                (0x1800195C, "d4c30018d4c30018546f0c1000020000", "SD disk node identity"),
                (0x1800196C, "0000000000b047077c19001800000000", "SD disk ops pointer"),
            ),
        ),
        (DISK_NODE, ((0x1800C3D4, "5c1900185c190018", "disk registry sole node"),)),
        (DISK_LIST, ((0x100258C4, "d4c30018dcc30018", "registry head literal"),)),
        (
            DISK_REGISTRY_BODY,
            ((0x10025870, "f8b50746dbf732fa0646124d12484ff0", "disk registry entry/literals"),),
        ),
        (
            DISK_FS,
            (
                (0x1800FD5C, "8c0a0118", "active FatFs pointer"),
                (0x100BC778, "546f0c10", "SD disk-name pointer"),
                (0x100A796E, "3490da69a9f10206b24209d8c8f80020", "FatFs count offsets"),
            ),
        ),
        (DISK_REGISTRY_ENTRY, ((0x100A1998, "10b583f769ff30b1836923b15b6813b1", "registry lookup call"),)),
        (
            DISK_TABLES,
            (
                (0x10040DC0, "68c70b103be20c10", "disk-name table literal"),
                (0x1003F864, "4cfd0018", "FatFs table literal"),
            ),
        ),
        (
            DISK_STATUS_MORE,
            ((0x10040D9C, "042808b509d8074b53f8200060f0f6fd", "named-disk status call/literal"),),
        ),
        (DISK_STATUS_ENTRY, ((0x1003F6B4, "237805f0fe056bb1607801f06dfbc707", "disk status direct call"),)),
        (
            DISK_VOLUME_BODY,
            (
                (0x1003F684, "2de9ff4700230b600f461546fff72cfc", "volume lookup entry"),
                (0x1003F694, "061ec0f2dc81724b53f82640002c00f0", "filesystem table load"),
            ),
        ),
        (
            DISK_MORE,
            (
                (0x100A794E, "2de9f04391b088460190154603a90022", "free-cluster entry"),
                (0x100A795E, "01a897f790fe044650b9039b2b60d3f8", "volume-lookup direct call"),
            ),
        ),
        (
            (*INFO_STORAGE_CALLBACK_TAIL, *DISK_ENTRY),
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
