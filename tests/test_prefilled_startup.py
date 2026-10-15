"""Full synthetic DEFAULT/pulse/FAST+15 existing transactions; no device evidence."""

import asyncio
import copy
import json
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_hci_interval import record
from test_paired_nor_audit import replace_download
from test_paired_nor_control import rewrite_capture
from test_param_window import fragment, remote, update
from test_prefilled_nor_control import RAM
from test_prefilled_nor_pages import fixture as old_fixture

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_link_checkpoint as times
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_nor_pages as N
from rcominote.experiments import prefilled_startup as S
from rcominote.log_capture import START, STOP
from rcominote.log_probe import ACK, PREPARE
from rcominote.log_stream import Stream


def fixture(root):
    actual, plan, _page, baseline = old_fixture(root)
    path = root / plan["pages"][0]["directory"]
    plan.update(
        startup_policy=S.POLICY,
        budget=N.budgets(1, startup_policy=S.POLICY),
        page_budget=S.budget(N.BUDGET, S.POLICY),
    )
    with patch.object(P, "RAM_SHA", A.A.sha(RAM)):
        page = C.page_plan(plan, 0, plan["expected_before"], plan["parent"]["ended_at"])
    actual.update({k: page[k] for k in C.fields(page)})
    raw = (path / "session.btsnoop").read_bytes()
    original = A.P.inspect(raw, link=actual["transport"]["link"], final=True)["transactions"][0]
    boundary = actual["file_list_span"][1]
    notes, rows = [], []
    for packet in (PREPARE, START, STOP):
        rows += [("tx", b"\x12\x16\0" + packet), ("rx", b"\x13"), ("rx", b"\x1b\x18\0" + ACK)]
        notes.append(ACK.hex())
    rows.append(("rx", b"\x1b\x18\0\x1d\xf1\x81\0\0"))
    notes.append("1df1810000")
    additions = [fragment(struct.pack("<HH", len(p), 4) + p, direction=d) for d, p in rows]
    additions += remote(identifier=99) + [update(12)]
    records = []
    first, last = original["remote_request"]["records"][0], original["update"]["record"]
    defaults = remote(24, 40, 0, 500) + [update(36)]
    base = None
    for n, code, stamp, packet in A.P.records(raw, actual["hci_capture"]["records"]):
        base = stamp - 1 if base is None else base
        records.append(defaults[n - first] if first <= n <= last else (code, packet))
        if n == last:
            records.extend(additions)
    raw = A.P.H.HEADER + b"".join(record(p, code, stamp=base + i) for i, (code, p) in enumerate(records, 1))
    (path / "session.btsnoop").write_bytes(raw)

    def move(value):
        return value + len(rows) if value >= boundary else value

    for owner in [actual, actual["baseline"], *actual["operations"]]:
        for key in ("actions_start", "actions_end", "download_start", "download_end", "verified_end"):
            if key in owner:
                owner[key] = move(owner[key])
        if "after_span" in owner:
            owner["after_span"] = list(map(move, owner["after_span"]))
    actual["att_packets"][boundary:boundary] = [
        {"direction": d, "hex": p.hex(), "monotonic_ns": 0} for d, p in rows
    ]
    for i, row in enumerate(actual["att_packets"]):
        row["monotonic_ns"] = i
    observed = A.P.inspect(raw, link=actual["transport"]["link"], final=True)
    actual["hci_capture"] = {"bytes": len(raw), "sha256": A.A.sha(raw), "records": observed["records"]}
    tx, wire = observed["transactions"], A.common.wire_positions(actual, raw)
    assert len(tx) == 16 and not observed["pending"]
    stream = Stream()
    for note in notes:
        stream.feed(bytes.fromhex(note))
    pulse = actual["startup_pulse"] = {
        "operation_id": "startup-default-pulse",
        "actions_start": boundary,
        "actions_end": boundary + len(rows),
        "started_at": times.iso(tx[0]["update"]["timestamp_us"]),
        "ended_at": times.iso(tx[1]["update"]["timestamp_us"]),
        "notifications": notes,
        "frames": stream.frames,
        "ack_count": 3,
        "end_received": True,
        "pending_hex": "",
        "log_session_complete": True,
        "live_complete": True,
        "sd_write_attempted": False,
        "writes": [{"hex": p.hex(), "att_write_confirmed": True} for p in (PREPARE, START, STOP)],
        "activity_fast": tx[1],
    }
    pulse["actions_verification"] = S.pulse(actual, pulse)
    pulse["activity_fast_verification"] = S.pulse_audit.activity_fast(actual, pulse, tx[0], tx[1], wire)
    actual["startup_settlement"] = tx[0]
    actual["startup_classification"] = C.startup.classify(tx[0], policy=S.POLICY)
    actual["hci_capture"] = {"bytes": len(raw), "sha256": A.A.sha(raw), "records": observed["records"]}
    actual["att_hci_binding"] = A.dual_hci.bind(actual, raw)
    actual["disconnect_observation"]["event"] = observed["disconnects"][0]
    stamp = observed["disconnects"][0]["timestamp_us"]
    actual.update(
        close_requested_us=stamp - 1, close_completed_us=stamp + 1, disconnect_observed_us=stamp + 2
    )
    actual["after_verification"] = A.A.identity(actual, actual, "after")
    stages = [actual["baseline"], *actual["operations"]]
    actual["baseline"]["started_at"] = times.iso(tx[2]["request"]["timestamp_us"] - 1)
    settled = tx[3]
    for i, op in enumerate(stages):
        normal, slow = tx[2:4] if i == 0 else tx[5 + (i - 1) * 3 : 7 + (i - 1) * 3]
        op.update(
            normalization=normal,
            slow_settlement=slow,
            normalization_requested_us=normal["request"]["timestamp_us"] - 1,
        )
        data = (path / op["operation_id"] / "download.bin").read_bytes()
        op["download_verification"] = A.A.download(actual, op, data, minimum_start=actual["setup_end"])
        op["after_verification"] = A.A.identity(actual, op, "after")
        if i:
            fast = tx[4 + (i - 1) * 3]
            op["pre_download_fast"] = [fast]
            op["activity_fast_verification"] = A.W.default_activity_fast(actual, op, settled, fast, wire)
            op["actions_verification"] = P.actions(actual, op)
            settled = slow
    (root / "plan.json").write_text(json.dumps(plan))
    actual["plan"] = C.J.reference(root, root / "plan.json")
    return actual, plan, page, baseline


def validate(root, actual, page, baseline):
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, page["ram_oracle"])),
    ):
        return N.validate(actual, root / f"page0-{page['nor_offset']:06x}", page, baseline)


def test_default_pulse_actual_fast_then_complete_full16_transaction_pair(tmp_path):
    actual, plan, page, baseline = fixture(tmp_path)
    proof = validate(tmp_path, actual, page, baseline)
    assert proof["pair_verified"] and proof["parameter_transactions"] == 16
    assert proof["startup_control"]["pulse_performed"] is True
    assert (
        plan["budget"]["max_parameter_transactions"] == 16 and "parameter_transactions" not in plan["budget"]
    )
    assert plan["page_budget"]["max_startup_commands"] == 3


def test_explicit_new_policy_with_actual_fast_has_no_pulse_and_still15(tmp_path):
    actual, plan, _page, baseline = old_fixture(tmp_path)
    plan.update(
        startup_policy=S.POLICY,
        budget=N.budgets(1, startup_policy=S.POLICY),
        page_budget=S.budget(N.BUDGET, S.POLICY),
    )
    with patch.object(P, "RAM_SHA", A.A.sha(RAM)):
        page = C.page_plan(plan, 0, plan["expected_before"], plan["parent"]["ended_at"])
    actual.update({k: page[k] for k in C.fields(page)})
    actual["startup_classification"] = C.startup.classify(actual["startup_settlement"], policy=S.POLICY)
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    actual["plan"] = C.J.reference(tmp_path, tmp_path / "plan.json")
    proof = validate(tmp_path, actual, page, baseline)
    assert proof["parameter_transactions"] == 15 and proof["startup_control"] == {
        "mode": "fast",
        "pulse_performed": False,
    }


@pytest.mark.parametrize(
    "fault",
    [
        "ack",
        "f1",
        "f0",
        "body",
        "pending",
        "late-frame",
        "early-normal",
        "stale-fast",
        "wrong-budget",
        "missing-pulse",
        "proof",
        "time",
    ],
)
def test_pulse_summary_cannot_replace_exact_stream_or_actual_order_and_ledger(tmp_path, fault):
    actual, _plan, page, baseline = fixture(tmp_path)
    op = actual["startup_pulse"]
    if fault == "ack":
        op["ack_count"] = 2
    elif fault == "f1":
        op["end_received"] = False
    elif fault == "f0":
        op["frames"].insert(0, {"command": 0xF0, "hex": "1df0810300000000", "log_type": 0})
    elif fault == "body":
        op["producer"] = "kernel version"
    elif fault == "pending":
        op["pending_hex"] = "1d"
    elif fault == "late-frame":
        op["frames"].append(op["frames"][0])
    elif fault == "early-normal":
        actual["baseline"]["normalization_requested_us"] = actual["startup_settlement"]["update"][
            "timestamp_us"
        ]
    elif fault == "stale-fast":
        op["activity_fast"]["remote_request"]["records"][0] = 1
    elif fault == "wrong-budget":
        page["budget"]["max_parameter_transactions"] = 15
    elif fault == "missing-pulse":
        del actual["startup_pulse"]
    elif fault == "proof":
        op["actions_verification"] = {}
    else:
        op["ended_at"] = op["started_at"]
    with pytest.raises((ValueError, KeyError)):
        validate(tmp_path, actual, page, baseline)


@pytest.mark.parametrize("fault", [None, "nofast", "extra", "pulse", "pending", "timestamp"])
def test_runtime_never_enters_baseline_before_actual_fast_and_zero_body_pulse(tmp_path, fault):
    actual, _job, page, _baseline = fixture(tmp_path)
    original = copy.deepcopy(actual["startup_pulse"])
    if fault == "timestamp":
        original["activity_fast"]["remote_request"]["timestamp_us"] = actual["startup_settlement"]["update"][
            "timestamp_us"
        ]
    actual.pop("startup_pulse")
    conn = SimpleNamespace()

    async def commands(op, body, *, sd_write_command_index):
        assert body == [] and sd_write_command_index is None
        op.update(copy.deepcopy(original))
        if fault == "pulse":
            op["frames"] = []

    actions = SimpleNamespace(run_commands=AsyncMock(side_effect=commands))
    with (
        patch.object(S.R, "observe", return_value={"transactions": [{}], "pending": []}),
        patch.object(
            S.R,
            "wait_transaction",
            new=AsyncMock(side_effect=TimeoutError("no FAST"))
            if fault == "nofast"
            else AsyncMock(return_value=original["activity_fast"]),
        ),
        patch.object(
            C.startup,
            "live_wire",
            new=AsyncMock(
                return_value=(
                    actual,
                    {
                        "transactions": [actual["startup_settlement"], original["activity_fast"]]
                        + ([{}] if fault == "extra" else []),
                        "pending": [{}] if fault == "pending" else [],
                    },
                    A.common.wire_positions(actual, (tmp_path / "page0-1ec200/session.btsnoop").read_bytes()),
                )
            ),
        ),
    ):
        if fault:
            with pytest.raises((ValueError, TimeoutError)):
                asyncio.run(
                    S.settle(
                        conn,
                        actions,
                        None,
                        actual,
                        page,
                        actual["startup_settlement"],
                        actual["startup_classification"],
                    )
                )
        else:
            fast, cursor, boundary = asyncio.run(
                S.settle(
                    conn,
                    actions,
                    None,
                    actual,
                    page,
                    actual["startup_settlement"],
                    actual["startup_classification"],
                )
            )
            assert cursor == 2 and fast == original["activity_fast"] and boundary == original["actions_end"]
    actions.run_commands.assert_awaited_once()


@pytest.mark.parametrize("tail", ["1df0810300000000", ACK.hex()])
def test_coalesced_f1_then_frame_in_actual_notification_never_allows_baseline(tmp_path, tail):
    actual, _plan, page, baseline = fixture(tmp_path)
    op = actual["startup_pulse"]
    actual["att_packets"][op["actions_end"] - 1]["hex"] += tail
    op["notifications"][-1] += tail
    stream = Stream()
    for note in op["notifications"]:
        stream.feed(bytes.fromhex(note))
    op["frames"] = stream.frames
    path = tmp_path / "page0-1ec200"
    replace_download(actual, path, "baseline", baseline)
    actual["hci_capture"]["bytes"] = len((path / "session.btsnoop").read_bytes())
    with pytest.raises(ValueError):
        validate(tmp_path, actual, page, baseline)


def test_extra_complete_actual_fast_in_hci_cannot_fit16_ledger(tmp_path):
    actual, _plan, page, baseline = fixture(tmp_path)
    path = tmp_path / "page0-1ec200"
    raw = (path / "session.btsnoop").read_bytes()
    records = [
        (code, stamp, packet)
        for _n, code, stamp, packet in A.P.records(raw, actual["hci_capture"]["records"])
    ]
    close = records.pop()
    records += [
        (code, close[1] + i, packet)
        for i, (code, packet) in enumerate(remote(identifier=200) + [update(12)], 1)
    ]
    records.append((close[0], close[1] + 6, close[2]))
    observed = rewrite_capture(path, actual, records)
    actual["disconnect_observation"]["event"] = observed["disconnects"][0]
    actual.update(
        close_requested_us=close[1] + 5, close_completed_us=close[1] + 7, disconnect_observed_us=close[1] + 8
    )
    with pytest.raises(ValueError):
        validate(tmp_path, actual, page, baseline)
