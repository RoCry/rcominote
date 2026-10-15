"""Independent retained SDK packer oracle; guards against false CRC/profile success."""

import base64
import hashlib
import json
import runpy
import struct
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def parser():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "tools"))
        return runpy.run_path(str(ROOT / "tools/acquire_actions_tester.py"))["parse_atf"]


@pytest.fixture
def oracle():
    fixture = json.loads((ROOT / "tests/fixtures/atf-reference.json").read_text())
    raw = zlib.decompress(base64.b64decode(fixture["zlib_base64"]))
    assert hashlib.sha256(raw).hexdigest() == fixture["sha256"]
    return raw


def header_crc(raw):
    struct.pack_into("<I", raw, 8, zlib.crc32(raw[12:512]))


def test_independent_sdk_producer_oracle(parser, oracle):
    report, files = parser(oracle, modern=True)
    assert all(report["checks"].values())
    assert files == {"payload.bin": b"abc", "aligned.bin": bytes(range(256)) * 2}
    assert [r["crc_state"] for r in report["members"]] == ["verified", "verified"]


def test_crc_failure_cannot_fall_back_to_legacy(parser, oracle):
    raw = bytearray(oracle)
    raw[512] ^= 1
    with pytest.raises(ValueError, match="header/body validation"):
        parser(raw, modern=True)


def test_valid_whole_package_crc_does_not_mask_wrong_member_crc(parser, oracle):
    raw = bytearray(oracle)
    raw[32 + 28] ^= 1
    header_crc(raw)
    with pytest.raises(ValueError, match="member CRC failed"):
        parser(raw, modern=True)


def test_valid_crcs_do_not_mask_member_overlapping_header(parser, oracle):
    raw = bytearray(oracle)
    struct.pack_into("<I", raw, 32 + 16, 0)
    header_crc(raw)
    with pytest.raises(ValueError, match="overlaps header"):
        parser(raw, modern=True)


def test_q_is_not_zero(parser, oracle):
    with pytest.raises(ValueError, match="digit zero"):
        parser(b"ACTTESTQ" + oracle[8:], modern=True)


def test_legacy_zero_crc_is_explicitly_unverified(parser, oracle):
    raw = bytearray(oracle)
    struct.pack_into("<I", raw, 8, 0x01000000)
    raw[16:32] = bytes(16)
    raw[32:44] = b"config.txt\0\0"
    struct.pack_into("<I", raw, 32 + 28, 0)
    report, files = parser(raw, modern=False)
    assert files["config.txt"] == b"abc"
    assert report["members"][0]["crc_state"] == "unverified-zero-field"
    with pytest.raises(ValueError, match="header/body validation"):
        parser(raw, modern=True)
