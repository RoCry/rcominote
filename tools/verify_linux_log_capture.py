#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Verify this bounded Linux capture against HCI and an independent good help frame."""

import hashlib
import json
import re
import sys
from pathlib import Path


def verify(directory: Path) -> dict:
    report_path = directory / "report.json"
    hci_path = directory / "session.btmon.txt"
    baseline_path = Path(__file__).resolve().parents[1] / "docs/evidence/log-commands-2026-10-12.json"
    report = json.loads(report_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    hci = hci_path.read_text()
    # This evidence verifier deliberately accepts only the observed, unfragmented
    # handle2048/CID4 trace. It is not a general btmon or ACL reassembly parser.
    blocks = re.split(r"(?=^\S)", hci, flags=re.MULTILINE)
    notifications = []
    for block in blocks:
        if "ATT: Handle Value Notification (0x1b)" not in block:
            continue
        if not block.startswith("> ACL Data RX: Handle 2048 "):
            raise ValueError("Unexpected notification connection in capture")
        header = re.search(r"flags 0x02 dlen (\d+)\s+#(\d+)", block)
        att = re.search(r"Notification \(0x1b\) len (\d+)", block)
        value = re.search(r"Handle: 0x0018 Type:.*\n\s+Data: ([0-9a-f]+)\n", block)
        if not header or not att or not value:
            raise ValueError("Unexpected HCI notification layout")
        payload = bytes.fromhex(value[1])
        if int(header[1]) != len(payload) + 7 or int(att[1]) != len(payload) + 2:
            raise ValueError("HCI/ATT length mismatch")
        notifications.append({"packet": int(header[2]), "hex": payload.hex()})
    values = [bytes.fromhex(row["hex"]) for row in notifications]
    raw = [
        bytes.fromhex(row["hex"])[3:]
        for row in report["att_packets"]
        if row["direction"] == "rx" and row["hex"].startswith("1b1800")
    ]
    frames = [bytes.fromhex(row["hex"]) for row in baseline["frames"] if row["command"] == 0xF0]
    ack = bytes.fromhex("1d108107007f0400a0860100")
    if baseline["ok"] is not True or report["ok"] is not False:
        raise ValueError("Expected good independent baseline and failed Linux capture")
    if len(values) != 11 or len(raw) != 9 or raw != values[:9]:
        raise ValueError("Raw socket notifications differ from expected HCI prefix")
    if values[:2] != [ack, ack] or b"".join(values[2:5]) != frames[0]:
        raise ValueError("Initial ACKs/first frame differ from baseline")
    if values[5:7] != [frames[1][244:488], frames[1][488:512]]:
        raise ValueError("HCI no longer matches missing first 244-byte fragment")
    if values[7:] != [frames[2], ack, ack, bytes.fromhex("1df1810000")]:
        raise ValueError("Expected remaining help frame, ACKs and F1 in HCI")
    if report["writes"][-1] != "1d108105000002002100":
        raise ValueError("STOP was not attempted")
    return {
        "scope": "Fixed Linux real-device capture; offline HCI/socket/baseline comparison; no reconstruction",
        "started_at": report["started_at"],
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (report_path, hci_path, directory / "session.btsnoop", baseline_path)
        },
        "hci_notifications": notifications,
        "hci_notification_lengths": [len(value) for value in values],
        "socket_notification_count": len(raw),
        "socket_matches_hci_prefix": True,
        "first_help_frame_matches_baseline": True,
        "second_frame_received_slices": [[244, 488], [488, 512]],
        "second_frame_missing_slice": [0, 244],
        "hci_tail_after_socket_closed": ["ACK", "F1"],
        "result": "Missing fragment already absent at Linux HCI boundary; not introduced by Python framing",
        "limits": [
            "No over-the-air trace; does not distinguish device firmware/controller, radio or host controller/driver",
            "Socket closed after strict parser failure; last ACK/F1 visible only in HCI, not application-validated",
            "STOP write and HCI tail do not establish application recording state",
            "This experiment failed overall; discovery and bidirectional MTU exchange succeeded",
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: uv run tools/verify_linux_log_capture.py CAPTURE_DIRECTORY")
    print(json.dumps(verify(Path(sys.argv[1])), ensure_ascii=False, indent=2))
