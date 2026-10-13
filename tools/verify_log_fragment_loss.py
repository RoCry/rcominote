#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Compare retained good/bad CoMi help captures; never reconstruct missing data."""

import hashlib
import json
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"


def verify() -> dict:
    names = ("log-commands-2026-10-12.json", "note-call-runtime-attempt-2026-10-13.json")
    good, failure = [json.loads((EVIDENCE / name).read_text()) for name in names]
    bad = failure["diagnostic_only_control"]
    if good["ok"] is not True or bad["transport_ok"] is not False:
        raise ValueError("Expected independently successful baseline and failed control")
    frames = [bytes.fromhex(row["hex"]) for row in good["frames"] if row["command"] == 0xF0]
    old_wire = b"".join(bytes.fromhex(row["hex"]) for row in good["notifications"])
    packets = [bytes.fromhex(row["hex"]) for row in bad["notifications"]]
    if len(packets) != 7 or old_wire[24:1048] != frames[0] + frames[1]:
        raise ValueError("Capture layout changed; baseline frames not backed by raw notifications")
    # Header/TLV oracle: 0x1fb-byte payload contains 0x1f8 bytes of text.
    if any(len(frame) != 512 or frame[:8] != bytes.fromhex("1df081fb0100f801") for frame in frames[:2]):
        raise ValueError("Expected two complete 512-byte baseline frames")
    if b"".join(packets[2:5]) != frames[0]:
        raise ValueError("Failed capture's first frame differs from independent baseline")
    if packets[5] != frames[1][244:488] or packets[6] != frames[1][488:512]:
        raise ValueError("Failure no longer matches missing first 244-byte fragment")
    return {
        "scope": "Offline exact-byte comparison; no device I/O, repaired capture or loss-layer attribution",
        "source_sha256": {name: hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest() for name in names},
        "baseline_first_frame_sha256": hashlib.sha256(frames[0]).hexdigest(),
        "baseline_second_frame_sha256": hashlib.sha256(frames[1]).hexdigest(),
        "failed_first_frame_matches": True,
        "second_frame_received_slices": [[244, 488], [488, 512]],
        "missing_slice_relative_to_baseline": [0, 244],
        "missing_contains": "8-byte frame/TLV header plus 236 text bytes",
        "limits": [
            "Missing relative to the independent baseline, not an over-the-air packet trace",
            "Does not distinguish device enqueue/controller, radio/host stack, or callback delivery",
            "Pre-framing text loss alone cannot explain this header-and-payload gap",
            "No evidence that this failure and the old recording's 244-byte gap have the same cause",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
