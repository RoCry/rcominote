"""Oracles: actual double-captured DSP directory and fixed SDK sd_dir layout."""

import struct
from pathlib import Path

import pytest

from rcominote.sdfs_directory import inspect, parse_directory

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/nor-partition-prefixes-2026-10-12"
CAPTURES = sorted((EVIDENCE / "dsp").glob("nor-dsp-prefix*-*.json"))
# Exact sixteen 16-byte NOR rows, independently captured twice on 2026-10-12.
DIRECTORY = bytes.fromhex(
    "736466732e62696e0000000007000000"
    "40ee0700000000003d5e0befa33f2aff"
    "7473742e62696e000000000000010000"
    "64100000000000000000000073ef800e"
    "736466732e7478740000000080110000"
    "0a000000000000000000000066686a6c"
    "6c6f676f2e73747900000000c0110000"
    "c400000000000000000000005af391a5"
    "6c6f676f2e72657300000000c0120000"
    "a00100000000000000000000ff4a2128"
    "6663632e62696e000000000080140000"
    "70bf00000000000000000000a21c6572"
    "61657265636f72642e64737000d40000"
    "44ae01000000000000000000bb85d696"
    "61646d757369632e6473700080820200"
    "b06b05000000000000000000dbd64fad"
)


def test_actual_directory_names_and_extents():
    report = parse_directory(DIRECTORY)
    assert [(file["name"], file["absolute_offset"], file["size"]) for file in report["files"]] == [
        ("tst.bin", 0x240100, 0x1064),
        ("sdfs.txt", 0x241180, 10),
        ("logo.sty", 0x2411C0, 0xC4),
        ("logo.res", 0x2412C0, 0x1A0),
        ("fcc.bin", 0x241480, 0xBF70),
        ("aerecord.dsp", 0x24D400, 0x1AE44),
        ("admusic.dsp", 0x268280, 0x56BB0),
    ]


def test_actual_captures_reproduce_complete_directory():
    report = inspect(CAPTURES)
    assert report["directory_sha256"] == "778e2e882fbfc0cd1f4d8ce67005aae3f4c8c3a2b3303f335fbbdaf2a906a755"
    assert report["directory_bytes"] == 256 and report["file_count"] == 7


def test_actual_checksum_words_are_retained_without_validation_claim():
    report = parse_directory(DIRECTORY)
    assert (
        report["checksum_verified"],
        report["header_checksum_word"],
        report["files"][5]["checksum_word"],
    ) == (
        False,
        "0xff2a3fa3",
        "0x96d685bb",
    )


def test_single_acquisition_lacks_directory_double_coverage():
    with pytest.raises(ValueError, match="lack independent double coverage"):
        inspect([path for path in CAPTURES if path.name.endswith("-first.json")])


def test_wrong_partition_target_is_rejected():
    system = sorted((EVIDENCE / "system").glob("nor-system-prefix*-*.json"))
    with pytest.raises(ValueError, match="requires fixed DSP target"):
        inspect(system)


@pytest.mark.parametrize("length", [0, 31, 255])
def test_truncated_actual_directory_rejected(length):
    with pytest.raises(ValueError, match="Truncated SDFS"):
        parse_directory(DIRECTORY[:length])


@pytest.mark.parametrize(
    ("position", "value", "message"),
    [
        (12, 16, "exceeds the fixed 512-byte"),
        (16, 0xB0001, "total size lies outside"),
        (0x2C, 0x80, "file extent outside"),
        (0x2C, 0xAFFFF, "file extent outside"),
        (0x4C, 0x1100, "Overlapping SDFS file extents"),
    ],
)
def test_captured_directory_mutations_reject_unsafe_extents(position, value, message):
    raw = bytearray(DIRECTORY)
    struct.pack_into("<I", raw, position, value)
    with pytest.raises(ValueError, match=message):
        parse_directory(raw)


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        (b"TST.BIN\0\0\0\0\0", "Duplicate case-insensitive"),
        (b"\xffdfs.txt\0\0\0\0", "printable ASCII"),
        (b"sdfs\0txt\0\0\0\0", "nonzero bytes after"),
    ],
)
def test_captured_directory_mutations_reject_bad_names(replacement, message):
    raw = bytearray(DIRECTORY)
    raw[0x40:0x4C] = replacement
    with pytest.raises(ValueError, match=message):
        parse_directory(raw)
