"""Synthetic full read-only ATT/HCI state proof; historical NOR replay mocked."""

import copy
import json
from unittest.mock import patch

import pytest
from test_controlled_tail_checkpoint import historical_plan as plan_fixture
from test_dual_probe import acl, info, setup
from test_param_window import LINK, capture, remote, update
from test_status_window_job import original_fixture

from rcominote import protocol as P
from rcominote.experiments import preproducer_state_checkpoint as K


def state_fixture():
    plan, prefix = plan_fixture()
    plan["profile"] = K.PROFILE
    report = original_fixture(plan, 0)
    report.update(
        ok=False,
        pair_verified=False,
        final_audit_complete=False,
        error=K.ERROR,
        capture_error=K.ERROR,
        status_events=[],
        listed_count=13,
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
        prepared_at="2026-10-14T10:00:30+00:00",
    )
    for op in report["operations"]:
        op.update(ok=False, sd_write_attempted=False)
        op.pop("live_complete")
    rows = setup()["att_packets"]
    rows[2:2] = [{"direction": d, "hex": h} for d, h in (("rx", "02f700"), ("tx", "03f700"))]
    rows[4:4] = [
        {"direction": d, "hex": h}
        for d, h in (
            ("tx", "10010013000028"),
            ("rx", "1106010008000118"),
            ("tx", "101a001f000028"),
            ("rx", "11061a001f00f0f5"),
        )
    ]
    report["att_packets"] = rows
    for i, row in enumerate(rows):
        row["monotonic_ns"] = i
    report["setup_end"] = len(rows)
    report["gatt_proof"] = K.A.setup(report)
    report["transport"]["update_attempted"] = False
    report["transport"]["link"] = LINK
    report["state_verification"] = K.verify_state(info(), info(), sd_write=False)

    def add(direction, packet):
        report["att_packets"].append(
            {"direction": direction, "hex": packet.hex(), "monotonic_ns": len(report["att_packets"])}
        )

    def identity(key):
        start = len(report["att_packets"])
        state = report[key]
        for command, payload in (
            (P.GET_SERIAL, state["serial"].encode()),
            (P.GET_BIND_INFO, b"\0"),
            (P.GET_DEVICE_INFO, bytes.fromhex(state["device"]["raw"])),
        ):
            add("tx", b"\x52\x22\0" + P.frame(command))
            add("rx", b"\x1b\x24\0" + P.frame(command, payload))
        report[f"{key}_span"] = [start, len(report["att_packets"])]

    identity("before")
    start = len(report["att_packets"])
    add("tx", b"\x52\x22\0" + P.frame(P.GET_FILE_LIST))
    for index in range(13):
        name = f"file{index:04d}".encode().ljust(14, b"\0")
        add("rx", b"\x1b\x24\0" + P.frame(P.GET_FILE_LIST, b"\0" + name + bytes(5)))
    add("rx", b"\x1b\x24\0" + P.frame(P.GET_FILE_LIST, b"\2"))
    report["file_list_span"] = [start, len(report["att_packets"])]
    identity("after")
    return plan, prefix, report, bind_capture(report)


def bind_capture(report, *, extra=False, pending=False):
    wire = [
        (4 if row["direction"] == "tx" else 5, acl(bytes.fromhex(row["hex"]), row["direction"]))
        for row in report["att_packets"]
    ]
    negotiation = remote(24, 40) + [update(36)]
    if extra:
        negotiation += remote(6, 12) + [update(12)]
    if pending:
        negotiation += remote(6, 12)
    raw = capture(wire[:55] + negotiation + wire[55:])
    observed = K.parameters.inspect(raw, link=LINK, final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": K.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = K.dual_hci.bind(report, raw)
    return raw


def test_readonly_failure_has_complete_state_without_nor_promotion():
    plan, _, report, raw = state_fixture()
    original = copy.deepcopy(report)
    result = K.failed_state(report, raw, plan, info())
    assert result["identity_verified"] is True and result["original_job_policy_rejection_preserved"] is True
    assert result["actions_commands"] == result["producer_executions"] == result["sd_write_attempts"] == 0
    assert result["new_raw_nor_coverage_bytes"] == 0
    assert result["startup_state_audit"]["requires_fast_before_normalization"] is True
    assert report == original


@pytest.mark.parametrize(
    "fault",
    [
        "promoted",
        "write",
        "action",
        "target",
        "nonce",
        "identity",
        "state",
        "span",
        "att",
        "hci",
        "extra",
        "pending",
        "summary",
    ],
)
def test_state_audit_rejects_execution_source_changes_or_incomplete_proof(fault):
    plan, _, report, raw = state_fixture()
    if fault == "promoted":
        report["ok"] = True
    elif fault == "write":
        report["operations"][0]["sd_write_attempted"] = True
    elif fault == "action":
        report["operations"][0]["actions_start"] = 55
    elif fault == "target":
        report["operations"][0]["producer"] = "dbg fread spi_flash 0x2800"
    elif fault == "nonce":
        plan["slots"][0]["names"][0] = "rcffffffffff"
    elif fault == "identity":
        report["att_packets"][-1]["hex"] = "1b2400" + P.frame(P.GET_DEVICE_INFO, bytes(52)).hex()
        raw = bind_capture(report)
    elif fault == "state":
        report["after"] = info(1)
    elif fault == "span":
        report["after_span"][0] -= 1
    elif fault == "att":
        report["att_packets"].pop()
    elif fault == "hci":
        raw = raw[:-1]
    elif fault == "extra":
        raw = bind_capture(report, extra=True)
    elif fault == "pending":
        raw = bind_capture(report, pending=True)
    elif fault == "summary":
        report["state_verification"] = {}
    with pytest.raises(ValueError):
        K.failed_state(report, raw, plan, info())


def synthetic_checkpoint(root, monkeypatch):
    plan, prefix, report, raw = state_fixture()
    for slot in plan["slots"]:
        for name in ("first", "second"):
            (root / slot["directory"] / name).mkdir(parents=True)
    (root / "2a00/session.btsnoop").write_bytes(raw)
    K.coverage.W.S.save(root / "2a00/report.json", report)
    K.coverage.W.S.save(root / "job-plan.json", plan)
    job = {
        "profile": K.PROFILE,
        "ok": False,
        "error": K.ERROR,
        "active_slot": "2a00",
        "completed": [],
        "plan": K.J.reference(root, root / "job-plan.json"),
        "started_at": "2026-10-14T10:02:00+00:00",
        "ended_at": report["ended_at"],
    }
    K.coverage.W.S.save(root / "report.json", job)
    monkeypatch.setattr(K, "PINS", {name: K.A.sha((root / name).read_bytes()) for name in K.PINS})
    return plan, prefix


def test_latest_state_checkpoint_keeps_coverage_anchor_and_failed_flags(tmp_path, monkeypatch):
    plan, prefix = synthetic_checkpoint(tmp_path, monkeypatch)
    with patch.object(K.coverage, "verify", return_value=(prefix, info(), plan["checkpoint"])):
        actual, state, summary = K.verify(tmp_path, tmp_path)
    assert actual == prefix and len(actual) == 2560 and state == info()
    assert summary["coverage_anchor"] == plan["checkpoint"] and summary["new_raw_nor_coverage_bytes"] == 0
    assert summary["original_job_ok"] is summary["original_failed_pair_verified"] is False
    assert {n for slot in plan["slots"] for n in slot["names"]} <= set(summary["prior_names"])


@pytest.mark.parametrize("fault", ["pin", "anchor", "output", "later", "chronology"])
def test_checkpoint_rejects_changed_pins_anchor_outputs_or_time(tmp_path, monkeypatch, fault):
    plan, prefix = synthetic_checkpoint(tmp_path, monkeypatch)
    anchor = copy.deepcopy(plan["checkpoint"])
    if fault == "pin":
        (tmp_path / "2a00/report.json").write_text("{}")
    elif fault == "anchor":
        anchor["latest_info"] = info(1)
    elif fault == "output":
        (tmp_path / "fw1_boot.bin").write_bytes(bytes(4096))
    elif fault == "later":
        (tmp_path / "2c00/first/payload").write_bytes(b"unexpected")
    elif fault == "chronology":
        path = tmp_path / "2a00/report.json"
        report = json.loads(path.read_bytes())
        report["started_at"] = "2026-10-14T09:00:00+00:00"
        path.write_text(json.dumps(report))
        K.PINS["2a00/report.json"] = K.A.sha(path.read_bytes())
    with patch.object(K.coverage, "verify", return_value=(prefix, info(), anchor)), pytest.raises(ValueError):
        K.verify(tmp_path, tmp_path)
