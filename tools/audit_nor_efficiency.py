#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Offline NOR capture cost accounting; never connects to a device."""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def audit(root: Path) -> dict:
    paths = sorted(root.glob("block-*/attempt-*/session.json"))
    if not paths:
        raise ValueError(f"No saved NOR sessions in {root}")
    sessions = []
    for path in paths:
        capture = json.loads(path.read_text())
        notifications = capture["notifications"]
        seconds = notifications[-1]["seconds"] if notifications else 0
        error = capture.get("error", "")
        sessions.append(
            {
                "ok": capture["ok"],
                "seconds": seconds,
                "commands": len(capture["writes"]),
                "producers": sum(
                    bytes.fromhex(packet)[8:].startswith(b"dbg fread ") for packet in capture["writes"]
                ),
                "warm_windows": len(capture.get("batch_records", [])),
                "published_windows": len(list(path.parent.glob("window-*.json"))),
                "error": "incomplete RAM row" if "16-byte row" in error else error,
                "bytes": path.stat().st_size,
            }
        )
    successful = [s for s in sessions if s["ok"]]
    failed = [s for s in sessions if not s["ok"]]
    return {
        "scope": "Saved sessions only; notification times exclude some discovery, reconnect and host overhead. "
        "Cached block count is inventory, not a fresh integrity verification.",
        "sessions": len(sessions),
        "successful_sessions": len(successful),
        "failed_sessions": len(failed),
        "cached_blocks": len(list(root.glob("block-*/sector.bin"))),
        "recorded_seconds": round(sum(s["seconds"] for s in sessions), 3),
        "failed_recorded_seconds": round(sum(s["seconds"] for s in failed), 3),
        "median_success_seconds": statistics.median(s["seconds"] for s in successful) if successful else None,
        "median_success_commands": statistics.median(s["commands"] for s in successful)
        if successful
        else None,
        "failed_without_retained_warm_windows": sum(s["warm_windows"] == 0 for s in failed),
        "failed_after_multiple_producers": sum(s["producers"] > 1 for s in failed),
        "windows_published_from_failed_sessions": sum(s["published_windows"] for s in failed),
        "errors": dict(Counter(s["error"] for s in failed)),
        "session_json_bytes": sum(s["bytes"] for s in sessions),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory), ensure_ascii=False, indent=2))
