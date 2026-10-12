"""Validate the observed mapped ACTH header, without claiming a raw flash image."""

import hashlib
import struct


def inspect_image_header(header: bytes, vectors: bytes) -> dict:
    if len(header) != 512 or len(vectors) != 8:
        raise ValueError("Observed ACTH profile requires a 512-byte header and 8-byte vector prefix")
    (
        magic0,
        magic1,
        load_addr,
        name,
        entry,
        image_size,
        image_sum,
        header_sum,
        header_size,
        protected_tlv,
        tlv,
        version,
        flags,
        ic_type,
        storage_type,
    ) = struct.unpack_from("<3I8s4I4HI7sB", header)
    if (magic0, magic1) != (0x48544341, 0x41435448) or header_size != 512:
        raise ValueError("ACTH magic or observed header size mismatch")
    if sum(struct.unpack("<128I", header)) & 0xFFFFFFFF != 0xFFFFFFFF:
        raise ValueError("ACTH additive header checksum mismatch")
    sp, reset = struct.unpack("<2I", vectors)
    if entry != reset or not reset & 1:
        raise ValueError("ACTH entry and Thumb reset vector disagree")
    return {
        "scope": "mapped image header and vector prefix only; image body checksum and raw-flash equivalence unverified",
        "mapped_header_address": "0x10000000",
        "header_sha256": hashlib.sha256(header).hexdigest(),
        "header_bytes": header_size,
        "header_checksum_valid": True,
        "stored_header_checksum": hex(header_sum),
        "name": name.split(b"\0", 1)[0].decode("ascii"),
        "load_addr_field": hex(load_addr),
        "entry": hex(entry),
        "image_bytes": image_size,
        "mapped_body_end_exclusive": hex(0x10000000 + header_size + image_size),
        "stored_image_checksum": hex(image_sum),
        "image_checksum_verified": False,
        "protected_tlv_bytes": protected_tlv,
        "tlv_bytes": tlv,
        "version": version,
        "flags": hex(flags),
        "sdk_image_flag4_set": bool(flags & 4),
        "ic_type_hex": ic_type.hex(),
        "storage_type": storage_type,
        "vector_sp": hex(sp),
        "vector_reset": hex(reset),
        "vector_entry_matches": True,
    }
