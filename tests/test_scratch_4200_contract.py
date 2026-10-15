"""Synthetic six-transaction wire; strict F0 retention without body requirement."""

import copy
import shutil
import struct

import pytest
import test_scratch_reuse_audit as old
from test_hci_interval import record
from test_nor_freshness import place
from test_scratch_reuse_parser import NONCE, OTHER, SECTOR, chain

from rcominote.experiments import scratch_4200_contract as C
from rcominote.log_probe import ACK
from rcominote.log_stream import Stream


def fixture(directory, *, with_f0=False):
    donor = directory / "donor"
    report, oldplan, _ = old.fixture(donor)
    capture = (donor / "session.btsnoop").read_bytes()
    observed = C.P.inspect(capture, link=report["transport"]["link"], final=True)
    wire = C.common.wire_positions(report, capture)
    first, second = report["operations"]
    selected = list(range(report["file_list_span"][1]))
    selected.extend(range(first["download_start"], first["verified_end"]))
    selected.extend(
        i
        for i in range(second["actions_start"], second["actions_end"])
        if with_f0
        or report["att_packets"][i]["direction"] == "tx"
        or bytes.fromhex(report["att_packets"][i]["hex"]) == b"\x13"
        or bytes.fromhex(report["att_packets"][i]["hex"])[3:] in (ACK, old.END)
    )
    selected.extend(range(second["download_start"], second["verified_end"]))
    selected.extend(range(*report["after_span"]))
    numbers = {number for i in selected for number in range(wire[i][0], wire[i][1] + 1)}
    discard = set()
    for transaction in observed["transactions"][1:4]:
        for key in ("request", "status", "update"):
            discard.add(transaction[key]["record"])
        for key in ("remote_request", "remote_accept"):
            if transaction[key]:
                discard.update(transaction[key]["records"])
    kept = []
    for number, opcode, stamp, packet in C.P.records(capture, report["hci_capture"]["records"]):
        att = opcode in (4, 5) and int.from_bytes(packet[6:8], "little") == 4
        if number not in discard and (not att or number in numbers):
            kept.append((opcode, stamp, packet))
    raw = C.P.H.HEADER + b"".join(record(packet, opcode, stamp=stamp) for opcode, stamp, packet in kept)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "session.btsnoop").write_bytes(raw)
    mapping = {before: after for after, before in enumerate(selected)}

    def span(value):
        return [mapping[value[0]], mapping[value[1] - 1] + 1]

    parent = {
        "directory": "/synthetic/postmortem",
        "ended_at": "2026-10-14T09:00:00+00:00",
        "latest_info": report["before"],
        "prior_names": [C.F.NAME, "rc8f8e3060d3", "rc15e8c0feb9"],
        "original_failed_retained": True,
        "reuse_pair_complete": False,
        "sources": {"oracles": {"4200": {"sha256": C.A.sha(bytes(reversed(SECTOR)))}}},
    }
    operation = copy.deepcopy(second)
    operation.update(operation_id="overwrite", ok=False)
    plan = {
        "profile": C.PROFILE,
        "name": C.F.NAME,
        "planned_at": oldplan["planned_at"],
        "parent": parent,
        "expected_before": report["before"],
        "budget": C.BUDGET.copy(),
        "actions_policy": C.ACTIONS_POLICY,
        "stage_timeout_scope": C.STAGE_SCOPE,
        "startup_policy": C.startup.LEGACY_POLICY,
        "status_event_policy": C.E.POLICY,
        "operation": {
            key: operation[key]
            for key in (
                "operation_id",
                "name",
                "nonce",
                "nor_offset",
                "uptime_command",
                "producer",
                "dump_command",
            )
        },
    }
    warm = {
        key: first[key]
        for key in (
            "name",
            "before",
            "started_at",
            "ended_at",
            "normalization_requested_us",
            "download_start",
            "download_end",
            "download_bytes",
            "received_bytes",
            "download_sha256",
            "after",
            "after_span",
            "verified_end",
        )
    }
    warm.update(
        operation_id="baseline",
        live_complete=True,
        ok=False,
        state_verification=C.verify_state(warm["before"], warm["after"], sd_write=False),
    )
    report.pop("operations")
    report.update(
        profile=C.PROFILE,
        budget=C.BUDGET.copy(),
        actions_policy=C.ACTIONS_POLICY,
        stage_timeout_scope=C.STAGE_SCOPE,
        baseline=warm,
        operation=operation,
        att_packets=[report["att_packets"][i] for i in selected],
    )
    report["after_span"] = span(report["after_span"])
    for stage, label in ((warm, "first"), (operation, "second")):
        stage["download_start"], stage["download_end"] = span(
            [stage["download_start"], stage["download_end"]]
        )
        stage["after_span"] = span(stage["after_span"])
        stage["verified_end"] = stage["after_span"][1]
        target = directory / stage["operation_id"]
        target.mkdir()
        shutil.copyfile(donor / label / "download.bin", target / "download.bin")
        stage["download_verification"] = C.A.download(
            report, stage, (target / "download.bin").read_bytes(), minimum_start=report["setup_end"]
        )
    operation["actions_start"], operation["actions_end"] = span(
        [second["actions_start"], second["actions_end"]]
    )
    if not with_f0:
        operation["notifications"] = [ACK.hex()] * 6 + [old.END.hex()]
        stream = Stream()
        for value in operation["notifications"]:
            stream.feed(bytes.fromhex(value))
        operation["frames"] = stream.frames
    operation["actions_verification"] = C.actions(report, operation)
    observed = C.P.inspect(raw, link=report["transport"]["link"], final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": C.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = C.dual_hci.bind(report, raw)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    tx = observed["transactions"]
    report.update(startup_settlement=tx[0], startup_classification=C.startup.classify(tx[0]))
    warm.update(normalization=tx[1], slow_settlement=tx[2])
    operation.update(pre_download_fast=[tx[3]], normalization=tx[4], slow_settlement=tx[5])
    operation["activity_fast_verification"] = C.W.default_activity_fast(
        report, operation, tx[2], tx[3], C.common.wire_positions(report, raw)
    )
    baseline = (directory / "baseline/download.bin").read_bytes()
    operation["verification"] = C.payload(
        operation, (directory / "overwrite/download.bin").read_bytes(), baseline, plan
    )
    (directory / "overwrite/sector.bin").write_bytes(bytes.fromhex(operation["verification"]["sector_hex"]))
    return report, plan, baseline


@pytest.mark.parametrize("with_f0", [False, True])
def test_complete_six_transactions_accepts_zero_or_retained_f0(tmp_path, with_f0):
    report, plan, baseline = fixture(tmp_path, with_f0=with_f0)
    proof = C.validate(report, tmp_path, plan, baseline)
    assert proof["parameter_transactions"] == 6 and proof["sd_writes"] == 1 and proof["downloads"] == 2
    assert proof["actions"]["f0_frames"] == int(with_f0)
    assert proof["original_trial_ok"] is False and proof["new_raw_nor_coverage_bytes"] == 0


@pytest.mark.parametrize(
    "fault", ["path", "target", "nonce", "prior", "budget", "bool", "policy", "f0-policy", "time"]
)
def test_fixed_plan_and_fresh_nonce_cannot_broaden_scope(tmp_path, fault):
    _report, plan, _baseline = fixture(tmp_path)
    if fault == "path":
        plan["operation"]["dump_command"] += "x"
    elif fault == "target":
        plan["operation"]["nor_offset"] = 0
    elif fault == "nonce":
        plan["operation"]["nonce"] = "not nonce"
    elif fault == "prior":
        plan["parent"]["prior_names"].append(OTHER)
    elif fault == "budget":
        plan["budget"]["sd_writes"] = 2
    elif fault == "bool":
        plan["budget"]["new_files"] = False
    elif fault == "policy":
        plan["startup_policy"] = C.startup.POLICY
    elif fault == "f0-policy":
        plan["actions_policy"] = "skip F0"
    else:
        plan["planned_at"] = "2026-10-14T08:00:00+00:00"
    with pytest.raises(ValueError):
        C.validate_plan(plan)


@pytest.mark.parametrize(
    "fault",
    [
        "baseline",
        "short",
        "oracle",
        "missing-fast",
        "stale-fast",
        "pending-proof",
        "frames",
        "state",
        "flag",
        "producer",
        "close",
        "stage",
    ],
)
def test_saved_material_and_original_wire_receipts_are_not_salvaged(tmp_path, fault):
    report, plan, baseline = fixture(tmp_path)
    op = report["operation"]
    if fault == "baseline":
        baseline = b"." * 4096
    elif fault == "short":
        (tmp_path / "overwrite/download.bin").write_bytes(b"partial")
    elif fault == "oracle":
        plan["parent"]["sources"]["oracles"]["4200"]["sha256"] = "0" * 64
    elif fault == "missing-fast":
        op["pre_download_fast"] = []
    elif fault == "stale-fast":
        op["activity_fast_verification"]["remote_request_first_record"] -= 1
    elif fault == "pending-proof":
        op["notifications"].append("1d")
    elif fault == "frames":
        op["frames"].pop()
    elif fault == "state":
        op["before"] = {}
    elif fault == "flag":
        op["live_complete"] = False
    elif fault == "producer":
        op["producer_attempted"] = False
    elif fault == "close":
        report["disconnect_observed_us"] += 9_000_000
    else:
        report["baseline"]["ended_at"] = "2026-10-14T10:01:40+00:00"
    with pytest.raises((ValueError, KeyError)):
        C.validate(report, tmp_path, plan, baseline)


def test_new_zero_f0_policy_does_not_change_old_failed_validator(tmp_path):
    report, _plan, _baseline = fixture(tmp_path)
    assert C.actions(report, report["operation"])["f0_frames"] == 0
    legacy = report["operation"] | {"operation_id": "second"}
    assert C.A.action_frames(report, legacy, expected=old.V.C.recipe(legacy))["acks"] == 6
    with pytest.raises(ValueError, match="uptime F0"):
        old.V.actions(report, legacy)


def test_wrong_target_retained_bytes_and_old_nonce_never_fill_candidate(tmp_path):
    _report, plan, baseline = fixture(tmp_path)
    op = plan["operation"]
    for ring in (place(chain(OTHER, 0x4200, SECTOR)), place(chain(NONCE, 0x4200, bytes(reversed(SECTOR))))):
        with pytest.raises(ValueError):
            C.payload(op, ring, baseline, plan)


@pytest.mark.parametrize("pending", [False, True])
def test_actual_extra_or_pending_parameter_wire_cannot_hide_after_final_identity(tmp_path, pending):
    from test_param_window import remote, update

    report, plan, baseline = fixture(tmp_path)
    raw = (tmp_path / "session.btsnoop").read_bytes()
    rows = list(C.P.records(raw, report["hci_capture"]["records"]))
    extra = remote(identifier=90) + ([] if pending else [update(12)])
    stamp = rows[-2][2]
    raw = C.P.H.HEADER + b"".join(record(packet, opcode, stamp=time) for _, opcode, time, packet in rows[:-1])
    raw += b"".join(record(packet, opcode, stamp=stamp + i + 1) for i, (opcode, packet) in enumerate(extra))
    raw += record(rows[-1][3], rows[-1][1], stamp=stamp + len(extra) + 1)
    (tmp_path / "session.btsnoop").write_bytes(raw)
    observed = C.P.inspect(raw, link=report["transport"]["link"], final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": C.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = C.dual_hci.bind(report, raw)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    report.update(close_completed_us=stamp + len(extra) + 2, disconnect_observed_us=stamp + len(extra) + 3)
    with pytest.raises(ValueError, match="exactly six"):
        C.validate(report, tmp_path, plan, baseline)


def test_all_actual_f0_fragments_must_remain_in_actions_evidence(tmp_path):
    report, _plan, _baseline = fixture(tmp_path, with_f0=True)
    op = report["operation"]
    op["notifications"] = [ACK.hex()] * 6 + [old.END.hex()]
    with pytest.raises(ValueError, match="Actions evidence"):
        C.actions(report, op)


def test_actual_early_f1_is_not_a_substitute_for_six_acks(tmp_path):
    report, plan, baseline = fixture(tmp_path)
    op = report["operation"]
    for row in report["att_packets"][op["actions_start"] : op["actions_end"]]:
        if row["hex"] == (b"\x1b\x18\0" + ACK).hex():
            row["hex"] = (b"\x1b\x18\0" + old.END).hex()
            break
    refresh_wire(report, tmp_path)
    with pytest.raises(ValueError, match="precedes exact write"):
        C.validate(report, tmp_path, plan, baseline)


def refresh_wire(report, directory):
    from test_param_window import fragment

    capture = (directory / "session.btsnoop").read_bytes()
    rows, index = [], 0
    for _number, opcode, stamp, packet in C.P.records(capture, report["hci_capture"]["records"]):
        if opcode in (4, 5) and int.from_bytes(packet[6:8], "little") == 4:
            row = report["att_packets"][index]
            pdu = bytes.fromhex(row["hex"])
            opcode, packet = fragment(struct.pack("<HH", len(pdu), 4) + pdu, direction=row["direction"])
            index += 1
        rows.append((opcode, stamp, packet))
    raw = C.P.H.HEADER + b"".join(record(packet, opcode, stamp=stamp) for opcode, stamp, packet in rows)
    (directory / "session.btsnoop").write_bytes(raw)
    report["hci_capture"].update(bytes=len(raw), sha256=C.A.sha(raw))
    report["att_hci_binding"] = C.dual_hci.bind(report, raw)
