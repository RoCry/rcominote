"""Real public provenance replay, plus small corruption gates; never device I/O."""

import json
from unittest.mock import patch

import pytest

from rcominote.experiments import boot_prefix_evidence as E


def test_actual_public_archive_closes_historical_prefix_provenance():
    data, summary = E.verify()
    assert data == E.PREFIX.read_bytes() and len(data) == 512
    assert summary["nor_range"] == [0x2000, 0x2200]
    assert summary["target"] == "backup-boot"
    assert summary["producer"] == "dbg fread spi_flash 0x2000"
    assert summary["sha256"] == E.PREFIX_SHA
    assert summary["complete"] is True
    assert summary["input_windows"] == summary["distinct_sources"] == 22
    assert summary["confirmed_rows"] == 32 and summary["min_sources_per_row"] == 2
    assert summary["sources"]["archive"]["sha256"] == E.ARCHIVE_SHA
    assert summary["sources"]["report"]["sha256"] == E.REPORT_SHA
    assert summary["sources"]["prefix"]["sha256"] == E.PREFIX_SHA


@pytest.mark.parametrize("source", ["ARCHIVE", "REPORT", "PREFIX"])
def test_changed_source_pin_fails_before_archive_or_analyzer(tmp_path, source):
    changed = tmp_path / "changed"
    changed.write_bytes(b"changed source, not substitute evidence")
    with (
        patch.object(E, source, changed),
        patch.object(E.tarfile, "open") as archive,
        patch.object(E.nor_windows, "analyze") as analyze,
        pytest.raises(ValueError, match="Pinned backup-boot evidence changed"),
    ):
        E.verify()
    archive.assert_not_called()
    analyze.assert_not_called()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("complete", False),
        ("target", "boot"),
        ("offset", 0),
        ("producer", "dbg fread spi_flash 0"),
        ("confirmed_rows", 31),
        ("distinct_sources", 21),
        ("conflicts", ["0x0"]),
    ],
)
def test_synthetic_analyzer_cannot_claim_incomplete_or_cross_target_coverage(key, value):
    observed = json.loads(E.REPORT.read_bytes())
    observed[key] = value
    with (
        patch.object(E.nor_windows, "analyze", return_value=observed),
        pytest.raises(ValueError, match="complete fixed0x2000 double coverage"),
    ):
        E.verify()


@pytest.mark.parametrize("fault", ["row-source", "sector-bytes", "extra-field"])
def test_matching_summary_cannot_replace_full_pinned_report(fault):
    observed = json.loads(E.REPORT.read_bytes())
    if fault == "row-source":
        observed["rows"][0]["variants"][0]["sources"] = 1
    elif fault == "sector-bytes":
        observed["sector_hex"] = "00" * 512
    else:
        observed["synthetic_extra_field"] = True
    with (
        patch.object(E.nor_windows, "analyze", return_value=observed),
        pytest.raises(ValueError, match="complete pinned backup-boot report"),
    ):
        E.verify()
