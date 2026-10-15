"""Early6/0/500 normalization preserves actual baseline and gates first Actions."""

from types import SimpleNamespace

import pytest
from test_dual_probe import acl
from test_hci_interval import HANDLE, LOCAL, connection, event, packets, record, request, update

from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_interval as D
from rcominote.experiments import hci_interval as H
from rcominote.experiments.hci_interval_io import Monitor
from rcominote.experiments.hci_monitor import Snoop


def initial_capture():
    initial = connection()[:-7] + bytes.fromhex("30000400580200")  # interval48/latency4/timeout600.
    records = [packets()[0], (3, initial), (2, request()), (3, event(0x0F, b"\0\x01\x13\x20"))]
    records += [(3, update())]  # Explicit6/0/500, not retained initial600.
    return H.HEADER + b"".join(record(p, op, stamp=100 + i) for i, (op, p) in enumerate(records))


def fixture():
    raw = initial_capture()
    parser = Snoop()
    parser.feed(raw, final=True)
    transport = {
        "policy": D.POLICY,
        "link": {"handle": HANDLE, "local": LOCAL, "peer": H.PEER, "controller": "hci0"},
        "baseline": parser.events[1],
        "update_requested_us": 102,
        "actual_hci_request": parser.events[2],
        "applied": parser.events[4],
    }
    return raw, parser, transport


def test_actual_nonzero_latency_baseline_retained_and_timeout_explicitly_normalized():
    _, parser, transport = fixture()
    actual = D.baseline(parser.events[:2], transport["link"])
    assert (actual["interval"], actual["latency"], actual["timeout"]) == (48, 4, 600)
    assert D.applied(parser.events, transport) == parser.events[4]
    assert transport["baseline"]["timeout"] == 600
    assert D.gate(SimpleNamespace(poll=lambda: parser.events), transport)["timeout"] == 500
    with pytest.raises(ValueError, match="Observed HCI request"):
        H.applied(parser.events, HANDLE, LOCAL, actual, 102)


def test_pending_request_and_already_normalized_baselines_rejected():
    _, parser, transport = fixture()
    with pytest.raises(ValueError, match="Prior parameter"):
        D.baseline(parser.events[:3], transport["link"])
    with pytest.raises(ValueError, match="Prior parameter"):
        D.baseline(parser.events[:-1] + [parser.events[-1] | {"interval": 12}], transport["link"])
    with pytest.raises(ValueError, match="interval above6"):
        D.baseline(parser.events[:1] + [parser.events[1] | {"interval": 6}], transport["link"])


def test_second_request_still_rejected_after_timestamp_model_fix():
    _, parser, transport = fixture()
    second = parser.events[2] | {"record": 6, "timestamp_us": 105}
    with pytest.raises(ValueError, match="Second parameter"):
        D.applied(parser.events + [second], transport)
    with pytest.raises(ValueError, match="Unknown transport"):
        D.applied(parser.events, transport | {"policy": "arbitrary"})


@pytest.mark.parametrize("identity_before_update", [False, True])
def test_hci_gate_includes_initial_identity_and_reports_normalized_timeout(identity_before_update):
    raw, _, transport = fixture()
    rows = [
        {"direction": "tx", "hex": "02f700"},
        {"direction": "tx", "hex": "02f700"},
        {"direction": "tx", "hex": "02f700"},
        {"direction": "rx", "hex": "03f700"},
    ]
    for index, row in enumerate(rows):
        stamp = 103 if identity_before_update and index == 0 else 105 + index
        raw += record(acl(bytes.fromhex(row["hex"]), row["direction"]), 4 if index < 3 else 5, stamp=stamp)
    parser = Snoop()
    parser.feed(raw, final=True)
    operation = {"phase": "backup-boot-block1", "actions_start": 1, "download_start": 2, "verified_end": 4}
    report = {
        "profile": D.EARLY_PROFILE,
        "operations": [operation],
        "att_packets": rows,
        "monitor_exit": 0,
        "before_span": [0, 1],
        "transport": transport,
        "hci_capture": {"bytes": len(raw), "sha256": A.sha(raw), "records": parser.records},
    }
    if identity_before_update:
        with pytest.raises(ValueError, match="did not retain"):
            A.hci(report, operation, raw)
    else:
        assert A.hci(report, operation, raw)["timeout"] == 500


def test_capture_can_select_modern_parser_without_changing_historical_default(tmp_path):
    modern = Snoop()
    assert Monitor(tmp_path, snoop=modern).snoop is modern
    assert isinstance(Monitor(tmp_path).snoop, H.Snoop)
