"""Explicit layout v2: synthetic wire evidence never relabels an old capture."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from test_nor_freshness import place
from test_paired_nor_audit import replace_download
from test_prefilled_nor_control import RAM, fixture, validate
from test_prefilled_nor_parser import fixture as ring_fixture
from test_scratch_reuse_parser import NONCE, chain

from rcominote.experiments import prefilled_nor_control as C
from rcominote.experiments import scratch_reuse_parser as F

PLAIN = b"\n" + F.F.LOG_PREFIX
OLD = b"\n" + F.F.COMPOSER_FPS2 + F.F.LOG_PREFIX
NEW = b"\n\r\n" + F.F.COMPOSER_FPS2 + F.F.LOG_PREFIX[2:]


def upgrade(root, actual, plan, baseline):
    plan.update(profile=C.PROFILE_V2, gap_policy=F.PREFILL_GAP_POLICY)
    actual.update(profile=C.PROFILE_V2, gap_policy=F.PREFILL_GAP_POLICY)
    previous, history = baseline, baseline
    with patch.object(C, "RAM_SHA", C.A.A.sha(RAM)):
        for op in actual["operations"]:
            path = root / op["operation_id"] / "download.bin"
            data = path.read_bytes()
            if op["kind"] == "nor":
                sector = bytes.fromhex(op["verification"]["sector_hex"])
                text = NEW.join(chain(op["nonce"], op["nor_offset"], sector).rsplit(PLAIN, 1))
                data = place(text, 300 if op["operation_id"] == "first" else 2600, initial=history)
                replace_download(actual, root, op["operation_id"], data)
            op["verification"] = C.content(op, data, previous, RAM, plan, history)
            if op["kind"] == "nor":
                history = data
            previous = data
    (root / "plan.json").write_text(json.dumps(plan))
    actual["plan"] = C.C.J.reference(root, root / "plan.json")


@pytest.mark.parametrize(
    "gap,form", [(PLAIN, "plain"), (OLD, "composer-before-crlf"), (NEW, "crlf-before-composer")]
)
def test_closed_three_layouts_preserve_exact_gap_span_bytes(gap, form):
    _current, history = ring_fixture()
    data = place(gap.join(chain(NONCE).rsplit(PLAIN, 1)), 300, initial=history)
    sector, proof = F.parse_prefilled_ring(
        data, RAM, history, nonce=NONCE, nor_offset=0, gap_policy=F.PREFILL_GAP_POLICY
    )
    assert len(sector) == 512 and proof["difference_proven_written_prefix_bytes"] == 4096
    assert proof["critical_chain_inside_written_prefix"] and "prefix_policy" not in proof
    evidence = proof["producer_dump_gap"]
    assert evidence["policy"] == F.PREFILL_GAP_POLICY and evidence["form"] == form
    a, b = evidence["span"]
    assert (data * 2)[a:b] == gap == bytes.fromhex(evidence["hex"])
    if gap == NEW:
        with pytest.raises(ValueError, match="Unexpected text after current producer before dump"):
            F.parse_prefilled_ring(data, RAM, history, nonce=NONCE, nor_offset=0)
    else:
        old = F.parse_prefilled_ring(data, RAM, history, nonce=NONCE, nor_offset=0)[1]
        assert "producer_dump_gap" not in old


@pytest.mark.parametrize(
    "gap",
    [
        NEW + b" ",
        NEW.replace(b"\r\n", b"\n", 1),
        NEW + NEW,
        NEW.replace(b"fps 2", b"fps 3"),
        b"\nunknown\n" + F.F.LOG_PREFIX,
    ],
)
def test_no_whitespace_normalization_or_unknown_notice(gap):
    _, history = ring_fixture()
    data = place(gap.join(chain(NONCE).rsplit(PLAIN, 1)), 300, initial=history)
    with pytest.raises(ValueError, match="Unexpected text"):
        F.parse_prefilled_ring(data, RAM, history, nonce=NONCE, nor_offset=0, gap_policy=F.PREFILL_GAP_POLICY)


@pytest.mark.parametrize("policy", [True, False, "unknown", "", 1])
def test_unknown_gap_policy_fails_closed(policy):
    data, history = ring_fixture()
    with pytest.raises(ValueError, match="Unknown explicit"):
        F.parse_prefilled_ring(data, RAM, history, nonce=NONCE, nor_offset=0, gap_policy=policy)


def test_full_synthetic_v2_fifteen_transactions_and_bound_layout_proofs(tmp_path):
    actual, plan, baseline, oracles = fixture(tmp_path)
    with patch.object(C.C.pins, "oracles", return_value=oracles):
        upgrade(tmp_path, actual, plan, baseline)
    proof = validate(tmp_path, actual, plan, baseline, oracles)
    assert proof["gap_policy"] == F.PREFILL_GAP_POLICY and proof["parameter_transactions"] == 15
    assert all(
        op["verification"]["freshness"]["producer_dump_gap"]["form"] == "crlf-before-composer"
        for op in actual["operations"]
        if op["kind"] == "nor"
    )
    actual["ok"] = False
    with pytest.raises(ValueError, match="cannot be promoted"):
        C.validate(actual, tmp_path, plan, baseline, RAM, archived=True)


@pytest.mark.parametrize("fault", ["v1-policy", "v2-absent", "v2-unknown", "report-policy", "target"])
def test_profile_plan_layout_binding_fails_before_any_io(tmp_path, fault):
    actual, plan, _baseline, oracles = fixture(tmp_path)
    if fault == "v1-policy":
        plan["gap_policy"] = F.PREFILL_GAP_POLICY
    else:
        plan.update(profile=C.PROFILE_V2, gap_policy=F.PREFILL_GAP_POLICY)
        actual.update(profile=C.PROFILE_V2, gap_policy=F.PREFILL_GAP_POLICY)
        if fault == "v2-absent":
            plan.pop("gap_policy")
        elif fault == "v2-unknown":
            plan["gap_policy"] = "unknown"
        elif fault == "report-policy":
            actual["gap_policy"] = "unknown"
        else:
            plan["operations"][1]["nor_offset"] = 0x24400
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    actual["plan"] = C.C.J.reference(tmp_path, tmp_path / "plan.json")
    with (
        patch.object(C, "RAM_SHA", C.A.A.sha(RAM)),
        patch.object(C.C.pins, "oracles", return_value=oracles),
        pytest.raises(ValueError),
    ):
        C.plan_gate(actual, plan, tmp_path)


def test_communication_is_content_independent_but_whole_validation_is_not(tmp_path):
    actual, plan, baseline, oracles = fixture(tmp_path)
    actual["operations"][1]["verification"] = {"not_content_evidence": True}
    with (
        patch.object(C, "RAM_SHA", C.A.A.sha(RAM)),
        patch.object(C.C.pins, "oracles", return_value=oracles),
        patch.object(C, "content", side_effect=AssertionError("communication must not parse")),
    ):
        transfers, context, _events = C.communication(actual, tmp_path, plan, baseline, RAM)
    assert len(transfers) == 4 and context["cursor"] == 15
    with pytest.raises(ValueError, match="strict proof changed"):
        validate(tmp_path, actual, plan, baseline, oracles)


@pytest.mark.parametrize("count", [True, False, 0, 1, 3, 5])
def test_communication_rejects_undeclared_partial_bound_before_wire_io(count):
    with pytest.raises(ValueError, match="exactly two or four"):
        C.communication({}, None, {}, b"", b"", operation_count=count)


def test_shared_capture_v2_admission_reaches_scan_and_tamper_stops_before_scan(tmp_path):
    from rcominote.experiments import paired_nor_runtime as runtime

    actual, plan, baseline, oracles = fixture(tmp_path)
    with patch.object(C.C.pins, "oracles", return_value=oracles):
        upgrade(tmp_path, actual, plan, baseline)
    with (
        patch.object(C, "RAM_SHA", C.A.A.sha(RAM)),
        patch.object(C.C.pins, "oracles", return_value=oracles),
        patch.object(runtime, "find_device", AsyncMock(side_effect=RuntimeError("scan sentinel"))) as scan,
    ):
        with pytest.raises(RuntimeError, match="scan sentinel"):
            asyncio.run(runtime.capture(actual, plan, baseline, tmp_path))
        scan.assert_awaited_once()
        scan.reset_mock()
        actual["gap_policy"] = "unknown"
        with pytest.raises(ValueError, match="immutable fixed stages"):
            asyncio.run(runtime.capture(actual, plan, baseline, tmp_path))
        scan.assert_not_called()


def test_prepare_v2_is_host_only_fixed_recipe_with_explicit_immutable_policy(tmp_path):
    actual, old, baseline, oracles = fixture(tmp_path)
    with (
        patch.object(C, "RAM_SHA", C.A.A.sha(RAM)),
        patch.object(C.C.pins, "oracles", return_value=oracles),
        patch.object(C.C, "parent_gate", return_value=(baseline, old["expected_before"], old["parent"])),
        patch.object(C, "ram_source", return_value=(RAM, old["ram_oracle"])),
    ):
        plan, previous = C.prepare_v2(None, tmp_path)
        C.validate_plan(plan)
        report = C.report(plan)
        assert C.source_gate(plan, None) == previous == baseline
        assert report["gap_policy"] == plan["gap_policy"] == F.PREFILL_GAP_POLICY
        assert plan["profile"] == C.PROFILE_V2 and plan["offsets"] == [0, 0x4200]
        assert [len(C.recipe(op)) for op in plan["operations"]] == [4, 6, 4, 6]
        assert set(C.nonces(plan)).isdisjoint(old["parent"]["prior_names"])
        assert actual["profile"] == old["profile"] == C.PROFILE
