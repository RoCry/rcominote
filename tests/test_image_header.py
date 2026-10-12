"""Oracle: actual stored header checksum and independent reset-vector words."""

import json
from pathlib import Path

import pytest

from rcominote.code_references import read_block
from rcominote.image_header import inspect_image_header

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/image-header-first-2026-10-12.json"


def captured() -> tuple[bytes, bytes]:
    capture = json.loads(EVIDENCE.read_text())
    return (
        b"".join(read_block(capture, address, 16) for address in range(0x10000000, 0x10000200, 16)),
        read_block(capture, 0x10000200, 8),
    )


def test_actual_header_and_vector_agree():
    report = inspect_image_header(*captured())
    assert (report["entry"], report["vector_reset"], report["vector_sp"]) == (
        "0x1002d819",
        "0x1002d819",
        "0x1002b40",
    )
    assert (report["image_bytes"], report["stored_image_checksum"], report["flags"]) == (
        927120,
        "0x4e7a894a",
        "0x0",
    )
    assert report["header_checksum_valid"] and not report["image_checksum_verified"]


def test_header_corruption_fails_stored_additive_checksum():
    header, vectors = captured()
    altered = bytearray(header)
    altered[0x40] ^= 1
    with pytest.raises(ValueError, match="header checksum mismatch"):
        inspect_image_header(bytes(altered), vectors)


def test_changed_vector_cannot_be_hidden_by_valid_header():
    header, vectors = captured()
    altered = bytearray(vectors)
    altered[4] ^= 2
    with pytest.raises(ValueError, match="reset vector disagree"):
        inspect_image_header(header, bytes(altered))
