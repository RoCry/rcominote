"""Latest known4200 pins with full real-byte synthetic wire; ancestor gate mocked."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import test_scratch_4200_contract as known
from test_sd_nor_probe import info

from rcominote.experiments import scratch_system_pair_sources as S


def fixture(directory, monkeypatch):
    with patch.object(known.old, "info", return_value=info(9)):
        report, plan, previous = known.fixture(directory)
    report["verification"] = known.C.validate(report, directory, plan, previous)
    report["ok"] = report["baseline"]["ok"] = report["operation"]["ok"] = True
    for name, value in (("report", report), ("plan", plan)):
        (directory / f"{name}.json").write_text(json.dumps(value))
    for attr, name in (
        ("REPORT_SHA", "report.json"),
        ("PLAN_SHA", "plan.json"),
        ("HCI_SHA", "session.btsnoop"),
        ("BASELINE_SHA", "overwrite/download.bin"),
    ):
        monkeypatch.setattr(S, attr, S.A.sha((directory / name).read_bytes()))
    return report, plan, report["verification"]


def test_pins_latest_complete_current_ring_state_and_every_prior_plan_nonce(tmp_path, monkeypatch):
    report, _plan, proof = fixture(tmp_path, monkeypatch)
    with patch.object(S.Q, "replay", return_value=proof) as replay:
        baseline, state, summary = S.verify(tmp_path, Path("unused-image"))
    replay.assert_called_once_with(tmp_path, Path("unused-image"))
    assert baseline == (tmp_path / "overwrite/download.bin").read_bytes()
    assert state == report["after"] and state["device"]["free_capacity"] == 59589
    assert summary["prior_names"] == sorted(
        {S.pins.NAME, "rc8f8e3060d3", "rc15e8c0feb9", report["operation"]["nonce"]}
    )
    assert summary["original_failed_retained"] and summary["unknown_raw_oracle"] is False


@pytest.mark.parametrize("name", ["report.json", "plan.json", "session.btsnoop", "overwrite/download.bin"])
def test_every_parent_source_pin_is_mandatory(tmp_path, monkeypatch, name):
    _report, _plan, proof = fixture(tmp_path, monkeypatch)
    path = tmp_path / name
    path.write_bytes(path.read_bytes() + b"changed")
    with patch.object(S.Q, "replay", return_value=proof), pytest.raises(ValueError, match="Pinned"):
        S.verify(tmp_path, Path("unused-image"))


@pytest.mark.parametrize(
    "fault", ["top-false", "baseline-false", "download-false", "old-success", "offset", "replay"]
)
def test_original_flags_and_full_replay_contract_cannot_be_promoted(tmp_path, monkeypatch, fault):
    report, _plan, proof = fixture(tmp_path, monkeypatch)
    if fault == "top-false":
        report["ok"] = False
    elif fault == "baseline-false":
        report["baseline"]["ok"] = False
    elif fault == "download-false":
        report["operation"]["ok"] = False
    elif fault == "old-success":
        report["verification"]["original_trial_ok"] = True
    elif fault == "offset":
        report["verification"]["known_offset"] = 0x24400
    else:
        proof = {}
    (tmp_path / "report.json").write_text(json.dumps(report))
    monkeypatch.setattr(S, "REPORT_SHA", S.A.sha((tmp_path / "report.json").read_bytes()))
    with patch.object(S.Q, "replay", return_value=proof), pytest.raises(ValueError):
        S.verify(tmp_path, Path("unused-image"))
