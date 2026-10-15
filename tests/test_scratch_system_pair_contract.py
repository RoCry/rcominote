"""Synthetic full nine-transaction unknown pair; no mapped/raw content oracle."""

import copy
import struct
from unittest.mock import patch

import pytest
import test_scratch_reuse_audit as old
from test_hci_interval import record
from test_nor_freshness import place
from test_param_window import fragment
from test_scratch_reuse_parser import NONCE, OTHER, SECTOR, chain

from rcominote.experiments import scratch_system_pair_contract as C
from rcominote.log_probe import ACK
from rcominote.log_stream import Stream


def fixture(directory, *, different=False, with_f0=False):
    report, oldplan, baseline = old.fixture(directory)
    parent = {
        "directory": "/synthetic/latest4200",
        "ended_at": "2026-10-14T09:00:00+00:00",
        "latest_info": report["before"],
        "prior_names": [C.F.NAME, "rc8f8e3060d3", "rc15e8c0feb9", "rce9a22fc609"],
        "original_failed_retained": True,
        "unknown_raw_oracle": False,
    }
    slots = []
    for label, nonce in (("first", NONCE), ("second", OTHER)):
        slots.append(
            {
                "operation_id": label,
                "name": C.F.NAME,
                "nonce": nonce,
                "nor_offset": C.OFFSET,
                "uptime_command": f"kernel uptime {nonce}",
                "producer": "dbg fread spi_flash 0x24200",
                "dump_command": C.F.DUMP,
            }
        )
    plan = {
        "profile": C.PROFILE,
        "name": C.F.NAME,
        "nor_offset": C.OFFSET,
        "planned_at": oldplan["planned_at"],
        "parent": parent,
        "expected_before": report["before"],
        "budget": C.BUDGET.copy(),
        "actions_policy": C.ACTIONS_POLICY,
        "stage_timeout_scope": C.STAGE_SCOPE,
        "startup_policy": C.startup.LEGACY_POLICY,
        "status_event_policy": C.E.POLICY,
        "operations": slots,
        "independent_oracle": False,
    }
    oldrows = copy.deepcopy(report["att_packets"])
    current = [place(chain(NONCE, C.OFFSET), 100)]
    current.append(
        place(
            chain(OTHER, C.OFFSET, bytes(reversed(SECTOR)) if different else SECTOR), 2400, initial=current[0]
        )
    )
    discarded = set()
    for slot, op, data in zip(slots, report["operations"], current, strict=True):
        op.update(slot)
        expected, number, at = C.recipe(op), 0, 0
        for index in range(op["actions_start"], op["actions_end"]):
            row = oldrows[index]
            packet = bytes.fromhex(row["hex"])
            if row["direction"] == "tx":
                row["hex"] = (b"\x12\x16\0" + expected[number]).hex()
                number += 1
            elif not with_f0 and packet[:3] == b"\x1b\x18\0" and packet[3:] not in (ACK, old.END):
                discarded.add(index)
        for index in range(op["download_start"], op["download_end"]):
            row = oldrows[index]
            packet = bytes.fromhex(row["hex"])
            if packet[:3] == b"\x1b\x2a\0":
                size = len(packet) - 3
                row["hex"] = (packet[:3] + data[at : at + size]).hex()
                at += size
        assert at == 4096
        op["writes"] = [{"hex": p.hex(), "att_write_confirmed": True} for p in expected]
        op["notifications"] = [
            row["hex"][6:]
            for i, row in enumerate(oldrows)
            if op["actions_start"] <= i < op["actions_end"]
            and i not in discarded
            and row["hex"].startswith("1b1800")
        ]
        stream = Stream()
        for value in op["notifications"]:
            stream.feed(bytes.fromhex(value))
        op["frames"] = stream.frames
        op.update(download_sha256=C.A.sha(data), producer_attempted=True)
        (directory / op["operation_id"] / "download.bin").write_bytes(data)
    raw = (directory / "session.btsnoop").read_bytes()
    selected = [i for i in range(len(oldrows)) if i not in discarded]
    mapping = {before: after for after, before in enumerate(selected)}
    rows, index = [], 0
    for _number, opcode, stamp, packet in C.P.records(raw, report["hci_capture"]["records"]):
        if opcode in (4, 5) and int.from_bytes(packet[6:8], "little") == 4:
            row = oldrows[index]
            discard = index in discarded
            index += 1
            if discard:
                continue
            pdu = bytes.fromhex(row["hex"])
            opcode, packet = fragment(struct.pack("<HH", len(pdu), 4) + pdu, direction=row["direction"])
        rows.append((opcode, stamp, packet))
    raw = C.P.H.HEADER + b"".join(record(packet, opcode, stamp=stamp) for opcode, stamp, packet in rows)
    (directory / "session.btsnoop").write_bytes(raw)
    report["att_packets"] = [oldrows[i] for i in selected]
    report.update(
        profile=C.PROFILE,
        budget=C.BUDGET.copy(),
        actions_policy=C.ACTIONS_POLICY,
        stage_timeout_scope=C.STAGE_SCOPE,
    )

    def span(value):
        return [mapping[value[0]], mapping[value[1] - 1] + 1]

    report["after_span"] = span(report["after_span"])
    for op in (report["baseline"], *report["operations"]):
        op["download_start"], op["download_end"] = span([op["download_start"], op["download_end"]])
        op["after_span"] = span(op["after_span"])
        op["verified_end"] = op["after_span"][1]
        if "actions_start" in op:
            op["actions_start"], op["actions_end"] = span([op["actions_start"], op["actions_end"]])
        data = (directory / op["operation_id"] / "download.bin").read_bytes()
        op["download_verification"] = C.A.download(report, op, data, minimum_start=report["setup_end"])
    observed = C.P.inspect(raw, link=report["transport"]["link"], final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": C.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = C.dual_hci.bind(report, raw)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    tx = observed["transactions"]
    report.update(startup_settlement=tx[0], startup_classification=C.startup.classify(tx[0]))
    report["baseline"].update(normalization=tx[1], slow_settlement=tx[2])
    previous, previous_tx = baseline, tx[2]
    wire = C.common.wire_positions(report, raw)
    for index, op in enumerate(report["operations"]):
        fast, normal, slow = tx[3 + 3 * index : 6 + 3 * index]
        op.update(pre_download_fast=[fast], normalization=normal, slow_settlement=slow)
        op["activity_fast_verification"] = C.W.default_activity_fast(report, op, previous_tx, fast, wire)
        op["actions_verification"] = C.actions(report, op)
        op["verification"] = C.payload(op, current[index], previous)
        (directory / op["operation_id"] / "sector.bin").write_bytes(
            bytes.fromhex(op["verification"]["sector_hex"])
        )
        previous, previous_tx = current[index], slow
    return report, plan, baseline


@pytest.mark.parametrize("with_f0", [False, True])
def test_full_independent_pair_requires_three_downloads_and_nine_transactions(tmp_path, with_f0):
    report, plan, baseline = fixture(tmp_path, with_f0=with_f0)
    proof = C.validate(report, tmp_path, plan, baseline)
    assert proof["pair_verified"] and proof["bytes"] == proof["new_raw_nor_coverage_bytes"] == 512
    assert proof["parameter_transactions"] == 9 and proof["downloads"] == 3
    assert proof["independent_oracle"] is False
    assert [item["nonce"] for item in proof["observations"]] == [NONCE, OTHER]
    assert (
        report["operations"][1]["verification"]["freshness"]["previous_ring_sha256"]
        == report["operations"][0]["download_sha256"]
    )


def test_two_complete_different_sectors_reject_after_full_final_identity(tmp_path):
    report, plan, baseline = fixture(tmp_path, different=True)
    with pytest.raises(ValueError, match="independent complete unknown24200 sectors differ"):
        C.validate(report, tmp_path, plan, baseline)
    assert report["after"] == report["operations"][1]["after"]


@pytest.mark.parametrize(
    "fault",
    [
        "offset",
        "same-nonce",
        "prior-nonce",
        "order",
        "missing-slot",
        "path",
        "budget",
        "bool",
        "oracle",
        "policy",
    ],
)
def test_fixed_plan_and_independent_nonce_admission_reject_mutations(tmp_path, fault):
    _report, plan, _baseline = fixture(tmp_path)
    if fault == "offset":
        plan["nor_offset"] = 0x24400
    elif fault == "same-nonce":
        plan["operations"][1].update(nonce=NONCE, uptime_command=f"kernel uptime {NONCE}")
    elif fault == "prior-nonce":
        plan["parent"]["prior_names"].append(OTHER)
    elif fault == "order":
        plan["operations"].reverse()
    elif fault == "missing-slot":
        plan["operations"].pop()
    elif fault == "path":
        plan["operations"][0]["dump_command"] += "x"
    elif fault == "budget":
        plan["budget"]["producers"] = 3
    elif fault == "bool":
        plan["budget"]["new_files"] = False
    elif fault == "oracle":
        plan["independent_oracle"] = True
    else:
        plan["startup_policy"] = C.startup.POLICY
    with patch.object(C.sources, "verify") as source, pytest.raises(ValueError):
        C.source_gate(plan, None)
    source.assert_not_called()


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "short",
        "reuse-first",
        "wrong-previous",
        "source",
        "proof",
        "state",
        "final",
        "flag",
        "missing-fast",
        "pending",
        "actions",
    ],
)
def test_equal_candidates_cannot_bypass_original_data_wire_or_final_gates(tmp_path, fault):
    report, plan, baseline = fixture(tmp_path)
    first, second = report["operations"]
    if fault == "missing":
        report["operations"].pop()
    elif fault == "short":
        (tmp_path / "second/download.bin").write_bytes(b"short")
    elif fault == "reuse-first":
        (tmp_path / "second/download.bin").write_bytes((tmp_path / "first/download.bin").read_bytes())
    elif fault == "wrong-previous":
        second["verification"]["freshness"]["previous_ring_sha256"] = C.A.sha(baseline)
    elif fault == "source":
        baseline = bytes(4096)
    elif fault == "proof":
        second["verification"]["freshness"]["nonce_span"][0] += 1
    elif fault == "state":
        second["before"] = {}
    elif fault == "final":
        report["state_verification"] = {}
    elif fault == "flag":
        second["live_complete"] = False
    elif fault == "missing-fast":
        second["pre_download_fast"] = []
    elif fault == "pending":
        second["notifications"].append("1d")
    else:
        first["frames"].pop()
    with pytest.raises((ValueError, KeyError)):
        C.validate(report, tmp_path, plan, baseline)


def test_pair_audit_does_not_change_original_flags_or_receipts(tmp_path):
    report, plan, baseline = fixture(tmp_path)
    before = copy.deepcopy((report, plan))
    C.validate(report, tmp_path, plan, baseline)
    assert (report, plan) == before
