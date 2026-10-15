"""Synthetic failed parent: real full ATT/HCI, only outer historical source mocked."""

import copy
import json
from unittest.mock import patch

import pytest
import test_scratch_reuse_audit as old
from test_hci_interval import record
from test_sd_nor_probe import END, info

from rcominote.experiments import scratch_postmortem_sources as S
from rcominote.log_probe import ACK
from rcominote.log_stream import Stream


def save(path, value):
    path.write_text(json.dumps(value))
    return S.A.sha(path.read_bytes())


def fixture(directory, *, keep_f0=False):
    """Trim the existing full synthetic wire to baseline/6ACK/0F0/final identity."""
    with patch.object(old, "info", return_value=info(9)):
        report, plan, baseline = old.fixture(directory)
    capture = (directory / "session.btsnoop").read_bytes()
    wire = S.common.wire_positions(report, capture)
    warm, original_first, _ = [report["baseline"], *report["operations"]]
    before_end = warm["verified_end"]
    selected = list(range(before_end))
    for i in range(original_first["actions_start"], original_first["actions_end"]):
        row = report["att_packets"][i]
        packet = bytes.fromhex(row["hex"])
        if keep_f0 or row["direction"] == "tx" or packet == b"\x13" or packet[3:] in (ACK, END):
            selected.append(i)
    actions_end = len(selected)
    selected.extend(range(*report["after_span"]))
    retained = {n for i in selected[before_end:] for n in range(wire[i][0], wire[i][1] + 1)}
    records = list(S.P.records(capture, report["hci_capture"]["records"]))
    last = wire[before_end - 1][1]
    kept = [row for row in records if row[0] <= last or row[0] in retained or row == records[-1]]
    raw = S.P.H.HEADER + b"".join(record(p, op, stamp=stamp) for _, op, stamp, p in kept)
    (directory / "session.btsnoop").write_bytes(raw)
    report["att_packets"] = [report["att_packets"][i] for i in selected]
    warm.update(ok=True, barrier_complete=True)
    first = copy.deepcopy(plan["operations"][0]) | {
        "ok": False,
        "live_complete": False,
        "before": warm["after"],
        "started_at": "2026-10-14T10:01:17+00:00",
        "ended_at": "2026-10-14T10:01:18+00:00",
        "producer_attempted": True,
        "sd_write_attempted": True,
        "actions_start": before_end,
        "actions_end": actions_end,
        "writes": original_first["writes"],
        "notifications": original_first["notifications"] if keep_f0 else [ACK.hex()] * 6 + [END.hex()],
        "ack_count": 6,
        "end_received": True,
        "pending_hex": "",
        "log_session_complete": True,
        "error": S.FAILURE,
    }
    stream = Stream()
    for value in first["notifications"]:
        stream.feed(bytes.fromhex(value))
    first["frames"] = stream.frames
    second = copy.deepcopy(plan["operations"][1]) | {"ok": False, "live_complete": False}
    for label in ("first", "second"):
        for path in (directory / label).iterdir():
            path.unlink()
    report.update(
        ok=False,
        operations=[first, second],
        error=S.FAILURE,
        capture_error=S.FAILURE,
        after_span=[actions_end, len(selected)],
        ended_at="2026-10-14T10:01:20+00:00",
    )
    observed = S.P.inspect(raw, link=report["transport"]["link"], final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": S.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = S.dual_hci.bind(report, raw)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    checkpoint = copy.deepcopy(report)
    checkpoint["att_packets"] = checkpoint["att_packets"][:before_end]
    checkpoint["operations"] = S.C.report(plan)["operations"]
    save(directory / "baseline/checkpoint.json", checkpoint)
    plan_hash = save(directory / "plan.json", plan)
    report["plan"] = {
        "file": "plan.json",
        "bytes": (directory / "plan.json").stat().st_size,
        "sha256": plan_hash,
    }
    save(directory / "report.json", report)
    return report, plan, baseline


@pytest.fixture
def failed(tmp_path, monkeypatch):
    report, plan, baseline = fixture(tmp_path)
    monkeypatch.setattr(S, "REPORT_SHA", S.A.sha((tmp_path / "report.json").read_bytes()))
    monkeypatch.setattr(S, "PLAN_SHA", S.A.sha((tmp_path / "plan.json").read_bytes()))
    monkeypatch.setattr(S, "HCI_SHA", S.A.sha((tmp_path / "session.btsnoop").read_bytes()))
    monkeypatch.setattr(S.sources, "BASELINE_SHA", S.A.sha(baseline))
    return tmp_path, report, plan, baseline


def verify(failed):
    directory, _, _, baseline = failed
    with patch.object(S.C, "source_gate", return_value=baseline) as gate:
        result = S.verify(directory, directory / "unused-image.bin")
    gate.assert_called_once()
    return result


def test_complete_failed_wire_admits_latest_state_without_promoting_overwrite(failed):
    directory, report, plan, expected = failed
    before = {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    baseline, state, summary = verify(failed)
    assert baseline == expected and state == info(9)
    assert summary["sources"] == plan["sources"] and summary["latest_info"] == report["after"]
    assert summary["name"] == S.sources.NAME and summary["nonce"] == plan["operations"][0]["nonce"]
    assert summary["original_failed_retained"] is True
    assert summary["current_object_equals_baseline_proven"] is False
    assert summary["same_file_overwrite_content_confirmed"] is False
    assert summary["verification"]["actions"]["acks"] == 6
    assert summary["verification"]["parameter_transactions"] == 3
    assert summary["new_raw_nor_coverage_bytes"] == 0
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize("file", ["report.json", "plan.json", "session.btsnoop"])
def test_changed_original_pin_fails_before_historical_replay(failed, file):
    directory, _, _, _ = failed
    (directory / file).write_bytes(b"changed")
    with patch.object(S.C, "source_gate") as gate, pytest.raises(ValueError, match="Pinned"):
        S.verify(directory, directory / "image")
    gate.assert_not_called()


@pytest.mark.parametrize(
    "fault",
    [
        "top-true",
        "first-true",
        "second-true",
        "baseline-false",
        "error",
        "sd-attempt",
        "producer",
        "first-download",
        "second-command",
        "target",
        "nonce",
        "prestate",
        "time",
        "missing-identity",
        "identity-summary",
        "capacity",
        "early-close",
        "late-close",
        "binding",
        "pending",
        "extra-txn",
        "baseline-content",
        "baseline-checkpoint",
        "first-file",
        "second-file",
        "ack",
        "f0",
        "gap",
    ],
)
def test_failed_parent_semantic_mutations_fail_closed(failed, monkeypatch, fault):
    directory, report, plan, baseline = failed
    first, second = report["operations"]
    if fault in ("top-true", "first-true", "second-true", "baseline-false"):
        owner = {
            "top-true": report,
            "first-true": first,
            "second-true": second,
            "baseline-false": report["baseline"],
        }[fault]
        owner["ok"] = fault != "baseline-false"
    elif fault == "error":
        report["error"] = "different failure"
    elif fault == "sd-attempt":
        first["sd_write_attempted"] = False
    elif fault == "producer":
        first["producer_attempted"] = False
    elif fault == "first-download":
        first["download_start"] = first["actions_end"]
    elif fault == "second-command":
        second["writes"] = []
    elif fault == "target":
        first["nor_offset"] = 0x4200
    elif fault == "nonce":
        first["nonce"] = plan["operations"][1]["nonce"]
    elif fault == "prestate":
        report["expected_before"] = info(8)
    elif fault == "time":
        first["started_at"] = report["started_at"]
    elif fault == "missing-identity":
        report["after_span"][1] -= 2
    elif fault == "identity-summary":
        report["after"] = info(8)
    elif fault == "capacity":
        report["state_verification"]["allowed_decrease"] = 1
    elif fault == "early-close":
        report["disconnect_observation"]["event"]["reason"] = 8
    elif fault == "late-close":
        report["disconnect_observed_us"] += 9_000_000
    elif fault == "binding":
        report["att_hci_binding"]["packets"] -= 1
    elif fault in ("pending", "extra-txn"):
        original = S.P.inspect

        def changed(*args, **kwargs):
            value = original(*args, **kwargs)
            if fault == "pending":
                value["pending"] = [{}]
            else:
                value["transactions"].append(copy.deepcopy(value["transactions"][0]))
            return value

        monkeypatch.setattr(S.P, "inspect", changed)
    elif fault == "baseline-content":
        (directory / "baseline/download.bin").write_bytes(b"X" * 4096)
    elif fault == "baseline-checkpoint":
        (directory / "baseline/checkpoint.json").write_text("{}")
    elif fault in ("first-file", "second-file"):
        (directory / fault.split("-")[0] / "download.bin").write_bytes(b"x")
    elif fault == "ack":
        first["ack_count"] = 5
    elif fault == "f0":
        first["frames"][0]["command"] = 0xF0
    else:
        report["file_list_span"][0] += 1  # Unconsumed ATT after before identity.
    monkeypatch.setattr(S, "REPORT_SHA", save(directory / "report.json", report))
    with patch.object(S.C, "source_gate", return_value=baseline), pytest.raises((ValueError, KeyError)):
        S.verify(directory, directory / "image")


def test_historical_source_gate_failure_propagates_without_partial_state(failed):
    directory, _, _, _ = failed
    with (
        patch.object(S.C, "source_gate", side_effect=ValueError("prior failed chain")),
        pytest.raises(ValueError, match="prior failed chain"),
    ):
        S.verify(directory, directory / "image")


def test_actual_f0_cannot_be_relabelled_as_original_missing_output(tmp_path, monkeypatch):
    report, _, baseline = fixture(tmp_path, keep_f0=True)
    first = report["operations"][0]
    assert S.A.action_frames(report, first, expected=S.C.recipe(first))["acks"] == 6
    assert any(f["command"] == 0xF0 for f in first["frames"])
    monkeypatch.setattr(S, "REPORT_SHA", S.A.sha((tmp_path / "report.json").read_bytes()))
    monkeypatch.setattr(S, "PLAN_SHA", S.A.sha((tmp_path / "plan.json").read_bytes()))
    monkeypatch.setattr(S, "HCI_SHA", S.A.sha((tmp_path / "session.btsnoop").read_bytes()))
    monkeypatch.setattr(S.sources, "BASELINE_SHA", S.A.sha(baseline))
    with patch.object(S.C, "source_gate", return_value=baseline), pytest.raises(ValueError, match="zero F0"):
        S.verify(tmp_path, tmp_path / "image")
