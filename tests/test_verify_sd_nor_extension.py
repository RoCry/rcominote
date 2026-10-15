"""Public fixed nonzero proof rejects wrong target, reuse and missing HCI coverage."""

import copy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "docs/evidence/sd-nor-offset4200-live-2026-10-14.json"


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    return (
        importlib.import_module("verify_sd_nor_interval"),
        importlib.import_module("sd_nor_interval_extension"),
    )


def test_actual_pair_selected_safe_spans_pass(modules):
    _, extension = modules
    _, result = extension.published(RECEIPT)
    assert result["unique_sector_bytes"] == 512
    assert result["independent_reads"] == 2
    assert result["full_private_audit_replayed"] is False


@pytest.mark.parametrize("fault", ["producer", "oracle-slice", "same-file", "wrong-parent", "overlap"])
def test_nonzero_pair_semantics_reject_corruption(modules, monkeypatch, fault):
    _, extension = modules
    data = json.loads(RECEIPT.read_bytes())
    a, b = data["observations"]
    match fault:
        case "producer":
            a["producer"] = "dbg fread spi_flash 0x4400"
        case "oracle-slice":
            data["oracle"]["slice"] = [0, 512]
        case "same-file":
            b["source_report"]["file"] = a["source_report"]["file"]
        case "wrong-parent":
            a["previous_report_sha256"] = "0" * 64
        case "overlap":
            b["started_at"] = a["started_at"]
    # Receipt pinning already rejects changed files; bypass JSON decoding only
    # to exercise the semantic guards independently of that outer hash check.
    monkeypatch.setattr(extension, "json", SimpleNamespace(loads=lambda _: data))
    with pytest.raises(ValueError):
        extension.published(RECEIPT)


@pytest.mark.parametrize("fault", ["coverage", "stop-delivery", "exit130-without-stop"])
def test_early_stop_requires_final_capture_coverage_and_owned_stop(modules, fault):
    verifier, _ = modules
    row = json.loads(RECEIPT.read_bytes())["observations"][0]
    transport = copy.deepcopy(row["transport"])
    match fault:
        case "coverage":
            transport["capture_last_timestamp_us"] = transport["download_end_us"] - 1
        case "stop-delivery":
            transport["monitor_stop"]["delivery"] = "failed"
        case "exit130-without-stop":
            transport["monitor_exit"] = 130
            transport["monitor_stop"] = {}
    with pytest.raises(ValueError):
        verifier.parameters(verifier.parser(), transport, early_stop=True)
