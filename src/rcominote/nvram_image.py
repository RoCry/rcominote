"""Bounded, host-only inspection of the two factory-RW NVRAM segments.

Format reference: lvgl/lv_port_actions_technology@26f51e584940d5b141cd1d09d2629d69b595f579,
zephyr/drivers/nvram/nvram_config.c and tools/build_nvram_bin.py. No codec
guessing, runtime segment selection, values in reports, or device operations.
The numeric magic0x5253564E is bytes'NVSR', despite the source comment'NVRS'.
This strict archival validator is not an emulation of the driver's recovery.
"""

import hashlib
import struct

SEGMENT_BYTES = 4096
REGION_BYTES = 8192
PHYSICAL_BASE = 0x1EC000
SOURCE = {
    "repository": "lvgl/lv_port_actions_technology",
    "commit": "26f51e584940d5b141cd1d09d2629d69b595f579",
    "root": "action_technology_sdk/zephyr/",
    "sha256": {
        "drivers/nvram/nvram_config.c": "151646f26771871fcc1156748b53ce4785b6832eb0a8579f683dc791b55f9c72",
        "tools/build_nvram_bin.py": "23bca206c213eb579bc46a54f95a351b352dec5592fbfc9eb3c5956fb67bc36f",
        "tools/nvram_prop.py": "c615b7d45e135e5f3bfab20b52e9b958e972269ac27082dce7b29ac3a0525eb9",
    },
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _crc8(data: bytes) -> int:
    # Reflected CRC-8/MAXIM (poly0x31, init0); independent bitwise expression
    # rather than the reference packer/driver's nibble lookup table.
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x8C if crc & 1 else 0)
    return crc


def _fail(offset: int, reason: str) -> None:
    # Never include raw input or a candidate key/value in diagnostics.
    raise ValueError(f"NVRAM region offset0x{offset:x}: {reason}")


def _header(data: bytes, offset: int) -> dict:
    result = {
        "region_offset": offset,
        "physical_offset": f"0x{PHYSICAL_BASE + offset:x}",
        "captured_bytes": len(data),
        "sha256": _sha(data),
        "complete_segment": len(data) == SEGMENT_BYTES,
    }
    if data == b"\xff" * len(data):
        return result | {
            "classification": "erased_segment" if len(data) == SEGMENT_BYTES else "erased_prefix",
            "header_crc_valid": False,
            "state": None,
        }
    if data[:4] != b"NVSR":
        _fail(offset, "unknown non-erased segment magic")
    state, stored_crc, version, reserved, sequence, head_size, seg_size = struct.unpack_from("<6BH", data, 4)
    if _crc8(data[6:16]) != stored_crc:
        _fail(offset, "segment header CRC mismatch")
    if state not in (0xFF, 0x5A):
        _fail(offset, "unsupported segment state")
    if version != 1 or head_size != 16 or seg_size != SEGMENT_BYTES:
        _fail(offset, "unsupported version/header/segment size")
    if reserved or data[12:16] != b"\0" * 4:
        _fail(offset, "unsupported segment reserved fields")
    return result | {
        "classification": "nvsr_header",
        "state": "valid_marker" if state == 0xFF else "obsolete_marker",
        "sequence": sequence,
        "version": version,
        "header_bytes": head_size,
        "segment_bytes": seg_size,
        "header_crc8": f"0x{stored_crc:02x}",
        "header_crc_valid": True,
        "header_crc_coverage": "segment[6:16]; excludes magic and state; not a whole-segment CRC",
    }


def _report(segments: list[dict], *, complete: bool) -> dict:
    if not any(segment["state"] == "valid_marker" for segment in segments):
        raise ValueError("No interpretable NVSR segment with a valid state marker")
    return {
        "scope": "fixed factory-RW raw bytes and reference-format checks; no runtime selection or restore proof",
        "complete": complete,
        "segments": segments,
        "active_segment": None,
        "runtime_selection_verified": False,
        "pairing_scope": "caller must independently verify repeated physical reads",
        "values_included": False,
        "source": SOURCE,
    }


def inspect_headers(first512: bytes, second512: bytes) -> dict:
    """Gate further capture using two exact512-byte prefixes, at offsets0/4096.

    An erased prefix says nothing about unread bytes. Item CRCs and item spans
    are intentionally not checked here: an item may extend beyond the prefix.
    Any unknown non-erased header, or absence of a valid marker, stops the gate.
    """
    if len(first512) != 512 or len(second512) != 512:
        raise ValueError("NVRAM header gate requires exactly two512-byte prefixes")
    return _report([_header(first512, 0), _header(second512, SEGMENT_BYTES)], complete=False)


def _items(data: bytes, base: int) -> dict:
    items = []
    offset = 16
    while offset < SEGMENT_BYTES:
        head = data[offset : offset + 8]
        if head == b"\xff" * 8:
            if data[offset:] != b"\xff" * (SEGMENT_BYTES - offset):
                _fail(base + offset, "non-erased bytes after empty item header")
            break
        magic, state, stored_crc, name_hash, reserved, name_size, data_size = struct.unpack("<6BH", head)
        if magic != 0x49 or state not in (0xFF, 0x5A) or reserved:
            _fail(base + offset, "unsupported item magic/state/reserved field")
        if not 2 <= name_size <= 120:
            _fail(base + offset, "unsupported name length for reference128-byte write buffer")
        end = offset + 8 + name_size + data_size
        next_offset = (end + 15) & ~15
        if next_offset > SEGMENT_BYTES:
            _fail(base + offset, "item span exceeds segment boundary")
        name = data[offset + 8 : offset + 8 + name_size]
        if name[-1] != 0 or any(byte < 0x21 or byte > 0x7E for byte in name[:-1]):
            _fail(base + offset, "unsupported key encoding or termination")
        if ((sum(name) & 0xFF) ^ 0xA5) != name_hash:
            _fail(base + offset, "item name hash mismatch")
        if _crc8(data[offset + 3 : end]) != stored_crc:
            _fail(base + offset, "item CRC mismatch, including obsolete records")
        if data[end:next_offset] != b"\xff" * (next_offset - end):
            _fail(base + offset, "non-erased item alignment padding")
        value = data[offset + 8 + name_size : end]
        items.append(
            {
                "region_offset": base + offset,
                "state": "valid_marker" if state == 0xFF else "obsolete_marker",
                "key": name[:-1].decode("ascii"),
                "name_bytes": name_size,
                "value_bytes": data_size,
                "value_sha256": _sha(value),
                "record_sha256": _sha(data[offset:end]),
                "record_bytes": end - offset,
                "aligned_bytes": next_offset - offset,
                "item_crc8": f"0x{stored_crc:02x}",
                "item_crc_valid": True,
                "name_hash_valid": True,
            }
        )
        offset = next_offset
    return {"items": items, "item_count": len(items), "erased_tail_bytes": SEGMENT_BYTES - offset}


def inspect_region(raw: bytes) -> dict:
    """Validate exactly8192 bytes, retaining obsolete records without selecting one.

    Bad CRCs even on obsolete records, unsupported fields and dirty padding
    stop interpretation. This deliberately exceeds the runtime driver's checks;
    rejection is not proof that the device cannot boot or use remaining records.
    Header/item CRCs exclude state bytes and erased/padding bytes. Hashes are
    integrity metadata, not privacy anonymization; keep device reports private.
    """
    if len(raw) != REGION_BYTES:
        raise ValueError("NVRAM region inspection requires exactly8192 bytes")
    segments = []
    for base in (0, SEGMENT_BYTES):
        data = raw[base : base + SEGMENT_BYTES]
        segment = _header(data, base)
        segment |= (
            _items(data, base)
            if segment["header_crc_valid"]
            else {"items": [], "item_count": 0, "erased_tail_bytes": SEGMENT_BYTES}
        )
        segments.append(segment)
    return _report(segments, complete=True) | {"raw_sha256": _sha(raw), "captured_bytes": len(raw)}
