"""Source pins and full replay linkage; aggregate prior source mocked only here."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import test_scratch_postmortem_contract as prior
from test_sd_nor_probe import info

from rcominote.experiments import scratch_4200_sources as S


def fixture(directory, monkeypatch):
    with patch.object(prior, "info", return_value=info(9)):
        report, plan, previous = prior.fixture(directory)
    report.update(ok=True, readonly_proof=prior.C.readonly(report, directory, plan))
    report["operation"]["ok"] = True
    report["content_verification"] = prior.C.content(
        (directory / "retained/download.bin").read_bytes(), previous, plan
    )
    failed = directory / "failed"
    failed.mkdir()
    oldplan = {"operations": [{"nonce": "rc8f8e3060d3"}, {"nonce": "rc15e8c0feb9"}]}
    (failed / "plan.json").write_text(json.dumps(oldplan))
    plan["parent"]["directory"] = str(failed)
    plan["parent"]["sources"] = {"oracles": {"4200": {"sha256": "synthetic-independent-oracle"}}}
    for label, value in (("report", report), ("plan", plan)):
        (directory / f"{label}.json").write_text(json.dumps(value))
    for attr, name in (
        ("REPORT_SHA", "report.json"),
        ("PLAN_SHA", "plan.json"),
        ("HCI_SHA", "session.btsnoop"),
        ("BASELINE_SHA", "retained/download.bin"),
    ):
        monkeypatch.setattr(S, attr, S.A.sha((directory / name).read_bytes()))
    monkeypatch.setattr(S.failed, "PLAN_SHA", S.A.sha((failed / "plan.json").read_bytes()))
    proof = {"readonly": report["readonly_proof"], "content": report["content_verification"]}
    return report, plan, proof


def test_parent_pins_full_replay_current_bytes_latest_state_and_old_false(tmp_path, monkeypatch):
    report, plan, proof = fixture(tmp_path, monkeypatch)
    with patch.object(S.P, "replay", return_value=proof) as replay:
        baseline, state, summary = S.verify(tmp_path, Path("unused-image"))
    replay.assert_called_once_with(tmp_path, Path("unused-image"))
    assert baseline == (tmp_path / "retained/download.bin").read_bytes()
    assert state == report["after"] and state["device"]["free_capacity"] == 59589
    assert summary["prior_names"] == [S.pins.NAME, "rc8f8e3060d3", "rc15e8c0feb9"]
    assert summary["sources"] == plan["parent"]["sources"]
    assert summary["original_failed_retained"] and summary["reuse_pair_complete"] is False


@pytest.mark.parametrize("fault", ["report-pin", "plan-pin", "hci-pin", "baseline-pin", "old-plan-pin"])
def test_every_original_source_pin_is_checked(tmp_path, monkeypatch, fault):
    _report, _plan, proof = fixture(tmp_path, monkeypatch)
    name = {
        "report-pin": "report.json",
        "plan-pin": "plan.json",
        "hci-pin": "session.btsnoop",
        "baseline-pin": "retained/download.bin",
        "old-plan-pin": "failed/plan.json",
    }[fault]
    path = tmp_path / name
    path.write_bytes(path.read_bytes() + b"changed")
    with patch.object(S.P, "replay", return_value=proof), pytest.raises(ValueError, match="Pinned"):
        S.verify(tmp_path, Path("unused-image"))


@pytest.mark.parametrize(
    "fault", ["top-false", "download-false", "old-success", "pair-success", "nonce", "replay"]
)
def test_original_flags_and_replay_semantics_cannot_be_promoted(tmp_path, monkeypatch, fault):
    report, _plan, proof = fixture(tmp_path, monkeypatch)
    if fault == "top-false":
        report["ok"] = False
    elif fault == "download-false":
        report["operation"]["ok"] = False
    elif fault == "old-success":
        report["content_verification"]["original_trial_ok"] = True
    elif fault == "pair-success":
        report["content_verification"]["reuse_pair_complete"] = True
    elif fault == "nonce":
        report["content_verification"]["freshness"]["nonce"] = "rc0000000000"
    else:
        proof = {}
    (tmp_path / "report.json").write_text(json.dumps(report))
    monkeypatch.setattr(S, "REPORT_SHA", S.A.sha((tmp_path / "report.json").read_bytes()))
    with patch.object(S.P, "replay", return_value=proof), pytest.raises(ValueError):
        S.verify(tmp_path, Path("unused-image"))
