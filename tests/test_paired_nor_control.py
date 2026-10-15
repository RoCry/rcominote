"""One real synthetic owned epoch: two known groups, six DLs, seventeen transactions."""

import copy
import json
from unittest.mock import patch

import pytest
import test_scratch_reuse_audit as old_fixture
import test_scratch_system_pair_contract as legacy
from test_hci_interval import record
from test_paired_nor_audit import fixture as page_fixture
from test_paired_nor_audit import relocate_wire, replace_baseline
from test_param_window import remote, update
from test_scratch_reuse_parser import NONCE, SECTOR, chain
from test_sd_nor_probe import info

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C


def fixture(root):
    first_path, second_path = root / "page0-000000", root / "page1-004200"
    first, plan, _page, baseline = page_fixture(first_path, offset=0)
    target = bytes(reversed(SECTOR))
    with patch.object(
        legacy, "chain", side_effect=lambda nonce, offset, _sector=SECTOR: chain(nonce, offset, target)
    ):
        second, second_plan, _page, _baseline = page_fixture(
            second_path, offset=0x4200, nonces=("rc1234567890", "rcabcdef0123"), placements=(500, 2800)
        )
    previous = (first_path / "second/download.bin").read_bytes()
    replace_baseline(second, second_path, previous)
    relocate_wire(second, second_path, 1_000_000)
    raw0, raw1 = (first_path / "session.btsnoop").read_bytes(), (second_path / "session.btsnoop").read_bytes()
    wire0 = A.common.wire_positions(first, raw0)
    end0 = first["operations"][-1]["verified_end"]
    begin1 = second["baseline"]["download_start"]
    tx1 = A.P.inspect(raw1, link=second["transport"]["link"], final=True)["transactions"][1]
    records = [
        row for row in A.P.records(raw0, first["hci_capture"]["records"]) if row[0] <= wire0[end0 - 1][1]
    ]
    records += [
        row
        for row in A.P.records(raw1, second["hci_capture"]["records"])
        if row[0] >= tx1["request"]["record"]
    ]
    raw = A.P.H.HEADER + b"".join(record(packet, opcode, stamp=stamp) for _, opcode, stamp, packet in records)
    (root / "session.btsnoop").write_bytes(raw)
    plan["pages"].append(second_plan["pages"][0] | {"page_index": 1, "directory": second_path.name})
    plan.update(
        profile=C.KNOWN_CONTROL,
        offsets=[0, 0x4200],
        budget=C.CONTROL_BUDGET.copy(),
        prefix_policy=C.F.PADDING_POLICY,
        independent_oracle=True,
        stage_timeout_scope="six-post-startup-stages18-each-under-single-active60",
    )
    oracles = {}
    for key, offset, sector in (("boot0", 0, SECTOR), ("4200", 0x4200, target)):
        path = root / f"oracle-{key}.bin"
        path.write_bytes(sector)
        oracles[key] = {
            "nor_offset": offset,
            "bytes": 512,
            "sha256": A.A.sha(sector),
            "proof": {"synthetic_independent_raw": True},
            "source": {"file": str(path.resolve()), "bytes": 512, "sha256": A.A.sha(sector)},
            "slice": [0, 512],
        }
    plan["oracles"] = oracles
    for page in plan["pages"]:
        for op in page["operations"]:
            op["prefix_policy"] = C.F.PADDING_POLICY
    groups = []
    for index, original in enumerate((first, second)):
        group = {
            "group_index": index,
            "nor_offset": plan["offsets"][index],
            "baseline": original["baseline"],
            "operations": original["operations"],
            "live_complete": True,
            "candidate": True,
        }
        for number, op in enumerate([group["baseline"], *group["operations"]]):
            op.update(ok=True, live_complete=True)
            op["started_at"] = f"2026-10-14T10:01:{1 + index * 6 + number * 2:02d}+00:00"
            op["ended_at"] = f"2026-10-14T10:01:{2 + index * 6 + number * 2:02d}+00:00"
            if index:
                shift = end0 - begin1
                for key in ("download_start", "download_end", "verified_end", "actions_start", "actions_end"):
                    if key in op:
                        op[key] += shift
                op["after_span"] = [n + shift for n in op["after_span"]]
            if number:
                op["prefix_policy"] = C.F.PADDING_POLICY
        groups.append(group)
    report = {k: v for k, v in first.items() if k not in ("baseline", "operations")}
    report.update({k: plan[k] for k in C.CONTROL_FIELDS})
    report.update(
        groups=groups,
        ok=False,
        ended_at="2026-10-14T10:01:20+00:00",
        att_packets=first["att_packets"][:end0] + second["att_packets"][begin1:],
    )
    report["after_span"] = [n + end0 - begin1 for n in second["after_span"]]
    for index, row in enumerate(report["att_packets"]):
        row["monotonic_ns"] = index
    for key in ("close_requested_us", "close_completed_us", "disconnect_observed_us"):
        report[key] = second[key]
    observed = A.P.inspect(raw, link=report["transport"]["link"], final=True)
    assert len(observed["transactions"]) == 17
    report["hci_capture"] = {"bytes": len(raw), "sha256": A.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = A.dual_hci.bind(report, raw)
    report["disconnect_observation"]["event"] = observed["disconnects"][0]
    tx, wire, cursor = observed["transactions"], A.common.wire_positions(report, raw), 1
    report.update(startup_settlement=tx[0], startup_classification=C.startup.classify(tx[0]))
    previous_tx, previous = tx[0], baseline
    for index, (group, path) in enumerate(zip(groups, (first_path, second_path), strict=True)):
        warm = group["baseline"]
        warm.update(normalization=tx[cursor], slow_settlement=tx[cursor + 1])
        warm["download_verification"] = A.A.download(
            report, warm, (path / "baseline/download.bin").read_bytes(), minimum_start=report["setup_end"]
        )
        cursor += 2
        previous_tx = warm["slow_settlement"]
        for op in group["operations"]:
            fast, normal, slow = tx[cursor : cursor + 3]
            op.update(pre_download_fast=[fast], normalization=normal, slow_settlement=slow)
            op["activity_fast_verification"] = A.W.default_activity_fast(report, op, previous_tx, fast, wire)
            op["actions_verification"] = C.actions(report, op)
            data = (path / op["operation_id"] / "download.bin").read_bytes()
            op["download_verification"] = A.A.download(report, op, data, minimum_start=report["setup_end"])
            op["verification"] = C.payload(op, data, previous)
            op["oracle_verification"] = A.oracle_proof(
                plan, index, bytes.fromhex(op["verification"]["sector_hex"])
            )
            previous, previous_tx, cursor = data, slow, cursor + 3
    C.S.save(root / "plan.json", plan)
    report["plan"] = C.J.reference(root, root / "plan.json")
    return report, plan, baseline, oracles


def validate(root, report, plan, baseline, oracles):
    with patch.object(C.pins, "oracles", return_value=oracles):
        return A.validate_control(report, root, plan, baseline)


def test_full_one_connection_six_downloads_four_known_reads_seventeen_transactions(tmp_path):
    report, plan, baseline, oracles = fixture(tmp_path)
    proof = validate(tmp_path, report, plan, baseline, oracles)
    assert proof["parameter_transactions"] == 17 and proof["connections"] == 1
    assert proof["downloads"] == 6 and proof["new_raw_nor_coverage_bytes"] == 0
    assert [p["known_offset"] for p in proof["groups"]] == [0, 0x4200]
    assert [p["sha256"] for p in proof["groups"]] == [A.A.sha(SECTOR), A.A.sha(bytes(reversed(SECTOR)))]
    assert (
        report["groups"][1]["baseline"]["download_sha256"]
        == report["groups"][0]["operations"][1]["download_sha256"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "baseline",
        "early-host",
        "extra-fast",
        "pending",
        "state",
        "oracle",
        "nonce",
        "future",
        "fake-disconnect",
        "group-flag",
        "final",
        "epoch",
        "short",
    ],
)
def test_global_wire_and_group_boundary_cannot_be_bypassed(tmp_path, fault):
    report, plan, baseline, oracles = fixture(tmp_path)
    group = report["groups"][1]
    if fault == "baseline":
        (tmp_path / "page1-004200/baseline/download.bin").write_bytes(baseline)
    elif fault == "early-host":
        group["baseline"]["normalization_requested_us"] = (
            report["groups"][0]["operations"][1]["slow_settlement"]["update"]["timestamp_us"] - 1
        )
    elif fault == "extra-fast":
        group["baseline"]["normalization"] = copy.deepcopy(group["operations"][0]["pre_download_fast"][0])
    elif fault == "pending":
        group["operations"][0]["notifications"].append("1d")
    elif fault == "state":
        group["baseline"]["before"] = {}
    elif fault == "oracle":
        (tmp_path / "oracle-4200.bin").write_bytes(SECTOR)
    elif fault == "nonce":
        group["operations"][0]["nonce"] = NONCE
    elif fault == "future":
        plan["parent"]["prior_names"].append(plan["pages"][1]["operations"][0]["nonce"])
    elif fault == "fake-disconnect":
        report["groups"][0]["disconnect_observation"] = report["disconnect_observation"]
    elif fault == "group-flag":
        group["candidate"] = False
    elif fault == "final":
        report["state_verification"] = {}
    elif fault == "epoch":
        report["ended_at"] = "2026-10-14T10:01:01+00:00"
    else:
        (tmp_path / "page1-004200/second/download.bin").write_bytes(b"short")
    with pytest.raises((ValueError, KeyError)):
        validate(tmp_path, report, plan, baseline, oracles)


def test_original_failure_cannot_be_replayed_as_known_control_parent(tmp_path):
    report, plan, baseline, oracles = fixture(tmp_path)
    with (
        patch.object(C.pins, "oracles", return_value=oracles),
        pytest.raises(ValueError, match="Original failed"),
    ):
        A.validate_control(report, tmp_path, plan, baseline, archived=True)


def rewrite_capture(root, report, records):
    raw = A.P.H.HEADER + b"".join(record(packet, opcode, stamp=stamp) for opcode, stamp, packet in records)
    (root / "session.btsnoop").write_bytes(raw)
    observed = A.P.inspect(raw, link=report["transport"]["link"], final=True)
    report["hci_capture"] = {"bytes": len(raw), "sha256": A.A.sha(raw), "records": observed["records"]}
    report["att_hci_binding"] = A.dual_hci.bind(report, raw)
    return observed


def test_coherent_host9_after_slow8_but_before_last_identity_rx_is_rejected(tmp_path):
    report, plan, baseline, oracles = fixture(tmp_path)
    raw = (tmp_path / "session.btsnoop").read_bytes()
    wire = A.common.wire_positions(report, raw)
    prior = report["groups"][0]["operations"][1]
    warm = report["groups"][1]["baseline"]
    last_rx = wire[prior["after_span"][1] - 1]
    request, status = warm["normalization"]["request"]["record"], warm["normalization"]["status"]["record"]
    original = [
        (opcode, stamp, packet)
        for _n, opcode, stamp, packet in A.P.records(raw, report["hci_capture"]["records"])
    ]
    command_rows = [original[request - 1], original[status - 1]]
    command_rows = [(op, last_rx[2] - 1, packet) for op, _stamp, packet in command_rows]
    modified = []
    for number, row in enumerate(original, 1):
        if number == last_rx[0]:
            modified.extend(command_rows)
        if number not in (request, status):
            modified.append(row)
    observed = rewrite_capture(tmp_path, report, modified)
    normal = observed["transactions"][9]
    warm.update(normalization=normal, normalization_requested_us=normal["request"]["timestamp_us"])
    assert prior["slow_settlement"]["update"]["record"] < normal["request"]["record"]
    assert normal["request"]["timestamp_us"] > prior["slow_settlement"]["update"]["timestamp_us"]
    with pytest.raises(ValueError, match="Continuation host normalization precedes prior final identity"):
        validate(tmp_path, report, plan, baseline, oracles)


def test_actual_extra_remote_fast_at_continuation_cannot_become_optional_eighteenth_transaction(tmp_path):
    report, plan, baseline, oracles = fixture(tmp_path)
    raw = (tmp_path / "session.btsnoop").read_bytes()
    rows = [
        (opcode, stamp, packet)
        for _n, opcode, stamp, packet in A.P.records(raw, report["hci_capture"]["records"])
    ]
    insertion = report["groups"][1]["baseline"]["normalization"]["request"]["record"] - 1
    stamp = rows[insertion - 1][1]
    extra = [
        (opcode, stamp + n + 1, packet)
        for n, (opcode, packet) in enumerate(remote(identifier=111) + [update(12)])
    ]
    observed = rewrite_capture(tmp_path, report, rows[:insertion] + extra + rows[insertion:])
    assert len(observed["transactions"]) == 18 and not observed["pending"]
    with pytest.raises(ValueError, match="exactly 17"):
        validate(tmp_path, report, plan, baseline, oracles)


def test_successful_known_control_iteratively_admits_current_file_for_next_generic_plan(tmp_path):
    root, anchor = tmp_path / "control", tmp_path / "legacy"
    with patch.object(old_fixture, "info", return_value=info(9)):
        report, plan, baseline, oracles = fixture(root)
    (anchor / "second").mkdir(parents=True)
    original = {
        "profile": C.legacy.PROFILE,
        "ok": True,
        "after": plan["expected_before"],
        "ended_at": plan["parent"]["ended_at"],
    }
    anchor_plan, anchor_proof = {"prior_names": plan["parent"]["prior_names"]}, {"verified": True}
    C.S.save(anchor / "report.json", original)
    C.S.save(anchor / "plan.json", anchor_plan)
    (anchor / "second/download.bin").write_bytes(baseline)
    (anchor / "session.btsnoop").write_bytes(b"synthetic historical outer anchor")
    pins = {name: A.A.sha((anchor / name).read_bytes()) for name in C.LEGACY_PINS}
    refs = {name: C.pins.pinned(anchor / name, sha)[1] for name, sha in pins.items()}
    plan["parent"] = C.source_summary(
        anchor, original, anchor_plan, anchor_proof, baseline, original["after"], refs
    )
    (root / "plan.json").write_text(json.dumps(plan))
    report["plan"] = C.J.reference(root, root / "plan.json")
    report["verification"] = validate(root, report, plan, baseline, oracles)
    report["ok"] = True
    C.S.save(root / "report.json", report)
    with (
        patch.object(C, "LEGACY_PINS", pins),
        patch.object(C.old, "replay", return_value=anchor_proof),
        patch.object(C.pins, "oracles", return_value=oracles),
        patch.object(C.S, "now", return_value="2026-10-14T10:01:21+00:00"),
    ):
        ring, state, summary = C.parent_gate(root, None)
        expected = (root / "page1-004200/second/download.bin").read_bytes()
        assert ring == expected and state == report["after"]
        assert (
            summary["profile"] == C.KNOWN_CONTROL
            and summary["verification"]["new_raw_nor_coverage_bytes"] == 0
        )
        next_plan, next_ring = C.prepare(None, root, [0x25200])
        assert next_ring == expected and C.source_gate(next_plan, None) == expected
        assert set(C.nonces(plan)).issubset(next_plan["parent"]["prior_names"])
        report["ok"] = False
        (root / "report.json").write_text(json.dumps(report))
        with pytest.raises(ValueError, match="failed parent"):
            C.parent_gate(root, None)
