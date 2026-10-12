"""Oracles: captured NOR tails; actual boundary truncation and one-byte corruption."""

import json
import re
from pathlib import Path

import pytest

from rcominote import printk_tail
from rcominote.nor_windows import _rows, analyze, main

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"
SECOND = EVIDENCE / "printk-nor-tail-second-2026-10-12.json"
THIRD = EVIDENCE / "printk-nor-tail-third-2026-10-12.json"
EXPECTED = [
    {"offset": "0x1e0", "variants": [{"hex": "b713b78078f2cd58e37b82e2c3862ea2", "sources": 2}]},
    {"offset": "0x1f0", "variants": [{"hex": "9f8b4b71c1a8d78e2e69f7cc8bb548e1", "sources": 2}]},
]


def write_capture(tmp_path, capture, name="capture.json"):
    path = tmp_path / name
    path.write_text(json.dumps(capture))
    return path


def corrupt_actual_ram_byte(capture):
    """Change the b7 printed for NOR 1e0 in the real mdb row, not cached tail."""
    tail = printk_tail.inspect(capture)
    index = bytes.fromhex(tail["hex"]).index(b"     1e0: b7") + len(b"     1e0: ")
    first, _ = tail["ranges"][0]
    address = first + index
    row, column = divmod(address - first, 16)
    prefix = f"{first + row * 16:08x}: "
    matches = 0
    for frame in capture["frames"]:
        text = frame.get("text", "")
        if match := re.search(rf"(?m)^{prefix}((?:[0-9a-f]{{2}} ){{16}})", text):
            start = match.start(1) + column * 3
            assert text[start : start + 2] == "62"  # ASCII b -> c; b7 becomes c7.
            frame["text"] = text[:start] + "63" + text[start + 2 :]
            matches += 1
    assert matches == 1


def test_actual_partial_captures_confirm_only_two_rows():
    report = analyze([SECOND, THIRD])
    assert report["rows"] == EXPECTED
    assert not report["complete"] and report["confirmed_rows"] == 2 and len(report["missing_rows"]) == 30
    assert "sector_hex" not in report


def test_cached_tail_fabrication_is_ignored(tmp_path):
    capture = json.loads(SECOND.read_text())
    capture["console_tail"]["text"] = "\r\n       0: " + "ff " * 16 + "\r\n"
    report = analyze([write_capture(tmp_path, capture), THIRD])
    assert report["rows"] == EXPECTED


def test_duplicate_files_and_rewrapped_source_count_once(tmp_path):
    capture = json.loads(SECOND.read_text())
    clone = tmp_path / "clone.json"
    clone.write_bytes(SECOND.read_bytes())
    rewrapped = write_capture(tmp_path, capture)
    report = analyze([SECOND, clone, rewrapped])
    assert report["distinct_sources"] == 1 and report["confirmed_rows"] == 0
    assert report["unconfirmed_rows"] == ["0x1e0", "0x1f0"]


def test_original_capture_digest_deduplicates_changed_metadata(tmp_path):
    capture = json.loads(SECOND.read_text())
    capture["captured_at"] = "rewrapped metadata"
    report = analyze([SECOND, write_capture(tmp_path, capture)])
    assert report["distinct_sources"] == 1 and report["confirmed_rows"] == 0


def test_corrupted_duplicate_source_still_reports_conflict(tmp_path):
    capture = json.loads(SECOND.read_text())
    corrupt_actual_ram_byte(capture)
    report = analyze([SECOND, write_capture(tmp_path, capture)])
    assert report["conflicts"] == ["0x1e0"] and report["distinct_sources"] == 1
    assert "sector_hex" not in report


def test_partial_and_truncated_boundary_rows_are_excluded():
    # Actual second-capture first fragment: truncated 1d0 address looks like 0.
    text = printk_tail.inspect(json.loads(SECOND.read_text()))["text"]
    assert [offset for offset, _ in _rows(text)] == [0x1E0, 0x1F0]
    # Even a syntactically complete first fragment lacks an internal CRLF prefix.
    assert _rows("       0: " + "ff " * 16 + "\r\n") == []
    assert _rows("\r\n      10: " + "ff " * 16) == []


def test_space_padded_single_digit_bytes_preserve_values():
    # Actual producer format uses %2x, not %02x. Hand-written independent oracle.
    text = "\r\n      20:  0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f \r\n"
    assert _rows(text) == [(0x20, b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f")]


def test_missing_rows_refuse_binary_publication(tmp_path):
    out = tmp_path / "sector.bin"
    with pytest.raises(ValueError, match="NOR sector incomplete: missing="):
        main([SECOND, THIRD], out=out)
    assert not out.exists()


def test_changed_producer_rejected_before_interpretation(tmp_path):
    capture = json.loads(SECOND.read_text())
    capture["fixed_text_commands"] = [
        "dbg fread spi_flash 200" if command == printk_tail.PRODUCER else command
        for command in capture["fixed_text_commands"]
    ]
    with pytest.raises(ValueError, match="exactly one fixed offset-zero NOR producer"):
        analyze([write_capture(tmp_path, capture)])
