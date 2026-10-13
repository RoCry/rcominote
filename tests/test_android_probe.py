"""Raw Android envelopes wrapping independent, retained CoMi wire captures."""

import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = runpy.run_path(str(ROOT / "tools/verify_android_probe.py"))["verify"]
ACK = "1d108107007f0400a0860100"
SERIAL = "d22d01010a4332363143463034333060bb"
INFO = "d22d0105340000e8f20000e8f00164000100040101ff78696e6b5f746573740000000000000000000000000009ff0300010000000000000000b321"
BOYI_WRITE = "0000e5e1-0000-1000-8000-00805f9b34fb"
BOYI_NOTIFY = "0000e5e2-0000-1000-8000-00805f9b34fb"
LOG_WRITE = "e49a3002-f69a-11e8-8eb2-f2801f1b9fd1"
LOG_NOTIFY = "e49a3003-f69a-11e8-8eb2-f2801f1b9fd1"


def capture(tmp_path: Path, *, missing: bool = False) -> Path:
    baseline = json.loads((ROOT / "docs/evidence/log-commands-2026-10-12.json").read_text())
    frames = [row["hex"] for row in baseline["frames"] if row["command"] == 240][:3]
    if missing:
        # Historical defect, independently measured on Linux: missing first244 B
        # of second512 B frame. Keep following ACK/F1 to expose false cleanup success.
        frames[1] = frames[1][488:]
    rows = [{"event": "session", "mode": "help", "serial": "C261CF0430"}]

    def row(event: str, characteristic: str, value: str):
        rows.append({"event": event, "characteristic": characteristic, "hex": value})

    row("write", BOYI_WRITE, "d22d010100e12e")
    row("notify", BOYI_NOTIFY, SERIAL)
    row("write", BOYI_WRITE, "d22d010500e3ee")
    row("notify", BOYI_NOTIFY, INFO)
    for command, packets in (
        ("1d108105000002000100", [ACK]),
        ("1d108105000002002000", [ACK]),
        ("1d1081070001040068656c70", [*frames, ACK]),
        ("1d108105000002002100", [ACK, "1df1810000"]),
    ):
        row("write", LOG_WRITE, command)
        for packet in packets:
            row("notify", LOG_NOTIFY, packet)
    row("write", BOYI_WRITE, "d22d010500e3ee")
    row("notify", BOYI_NOTIFY, INFO)
    # An app's success label must not override defective raw bytes.
    rows.append({"event": "result", "ok": True})
    for index, value in enumerate(rows):
        value["elapsed_ns"] = index
    path = tmp_path / "android.jsonl"
    path.write_text("".join(json.dumps(value) + "\n" for value in rows))
    return path


def test_independent_good_help_and_info(tmp_path):
    result = VERIFY(capture(tmp_path))
    assert result["ok"] is True
    assert result["f0_lengths"] == [512, 512, 199]
    assert result["strict_acks"] == 4
    assert result["before_after_full_info_match"] is True


def test_missing_fragment_cannot_be_repaired_by_cleanup_ack(tmp_path):
    result = VERIFY(capture(tmp_path, missing=True))
    assert result["ok"] is False
    assert result["app_result"]["ok"] is True
    assert result["strict_parse_error"]
    assert result["help_matches_independent_baseline"] is False
    assert result["strict_end"] is False


def test_interrupted_jsonl_has_no_verdict(tmp_path):
    path = capture(tmp_path)
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ValueError, match="incomplete"):
        VERIFY(path)


def test_post_state_must_be_observed_not_app_claimed(tmp_path):
    path = capture(tmp_path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    del rows[-2]  # Drop final raw GET_DEVICE_INFO response, retain result.ok=true.
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = VERIFY(path)
    assert result["ok"] is False
    assert result["before_after_full_info_match"] is False
