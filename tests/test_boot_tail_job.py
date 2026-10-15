"""Fixed planning, byte assembly and failure preservation; synthetic data is not live proof."""

import copy
import json
from unittest.mock import patch

import pytest
from test_boot_tail_contract import fixture, synthetic_ring
from test_dual_probe import info

from rcominote.experiments import boot_tail_job as J


def plan_fixture():
    return {
        "profile": J.PROFILE,
        "planned_at": J.S.now(),
        "serial": J.OWNED_SERIAL,
        "source_image_sha256": J.U.probe.IMAGE_SHA,
        "coverage_basis": J.C.coverage_basis(),
        "max_connections": 6,
        "max_producer_executions": 12,
        "max_sd_test_files": 12,
        "slots": [
            {"nor_offset": offset, "directory": f"{offset:04x}", "names": [f"rc{i:09x}{n}" for n in (0, 1)]}
            for i, offset in enumerate(J.C.OFFSETS)
        ],
    }


def reports_fixture():
    return [fixture(offset) | {"started_at": J.S.now(), "ok": False} for offset in J.C.OFFSETS]


def test_assembly_preserves_all_distinct_synthetic_bytes_and_address_order():
    sectors = [(offset, bytes([index]) * 512) for index, offset in enumerate(J.C.OFFSETS, start=1)]
    before = copy.deepcopy(sectors)
    prefix, block2200 = bytes([0xA5]) * 512, bytes([0x5A]) * 512
    tail, full = J.join_sectors(sectors, prefix, block2200)
    assert len(tail) == 3072 and len(full) == 4096
    assert full == prefix + block2200 + b"".join(data for _, data in sectors)
    assert sectors == before


@pytest.mark.parametrize(
    "values",
    [
        ["2026-10-14T01:00:00+00:00", "2026-10-14T00:59:59+00:00"],
        ["2026-10-14T01:00:00"],
        ["2026-10-14T01:00:00+00:00", "2026-10-14T00:59:59+00:00", "2026-10-14T02:00:00+00:00"],
    ],
)
def test_late_plan_or_reversed_acquisition_time_cannot_pass(values):
    with pytest.raises(ValueError, match="timezone-aware and chronological"):
        J.time_order(*values)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "reordered", "short", "prefix", "2200"])
def test_assembly_never_fills_holes_or_reuses_the_old_prefix(fault):
    sectors = [(offset, bytes([index]) * 512) for index, offset in enumerate(J.C.OFFSETS)]
    prefix = block2200 = bytes(512)
    if fault == "missing":
        sectors.pop()
    elif fault == "duplicate":
        sectors[-1] = sectors[-2]
    elif fault == "reordered":
        sectors.reverse()
    elif fault == "short":
        sectors[-1] = (sectors[-1][0], bytes(511))
    elif fault == "prefix":
        prefix = bytes(511)
    else:
        block2200 = bytes(511)
    with pytest.raises(ValueError, match="requires"):
        J.join_sectors(sectors, prefix, block2200)


@pytest.mark.parametrize("fault", ["count", "offset", "path", "nonce", "budget", "profile"])
def test_job_plan_cannot_expand_or_alias_fixed_slots(fault):
    plan = plan_fixture()
    J.validate_plan(plan)
    if fault == "count":
        plan["slots"].pop()
    elif fault == "offset":
        plan["slots"][-1]["nor_offset"] = 0x3000
    elif fault == "path":
        plan["slots"][0]["directory"] = "../2400"
    elif fault == "nonce":
        plan["slots"][-1]["names"][0] = plan["slots"][0]["names"][0]
    elif fault == "budget":
        plan["max_connections"] = 7
    else:
        plan["profile"] = "arbitrary-nor-job"
    with pytest.raises(ValueError):
        J.validate_plan(plan)


@pytest.mark.parametrize("offset", J.C.OFFSETS)
def test_shared_pair_comparator_uses_validated_actual_target(tmp_path, offset):
    report = fixture(offset) | {"final_audit_complete": True}
    first, second = report["operations"]
    sector = bytes(range(256)) * 2
    for index, operation in enumerate((first, second)):
        # These flags exercise byte comparison only; no synthetic HCI success is claimed.
        operation.update(
            ok=True, live_complete=True, actions_start=10 + index * 40, verified_end=30 + index * 40
        )
        previous = first["dump_command"] if index else None
        ring = synthetic_ring(operation, sector, offset, previous=previous)
        path = tmp_path / operation["operation_id"]
        path.mkdir()
        (path / "download.bin").write_bytes(ring)
        (path / "sector.bin").write_bytes(sector)
        operation.update(download_bytes=4096, received_bytes=4096, download_sha256=J.S.audit.sha(ring))
        operation["verification"] = J.C.payload(report, operation, ring)
    result = J.compare(report, tmp_path)
    assert result["nor_range"] == [offset, offset + 512]
    assert result["sha256"] == J.S.audit.sha(sector) and result["independent_oracle"] is False


@pytest.mark.parametrize("completed_before_failure", [0, 1])
def test_first_failure_stops_remaining_plan_and_preserves_completed_pair(tmp_path, completed_before_failure):
    out, parent = tmp_path / "job", tmp_path / "parent"
    parent.mkdir()
    (parent / "report.json").write_text(json.dumps({"after": info()}))
    plan, reports = plan_fixture(), reports_fixture()
    calls = []

    def run_pair(report, directory):
        calls.append(report["nor_offset"])
        if len(calls) > completed_before_failure:
            report.update(ok=False, error="intentional failed acquisition")
            J.S.save(directory / "report.json", report)
            raise ValueError("intentional failed acquisition")
        report.update(ok=True, after=info(), ended_at=J.S.now())
        J.S.save(directory / "report.json", report)

    # Control-flow mocks do not replace real pair validation; these jobs must fail.
    with (
        patch.object(J, "prepare", return_value=(plan, reports)),
        patch.object(J, "authorize") as authorization,
        patch.object(J, "run_pair", side_effect=run_pair),
        patch.object(J, "pair_replay", return_value={"synthetic_control_flow_only": True}) as pair,
        pytest.raises(ValueError, match="intentional"),
    ):
        J.main(tmp_path / "unused.bin", parent, out)
    authorization.assert_called_once()
    assert calls == list(J.C.OFFSETS[: completed_before_failure + 1])
    assert pair.call_count == completed_before_failure
    final = json.loads((out / "report.json").read_bytes())
    assert final["ok"] is False and "intentional" in final["error"]
    assert len(final["completed"]) == completed_before_failure
    assert not (out / "tail.bin").exists() and not (out / "fw1_boot.bin").exists()
    if completed_before_failure:
        checkpoint = json.loads((out / "checkpoint-2400.json").read_bytes())
        assert len(checkpoint["completed"]) == 1 and checkpoint["ok"] is False
        assert (out / "2400/report.json").read_bytes()
    with patch.object(J, "audit_job") as audit, pytest.raises(ValueError, match="Original full job"):
        J.replay(out, tmp_path / "unused.bin")
    audit.assert_not_called()


def test_failed_pair_preserves_download_and_never_attempts_pairing(tmp_path):
    report = fixture() | {"started_at": J.S.now(), "ok": False, "pair_verified": False}
    (tmp_path / "first").mkdir()

    async def failure(actual, directory):
        (directory / "first/download.bin").write_bytes(b"retained partial fixture")
        raise ValueError("original capture failure")

    with (
        patch.object(J.S, "capture", side_effect=failure),
        patch.object(J, "compare") as compare,
        pytest.raises(ValueError, match="original capture"),
    ):
        J.run_pair(report, tmp_path)
    compare.assert_not_called()
    original = json.loads((tmp_path / "report.json").read_bytes())
    assert original["ok"] is False and original["pair_verified"] is False
    assert (tmp_path / "first/download.bin").read_bytes() == b"retained partial fixture"


def test_archived_success_cannot_omit_its_end_timestamp(tmp_path):
    (tmp_path / "report.json").write_text(json.dumps({"ok": True, "started_at": J.S.now()}))
    with patch.object(J, "audit_job") as audit, pytest.raises(ValueError, match="original end timestamp"):
        J.replay(tmp_path, tmp_path / "unused.bin")
    audit.assert_not_called()


@pytest.mark.parametrize("fault", ["ok", "pair_verified", "final_audit_complete", "operation", "after_error"])
def test_pair_replay_never_promotes_original_failure(tmp_path, fault):
    report = fixture() | {"ok": True, "pair_verified": True, "final_audit_complete": True}
    for operation in report["operations"]:
        operation["ok"] = True
    if fault == "operation":
        report["operations"][1]["ok"] = False
    else:
        report[fault] = "original failure" if fault == "after_error" else False
    original = json.dumps(report).encode()
    (tmp_path / "report.json").write_bytes(original)
    with patch.object(J.C, "parent_gate") as parent, pytest.raises(ValueError, match="Original pair"):
        J.pair_replay(tmp_path, tmp_path / "unused.bin")
    parent.assert_not_called()
    assert (tmp_path / "report.json").read_bytes() == original
