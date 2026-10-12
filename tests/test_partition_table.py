"""Oracle: actual device ACPT bytes and its stored CRC, independent of this decoder."""

import json
from pathlib import Path

import pytest

from rcominote.code_references import read_block
from rcominote.partition_table import inspect_acpt

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/partition-first-2026-10-12.json"


def captured_table() -> bytes:
    capture = json.loads(EVIDENCE.read_text())
    return b"".join(
        read_block(capture, address, min(16, 0x01000328 - address))
        for address in range(0x01000040, 0x01000328, 16)
    )


def test_actual_acpt_crc_and_partition_fields():
    report = inspect_acpt(captured_table())
    assert report["crc32"] == "0x703f5674"
    assert report["partition_count"] == 18
    # Hand-decoded actual system entry: name8/type/file/storage+mirror/flag/3 u32.
    system = report["entries"][5]
    assert (system["name"], system["offset"], system["size_bytes"], system["flags"]) == (
        "fw0_sys",
        "0x24000",
        0x1A5000,
        2,
    )
    assert report["entries"][2]["mirror_id"] == 1
    assert report["entries"][17]["end_exclusive"] == "0x400000"


def test_corrupt_payload_rejected_by_stored_crc():
    data = bytearray(captured_table())
    data[32] ^= 1
    with pytest.raises(ValueError, match="CRC mismatch"):
        inspect_acpt(bytes(data))


def test_truncated_table_rejected_before_decode():
    with pytest.raises(ValueError, match="exactly 744"):
        inspect_acpt(captured_table()[:-4])
