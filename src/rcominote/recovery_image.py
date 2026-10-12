"""Offline verification of the fixed CoMi recovery image; no device I/O."""

import hashlib
import struct

from .nor_codec import decode
from .printk_tail import RECOVERY_BYTES
from .sdfs_checksum import checksum32

HEADER_SHA = "121a4b6beb56293ded54630fb33cfc871cfc64cbfaf23454e7f3e1d7763374b9"


def verify(raw: bytes) -> tuple[bytes, dict]:
    if len(raw) != RECOVERY_BYTES:
        raise ValueError("Recovery image must contain exactly63288 raw bytes")
    plain = decode(raw, block_bytes=32)
    if hashlib.sha256(plain[:512]).hexdigest() != HEADER_SHA:
        raise ValueError("Recovery header differs from independently verified device header")
    body_size, body_checksum = struct.unpack_from("<II", plain, 24)
    if body_size != len(plain) - 512 or checksum32(plain[:512]) != 0xFFFFFFFF:
        raise ValueError("Recovery header size/checksum failed")
    if (checksum32(plain[512:]) + body_checksum) & 0xFFFFFFFF != 0xFFFFFFFF:
        raise ValueError("Recovery body checksum failed; decode profile or readback requires investigation")
    return plain, {
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "decoded_sha256": hashlib.sha256(plain).hexdigest(),
        "header_checksum_valid": True,
        "body_checksum_valid": True,
        "decode_reset_bytes": 32,
    }
