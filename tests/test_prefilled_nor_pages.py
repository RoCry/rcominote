"""Finite prefilled unknown plans and synthetic full15-transaction page fixtures."""

import struct
from unittest.mock import patch

import pytest
from test_nor_freshness import place
from test_paired_nor_audit import replace_download
from test_paired_nor_control import rewrite_capture
from test_param_window import fragment
from test_prefilled_nor_control import RAM
from test_prefilled_nor_control import fixture as known_fixture
from test_scratch_reuse_parser import SECTOR, chain

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_nor_pages as N


@patch.object(P, "RAM_SHA", A.A.sha(RAM))
def fixture(root, offset=0x1EC200):
    directory = root / f"page0-{offset:06x}"
    actual, known, baseline, _oracles = known_fixture(directory)
    known["parent"]["profile"] = P.PROFILE_V2
    with (
        patch.object(C, "parent_gate", return_value=(baseline, known["expected_before"], known["parent"])),
        patch.object(P, "ram_source", return_value=(RAM, known["ram_oracle"])),
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(C.S, "now", return_value=known["planned_at"]),
    ):
        plan, _previous = N.prepare(None, root, [offset])
    page = C.page_plan(plan, 0, plan["expected_before"], plan["parent"]["ended_at"])
    for key in (*P.fields(known),):
        actual.pop(key, None)
    actual.update({key: page[key] for key in C.fields(page)})
    for slot, op in zip(page["operations"], actual["operations"], strict=True):
        op.update(slot)
        if op["kind"] == "nor":
            tx = [
                row
                for row in actual["att_packets"][op["actions_start"] : op["actions_end"]]
                if row["direction"] == "tx"
            ]
            for row, packet in zip(tx, P.recipe(op), strict=True):
                row["hex"] = (b"\x12\x16\0" + packet).hex()
            op["writes"] = [{"hex": packet.hex(), "att_write_confirmed": True} for packet in P.recipe(op)]
    old = (directory / "session.btsnoop").read_bytes()
    records, index = [], 0
    for _number, opcode, stamp, packet in A.P.records(old, actual["hci_capture"]["records"]):
        if opcode in (4, 5) and int.from_bytes(packet[6:8], "little") == 4:
            row = actual["att_packets"][index]
            index += 1
            pdu = bytes.fromhex(row["hex"])
            opcode, packet = fragment(struct.pack("<HH", len(pdu), 4) + pdu, direction=row["direction"])
        records.append((opcode, stamp, packet))
    rewrite_capture(directory, actual, records)
    history, previous = baseline, baseline
    for op in actual["operations"]:
        if op["kind"] == "prefill":
            data = RAM
        else:
            data = place(
                chain(op["nonce"], offset, SECTOR),
                300 if op["operation_id"] == "first" else 2600,
                initial=history,
            )
        replace_download(actual, directory, op["operation_id"], data)
        op["actions_verification"] = P.actions(actual, op)
        with patch.object(P, "RAM_SHA", A.A.sha(RAM)):
            op["verification"] = N.content(op, data, previous, RAM, page, history)
        if op["kind"] == "nor":
            (directory / op["operation_id"] / "sector.bin").write_bytes(SECTOR)
            history = data
        previous = data
    C.S.save(root / "plan.json", plan)
    actual["plan"] = C.J.reference(root, root / "plan.json")
    return actual, plan, page, baseline


def validate(root, actual, page, baseline):
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, page["ram_oracle"])),
    ):
        return N.validate(actual, root / f"page{page['page_index']}-{page['nor_offset']:06x}", page, baseline)


@pytest.mark.parametrize("offsets", [[], [True], [1], [-512], [0x400000], [0, 0], list(range(0, 2560, 512))])
def test_bad_finite_targets_reject_before_parent_admission(offsets):
    with patch.object(C, "parent_gate") as parent, pytest.raises(ValueError):
        N.prepare(None, None, offsets)
    parent.assert_not_called()


def test_complete_unknown_pair_has_no_nor_oracle_and_real_distinct_current_rings(tmp_path):
    actual, plan, page, baseline = fixture(tmp_path)
    proof = validate(tmp_path, actual, page, baseline)
    assert proof["pair_verified"] and proof["sha256"] == A.A.sha(SECTOR)
    assert proof["downloads"] == 5 and proof["parameter_transactions"] == 15
    assert proof["producers"] == proof["ram_exports"] == 2
    assert proof["independent_oracle"] is False and "oracles" not in plan
    assert len({row["ring_sha256"] for row in proof["observations"]}) == 2
    assert all(
        op["verification"]["freshness"]["difference_proven_written_prefix_bytes"] == 4096
        for op in actual["operations"]
        if op["kind"] == "nor"
    )
    assert [op["actions_verification"]["acks"] for op in actual["operations"]] == [4, 6, 4, 6]


@pytest.mark.parametrize(
    "fault",
    [
        "target",
        "nonce",
        "history",
        "budget-bool",
        "page-bool",
        "policy",
        "oracle",
        "ram",
        "order",
        "path",
        "kind",
    ],
)
def test_plan_tampering_fails_before_source_replay(tmp_path, fault):
    _actual, plan, _page, _baseline = fixture(tmp_path)
    if fault == "target":
        plan["pages"][0]["operations"][1]["nor_offset"] += 512
    elif fault == "nonce":
        plan["pages"][0]["operations"][3].update(
            nonce=C.nonces(plan)[0], uptime_command="kernel uptime " + C.nonces(plan)[0]
        )
    elif fault == "history":
        plan["parent"]["prior_names"].append(C.nonces(plan)[0])
    elif fault == "budget-bool":
        plan["budget"]["new_files"] = False
    elif fault == "page-bool":
        plan["page_budget"]["connections"] = True
    elif fault == "policy":
        plan["content_policy"] = C.F.FORMAT_POLICY
    elif fault == "oracle":
        plan["oracles"] = {"mapped": "not raw evidence"}
    elif fault == "ram":
        plan["ram_oracle"]["sha256"] = "0" * 64
    elif fault == "order":
        plan["pages"][0]["operations"].reverse()
    elif fault == "path":
        plan["pages"][0]["directory"] = "../escape"
    else:
        plan["pages"][0]["operations"][1]["kind"] = "prefill"
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(C, "parent_gate") as parent,
        pytest.raises(ValueError),
    ):
        C.source_gate(plan, None)
    parent.assert_not_called()


@pytest.mark.parametrize(
    "profile",
    [
        C.legacy.PROFILE,
        C.PROFILE_V3,
        P.PROFILE,
        C.CHECKPOINT_PROFILE,
        C.CONTENT_CHECKPOINT_PROFILE,
        C.RECOVERY_PROFILE,
    ],
)
def test_direct_unproven_capability_parent_cannot_start_unknown_prefilled_job(tmp_path, profile):
    _actual, plan, _page, _baseline = fixture(tmp_path)
    plan["parent"]["profile"] = profile
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(C, "parent_gate") as parent,
        pytest.raises(ValueError, match="successful knownV2"),
    ):
        C.source_gate(plan, None)
    parent.assert_not_called()


def test_max_four_finite_pages_all_names_preplanned_and_exact_bounded_cost(tmp_path):
    _actual, old, _page, baseline = fixture(tmp_path)
    offsets = [0, 0x1EC200, 0x24C00, 0x3FFE00]
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, old["ram_oracle"])),
        patch.object(C, "parent_gate", return_value=(baseline, old["expected_before"], old["parent"])),
    ):
        plan, previous = N.prepare(None, None, offsets)
        assert C.source_gate(plan, None) == previous == baseline
    assert plan["offsets"] == offsets and len(set(C.nonces(plan))) == 8
    assert plan["budget"] == {
        "connections": 4,
        "downloads": 20,
        "producers": 8,
        "ram_exports": 8,
        "sd_writes": 16,
        "new_files": 0,
        "nor_writes": 0,
        "ram_writes": 0,
        "deletes": 0,
        "parameter_transactions": 60,
        "max_verified_bytes": 2048,
    }
    assert "new_raw_nor_coverage_bytes" not in plan["budget"]


def test_shared_capture_binds_unknown_page_before_scan_and_no_tamper_io(tmp_path):
    import asyncio
    from unittest.mock import AsyncMock

    from rcominote.experiments import paired_nor_runtime as runtime

    actual, job, page, baseline = fixture(tmp_path)
    directory = tmp_path / job["pages"][0]["directory"]
    runtime.save_job(
        tmp_path,
        {
            "profile": job["profile"],
            "budget": job["budget"],
            "plan": actual["plan"],
            "started_at": actual["started_at"],
            "completed": [],
            "ok": False,
        },
    )
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(runtime, "find_device", AsyncMock(side_effect=RuntimeError("scan sentinel"))) as scan,
    ):
        with pytest.raises(RuntimeError, match="scan sentinel"):
            asyncio.run(runtime.capture(actual, page, baseline, directory))
        scan.assert_awaited_once()
        scan.reset_mock()
        actual["operations"][1]["producer"] = "dbg fread spi_flash 0"
        with pytest.raises(ValueError, match="slots differ"):
            asyncio.run(runtime.capture(actual, page, baseline, directory))
        scan.assert_not_called()
