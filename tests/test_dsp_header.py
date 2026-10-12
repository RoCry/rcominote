"""Oracle: actual double-read header; explicit format boundary corruptions."""

import json
from pathlib import Path

import pytest

from rcominote.dsp_header import inspect_header

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/record-dsp-header-2026-10-12"


def actual_header():
    return bytes.fromhex(json.loads((EVIDENCE / "header.json").read_text())["header_hex"])


def test_actual_full_header_pointer_inventory():
    report = inspect_header(actual_header(), file_size=110148)
    assert (report["code_offset"], report["data_offset"]) == (540, 16112)
    assert report["entry_point"] == "0x8e"
    assert report["nonzero_banks"] == [
        {"bank": 18, "code_offset": 52812, "data_offset": 0},
        {"bank": 19, "code_offset": 52968, "data_offset": 0},
        {"bank": 34, "code_offset": 80636, "data_offset": 105520},
    ]


@pytest.mark.parametrize("offset", [539, 110141, 0xFFFFFFFF])
def test_pointer_must_fit_complete_eight_byte_section_header(offset):
    raw = bytearray(actual_header())
    raw[20:24] = offset.to_bytes(4, "little")
    with pytest.raises(ValueError, match="section header outside file bounds"):
        inspect_header(bytes(raw), file_size=110148)


def test_earlier_64_byte_capture_does_not_prove_bank_table():
    with pytest.raises(ValueError, match="exactly 540 bytes"):
        inspect_header(actual_header()[:64], file_size=110148)
