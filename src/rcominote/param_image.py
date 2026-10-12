"""Inspect fixed CoMi parameter slots offline; CRC coverage is only the first872 B.

Actual boot010106a8..010106ec checks ACPT/FVER magic and their stored CRCs.
Plain and observed32/512-byte codecs are bounded candidates, not assumptions
about either parameter slot. Param0's paired first sector matches independent
cached ACPT bytes only with reset32. No image is executed or device accessed.
"""

import hashlib
import struct
import zlib

from .nor_codec import decode
from .partition_table import inspect_acpt

ACPT_BYTES = 744
FVER_BYTES = 128
CHECKED_BYTES = 872
CACHED_ACPT_SHA = "a071b0cdafad355eb05a71e96fc2cb6a5348ec8b5e11d0ac4dfe54d83671a144"
CACHED_FVER_SHA = "4e9d0059884cd1294c258d7f5bc43e5975641963d043c4d41eba420af0d22dc1"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate(data: bytes) -> dict:
    acpt, fver = data[:ACPT_BYTES], data[ACPT_BYTES:CHECKED_BYTES]
    if acpt[:4] != b"ACPT" or fver[:4] != b"FVER":
        raise ValueError("ACPT/FVER magic mismatch")
    acpt_crc = int.from_bytes(acpt[-4:], "little")
    fver_crc = int.from_bytes(fver[-4:], "little")
    if zlib.crc32(acpt[:-4]) != acpt_crc:
        raise ValueError("ACPT CRC mismatch")
    if zlib.crc32(fver[:-4]) != fver_crc:
        raise ValueError("FVER CRC mismatch")
    # Structural interpretation is reported separately: the actual boot checker
    # only enforces the magic/CRC conditions above, not this SDK field schema.
    try:
        partition = inspect_acpt(acpt)
        partition["scope"] = "decoded physical parameter metadata; configured partition entries"
        layout_error = None
    except ValueError as error:
        partition, layout_error = None, str(error)
    version_code, resource_version, system_version = struct.unpack_from("<3I", fver, 4)
    return {
        "acpt": {
            "sha256": digest(acpt),
            "crc32": f"0x{acpt_crc:08x}",
            "crc_valid": True,
            "matches_cached_sram": digest(acpt) == CACHED_ACPT_SHA,
            "partition_table": partition,
            "layout_error": layout_error,
        },
        "fver": {
            "sha256": digest(fver),
            "crc32": f"0x{fver_crc:08x}",
            "crc_valid": True,
            "matches_cached_sram": digest(fver) == CACHED_FVER_SHA,
            "version_code": f"0x{version_code:08x}",
            "resource_version": f"0x{resource_version:08x}",
            "system_version": f"0x{system_version:08x}",
            # Preserve non-ASCII bytes explicitly rather than invent a decoding.
            "version_name": fver[16:80].split(b"\0", 1)[0].decode("ascii", errors="backslashreplace"),
            "board_name": fver[80:112].split(b"\0", 1)[0].decode("ascii", errors="backslashreplace"),
        },
    }


def _inspect(raw: bytes, offset: int) -> tuple[dict, bytes | None]:
    result = {
        "physical_offset": f"0x{offset:x}",
        "captured_bytes": len(raw),
        "raw_sha256": digest(raw),
        "complete_slot": len(raw) == 4096,
        "boot_metadata_crc_valid": False,
    }
    if raw == b"\xff" * len(raw) or raw == b"\0" * len(raw):
        return result | {
            "classification": "uniform_slot" if len(raw) == 4096 else "uniform_prefix",
            "fill_byte": f"{raw[0]:02x}",
            "valid_parameter": False,
            "note": "Uniform captured bytes are not a valid parameter; prefix does not classify unread tail",
        }, None
    candidates = []
    rejected = {}
    prefix = raw[:1024]
    for profile, data in (
        ("plain", prefix),
        ("reset32", decode(prefix, block_bytes=32)),
        ("reset512", decode(prefix, block_bytes=512)),
    ):
        try:
            metadata = _validate(data)
        except ValueError as error:
            rejected[profile] = str(error)
            continue
        candidates.append((profile, data, metadata))
    if len(candidates) != 1:
        raise ValueError(
            f"Parameter slot0x{offset:x}: expected exactly one interpretable plain/reset32/reset512 profile; "
            f"found {len(candidates)}; {rejected}"
        )
    profile, data, metadata = candidates[0]
    return result | {
        "classification": "validated_parameter_metadata",
        "valid_parameter": True,
        "boot_metadata_crc_valid": True,
        "profile": profile,
        "decoded_prefix_1024_sha256": digest(data),
        "decoded_checked_prefix_sha256": digest(data[:CHECKED_BYTES]),
        "crc_covered_bytes": CHECKED_BYTES,
        "bytes_outside_crc_coverage": len(raw) - CHECKED_BYTES,
        "decoded_tail_semantics_verified": False,
        "part_marker_at_1020": data[1020:1024] == b"part",
        **metadata,
    }, data[:CHECKED_BYTES]


def inspect_slots(primary: bytes, backup: bytes) -> dict:
    """Inspect paired input buffers; caller separately proves independent reads.

    Accept only equal1024-byte prefixes or equal4096-byte complete slots. Any
    nonuniform uninterpretable slot, ambiguous codec, or no valid metadata stops
    the acquisition gate. Checksums do not cover padding or authenticate boot.
    """
    if len(primary) != len(backup) or len(primary) not in (1024, 4096):
        raise ValueError("Parameter inputs require equal lengths, exactly1024 or4096 bytes each")
    first, first_metadata = _inspect(primary, 0x1000)
    second, second_metadata = _inspect(backup, 0x3000)
    if first_metadata is None and second_metadata is None:
        raise ValueError("Neither parameter slot contains interpretable ACPT/FVER metadata")
    both_valid = first_metadata is not None and second_metadata is not None
    return {
        "scope": "fixed parameter slot bytes and static boot metadata checks; no execution or restore proof",
        "complete": len(primary) == 4096,
        "crc_coverage_per_valid_slot": "[0x0,0x368), including stored ACPT/FVER CRC words",
        "pairing_scope": "caller must independently verify repeated physical reads",
        "codec_profile_evidence": {
            "reset32": {
                "basis": "paired param0 first sector decoded equals independent cached ACPT first512 bytes",
                "raw_sector_sha256": "a68cd2b9f73f9b2d09231f440bce02efe52216961acaad1b633f360d34d901db",
                "cached_plain_prefix_sha256": "2500396c8205615e6eb258a28cfcc2a2d3cd7da1c262091940e55559d4a2f37e",
            },
            "reset512": {
                "basis": "independently verified complete boot codec; not assumed for parameters",
                "raw_boot_sha256": "782c26c3ba9bee07a8b0b464898fb963a76eb35a2916586b854f8f45993f4166",
            },
            "effective_state": "0x0a15a191; observed conversion state, not recovered efuse key",
        },
        "primary": first,
        "backup": second,
        "comparison": {
            "raw_equal": primary == backup,
            "raw_different_bytes": sum(a != b for a, b in zip(primary, backup, strict=True)),
            "both_metadata_valid": both_valid,
            "decoded_metadata_equal": first_metadata == second_metadata if both_valid else None,
            "acpt_equal": first_metadata[:744] == second_metadata[:744] if both_valid else None,
            "fver_equal": first_metadata[744:] == second_metadata[744:] if both_valid else None,
        },
        "cached_oracles": {
            "acpt": {
                "source": "docs/evidence/partition-analysis-2026-10-12.json:blocks",
                "sram_address": "0x01000040",
                "bytes": 744,
                "sha256": CACHED_ACPT_SHA,
            },
            "fver": {
                "sources": [
                    "docs/evidence/firmware-identity-first-2026-10-12.json:parameter_version_hex",
                    "docs/evidence/firmware-identity-second-2026-10-12.json:parameter_version_hex",
                ],
                "sram_address": "0x01000328",
                "bytes": 128,
                "sha256": CACHED_FVER_SHA,
            },
        },
    }
