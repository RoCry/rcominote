"""The status literal policy is an explicit fixed known-control contract."""

import copy
import json
from unittest.mock import Mock, patch

import pytest
from test_paired_nor_continuous_control import fixture as continuous_fixture

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import paired_nor_runtime as R


def fixture(root, *, profile=C.STATUS_CONTROL):
    report, plan, baseline, oracles = continuous_fixture(root)
    policy = C.F.FORMAT_POLICY if profile == C.FORMAT_CONTROL else C.F.STATUS_POLICY
    plan.update(profile=profile, prefix_policy=policy)
    previous = baseline
    for index, page in enumerate(plan["pages"]):
        for slot, op in zip(page["operations"], report["groups"][index]["operations"], strict=True):
            slot["prefix_policy"] = op["prefix_policy"] = policy
            data = (root / page["directory"] / op["operation_id"] / "download.bin").read_bytes()
            op["verification"] = C.payload(op, data, previous)
            previous = data
    report.update({key: plan[key] for key in C.CONTROL_FIELDS})
    (root / "plan.json").write_text(json.dumps(plan))
    report["plan"] = C.J.reference(root, root / "plan.json")
    return report, plan, baseline, oracles


@pytest.mark.parametrize("profile", [C.STATUS_CONTROL, C.FORMAT_CONTROL])
def test_explicit_fixed_formatter_control_keeps_entire_fifteen_transaction_contract(tmp_path, profile):
    report, plan, baseline, oracles = fixture(tmp_path, profile=profile)
    original = copy.deepcopy(report)
    with patch.object(C.pins, "oracles", return_value=oracles):
        R.plan_gate(report, plan, tmp_path)
        proof = A.validate_control(report, tmp_path, plan, baseline)
    assert proof["parameter_transactions"] == 15 and proof["downloads"] == 5
    assert proof["producers"] == 4 and proof["new_raw_nor_coverage_bytes"] == 0
    assert original == report and "baseline" not in report["groups"][1]
    assert all(
        op["verification"]["freshness"]["prefix_policy"] == plan["prefix_policy"]
        for group in report["groups"]
        for op in group["operations"]
    )


@pytest.mark.parametrize(
    "fault",
    ["old-profile", "old-policy", "unknown-policy", "operation-policy", "unknown-offset", "oracle", "budget"],
)
@pytest.mark.parametrize("profile", [C.STATUS_CONTROL, C.FORMAT_CONTROL])
def test_status_policy_is_never_implicit_or_a_generic_address_option(tmp_path, fault, profile):
    report, plan, _baseline, oracles = fixture(tmp_path, profile=profile)
    if fault == "old-profile":
        plan["profile"] = C.CONTINUOUS_CONTROL
    elif fault == "old-policy":
        plan["prefix_policy"] = C.F.PADDING_POLICY
    elif fault == "unknown-policy":
        plan["prefix_policy"] = "optional-all-ASCII"
    elif fault == "operation-policy":
        plan["pages"][0]["operations"][1]["prefix_policy"] = C.F.PADDING_POLICY
    elif fault == "unknown-offset":
        plan["offsets"][1] = 0x24400
    elif fault == "oracle":
        plan["oracles"] = {}
    else:
        plan["budget"]["parameter_transactions"] = 9
    with (
        patch.object(C.pins, "oracles", return_value=oracles),
        patch.object(R, "find_device") as scan,
        pytest.raises(ValueError),
    ):
        R.plan_gate(report, plan, tmp_path)
    scan.assert_not_called()


@pytest.mark.parametrize("policy", [C.F.STATUS_POLICY, C.F.FORMAT_POLICY])
def test_generic_prepare_cannot_choose_status_policy_before_parent_admission(tmp_path, policy):
    with patch.object(C, "parent_gate") as parent, pytest.raises(ValueError, match="Unknown explicit"):
        C.prepare(None, tmp_path, [0x24400], prefix_policy=policy)
    parent.assert_not_called()


@pytest.mark.parametrize("profile", [C.STATUS_CONTROL, C.FORMAT_CONTROL])
def test_fixed_preparation_requires_explicit_new_entry_and_fresh_four_names(tmp_path, profile):
    _report, old, baseline, oracles = fixture(tmp_path, profile=profile)
    prepare = C.prepare_formatter_control if profile == C.FORMAT_CONTROL else C.prepare_status_control
    policy = C.F.FORMAT_POLICY if profile == C.FORMAT_CONTROL else C.F.STATUS_POLICY
    with (
        patch.object(C, "parent_gate", return_value=(baseline, old["expected_before"], old["parent"])),
        patch.object(C.pins, "oracles", return_value=oracles),
    ):
        plan, data = prepare(None, tmp_path)
        assert plan["profile"] == profile and plan["offsets"] == [0, 0x4200]
        assert plan["prefix_policy"] == policy and data == baseline
        assert len(set(C.nonces(plan))) == 4
        assert all(op["prefix_policy"] == policy for page in plan["pages"] for op in page["operations"])


@pytest.mark.parametrize("profile", [C.STATUS_CONTROL, C.FORMAT_CONTROL])
def test_original_failed_new_contract_cannot_be_adopted_by_pair_equality(tmp_path, profile):
    report, _plan, _baseline, _oracles = fixture(tmp_path, profile=profile)
    C.S.save(tmp_path / "report.json", report)
    with (
        patch.object(C.old, "replay", Mock(side_effect=AssertionError("historical read"))),
        pytest.raises(ValueError, match="failed parent"),
    ):
        C.parent_gate(tmp_path, None)


def test_content_checkpoint_is_iterative_owned_parent_for_explicit_status_plan(tmp_path):
    from test_paired_nor_content_checkpoint import failure_gate, reseal
    from test_paired_nor_content_checkpoint import fixture as failed_fixture

    from rcominote.experiments import paired_nor_checkpoint as K

    failed, anchor, out = tmp_path / "failed", tmp_path / "anchor", tmp_path / "checkpoint"
    original, old, baseline, current, oracles, code = failed_fixture(failed)
    (anchor / "second").mkdir(parents=True)
    observed = {
        "profile": C.legacy.PROFILE,
        "ok": True,
        "after": old["expected_before"],
        "ended_at": old["parent"]["ended_at"],
    }
    anchor_plan, proof = {"prior_names": old["parent"]["prior_names"]}, {"verified": True}
    C.S.save(anchor / "report.json", observed)
    C.S.save(anchor / "plan.json", anchor_plan)
    (anchor / "second/download.bin").write_bytes(baseline)
    (anchor / "session.btsnoop").write_bytes(b"historical outer fixture")
    pins = {name: A.A.sha((anchor / name).read_bytes()) for name in C.LEGACY_PINS}
    refs = {name: C.pins.pinned(anchor / name, sha)[1] for name, sha in pins.items()}
    old["parent"] = C.source_summary(anchor, observed, anchor_plan, proof, baseline, observed["after"], refs)
    reseal(failed, original, old)
    with (
        failure_gate(oracles, code),
        patch.object(C, "LEGACY_PINS", pins),
        patch.object(C.old, "replay", return_value=proof),
        patch.object(R, "private_output"),
    ):
        copied, state, source = K.create(None, failed, out)
        assert copied == current and state == original["after"]
        assert (
            source["profile"] == K.CONTENT_PROFILE
            and source["verification"]["new_raw_nor_coverage_bytes"] == 0
        )
        assert C.parent_gate(out, None) == (current, state, source)
        plan, actual = C.prepare_status_control(None, out)
        assert actual == current and C.source_gate(plan, None) == current
        assert plan["profile"] == C.STATUS_CONTROL and plan["parent"] == source
        assert set(C.nonces(old)).issubset(plan["parent"]["prior_names"])
        assert original["ok"] is False and original["groups"][0]["operations"][1]["ok"] is False
        with pytest.raises(ValueError, match="failed parent"):
            C.parent_gate(failed, None)


@pytest.mark.parametrize("profile", [C.STATUS_CONTROL, C.FORMAT_CONTROL])
def test_successful_status_control_is_admitted_by_full_fifteen_transaction_replay(tmp_path, profile):
    import test_scratch_reuse_audit as old_fixture
    from test_sd_nor_probe import info

    root, anchor = tmp_path / "control", tmp_path / "anchor"
    with patch.object(old_fixture, "info", return_value=info(9)):
        actual, plan, baseline, oracles = fixture(root, profile=profile)
    (anchor / "second").mkdir(parents=True)
    original = {
        "profile": C.legacy.PROFILE,
        "ok": True,
        "after": plan["expected_before"],
        "ended_at": plan["parent"]["ended_at"],
    }
    anchor_plan, anchor_proof = {"prior_names": plan["parent"]["prior_names"]}, {"verified": True}
    C.S.save(anchor / "report.json", original)
    C.S.save(anchor / "plan.json", anchor_plan)
    (anchor / "second/download.bin").write_bytes(baseline)
    (anchor / "session.btsnoop").write_bytes(b"outer historical fixture")
    pins = {name: A.A.sha((anchor / name).read_bytes()) for name in C.LEGACY_PINS}
    refs = {name: C.pins.pinned(anchor / name, sha)[1] for name, sha in pins.items()}
    plan["parent"] = C.source_summary(
        anchor, original, anchor_plan, anchor_proof, baseline, original["after"], refs
    )
    (root / "plan.json").write_text(json.dumps(plan))
    actual["plan"] = C.J.reference(root, root / "plan.json")
    with (
        patch.object(C, "LEGACY_PINS", pins),
        patch.object(C.old, "replay", return_value=anchor_proof),
        patch.object(C.pins, "oracles", return_value=oracles),
    ):
        actual["verification"] = A.validate_control(actual, root, plan, baseline)
        actual["ok"] = True
        C.S.save(root / "report.json", actual)
        current, state, source = C.parent_gate(root, None)
        assert current == (root / "page1-004200/second/download.bin").read_bytes()
        assert state == actual["after"] and source["profile"] == profile
        assert source["verification"]["parameter_transactions"] == 15
        actual["ok"] = False
        (root / "report.json").write_text(json.dumps(actual))
        with pytest.raises(ValueError, match="failed parent"):
            C.parent_gate(root, None)
