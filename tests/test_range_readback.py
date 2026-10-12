"""Oracle: captured multiline output versus prior independent single-row capture."""

import json
from pathlib import Path

import pytest

from rcominote.code_references import read_block
from rcominote.range_readback import read_range
from rcominote.readback_verify import verify_readback

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"


def capture() -> dict:
    return json.loads((EVIDENCE / "header-batch512-first-2026-10-12.json").read_text())


def test_multiline_batch_matches_prior_independent_single_rows():
    prior = json.loads((EVIDENCE / "image-header-first-2026-10-12.json").read_text())
    expected = b"".join(read_block(prior, a, 16) for a in range(0x10000000, 0x10000200, 16))
    assert read_range(capture(), 0x10000000, 512) == expected


@pytest.mark.parametrize("failure", ["lost", "duplicate", "truncated"])
def test_completed_transport_cannot_hide_bad_row(failure):
    result = capture()
    if failure == "duplicate":
        result["frames"].append({"text": "\n100001f0: 00 00\n"})
    else:
        for frame in result["frames"]:
            lines = frame.get("text", "").splitlines(keepends=True)
            frame["text"] = "".join(
                ("" if failure == "lost" else "100001f0: 00 00\n") if line.startswith("100001f0:") else line
                for line in lines
            )
    verify_readback(result)
    assert result["transport_ok"] and not result["readback_complete"] and not result["ok"]


def test_complete_changed_header_is_rejected():
    result = capture()
    for frame in result["frames"]:
        frame["text"] = frame.get("text", "").replace("41 43 54 48", "40 43 54 48")
    verify_readback(result)
    assert not result["ok"] and "differs from independently validated" in result["error"]


def test_fixed_image_session_boundary_from_captured_header():
    from rcominote.range_readback import image_ranges

    # ACTH evidence declares body 0xe2590 at 0x10000200; final 0x190 bytes.
    assert image_ranges([1810]) == (
        (0x100E2600, 64),
        (0x100E2640, 64),
        (0x100E2680, 64),
        (0x100E26C0, 64),
        (0x100E2700, 64),
        (0x100E2740, 64),
        (0x100E2780, 16),
    )


@pytest.mark.parametrize("indices", [[1811], [-1], [0, 0], [True], list(range(65))])
def test_reject_invalid_image_session(indices):
    from rcominote.range_readback import image_ranges

    with pytest.raises(ValueError):
        image_ranges(indices)


def test_actual_long_session_truncation_rejects_block_despite_end_marker():
    result = json.loads((EVIDENCE / "image-session-truncated-2026-10-12.json").read_text())
    # Isolate the actual data failure from the overall failed session status.
    with pytest.raises(ValueError, match="0x10001c60"):
        read_range(result | {"ok": True}, 0x10001C00, 512)


def test_independent_contiguous_body_readbacks_match():
    from rcominote.range_readback import BODY_PROBE_RANGES

    first = json.loads((EVIDENCE / "body-probe-first-2026-10-12.json").read_text())
    second = json.loads((EVIDENCE / "body-probe-second-2026-10-12.json").read_text())
    assert all(read_range(first, a, n) == read_range(second, a, n) for a, n in BODY_PROBE_RANGES)


def test_two_256_reads_match_prior_512_read_for_same_body_block():
    prior = json.loads((EVIDENCE / "image-short-session-truncated-2026-10-12.json").read_text())
    current = json.loads((EVIDENCE / "image-256-first-2026-10-12.json").read_text())
    # Prior session failed later at 0x10009a60; this earlier block has all rows.
    assert read_range(current, 0x10009200, 256) + read_range(current, 0x10009300, 256) == read_range(
        prior | {"ok": True}, 0x10009200, 512
    )


def test_scoped_guard_preserves_unaligned_code_references():
    result = json.loads((EVIDENCE / "image-unaligned-guard-2026-10-12.json").read_text())
    # Transport and rows complete; old verifier incorrectly imposed 16B alignment
    # on the existing 0x1000c0ac/0x100c26ba/0x100ad486 guard reads.
    result["ok"] = True
    verify_readback(result)
    assert result["readback_complete"]


def test_actual_guard_and_body_overlap_are_independently_validated():
    from rcominote.range_readback import scoped_capture

    result = json.loads((EVIDENCE / "image-scoped-overlap-2026-10-12.json").read_text())
    guard = read_block(scoped_capture(result, "dbg mdb 1000bf20 10"), 0x1000BF20, 16)
    assert read_range(result, 0x1000BF00, 256)[32:48] == guard


def test_actual_64_byte_session_and_missing_declaration():
    result = json.loads((EVIDENCE / "image-64-first-2026-10-12.json").read_text())
    verify_readback(result)
    assert result["readback_complete"]
    result["fixed_text_commands"].remove("dbg mdb 1000e200 40")
    verify_readback(result)
    assert not result["ok"] and "missing a declared" in result["error"]


def test_small_header_matches_independent_original_and_rejects_missing_segment():
    from rcominote.range_readback import read_header

    result = json.loads((EVIDENCE / "image-small-header-first-2026-10-12.json").read_text())
    assert read_header(result) == read_range(capture(), 0x10000000, 512)
    result["fixed_text_commands"].remove("dbg mdb 100001c0 40")
    verify_readback(result)
    assert not result["ok"] and "Missing declared range" in result["error"]


def test_actual_header_burst_loss_rejects_ack_and_end_without_complete_rows():
    from rcominote.range_readback import read_header

    result = json.loads((EVIDENCE / "image-header-burst-failure-2026-10-12.json").read_text())
    with pytest.raises(ValueError, match="Incomplete frame span"):
        read_header(result | {"ok": True})
