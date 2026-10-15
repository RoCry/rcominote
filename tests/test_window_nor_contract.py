"""Offline dual-parent and shared fixed-target gates; no hardware fixtures."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from test_boot_tail_contract import fixture as tail_fixture
from test_boot_tail_contract import synthetic_ring

from rcominote.experiments import boot_tail_contract as C
from rcominote.experiments import window_nor_contract as W


def fixture(offset=0x2400):
    report = tail_fixture(offset)
    report.update(
        profile=W.PROFILE,
        started_at="2026-10-14T12:00:00+00:00",
        parent={
            "directory": "/unit-test/early-parent",
            "report_sha256": C.PARENT_SHA,
            "hci_sha256": C.PARENT_HCI_SHA,
            "verification": {"unit_test_stub": True},
        },
        window_parent={
            "directory": "/unit-test/window-parent",
            "report_sha256": W.WINDOW_PARENT_SHA,
            "hci_sha256": W.WINDOW_HCI_SHA,
            "verification": {"unit_test_stub": True},
        },
    )
    report["transport"]["policy"] = W.POLICY
    return report


@pytest.mark.parametrize("offset", C.OFFSETS)
def test_profile_shares_all_six_targets_without_fabricating_a_legacy_report(offset):
    report = fixture(offset)
    original = copy.deepcopy(report)
    W.recipe(report)
    C.common_recipe(report)
    with pytest.raises(ValueError, match="profile"):
        C.recipe(report)
    for index, op in enumerate(report["operations"]):
        previous = report["operations"][0]["dump_command"] if index else None
        data = synthetic_ring(op, bytes(range(256)) * 2, offset, previous=previous)
        result = W.payload(report, op, data)
        assert result == C.parse_payload(report, op, data, allow_composer_fps2=True)
        assert result["nor_offset"] == offset
        assert result["freshness"]["previous_dump_required"] == bool(index)
    assert report == original


def test_window_payload_explicitly_enables_only_the_new_composer_option():
    report = fixture()
    operation = report["operations"][0]
    ring = bytes(4096)
    with patch.object(C, "parse_payload", return_value={"unit_test_stub": True}) as parse:
        assert W.payload(report, operation, ring) == {"unit_test_stub": True}
    parse.assert_called_once_with(report, operation, ring, allow_composer_fps2=True)
    assert "freshness_policy" not in report


@pytest.mark.parametrize("parent", ["parent", "window_parent"])
@pytest.mark.parametrize("key", ["report_sha256", "hci_sha256", "directory"])
def test_both_parent_pins_are_mandatory_before_payload(parent, key):
    report = fixture()
    report[parent][key] = "" if key == "directory" else "0" * 64
    with patch.object(C, "parse_payload") as parse, pytest.raises(ValueError, match="parent identity"):
        W.payload(report, report["operations"][0], bytes(4096))
    parse.assert_not_called()


@pytest.mark.parametrize("fault", ["profile", "policy", "offset", "producer", "oracle", "nonce"])
def test_new_transport_does_not_bypass_shared_target_and_freshness_contract(fault):
    report = fixture()
    if fault == "profile":
        report["profile"] = C.PROFILE
    elif fault == "policy":
        report["transport"]["policy"] = C.condition.POLICY
    elif fault == "offset":
        report["nor_offset"] = True
    elif fault == "producer":
        report["operations"][1]["producer"] = "dbg fread spi_flash 0x2600"
    elif fault == "oracle":
        report["operations"][0]["oracle"] = {}
    else:
        report["operations"][1] = report["operations"][0] | {"operation_id": "second"}
    with pytest.raises(ValueError):
        W.recipe(report)


def test_second_still_requires_previous_dump_marker():
    report = fixture()
    second = report["operations"][1]
    with pytest.raises(ValueError):
        W.payload(report, second, synthetic_ring(second, bytes(512), 0x2400))


def test_prepare_checks_complete_early_contract_before_window_parent():
    with (
        patch.object(C, "prepare", side_effect=ValueError("fixed image/early failed")),
        patch.object(W, "window_parent_gate") as window,
        pytest.raises(ValueError, match="early failed"),
    ):
        W.prepare(Path("unused"), Path("unused"), Path("unused"), 0x2400)
    window.assert_not_called()


def test_prepare_preserves_early_parent_and_unclassified_operations():
    legacy = tail_fixture()
    legacy.update(parent=fixture()["parent"], ok=False, pair_verified=False)
    legacy["transport"]["update_attempted"] = False
    window = fixture()["window_parent"]
    with (
        patch.object(C, "prepare", return_value=legacy),
        patch.object(W, "window_parent_gate", return_value=window),
    ):
        report = W.prepare(Path("unused"), Path("unused"), Path("unused"), 0x2400)
    assert report["profile"] == W.PROFILE and report["transport"]["policy"] == W.POLICY
    assert report["parent"] == fixture()["parent"] and report["window_parent"] == window
    assert report["ok"] is report["pair_verified"] is report["transport"]["update_attempted"] is False
    assert all(op["independent_oracle"] is op["pair_verified"] is False for op in report["operations"])


@pytest.mark.parametrize("fault", ["report", "capture"])
def test_window_parent_hash_failures_never_call_replay(tmp_path, fault):
    (tmp_path / "report.json").write_bytes(b"{}")
    (tmp_path / "session.btsnoop").write_bytes(b"invalid")
    hashes = ["0" * 64, W.WINDOW_HCI_SHA] if fault == "report" else [W.WINDOW_PARENT_SHA, "0" * 64]
    with (
        patch.object(C.session.audit, "sha", side_effect=hashes),
        patch.object(W.R, "replay") as replay,
        pytest.raises(ValueError, match="exact successful"),
    ):
        W.window_parent_gate(tmp_path, tmp_path)
    replay.assert_not_called()


@pytest.mark.parametrize("fault", [None, "early-chain", "window-chain", "early-date", "window-date"])
def test_validate_parents_replays_both_chains_and_rejects_changed_or_future_parents(tmp_path, fault):
    report = fixture()
    for key in ("parent", "window_parent"):
        directory = tmp_path / key
        directory.mkdir()
        report[key]["directory"] = str(directory)
        ended = (
            "2026-10-14T13:00:00+00:00"
            if fault == ("early-date" if key == "parent" else "window-date")
            else "2026-10-14T10:00:00+00:00"
        )
        (directory / "report.json").write_text(json.dumps({"ended_at": ended}))
    early, window = copy.deepcopy(report["parent"]), copy.deepcopy(report["window_parent"])
    if fault == "early-chain":
        early["verification"] = {"changed": True}
    elif fault == "window-chain":
        window["verification"] = {"changed": True}
    with (
        patch.object(C, "parent_gate", return_value=early) as e,
        patch.object(W, "window_parent_gate", return_value=window) as w,
    ):
        if fault:
            with pytest.raises(ValueError):
                W.validate_parents(report, tmp_path)
        else:
            assert W.validate_parents(report, tmp_path) == {"parent": early, "window_parent": window}
        e.assert_called_once_with(Path(report["parent"]["directory"]), tmp_path)
        w.assert_called_once_with(Path(report["window_parent"]["directory"]), tmp_path)
