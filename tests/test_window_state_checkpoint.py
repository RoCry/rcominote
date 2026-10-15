"""Synthetic checkpoint linkage and real byte-audit tests; no private captures.

The state fixture has real synthetic ATT/Actions/HCI bytes and six complete
parameter transactions. Parent NOR replay is explicitly mocked only in the
job-level assembly fixture; its bytes never claim actual device coverage.
"""

import copy
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from test_dual_probe import acl, setup
from test_param_window import LINK, STATUS, capture, command, update
from test_sd_nor_probe import attach_actions, info
from test_window_nor_contract import fixture as pair_fixture
from test_window_nor_job import original_fixture, plan_fixture

from rcominote import protocol as P
from rcominote.experiments import window_state_checkpoint as K


def state_fixture():
    report = pair_fixture(0x2800) | setup()
    report.update(
        ok=False,
        pair_verified=False,
        final_audit_complete=False,
        error=K.GAP_ERROR,
        final_evidence_error=K.GAP_ERROR,
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
        before=info(),
        after=info(1),
        listed_count=0,
    )
    report["transport"]["link"] = LINK

    def add(direction, packet):
        report["att_packets"].append(
            {"direction": direction, "hex": packet.hex(), "monotonic_ns": len(report["att_packets"])}
        )

    def identity(owner, key):
        start = len(report["att_packets"])
        state = owner[key]
        for cmd, payload in (
            (P.GET_SERIAL, state["serial"].encode()),
            (P.GET_BIND_INFO, b"\0"),
            (P.GET_DEVICE_INFO, bytes.fromhex(state["device"]["raw"])),
        ):
            add("tx", b"\x52\x22\0" + P.frame(cmd))
            add("rx", b"\x1b\x24\0" + P.frame(cmd, payload))
        owner[f"{key}_span"] = [start, len(report["att_packets"])]

    identity(report, "before")
    start = len(report["att_packets"])
    add("tx", b"\x52\x22\0" + P.frame(P.GET_FILE_LIST))
    add("rx", b"\x1b\x24\0" + P.frame(P.GET_FILE_LIST, b"\x02"))
    report["file_list_span"] = [start, len(report["att_packets"])]
    state = report["before"]
    for index, op in enumerate(report["operations"]):
        producer = op["producer"]
        attach_actions(op, producer=True)
        op["producer"] = producer
        op["writes"][2]["hex"] = K.W.U.probe.console_packet(producer).hex()
        rows = op.pop("att_packets")[8:]
        rows[6]["hex"] = "121600" + op["writes"][2]["hex"]
        op.update(
            ok=False,
            sd_write_attempted=True,
            live_complete=True,
            barrier_complete=True,
            before=state,
            after=info(index),
            actions_start=len(report["att_packets"]),
        )
        for row in rows:
            add(row["direction"], bytes.fromhex(row["hex"]))
        op["actions_end"] = len(report["att_packets"])
        op["actions_verification"] = K.A.actions(report, op)
        if index:
            raw_info = bytes.fromhex(op["after"]["device"]["raw"])
            status = bytes(
                (
                    raw_info[8],
                    raw_info[9],
                    raw_info[14],
                    raw_info[15],
                    0,
                    raw_info[39],
                    raw_info[40],
                    raw_info[16],
                    raw_info[41],
                    raw_info[42],
                    1,
                )
            ) + bytes(9)
            add("rx", b"\x1b\x24\0" + P.frame(0x0F, status))
        op["download_start"] = len(report["att_packets"])
        # Download validity is deliberately outside the failed-state claim.
        add("rx", b"\x1b\x2a\0synthetic retained download")
        op["download_end"] = len(report["att_packets"])
        identity(op, "after")
        op["verified_end"] = len(report["att_packets"])
        op["state_verification"] = K.verify_state(state, op["after"], sd_write=True)
        state = op["after"]
    identity(report, "after")
    report["state_verification"] = K.verify_state(state, report["after"], sd_write=False)
    return report, bind_capture(report)


def bind_capture(report, *, pending=False):
    parameters = [row for _ in range(6) for row in (command(), STATUS, update())]
    if pending:
        parameters.append(command())
    hci_rows = [
        (4 if row["direction"] == "tx" else 5, acl(bytes.fromhex(row["hex"]), row["direction"]))
        for row in report["att_packets"]
    ]
    raw = capture(parameters + hci_rows)
    observed = K.parameters.inspect(raw, link=LINK, final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": K.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = K.dual_hci.bind(report, raw)
    return raw


def test_failed_state_proves_only_identity_and_bounded_capacity_without_promotion():
    report, raw = state_fixture()
    original = copy.deepcopy(report)
    result = K.failed_state(report, raw)
    assert result["identity_verified"] is True
    assert result["attempted_fixed_sd_writes"] == 2
    assert result["parameter_transactions"] == 6 and result["pending_transactions"] == 0
    assert [step["free_capacity_decrease"] for step in result["per_write_state"]] == [0, 1]
    assert result["coverage_bytes"] == 0 and result["original_nor_pair_verified"] is False
    assert report == original


@pytest.mark.parametrize(
    "key", ["ok", "pair_verified", "final_audit_complete", "error", "final_evidence_error"]
)
def test_failed_state_rejects_flag_promotion_or_changed_failure(key):
    report, raw = state_fixture()
    report[key] = True if key in ("ok", "pair_verified", "final_audit_complete") else "other failure"
    with pytest.raises(ValueError, match="original failed2800"):
        K.failed_state(report, raw)


@pytest.mark.parametrize(
    "fault", ["identity", "capacity", "action", "barrier", "hci", "parameters", "gap", "target"]
)
def test_failed_state_requires_actual_identity_actions_hci_and_bounded_state(fault):
    report, raw = state_fixture()
    if fault == "identity":
        report["att_packets"][report["after_span"][0]]["hex"] = "522200" + P.frame(P.GET_SERIAL + 1).hex()
        raw = bind_capture(report)
    elif fault == "capacity":
        report["operations"][0]["after"] = info(2)
    elif fault == "action":
        report["operations"][0]["writes"][0]["hex"] = "00"
    elif fault == "barrier":
        report["operations"][1]["barrier_complete"] = False
    elif fault == "hci":
        raw = raw[:-1]
    elif fault == "parameters":
        with (
            patch.object(K.parameters, "inspect", return_value={"transactions": [None] * 5}),
            pytest.raises(ValueError, match="parameter evidence"),
        ):
            K.failed_state(report, raw)
        return
    elif fault == "gap":
        report["operations"][1]["download_start"] += 1
    else:
        report["operations"][0]["producer"] = "dbg fread spi_flash 0x2600"
    with pytest.raises(ValueError):
        K.failed_state(report, raw)


def test_capacity_change_is_rejected_after_independent_actual_identity_audit():
    report, raw = state_fixture()
    op = report["operations"][0]
    op["after"] = info(2)
    report["att_packets"][op["after_span"][1] - 1]["hex"] = (
        b"\x1b\x24\0" + P.frame(P.GET_DEVICE_INFO, bytes.fromhex(op["after"]["device"]["raw"]))
    ).hex()
    raw = bind_capture(report)
    with pytest.raises(ValueError, match="bounded SD capacity"):
        K.failed_state(report, raw)


def test_pending_parameter_transaction_rejects_even_with_six_complete_transactions():
    report, _ = state_fixture()
    raw = bind_capture(report, pending=True)
    with pytest.raises(ValueError, match="parameter evidence"):
        K.failed_state(report, raw)


def test_pin_mismatch_stops_before_any_parent_replay(tmp_path):
    (tmp_path / "report.json").write_bytes(b"{}")
    with patch.object(K.W, "progress_gate") as parent, pytest.raises(ValueError, match="Pinned"):
        K.verify(tmp_path, tmp_path)
    parent.assert_not_called()


@pytest.mark.parametrize("fault", ["target", "nonce", "parent", "prestate", "proof", "time"])
def test_slot_is_bound_to_original_plan_and_chronological_predecessor(fault):
    plan = plan_fixture()
    report = original_fixture(plan, 0)
    previous = {"after": info(), "ended_at": "2026-10-14T10:00:00+00:00"}
    if fault == "target":
        report["nor_offset"] = 0x2800
    elif fault == "nonce":
        plan["slots"][0]["names"][0] = "rcabcdef1234"
    elif fault == "parent":
        report["window_parent"] = report["window_parent"] | {"directory": "/changed"}
    elif fault == "prestate":
        previous["after"] = info(1)
    elif fault == "proof":
        report["predecessor_state_verification"] = {}
    else:
        previous["ended_at"] = "2026-10-14T10:05:00+00:00"
    with pytest.raises(ValueError):
        K.bind_slot(report, plan["slots"][0], plan, previous)


def synthetic_job(tmp_path, monkeypatch):
    plan = plan_fixture()
    blocks = [bytes([i]) * 512 for i in range(4)]
    for key, offset, block in (("parent", 0x2200, blocks[1]), ("progress_parent", 0x2400, blocks[2])):
        directory = tmp_path / key
        (directory / "first").mkdir(parents=True)
        (directory / "first/sector.bin").write_bytes(block)
        plan[key]["directory"] = str(directory)
        plan[key]["verification"] = {"nor_range": [offset, offset + 512], "sha256": K.A.sha(block)}
    good = original_fixture(plan, 0)
    failed = original_fixture(plan, 1) | {"ok": False, "after": info(1)}
    failed["expected_before"] = good["after"]
    original2400 = {
        "after": info(),
        "ended_at": "2026-10-14T10:00:00+00:00",
        "parent": plan["parent"],
        "window_parent": plan["window_parent"],
    }
    verification = {"nor_range": [0x2600, 0x2800], "sha256": K.A.sha(blocks[3])}
    for name, report, block in (("2600", good, blocks[3]), ("2800", failed, bytes([99]) * 512)):
        (tmp_path / name / "first").mkdir(parents=True)
        (tmp_path / name / "first/sector.bin").write_bytes(block)
        (tmp_path / name / "report.json").write_text(json.dumps(report))
        (tmp_path / name / "session.btsnoop").write_bytes(name.encode())
        monkeypatch.setattr(K, f"REPORT{name}_SHA", K.A.sha((tmp_path / name / "report.json").read_bytes()))
        monkeypatch.setattr(K, f"HCI{name}_SHA", K.A.sha(name.encode()))
    (tmp_path / "job-plan.json").write_text(json.dumps(plan))
    job = {
        "profile": K.W.PROFILE,
        "ok": False,
        "error": K.GAP_ERROR,
        "active_slot": "2800",
        "plan": K.J.reference(tmp_path, tmp_path / "job-plan.json"),
        "started_at": "2026-10-14T10:02:00+00:00",
        "ended_at": failed["ended_at"],
        "completed": [
            {"report": K.J.reference(tmp_path, tmp_path / "2600/report.json"), "verification": verification}
        ],
    }
    checkpoint = {
        k: ("2600" if k == "active_slot" else v) for k, v in job.items() if k not in ("error", "ended_at")
    }
    (tmp_path / "checkpoint-2600.json").write_text(json.dumps(checkpoint))
    (tmp_path / "report.json").write_text(json.dumps(job))
    monkeypatch.setattr(K, "JOB_SHA", K.A.sha((tmp_path / "report.json").read_bytes()))
    stack = ExitStack()
    stack.enter_context(
        patch.object(K.prefix_source, "verify", return_value=(blocks[0], plan["prefix_evidence"]))
    )
    stack.enter_context(
        patch.object(K.W, "progress_gate", return_value=(plan["progress_parent"], original2400))
    )
    replay = stack.enter_context(patch.object(K.N, "replay", return_value=verification))
    stack.enter_context(patch.object(K, "failed_state", return_value={"coverage_bytes": 0}))
    stack.enter_context(patch.object(K, "prior_names", return_value=plan["slots"][0]["names"]))
    return stack, plan, blocks, replay


def test_four_source_assembly_never_uses_failed2800_sector(tmp_path, monkeypatch):
    stack, plan, blocks, replay = synthetic_job(tmp_path, monkeypatch)
    with stack:
        prefix, state, summary = K.verify(tmp_path, tmp_path / "unused-image")
    assert prefix == b"".join(blocks) and len(prefix) == 2048
    assert state == info(1) and summary["verified_prefix"] == [0x2000, 0x2800]
    assert summary["parent"] == plan["parent"] and summary["original_failed_pair_verified"] is False
    assert [item["nor_range"] for item in summary["coverage_sources"]] == [
        [0x2000, 0x2200],
        [0x2200, 0x2400],
        [0x2400, 0x2600],
        [0x2600, 0x2800],
    ]
    replay.assert_called_once_with(tmp_path / "2600", tmp_path / "unused-image")


@pytest.mark.parametrize("fault", ["source", "plan", "checkpoint", "provenance"])
def test_changed_source_or_immutable_provenance_blocks_checkpoint(tmp_path, monkeypatch, fault):
    stack, plan, _, _ = synthetic_job(tmp_path, monkeypatch)
    if fault == "source":
        (Path(plan["parent"]["directory"]) / "first/sector.bin").write_bytes(bytes(512))
    elif fault == "plan":
        (tmp_path / "job-plan.json").write_text("{}")
    elif fault == "checkpoint":
        (tmp_path / "checkpoint-2600.json").write_text("{}")
    else:
        original = {
            "after": info(),
            "ended_at": "2026-10-14T10:00:00+00:00",
            "parent": {},
            "window_parent": plan["window_parent"],
        }
        stack.enter_context(
            patch.object(K.W, "progress_gate", return_value=(plan["progress_parent"], original))
        )
    with stack, pytest.raises(ValueError):
        K.verify(tmp_path, tmp_path)
