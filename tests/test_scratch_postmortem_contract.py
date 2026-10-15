"""Synthetic readonly three-transaction original wire; source chain mocked outside."""

import copy
import struct
from unittest.mock import patch

import pytest
from test_dual_probe import setup
from test_hci_interval import connection, event, record
from test_nor_freshness import place
from test_param_window import CONTROL, LINK, STATUS, command, fragment, remote, update
from test_scratch_reuse_parser import SECTOR, chain
from test_sd_nor_probe import info

from rcominote import protocol as P
from rcominote.experiments import scratch_postmortem_contract as C


def plan_fixture():
    parent = {
        "directory": "/synthetic/failed",
        "latest_info": info(),
        "ended_at": "2026-10-14T09:00:00+00:00",
        "name": C.F.NAME,
        "nonce": C.NONCE,
        "nor_offset": 0,
        "original_failed_retained": True,
        "sources": {"oracles": {"boot0": {"sha256": C.A.sha(SECTOR)}}},
    }
    return {
        "profile": C.PROFILE,
        "name": C.F.NAME,
        "nonce": C.NONCE,
        "nor_offset": 0,
        "parent": parent,
        "expected_before": info(),
        "planned_at": "2026-10-14T10:00:00+00:00",
        "budget": C.BUDGET.copy(),
        "stage_timeout_scope": C.STAGE_SCOPE,
        "startup_policy": C.startup.LEGACY_POLICY,
        "status_event_policy": C.E.POLICY,
    }


def fixture(directory, *, fault=None):
    directory.joinpath("retained").mkdir(parents=True)
    plan = plan_fixture()
    report = C.report(plan) | setup()
    report.update(
        transport={"link": LINK},
        status_events=[],
        started_at="2026-10-14T10:01:00+00:00",
        ended_at="2026-10-14T10:01:30+00:00",
        monitor_exit=0,
        monitor_stop={"signal": "SIGINT", "requested": True, "delivery": "sent"},
    )
    rows = [CONTROL, (3, connection())]

    def emit(direction, pdu, *, existing=False):
        if not existing:
            report["att_packets"].append(
                {"direction": direction, "hex": pdu.hex(), "monotonic_ns": len(rows)}
            )
        rows.append(fragment(struct.pack("<HH", len(pdu), 4) + pdu, direction=direction))

    for row in report["att_packets"]:
        emit(row["direction"], bytes.fromhex(row["hex"]), existing=True)

    def identity(owner, key):
        start = len(report["att_packets"])
        for cmd, payload in ((1, b"C261CF0430"), (2, b"\0"), (5, bytes.fromhex(info()["device"]["raw"]))):
            emit("tx", b"\x52\x22\0" + P.frame(cmd))
            emit("rx", b"\x1b\x24\0" + P.frame(cmd, payload))
        owner[key], owner[f"{key}_span"] = info(), [start, len(report["att_packets"])]

    identity(report, "before")
    report["predecessor_state_verification"] = C.verify_state(info(), info(), sd_write=False)
    start = len(report["att_packets"])
    emit("tx", b"\x52\x22\0" + P.frame(10))
    emit("rx", b"\x1b\x24\0" + P.frame(10, b"\2"))
    report.update(file_list_span=[start, len(report["att_packets"])], listed_count=0)
    rows.extend(remote(24, 40) + [update(36)] if fault == "default" else remote() + [update(12)])
    op = report["operation"]
    op.update(
        before=info(),
        live_complete=True,
        started_at="2026-10-14T10:01:10+00:00",
        ended_at="2026-10-14T10:01:20+00:00",
        normalization_requested_us=1000 + len(rows) - 1,
    )
    rows.extend([command(), STATUS, update()])
    data = place(chain(C.NONCE), 500)
    op["download_start"] = len(report["att_packets"])
    emit("tx", b"\x52\x22\0" + P.frame(11, C.F.NAME.encode().ljust(14, b"\0") + bytes(4)))
    emit("rx", b"\x1b\x24\0" + P.frame(11, b"\0" + struct.pack(">I", 4096)))
    for at in range(0, 4096, 244):
        emit("rx", b"\x1b\x2a\0" + data[at : at + 244])
    rows.extend(remote(32, 48, 4, 600, identifier=20))
    if fault == "early-slow":
        rows.append(update(48, 4, 600))
    emit("rx", b"\x1b\x24\0" + P.frame(11, b"\2"))
    op["download_end"] = len(report["att_packets"])
    if fault != "early-slow":
        rows.append(update(48, 4, 600))
    identity(op, "after")
    op.update(
        verified_end=len(report["att_packets"]),
        download_bytes=4096,
        received_bytes=4096,
        download_sha256=C.A.sha(data),
        state_verification=C.verify_state(info(), info(), sd_write=False),
    )
    op["download_verification"] = C.A.download(report, op, data, minimum_start=report["setup_end"])
    identity(report, "after")
    report["state_verification"] = C.verify_state(info(), info(), sd_write=False)
    if fault == "actions":
        emit("tx", b"\x12\x16\0forbidden Actions")
    elif fault == "extra":
        rows.extend(remote(identifier=80) + [update(12)])
    elif fault == "pending":
        rows.extend(remote(identifier=80))
    report["close_requested_us"] = 1000 + len(rows) - 1
    rows.append((3, event(5, struct.pack("<BHB", 0, LINK["handle"], 8 if fault == "disconnect" else 0x16))))
    report.update(close_completed_us=1000 + len(rows), disconnect_observed_us=1001 + len(rows))
    raw = C.P.H.HEADER + b"".join(
        record(packet, opcode, stamp=1000 + i) for i, (opcode, packet) in enumerate(rows)
    )
    (directory / "session.btsnoop").write_bytes(raw)
    (directory / "retained" / "download.bin").write_bytes(data)
    observed = C.P.inspect(raw, link=LINK, final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": C.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = C.dual_hci.bind(report, raw)
    report["disconnect_observation"] = {
        "observed": True,
        "event": observed["disconnects"][0],
        "max_wait_seconds": 8,
    }
    warm, normal, slow = observed["transactions"][:3]
    report.update(
        startup_settlement=warm,
        startup_classification=C.startup.classify(
            warm, policy=C.startup.POLICY if fault == "default" else None
        ),
    )
    op.update(normalization=normal, slow_settlement=slow)
    return report, plan, b"." * 4096


def test_readonly_wire_proof_and_retained_content_are_separate(tmp_path):
    report, plan, previous = fixture(tmp_path)
    original = copy.deepcopy(report)
    proof = C.readonly(report, tmp_path, plan)
    assert proof["parameter_transactions"] == 3 and proof["actions"] == proof["sd_writes"] == 0
    content = C.content((tmp_path / "retained/download.bin").read_bytes(), previous, plan)
    assert content["original_trial_ok"] is False and content["reuse_pair_complete"] is False
    assert report == original and report["ok"] is False


@pytest.mark.parametrize("fault", ["default", "early-slow", "actions", "extra", "pending", "disconnect"])
def test_original_wire_faults_fail_without_salvage(tmp_path, fault):
    report, plan, _previous = fixture(tmp_path, fault=fault)
    with pytest.raises(ValueError):
        C.readonly(report, tmp_path, plan)


@pytest.mark.parametrize(
    "fault", ["name", "nonce", "target", "budget", "bool", "policy", "time", "old-success"]
)
def test_fixed_plan_cannot_broaden_readonly_target_or_budget(fault):
    plan = plan_fixture()
    if fault == "name":
        plan["name"] = "rc0000000000"
    elif fault == "nonce":
        plan["nonce"] = "rc0000000000"
    elif fault == "target":
        plan["nor_offset"] = 0x4200
    elif fault == "budget":
        plan["budget"]["actions"] = 1
    elif fault == "bool":
        plan["budget"]["sd_writes"] = False
    elif fault == "policy":
        plan["startup_policy"] = C.startup.POLICY
    elif fault == "time":
        plan["planned_at"] = "2026-10-14T08:00:00+00:00"
    else:
        plan["parent"]["original_failed_retained"] = False
    with patch.object(C.sources, "verify") as verify, pytest.raises(ValueError):
        C.source_gate(plan, None)
    verify.assert_not_called()


@pytest.mark.parametrize("fault", ["state", "flag", "short", "error", "close", "stage"])
def test_saved_transport_mutations_reject(tmp_path, fault):
    report, plan, _previous = fixture(tmp_path)
    if fault == "state":
        report["expected_before"] = {}
    elif fault == "flag":
        report["operation"]["live_complete"] = False
    elif fault == "short":
        (tmp_path / "retained/download.bin").write_bytes(b"partial")
    elif fault == "error":
        report["capture_error"] = "lost bytes"
    elif fault == "stage":
        report["operation"]["ended_at"] = "2026-10-14T10:01:29+00:00"
    else:
        report["disconnect_observed_us"] += 9_000_000
    with pytest.raises(ValueError):
        C.readonly(report, tmp_path, plan)


def test_content_failure_does_not_invalidate_independent_saved_readonly_proof(tmp_path):
    report, plan, _previous = fixture(tmp_path)
    proof = C.readonly(report, tmp_path, plan)
    report.update(content_error="nonce not retained", readonly_proof=proof)
    assert C.readonly(report, tmp_path, plan) == proof
    assert report["ok"] is False


@pytest.mark.parametrize("fault", ["wrong-bytes", "wrong-target", "nonce-absent", "nonce-prior"])
def test_content_gate_never_uses_oracle_to_choose_or_fill_retained_chain(fault):
    plan = plan_fixture()
    previous = b"." * 4096
    data = place(chain(C.NONCE), 500)
    if fault == "wrong-bytes":
        data = place(chain(C.NONCE, sector=bytes(reversed(SECTOR))), 500)
    elif fault == "wrong-target":
        data = place(chain(C.NONCE, offset=0x4200), 500)
    elif fault == "nonce-absent":
        data = place(chain("rc0000000000"), 500)
    else:
        previous = place(C.NONCE.encode())
    with pytest.raises(ValueError):
        C.content(data, previous, plan)
