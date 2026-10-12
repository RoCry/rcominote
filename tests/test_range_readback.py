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
