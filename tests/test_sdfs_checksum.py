"""Oracles: hand-calculated words and actual repeated CoMi directory bytes."""

import pytest

from rcominote.sdfs_checksum import checksum32


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (bytes.fromhex("0102030405060708"), 0x0C0A0806),
        (bytes.fromhex("ffffffff02000000"), 1),
        (b"", 0),
        (bytes.fromhex("01"), 0),
        (bytes.fromhex("0102"), 0),
        (bytes.fromhex("010203"), 0),
        (bytes.fromhex("01020304ff"), 0x04030201),
        (bytes.fromhex("01020304ffff"), 0x04030201),
        (bytes.fromhex("01020304ffffff"), 0x04030201),
    ],
)
def test_little_endian_addition_overflow_and_ignored_partial_word(raw, expected):
    assert checksum32(raw) == expected


def test_actual_directory_matches_independently_stored_checksum_word():
    # NOR 0x240020..0x240100, double-read evidence 2026-10-12. Expected value
    # is the separately acquired header reserved[1], not computed by a fixture.
    directory = bytes.fromhex(
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
    assert checksum32(directory) == 0xEF0B5E3D
