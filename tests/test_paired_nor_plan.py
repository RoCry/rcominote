"""Finite plans and successful-only source admission; synthetic host fixtures."""

import copy
import json
from unittest.mock import patch

import pytest
from test_scratch_system_pair_contract import fixture as legacy_fixture

from rcominote.experiments import paired_nor_plan as C


def fixture(directory, offsets=None):
    original, oldplan, baseline = legacy_fixture(directory)
    source = oldplan["parent"] | {"profile": C.legacy.PROFILE}
    with (
        patch.object(C, "parent_gate", return_value=(baseline, original["before"], source)),
        patch.object(C.S, "now", return_value=oldplan["planned_at"]),
    ):
        plan, _baseline = C.prepare(None, None, [0x24400] if offsets is None else offsets)
    # All synthetic original captures use this earlier clock, independent of host now.
    plan["planned_at"] = oldplan["planned_at"]
    C.validate_plan(plan)
    return plan, baseline


@pytest.mark.parametrize("offsets", [[], [0] * 2, [True], [1], [-512], [0x400000], list(range(0, 2560, 512))])
def test_bad_ranges_fail_before_parent_replay(offsets):
    with patch.object(C, "parent_gate") as parent, pytest.raises(ValueError):
        C.prepare(None, None, offsets)
    parent.assert_not_called()


def test_finite_whole_physical_nor_range_and_all_nonce_budget(tmp_path):
    plan, baseline = fixture(tmp_path, [0, 0x24400, 0x1C9000, 0x3FFE00])
    assert plan["budget"] == C.budgets(4)
    assert len(set(C.nonces(plan))) == 8
    assert (
        C.page_plan(plan, 1, plan["expected_before"], plan["planned_at"])["future_nonces"]
        == C.nonces(plan)[2:]
    )
    C.F.absent(baseline, C.nonces(plan))
    assert "new_raw_nor_coverage_bytes" not in plan["page_budget"]


@pytest.mark.parametrize(
    "fault",
    [
        "address",
        "directory",
        "duplicate",
        "ancestor",
        "budget-bool",
        "page-bool",
        "policy",
        "producer",
        "order",
        "source-state",
    ],
)
def test_frozen_plan_tampering_fails_before_source(tmp_path, fault):
    plan, _baseline = fixture(tmp_path, [0x24400, 0x24600])
    if fault == "address":
        plan["offsets"][1] = 0x400000
    elif fault == "directory":
        plan["pages"][0]["directory"] = "../escape"
    elif fault == "duplicate":
        first = plan["pages"][0]["operations"][0]["nonce"]
        plan["pages"][1]["operations"][0].update(nonce=first, uptime_command=f"kernel uptime {first}")
    elif fault == "ancestor":
        plan["parent"]["prior_names"].append(C.nonces(plan)[-1])
    elif fault == "budget-bool":
        plan["budget"]["new_files"] = False
    elif fault == "page-bool":
        plan["page_budget"]["connections"] = True
    elif fault == "policy":
        plan["startup_policy"] = C.startup.POLICY
    elif fault == "producer":
        plan["pages"][0]["operations"][0]["producer"] = "dbg fread spi_flash 0x24200"
    elif fault == "order":
        plan["pages"].reverse()
    else:
        plan["expected_before"] = {}
    with patch.object(C, "parent_gate") as parent, pytest.raises(ValueError):
        C.source_gate(plan, None)
    parent.assert_not_called()


def test_every_preplanned_nonce_absent_initial_baseline(tmp_path):
    plan, baseline = fixture(tmp_path)
    polluted = bytearray(baseline)
    polluted[:12] = C.nonces(plan)[-1].encode()
    with (
        patch.object(
            C, "parent_gate", return_value=(bytes(polluted), plan["expected_before"], plan["parent"])
        ),
        pytest.raises(ValueError, match="nonce absent"),
    ):
        C.source_gate(plan, None)


@pytest.mark.parametrize("profile", [C.PROFILE, C.legacy.PROFILE, "unsupported"])
def test_failed_parent_rejected_before_any_replay(tmp_path, profile):
    (tmp_path / "report.json").write_text(json.dumps({"profile": profile, "ok": False}))
    with patch.object(C.old, "replay") as replay, pytest.raises(ValueError, match="failed parent"):
        C.parent_gate(tmp_path, None)
    replay.assert_not_called()


def test_source_gate_rejects_changed_original_parent_summary(tmp_path):
    plan, baseline = fixture(tmp_path)
    source = copy.deepcopy(plan["parent"])
    source["ended_at"] = "2026-10-14T09:00:01+00:00"
    with (
        patch.object(C, "parent_gate", return_value=(baseline, plan["expected_before"], source)),
        pytest.raises(ValueError, match="frozen plan"),
    ):
        C.source_gate(plan, None)


def test_v3_requires_explicit_policy_and_binds_every_operation_and_page(tmp_path):
    old, baseline = fixture(tmp_path)
    with (
        patch.object(C, "parent_gate", return_value=(baseline, old["expected_before"], old["parent"])),
        patch.object(C.S, "now", return_value=old["planned_at"]),
    ):
        plan, _baseline = C.prepare(None, None, [0x24A00], prefix_policy=C.F.PADDING_POLICY)
    assert plan["profile"] == C.PROFILE_V3
    page = C.page_plan(plan, 0, plan["expected_before"], plan["parent"]["ended_at"])
    assert page["profile"] == C.PAGE_PROFILE_V3 and page["prefix_policy"] == C.F.PADDING_POLICY
    C.validate_page(page)
    assert C.report(page)["prefix_policy"] == C.F.PADDING_POLICY
    plan["pages"][0]["operations"][0].pop("prefix_policy")
    with pytest.raises(ValueError, match="Producer policy"):
        C.validate_plan(plan)


@pytest.mark.parametrize("policy", [None, False, True, "unknown"])
def test_unsupported_policy_fails_before_parent_admission(policy):
    with patch.object(C, "parent_gate") as source, pytest.raises(ValueError, match="Unknown explicit"):
        C.prepare(None, None, [0x24A00], prefix_policy=policy)
    source.assert_not_called()


def test_legacy_v2_profile_cannot_smuggle_new_prefix_policy(tmp_path):
    plan, _baseline = fixture(tmp_path)
    plan["prefix_policy"] = C.F.PADDING_POLICY
    with pytest.raises(ValueError, match="Legacy v2"):
        C.validate_plan(plan)


def test_checkpoint_creation_time_must_precede_next_plan(tmp_path):
    plan, _baseline = fixture(tmp_path)
    plan["parent"].update(profile=C.CHECKPOINT_PROFILE, created_at="2026-10-14T12:00:00+00:00")
    with pytest.raises(ValueError, match="chronological"):
        C.validate_plan(plan)
