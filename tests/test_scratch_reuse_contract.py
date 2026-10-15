"""Immutable recipe/source admission only; synthetic sources are not HCI proof."""

import copy
from unittest.mock import patch

import pytest
from test_scratch_reuse_audit import plan_fixture

from rcominote.experiments import scratch_reuse_contract as C


@pytest.mark.parametrize(
    "fault",
    [
        "path",
        "nonce",
        "same",
        "offset",
        "producer",
        "uptime",
        "budget",
        "bool",
        "policy",
        "order",
        "time",
        "state",
    ],
)
def test_plan_mutations_fail_before_any_source_or_io(fault):
    plan = plan_fixture()
    if fault == "path":
        plan["operations"][0]["dump_command"] += "x"
    elif fault == "nonce":
        plan["operations"][0]["nonce"] = "rc;bad"
    elif fault == "same":
        first, second = plan["operations"]
        second.update(nonce=first["nonce"], uptime_command=first["uptime_command"])
    elif fault == "offset":
        plan["operations"][0]["nor_offset"] = 512
    elif fault == "producer":
        plan["operations"][0]["producer"] = "dbg fread spi_flash 512"
    elif fault == "uptime":
        plan["operations"][0]["uptime_command"] = "kernel uptime"
    elif fault == "budget":
        plan["budget"]["sd_writes"] += 1
    elif fault == "bool":
        plan["budget"]["new_files"] = False
    elif fault == "policy":
        plan["startup_policy"] = C.startup.POLICY
    elif fault == "order":
        plan["operations"].reverse()
    elif fault == "time":
        plan["planned_at"] = "2026-10-14T08:00:00+00:00"
    else:
        plan["expected_before"] = {}
    with patch.object(C.sources, "verify") as source, pytest.raises((ValueError, KeyError)):
        C.source_gate(plan, None)
    source.assert_not_called()


def test_source_gate_replays_and_strictly_compares_full_original_summary():
    plan = plan_fixture()
    plan["sources"]["known_parent"] = {"directory": "/synthetic/known"}
    plan["sources"]["state_parent"]["directory"] = "/synthetic/state"
    baseline = b"." * 4096
    with patch.object(
        C.sources, "verify", return_value=(baseline, plan["expected_before"], plan["sources"])
    ) as source:
        assert C.source_gate(plan, None) == baseline
    assert source.call_count == 1
    changed = copy.deepcopy(plan["sources"])
    changed["new_unpinned_claim"] = True
    with (
        patch.object(C.sources, "verify", return_value=(baseline, plan["expected_before"], changed)),
        pytest.raises(ValueError, match="source chain"),
    ):
        C.source_gate(plan, None)


def test_nonce_already_in_baseline_rejected_without_regeneration():
    plan = plan_fixture()
    plan["sources"]["known_parent"] = {"directory": "/synthetic/known"}
    plan["sources"]["state_parent"]["directory"] = "/synthetic/state"
    nonce = plan["operations"][0]["nonce"].encode()
    with (
        patch.object(
            C.sources,
            "verify",
            return_value=(nonce.ljust(4096, b"."), plan["expected_before"], plan["sources"]),
        ),
        pytest.raises(ValueError, match="nonce absent"),
    ):
        C.source_gate(plan, None)
