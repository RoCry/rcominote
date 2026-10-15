"""Actual synthetic single-epoch15txn, five downloads, four known producers."""

import asyncio
import copy
import json
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_paired_nor_control import fixture as original_fixture
from test_paired_nor_control import rewrite_capture
from test_param_window import remote, update

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import paired_nor_runtime as R


def fixture(root):
    report, plan, baseline, oracles = original_fixture(root)
    warm = report["groups"][1].pop("baseline")
    begin, end = warm["download_start"], warm["verified_end"]
    raw = (root / "session.btsnoop").read_bytes()
    wire = A.common.wire_positions(report, raw)
    first_record, last_record = warm["normalization"]["request"]["record"], wire[end - 1][1]
    rows = [
        (opcode, stamp, packet)
        for n, opcode, stamp, packet in A.P.records(raw, report["hci_capture"]["records"])
        if not first_record <= n <= last_record
    ]
    report["att_packets"] = report["att_packets"][:begin] + report["att_packets"][end:]
    shift = end - begin
    for index, row in enumerate(report["att_packets"]):
        row["monotonic_ns"] = index
    for op in report["groups"][1]["operations"]:
        for key in ("download_start", "download_end", "verified_end", "actions_start", "actions_end"):
            op[key] -= shift
        op["after_span"] = [n - shift for n in op["after_span"]]
    report["after_span"] = [n - shift for n in report["after_span"]]
    observed = rewrite_capture(root, report, rows)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    assert len(observed["transactions"]) == 15 and not observed["pending"]
    tx, wire, cursor = (
        observed["transactions"],
        A.common.wire_positions(report, (root / "session.btsnoop").read_bytes()),
        1,
    )
    previous = tx[0]
    for index, group in enumerate(report["groups"]):
        if index == 0:
            warm = group["baseline"]
            warm.update(normalization=tx[1], slow_settlement=tx[2])
            cursor, previous = 3, tx[2]
        for op in group["operations"]:
            fast, normal, slow = tx[cursor : cursor + 3]
            op.update(pre_download_fast=[fast], normalization=normal, slow_settlement=slow)
            op["activity_fast_verification"] = A.W.default_activity_fast(report, op, previous, fast, wire)
            op["actions_verification"] = C.actions(report, op)
            data = (
                root / plan["pages"][index]["directory"] / op["operation_id"] / "download.bin"
            ).read_bytes()
            op["download_verification"] = A.A.download(report, op, data, minimum_start=report["setup_end"])
            cursor, previous = cursor + 3, slow
    report["groups"][1]["continuation"] = C.continuation(report["groups"][0]["operations"][-1])
    shutil.rmtree(root / plan["pages"][1]["directory"] / "baseline")
    plan.update(
        profile=C.CONTINUOUS_CONTROL,
        budget=C.CONTINUOUS_BUDGET.copy(),
        stage_timeout_scope="five-post-startup-stages18-each-under-single-active60",
    )
    report.update({k: plan[k] for k in C.CONTROL_FIELDS})
    (root / "plan.json").write_text(json.dumps(plan))
    report["plan"] = C.J.reference(root, root / "plan.json")
    return report, plan, baseline, oracles


def validate(root, report, plan, baseline, oracles):
    with patch.object(C.pins, "oracles", return_value=oracles):
        return A.validate_control(report, root, plan, baseline)


def test_five_downloads_fifteen_actual_transactions_with_one_baseline(tmp_path):
    report, plan, baseline, oracles = fixture(tmp_path)
    original = copy.deepcopy(report)
    proof = validate(tmp_path, report, plan, baseline, oracles)
    assert proof["downloads"] == 5 and proof["parameter_transactions"] == 15
    assert proof["sd_writes"] == proof["producers"] == 4 and proof["connections"] == 1
    assert proof["new_raw_nor_coverage_bytes"] == 0 and proof["independent_oracle"]
    assert "baseline" not in report["groups"][1] and report == original
    assert [group["known_offset"] for group in proof["groups"]] == [0, 0x4200]


@pytest.mark.parametrize(
    "fault",
    [
        "fake-baseline",
        "stale-ring",
        "stale-state",
        "stale-span",
        "stale-slow",
        "missing-fast",
        "candidate",
        "oracle",
        "sector",
        "second-file",
        "future-nonce",
    ],
)
def test_continuation_or_independent_pair_proof_cannot_be_fabricated(tmp_path, fault):
    report, plan, baseline, oracles = fixture(tmp_path)
    group = report["groups"][1]
    if fault == "fake-baseline":
        group["baseline"] = copy.deepcopy(report["groups"][0]["baseline"])
    elif fault == "stale-ring":
        group["continuation"]["download_sha256"] = A.A.sha(baseline)
    elif fault == "stale-state":
        group["continuation"]["after"] = {}
    elif fault == "stale-span":
        group["continuation"]["verified_end"] -= 1
    elif fault == "stale-slow":
        group["continuation"]["slow_settlement"] = report["groups"][0]["baseline"]["slow_settlement"]
    elif fault == "missing-fast":
        group["operations"][0]["pre_download_fast"] = []
    elif fault == "candidate":
        group["candidate"] = False
    elif fault == "oracle":
        group["operations"][0]["oracle_verification"] = {}
    elif fault == "sector":
        (tmp_path / plan["pages"][1]["directory"] / "second/sector.bin").write_bytes(bytes(512))
    elif fault == "second-file":
        (tmp_path / plan["pages"][1]["directory"] / "second/download.bin").write_bytes(
            (tmp_path / plan["pages"][1]["directory"] / "first/download.bin").read_bytes()
        )
    else:
        # Admission independently requires all four preplanned names absent initially.
        plan["parent"]["prior_names"].append(C.nonces(plan)[-1])
    with pytest.raises((ValueError, IndexError)):
        validate(tmp_path, report, plan, baseline, oracles)


@pytest.mark.parametrize("pending", [False, True])
def test_actual_extra_fast_or_pending_between_groups_rejected(tmp_path, pending):
    report, plan, baseline, oracles = fixture(tmp_path)
    raw = (tmp_path / "session.btsnoop").read_bytes()
    rows = [
        (opcode, stamp, packet)
        for _n, opcode, stamp, packet in A.P.records(raw, report["hci_capture"]["records"])
    ]
    insertion = (
        report["groups"][1]["operations"][0]["pre_download_fast"][0]["remote_request"]["records"][0] - 1
    )
    if pending:
        insertion = len(rows) - 1
    extra = remote(identifier=111) + ([] if pending else [update(12)])
    rows[insertion:insertion] = [(opcode, rows[insertion - 1][1], packet) for opcode, packet in extra]
    observed = rewrite_capture(tmp_path, report, rows)
    assert observed["pending"] or len(observed["transactions"]) == 16
    with pytest.raises(ValueError, match="exactly 15"):
        validate(tmp_path, report, plan, baseline, oracles)


@pytest.mark.parametrize("fault", ["profile", "budget", "offset", "scope"])
def test_immutable_continuous_plan_is_closed_before_scan(tmp_path, fault):
    report, plan, _baseline, oracles = fixture(tmp_path)
    if fault == "profile":
        plan["profile"] = C.KNOWN_CONTROL
    elif fault == "budget":
        plan["budget"]["downloads"] = 6
    elif fault == "offset":
        plan["offsets"][1] = 0x24400
    else:
        plan["stage_timeout_scope"] = "six-post-startup-stages18-each-under-single-active60"
    with (
        patch.object(C.pins, "oracles", return_value=oracles),
        patch.object(R, "find_device") as scan,
        pytest.raises(ValueError),
    ):
        R.plan_gate(report, plan, tmp_path)
    scan.assert_not_called()


@pytest.mark.parametrize("failure", range(5))
@pytest.mark.parametrize("error_type", [ValueError, TimeoutError, asyncio.CancelledError])
def test_five_stage_runtime_failure_stops_and_preserves_actual_predecessor(tmp_path, failure, error_type):
    original, plan, baseline, oracles = fixture(tmp_path)
    with patch.object(C.pins, "oracles", return_value=oracles):
        report = C.control_report(plan) | {"att_packets": [], "transport": {"link": {}}}
    identities, stages, contexts = [], [], []
    conn = SimpleNamespace(file_list=AsyncMock(return_value=[]))

    async def identity(_conn, owner, key, state, **_kwargs):
        identities.append(key)
        owner[key] = state

    async def transfer(_conn, _monitor, _report, stage, context, target, _future):
        contexts.append(copy.deepcopy(context))
        stages.append(stage["operation_id"])
        index = len(stages) - 1
        if index == failure:
            (target / "download.bin").write_bytes(b"actual partial")
            raise error_type("stage failed")
        group_index = 0 if index < 3 else 1
        owner = original["groups"][group_index]
        actual = owner["baseline"] if index == 0 else owner["operations"][(index - 1) % 2]
        stage.update(copy.deepcopy(actual))
        data = (
            tmp_path / plan["pages"][group_index]["directory"] / stage["operation_id"] / "download.bin"
        ).read_bytes()
        context.update(
            state=stage["after"],
            previous=data,
            boundary=stage["verified_end"],
            previous_tx=stage["slow_settlement"],
            cursor=context["cursor"] + (2 if index == 0 else 3),
        )

    async def producer(conn, _actions, monitor, report, stage, context, target, future, **_kwargs):
        await transfer(conn, monitor, report, stage, context, target, future)

    with (
        patch.object(R, "plan_gate"),
        patch.object(R.shared, "identity", new=AsyncMock(side_effect=identity)),
        patch.object(C.startup, "wait_startup", new=AsyncMock(return_value=({}, {}))),
        patch.object(R, "baseline_transfer", new=AsyncMock(side_effect=transfer)) as warm,
        patch.object(R, "producer_transfer", new=AsyncMock(side_effect=producer)) as produce,
        patch.object(R.R, "observe"),
        patch.object(R, "final_state", return_value=plan["expected_before"]),
        pytest.raises(error_type, match="stage failed"),
    ):
        asyncio.run(R.connected(conn, None, None, report, plan, baseline, tmp_path))
    assert warm.await_count == 1 and produce.await_count == failure
    assert stages == ["baseline", "first", "second", "first", "second"][: failure + 1]
    assert identities == (["before", "after"] if error_type is ValueError else ["before"])
    assert report["groups"][0]["candidate"] is (failure >= 3)
    assert report["groups"][1]["candidate"] is False and "baseline" not in report["groups"][1]
    if failure >= 3:
        assert contexts[3]["cursor"] == 9
        assert report["groups"][1]["continuation"] == C.continuation(report["groups"][0]["operations"][-1])


def test_original_failed_continuous_control_still_rejected_before_source_walk(tmp_path):
    report, _plan, _baseline, _oracles = fixture(tmp_path)
    C.S.save(tmp_path / "report.json", report)
    with patch.object(C.old, "replay") as replay, pytest.raises(ValueError, match="failed parent"):
        C.parent_gate(tmp_path, None)
    replay.assert_not_called()


def test_successful_continuous_control_admits_actual_last_file_for_future_pages(tmp_path):
    import test_scratch_reuse_audit as old_fixture
    from test_sd_nor_probe import info

    root, anchor = tmp_path / "control", tmp_path / "anchor"
    with patch.object(old_fixture, "info", return_value=info(9)):
        report, plan, baseline, oracles = fixture(root)
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
    (anchor / "session.btsnoop").write_bytes(b"outer historical source fixture")
    pins = {name: A.A.sha((anchor / name).read_bytes()) for name in C.LEGACY_PINS}
    refs = {name: C.pins.pinned(anchor / name, sha)[1] for name, sha in pins.items()}
    plan["parent"] = C.source_summary(
        anchor, original, anchor_plan, anchor_proof, baseline, original["after"], refs
    )
    (root / "plan.json").write_text(json.dumps(plan))
    report["plan"] = C.J.reference(root, root / "plan.json")
    report["verification"] = validate(root, report, plan, baseline, oracles)
    report["ok"] = True
    C.S.save(root / "report.json", report)
    with (
        patch.object(C, "LEGACY_PINS", pins),
        patch.object(C.old, "replay", return_value=anchor_proof),
        patch.object(C.pins, "oracles", return_value=oracles),
    ):
        current, state, summary = C.parent_gate(root, None)
        assert current == (root / "page1-004200/second/download.bin").read_bytes()
        assert state == report["after"] and summary["profile"] == C.CONTINUOUS_CONTROL
        assert summary["verification"]["parameter_transactions"] == 15
        next_plan, next_baseline = C.prepare(None, root, [0x25800])
        assert next_baseline == current and C.source_gate(next_plan, None) == current
        assert set(C.nonces(plan)).issubset(next_plan["parent"]["prior_names"])


def test_preparation_is_fixed_known_pair_and_four_names_exclude_admitted_history(tmp_path):
    _report, plan, baseline, oracles = fixture(tmp_path)
    parent = plan["parent"]
    with (
        patch.object(C, "parent_gate", return_value=(baseline, plan["expected_before"], parent)),
        patch.object(C.pins, "oracles", return_value=oracles),
    ):
        new, previous = C.prepare_continuous_control(None, tmp_path)
        assert new["profile"] == C.CONTINUOUS_CONTROL and new["offsets"] == [0, 0x4200]
        assert new["budget"] == C.CONTINUOUS_BUDGET and previous == baseline
        assert len(set(C.nonces(new))) == 4 and not set(C.nonces(new)).intersection(parent["prior_names"])
        actual = C.control_report(new)
        assert "baseline" not in actual["groups"][1] and actual["groups"][1]["continuation"] is None


@pytest.mark.parametrize("pending", [False, True])
def test_continuation_extra_fast_stops_before_any_new_actions(tmp_path, pending):
    op = {"operation_id": "first"}
    context = {"state": {}, "previous": bytes(4096), "previous_tx": {}, "cursor": 9, "boundary": 1}
    report = {"transport": {"link": {}}}
    actions = SimpleNamespace(run_commands=AsyncMock())
    snapshot = {"transactions": [{}] * (9 if pending else 10), "pending": [{}] if pending else []}
    with (
        patch.object(R.R, "observe", return_value=snapshot),
        pytest.raises(ValueError, match="before producer"),
    ):
        asyncio.run(
            R.producer_transfer(None, actions, None, report, op, context, tmp_path, [], control_plan={})
        )
    actions.run_commands.assert_not_called()
    assert "producer_attempted" not in op and "started_at" not in op
