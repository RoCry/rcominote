"""Independent mapped bytes, stored boot checksums, and captured recovery boundaries."""

import struct
from pathlib import Path

import pytest

from rcominote.nor_codec import decode
from rcominote.printk_tail import NorTarget, block_offset
from rcominote.recovery_image import verify

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"


def test_decoder_matches_independently_read_mapped_header():
    directory = EVIDENCE / "system-raw-header-2026-10-12"
    assert (
        decode((directory / "raw.bin").read_bytes(), block_bytes=32)
        == (directory / "mapped.bin").read_bytes()
    )


def test_boot_decode_matches_stored_image_checksum():
    raw = (EVIDENCE / "boot-complete-2026-10-12/raw.bin").read_bytes()
    plain = decode(raw, block_bytes=512)
    # Captured boot header declares56B header,3616B body, checksum0x1264aa7d.
    assert (sum(struct.unpack("<904I", plain[56:3672])) + 0x1264AA7D) & 0xFFFFFFFF == 0xFFFFFFFF


def test_recovery_final_read_stays_inside_acpt_partition():
    # Actual header512+0xf538, NOR start4000; lastblock123 starts13600.
    assert block_offset(NorTarget.recovery, 123) == 0x13600
    with pytest.raises(ValueError, match="NOR block"):
        block_offset(NorTarget.recovery, 124)


def test_captured_header_alone_is_not_complete_recovery():
    raw = (EVIDENCE / "boot-recovery-prefixes-2026-10-12/recovery.bin").read_bytes()
    with pytest.raises(ValueError, match="exactly63288"):
        verify(raw)
    with pytest.raises(ValueError, match="body checksum failed"):
        verify(raw + bytes(63288 - len(raw)))


def test_complete_real_recovery_passes_its_stored_checksum():
    # Device-stored header/body checksums are the independent acceptance oracle.
    verify((EVIDENCE / "recovery-complete-2026-10-13/recovery-raw.bin").read_bytes())
