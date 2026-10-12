"""Real captured code and a reproduced false-independent-comparison failure."""

from pathlib import Path

import pytest

from rcominote.code_sample import inspect_samples
from rcominote.log_capture import observed_logsrv_code

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"
FIRST = EVIDENCE / "log-code-sample-2026-10-12.json"
SECOND = EVIDENCE / "log-code-sample-repeat-2026-10-12.json"


def test_distinct_real_captures_match_observed_thumb_entry():
    report = inspect_samples(FIRST, SECOND)
    assert report["hex"] == "2de9f0476149624e86b05020a1f0abfa"
    assert (report["decoded_bytes"], report["instructions"][0]["mnemonic"]) == (16, "push.w")


def test_same_capture_cannot_count_as_independent_read(tmp_path):
    copied = tmp_path / "copy.json"
    copied.write_bytes(FIRST.read_bytes())
    for second in (FIRST, copied):
        with pytest.raises(ValueError, match="distinct capture"):
            inspect_samples(FIRST, second)


def test_literal_read_guard_uses_real_capture_and_rejects_changed_instruction():
    import json

    frames = json.loads(FIRST.read_text())["frames"]
    assert observed_logsrv_code(frames)
    changed = [{"text": row.get("text", "").replace("61 49 62 4e", "60 49 62 4e")} for row in frames]
    with pytest.raises(ValueError, match="code changed"):
        observed_logsrv_code(changed)
    assert not observed_logsrv_code([{"text": "1000bf20: 2d e9"}])
