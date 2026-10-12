"""Oracle: unmodified pinned SDK pack() output, including its 512-byte padding."""

import json
import struct
import zlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rcominote.cli import app
from rcominote.ota_package import inspect_package

FIXTURE = Path(__file__).parent / "fixtures" / "ota-sdk-golden.bin"


def repaired_header(data: bytearray) -> bytearray:
    # Independent mutation repair: header CRC covers fixed bytes8:1024.
    struct.pack_into("<I", data, 4, zlib.crc32(data[8:1024]))
    return data


def test_vendor_pack_golden_layout_and_crc():
    result = inspect_package(FIXTURE.read_bytes())
    assert {
        key: result[key]
        for key in ("sha256", "total_size", "header_version", "header_crc32", "data_crc32", "entries")
    } == {
        "sha256": "6c8ccca1ba8e3a37f86badb5dd7565097c671258a637f824d86aff0ff9b936d4",
        "total_size": 2048,
        "header_version": 256,
        "header_crc32": "6d549b8c",
        "data_crc32": "85516189",
        "entries": [
            {"name": "ota.xml", "offset": 1024, "size": 222, "crc32": "fe060b68"},
            {"name": "payload.bin", "offset": 1536, "size": 3, "crc32": "352441c2"},
        ],
    }


def test_xml_metadata_uses_xml_not_conflicting_c_header_struct():
    assert inspect_package(FIXTURE.read_bytes())["metadata"]["versions"] == [
        {
            "tag": "firmware_version",
            "fields": [
                {"name": "version_name", "text": "fixture-only"},
                {"name": "version_code", "text": "0x01020304"},
                {"name": "version_res", "text": "0x05060708"},
                {"name": "board_name", "text": "test-not-comi"},
            ],
        }
    ]


@pytest.mark.parametrize(
    ("data", "message"),
    [(b"", "magic"), (b"LZMA" + bytes(32), "wrapper"), (b"AOTA" + bytes(5), "Truncated")],
)
def test_not_an_uncompressed_complete_header(data, message):
    with pytest.raises(ValueError, match=message):
        inspect_package(data)


@pytest.mark.parametrize("length", [1024, 1538, 2047, 2049])
def test_truncated_or_appended_container(length):
    data = (FIXTURE.read_bytes() + b"x")[:length]
    with pytest.raises(ValueError, match="total size"):
        inspect_package(data)


@pytest.mark.parametrize(
    ("position", "format", "value", "message"),
    [
        (10, "H", 512, "Unsupported.*layout"),
        (16, "H", 0, "Unsupported.*layout"),
        (18, "H", 512, "Unsupported.*layout"),
        (12, "H", 17, "maximum is 16"),
        (20, "I", 1023, "total size"),
        (560, "I", 1000, "outside body"),
        (560, "I", 2047, "outside body"),
        (560, "I", 0xFFFFFFFE, "overflow"),
        (560, "I", 1100, "overlapping"),
        (572, "I", 0, "payload.bin: CRC32 mismatch"),
    ],
)
def test_valid_header_crc_does_not_bypass_structural_or_file_checks(position, format, value, message):
    data = bytearray(FIXTURE.read_bytes())
    struct.pack_into("<" + format, data, position, value)
    with pytest.raises(ValueError, match=message):
        inspect_package(repaired_header(data))


@pytest.mark.parametrize(
    ("name", "message"),
    [
        (b"ota.xml\0\0\0\0\0", "Duplicate"),
        (b"../bad\0\0\0\0\0\0", "unsafe"),
        (b"x\0y" + bytes(9), "terminator"),
    ],
)
def test_ambiguous_directory_names_are_rejected(name, message):
    data = bytearray(FIXTURE.read_bytes())
    data[544:556] = name
    with pytest.raises(ValueError, match=message):
        inspect_package(repaired_header(data))


@pytest.mark.parametrize(("position", "message"), [(80, "header CRC32"), (2000, "data CRC32")])
def test_corrupted_header_or_body_padding(position, message):
    data = bytearray(FIXTURE.read_bytes())
    data[position] ^= 1
    with pytest.raises(ValueError, match=message):
        inspect_package(data)


def test_file_crc_excludes_padding_and_data_crc_includes_it():
    data = bytearray(FIXTURE.read_bytes())
    data[2000] = 0x55
    struct.pack_into("<I", data, 24, zlib.crc32(data[1024:]))
    assert inspect_package(repaired_header(data))["entries"][1]["crc32"] == "352441c2"


def test_malformed_xml_fails_after_valid_integrity_checks():
    data = bytearray(FIXTURE.read_bytes())
    data[1024] = ord("!")
    struct.pack_into("<I", data, 540, zlib.crc32(data[1024:1246]))
    struct.pack_into("<I", data, 24, zlib.crc32(data[1024:]))
    with pytest.raises(ValueError, match="malformed XML"):
        inspect_package(repaired_header(data))


def test_cli_is_offline_and_reports_limited_scope():
    result = CliRunner().invoke(app, ["inspect-ota", str(FIXTURE)])
    assert result.exit_code == 0, result.output
    assert "device acceptance and recoverability unverified" in json.loads(result.stdout)["scope"]
