"""Real captured cache mutations identified during independent review."""

import json
import tarfile
from pathlib import Path

import pytest

from rcominote.experiments.recovery_tail import checked_read

CAPTURES = Path("docs/evidence/recovery-complete-2026-10-13/captures.tar.gz")


@pytest.fixture
def baseline_report(tmp_path):
    with tarfile.open(CAPTURES) as archive:
        members = [item for item in archive.getmembers() if item.name.startswith("block-093-a/")]
        archive.extractall(tmp_path, members=members, filter="data")
    path = tmp_path / "block-093-a"
    return path, path / "baseline/report.json"


def test_renamed_metadata_cannot_claim_an_independent_file(baseline_report):
    path, report_path = baseline_report
    report = json.loads(report_path.read_text())
    report["name"] = "rc0000000000"
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="filename/command identity differs"):
        checked_read(path, 93, image=b"")


def test_declared_guard_text_cannot_hide_changed_wire_bytes(baseline_report):
    path, report_path = baseline_report
    report = json.loads(report_path.read_text())
    frame = next(item for item in report["frames"] if "10000000:" in item.get("text", ""))
    frame["hex"] = bytes.fromhex(frame["hex"]).replace(b"10000000:", b"10000001:", 1).hex()
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="Invalid frame"):
        checked_read(path, 93, image=b"")
