"""M1 dump verifier against retained raw captures; synthetic dumps built from the evidence files."""

import runpy
from itertools import pairwise
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tool():
    return runpy.run_path(str(ROOT / "tools/verify_full_dump.py"))


@pytest.fixture(scope="module")
def synthetic_dump(tool) -> bytes:
    buf = bytearray(b"\xff" * tool["NOR_SIZE"])
    for s in tool["KNOWN_SLICES"]:
        data = s.path.read_bytes()
        buf[s.offset : s.offset + len(data)] = data
    # Keep the chip non-uniform even if a future slice list were empty.
    buf[0x300000:0x300010] = bytes(range(16))
    return bytes(buf)


def test_known_slices_do_not_overlap_and_lie_inside_partitions(tool):
    spans = sorted((s.offset, s.offset + s.path.stat().st_size, s.name) for s in tool["KNOWN_SLICES"])
    for (_, end, name), (start, _, nxt) in pairwise(spans):
        assert end <= start, f"{name} overlaps {nxt}"
    assert spans[-1][1] <= tool["NOR_SIZE"]


def test_recovery_tail_is_contiguous_with_recovery_image(tool):
    by_name = {s.name: s for s in tool["KNOWN_SLICES"]}
    rec = by_name["recovery"]
    assert rec.offset + rec.path.stat().st_size == by_name["recovery-tail"].offset == 0x13738


def test_assembled_evidence_passes_and_two_identical_reads_agree(tool, synthetic_dump):
    report = tool["verify"](synthetic_dump, synthetic_dump)
    assert report["ok"] is True
    assert report["all_known_match"] is True
    assert report["second_dump_identical"] is True
    assert {p["name"] for p in report["partitions"]} >= {"fw0_boot", "fw0_sys", "runtimel"}


def test_single_flipped_byte_in_known_slice_fails_with_address(tool, synthetic_dump):
    bad = bytearray(synthetic_dump)
    bad[0x24D400 + 7] ^= 0x01  # inside record-dsp
    report = tool["verify"](bytes(bad), None)
    assert report["ok"] is False
    failing = [s for s in report["known_slices"] if not s["match"]]
    assert [s["name"] for s in failing] == ["record-dsp"]
    assert failing[0]["first_diff"] == "0x24d407"


def test_second_read_mismatch_reports_page(tool, synthetic_dump):
    other = bytearray(synthetic_dump)
    other[0x3F0123] ^= 0xFF
    report = tool["verify"](synthetic_dump, bytes(other))
    assert report["ok"] is False
    assert report["differing_4k_pages"] == ["0x3f0000"]


@pytest.mark.parametrize("fill", [b"\xff", b"\x00"])
def test_uniform_dump_is_rejected(tool, fill):
    with pytest.raises(ValueError, match="uniform"):
        tool["verify"](fill * tool["NOR_SIZE"], None)


def test_wrong_size_is_rejected(tool):
    with pytest.raises(ValueError, match="expected"):
        tool["verify"](b"\x01" * 1024, None)
