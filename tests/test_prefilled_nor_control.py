"""Full synthetic15txn/4ACK+6ACK wire, independent RAM and known NOR oracles."""

import copy
import json
import shutil
import struct
from unittest.mock import patch

import pytest
from test_hci_interval import record
from test_nor_freshness import echo, place
from test_paired_nor_continuous_control import fixture as old_fixture
from test_param_window import fragment
from test_scratch_reuse_parser import SECTOR, chain

from rcominote.experiments import prefilled_nor_control as C
from rcominote.log_stream import Stream

RAM = b"\xa5" * 4095 + b"H"


def fixture(root):
    original, old, _old_baseline, oracles = old_fixture(root)
    baseline = place(echo(C.C.F.DUMP), 20)
    baseline = place(echo(C.C.F.DUMP), 110, initial=baseline)
    source_ops = [*original["groups"][0]["operations"], *original["groups"][1]["operations"]]
    slots, stages, previous = [], [], baseline
    for index, owner in enumerate(source_ops):
        if index % 2 == 0:
            slot = {
                "kind": "prefill",
                "operation_id": "prefill-first" if index == 0 else "prefill-second",
                "name": C.C.F.NAME,
                "dump_command": C.RAM_DUMP,
            }
        else:
            slot = {
                k: owner[k]
                for k in (
                    "operation_id",
                    "nonce",
                    "nor_offset",
                    "uptime_command",
                    "producer",
                    "dump_command",
                    "name",
                )
            }
            slot.update(kind="nor", operation_id="first" if index == 1 else "second")
        slots.append(slot)
        op = copy.deepcopy(owner)
        for key in (
            "nonce",
            "nor_offset",
            "uptime_command",
            "producer",
            "prefix_policy",
            "verification",
            "oracle_verification",
            "producer_attempted",
        ):
            op.pop(key, None)
        op.update(slot)
        op["ram_export_attempted" if slot["kind"] == "prefill" else "producer_attempted"] = True
        stages.append(op)
    oracle = {
        "image": {"file": "/synthetic/image"},
        "image_slice": list(C.RAM_SLICE),
        "cpu_address": C.RAM.ADDRESS,
        "bytes": 4096,
        "sha256": C.A.A.sha(RAM),
        "last_byte": "48",
        "permanent_ram_stability_assumed": False,
    }
    plan = {
        "profile": C.PROFILE,
        "name": C.C.F.NAME,
        "offsets": [0, 0x4200],
        "operations": slots,
        "parent": old["parent"],
        "expected_before": old["expected_before"],
        "ram_oracle": oracle,
        "oracles": oracles,
        "budget": C.BUDGET.copy(),
        "startup_policy": old["startup_policy"],
        "status_event_policy": old["status_event_policy"],
        "content_policy": C.C.F.STRICT_POLICY,
        "planned_at": old["planned_at"],
    }
    actual = {
        k: v
        for k, v in original.items()
        if k not in ("groups", "prefix_policy", "actions_policy", "stage_timeout_scope")
    }
    actual.update({k: plan[k] for k in C.FIELDS})
    actual.update(baseline=copy.deepcopy(original["groups"][0]["baseline"]), operations=stages)
    data = [baseline, RAM, place(chain(slots[1]["nonce"]), 300, initial=baseline), RAM]
    data.append(place(chain(slots[3]["nonce"], 0x4200, bytes(reversed(SECTOR))), 2600, initial=data[2]))
    rows = copy.deepcopy(original["att_packets"])
    discarded = set()
    for op, content in zip([actual["baseline"], *stages], data, strict=True):
        at = 0
        for i in range(op["download_start"], op["download_end"]):
            packet = bytes.fromhex(rows[i]["hex"])
            if packet[:3] == b"\x1b\x2a\0":
                size = len(packet) - 3
                rows[i]["hex"] = (packet[:3] + content[at : at + size]).hex()
                at += size
        assert at == 4096
        if op.get("kind") == "prefill":
            number = -1
            for i in range(op["actions_start"], op["actions_end"]):
                packet = bytes.fromhex(rows[i]["hex"])
                if rows[i]["direction"] == "tx":
                    number += 1
                if number in (2, 3):
                    discarded.add(i)
                elif number == 4 and rows[i]["direction"] == "tx":
                    rows[i]["hex"] = (b"\x12\x16\0" + C.recipe(op)[2]).hex()
    selected = [i for i in range(len(rows)) if i not in discarded]
    mapping = {before: after for after, before in enumerate(selected)}
    raw = (root / "session.btsnoop").read_bytes()
    records, index = [], 0
    for _n, opcode, stamp, packet in C.A.P.records(raw, original["hci_capture"]["records"]):
        if opcode in (4, 5) and int.from_bytes(packet[6:8], "little") == 4:
            row = rows[index]
            discard = index in discarded
            index += 1
            if discard:
                continue
            pdu = bytes.fromhex(row["hex"])
            opcode, packet = fragment(struct.pack("<HH", len(pdu), 4) + pdu, direction=row["direction"])
        records.append(record(packet, opcode, stamp=stamp))
    raw = C.A.P.H.HEADER + b"".join(records)
    (root / "session.btsnoop").write_bytes(raw)
    actual["att_packets"] = [rows[i] for i in selected]
    for n, row in enumerate(actual["att_packets"]):
        row["monotonic_ns"] = n

    def span(value):
        return [mapping[value[0]], mapping[value[1] - 1] + 1]

    actual["after_span"] = span(actual["after_span"])
    for op, content in zip([actual["baseline"], *stages], data, strict=True):
        op["download_start"], op["download_end"] = span([op["download_start"], op["download_end"]])
        op["after_span"] = span(op["after_span"])
        op["verified_end"] = op["after_span"][1]
        op["download_sha256"] = C.A.A.sha(content)
        op["download_verification"] = C.A.A.download(actual, op, content, minimum_start=actual["setup_end"])
        target = root / op["operation_id"]
        target.mkdir()
        (target / "download.bin").write_bytes(content)
        if "actions_start" in op:
            op["actions_start"], op["actions_end"] = span([op["actions_start"], op["actions_end"]])
            op["notifications"] = [
                row["hex"][6:]
                for row in actual["att_packets"][op["actions_start"] : op["actions_end"]]
                if row["hex"].startswith("1b1800")
            ]
            stream = Stream()
            for value in op["notifications"]:
                stream.feed(bytes.fromhex(value))
            op.update(
                frames=stream.frames,
                ack_count=stream.acks,
                pending_hex=stream.pending.hex(),
                end_received=stream.ended,
                writes=[{"hex": p.hex(), "att_write_confirmed": True} for p in C.recipe(op)],
            )
            op["actions_verification"] = C.actions(actual, op)
    observed = C.A.P.inspect(raw, link=actual["transport"]["link"], final=True)
    assert len(observed["transactions"]) == 15 and not observed["pending"]
    actual["hci_capture"] = {"bytes": len(raw), "sha256": C.A.A.sha(raw), "records": observed["records"]}
    actual["att_hci_binding"] = C.A.dual_hci.bind(actual, raw)
    actual["disconnect_observation"]["event"] = observed["disconnects"][0]
    tx, wire = observed["transactions"], C.A.common.wire_positions(actual, raw)
    actual.update(startup_settlement=tx[0], startup_classification=C.C.startup.classify(tx[0]))
    actual["baseline"].update(normalization=tx[1], slow_settlement=tx[2])
    settled, history = tx[2], baseline
    with patch.object(C, "RAM_SHA", C.A.A.sha(RAM)), patch.object(C.C.pins, "oracles", return_value=oracles):
        for index, (op, current) in enumerate(zip(stages, data[1:], strict=True)):
            fast, normal, slow = tx[3 + index * 3 : 6 + index * 3]
            op.update(pre_download_fast=[fast], normalization=normal, slow_settlement=slow)
            op["activity_fast_verification"] = C.A.W.default_activity_fast(actual, op, settled, fast, wire)
            op["verification"] = C.content(op, current, previous, RAM, plan, history)
            if op["kind"] == "nor":
                (root / op["operation_id"] / "sector.bin").write_bytes(
                    bytes.fromhex(op["verification"]["sector_hex"])
                )
                history = current
            previous, settled = current, slow
    for slot in old["pages"]:
        shutil.rmtree(root / slot["directory"])
    (root / "plan.json").write_text(json.dumps(plan))
    actual["plan"] = C.C.J.reference(root, root / "plan.json")
    return actual, plan, baseline, oracles


def validate(root, actual, plan, baseline, oracles, *, ram=RAM):
    with patch.object(C, "RAM_SHA", C.A.A.sha(RAM)), patch.object(C.C.pins, "oracles", return_value=oracles):
        return C.validate(actual, root, plan, baseline, ram)


def test_full_synthetic_wire_has_five_downloads_four_then_six_acks_and_fifteen_transactions(tmp_path):
    actual, plan, baseline, oracles = fixture(tmp_path)
    proof = validate(tmp_path, actual, plan, baseline, oracles)
    assert proof["downloads"] == 5 and proof["parameter_transactions"] == 15
    assert proof["producers"] == proof["ram_exports"] == 2 and proof["sd_writes"] == 4
    assert proof["new_raw_nor_coverage_bytes"] == 0 and proof["content_policy"] == C.C.F.STRICT_POLICY
    assert [op["actions_verification"]["acks"] for op in actual["operations"]] == [4, 6, 4, 6]
    assert actual["operations"][1]["verification"]["freshness"]["historical_dump_spans"]
    assert (
        actual["operations"][3]["verification"]["freshness"]["marker_previous_ring_sha256"]
        == actual["operations"][1]["download_sha256"]
    )
    assert actual["ok"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "wrong-ram-argument",
        "partial-prefill",
        "wrong-prefill",
        "RAM-instead-of-NOR",
        "wrong-history",
        "old-nonce",
        "missing-fast",
        "normalization",
        "state",
        "oracle",
        "original-flag",
        "pending",
        "error",
        "final-identity",
        "prefill-producer",
        "prefill-6ACK",
    ],
)
def test_no_stage_or_whole_control_can_self_certify_bad_evidence(tmp_path, fault):
    actual, plan, baseline, oracles = fixture(tmp_path)
    ram = RAM
    if fault == "wrong-ram-argument":
        ram = b"R" * 4095 + b"H"
    elif fault == "partial-prefill":
        (tmp_path / "prefill-first/download.bin").write_bytes(RAM[:2048])
    elif fault == "wrong-prefill":
        (tmp_path / "prefill-first/download.bin").write_bytes(b"R" * 4095 + b"H")
    elif fault == "RAM-instead-of-NOR":
        (tmp_path / "first/download.bin").write_bytes(RAM)
    elif fault == "wrong-history":
        actual["operations"][3]["verification"]["freshness"]["marker_previous_ring_sha256"] = C.A.A.sha(RAM)
    elif fault == "old-nonce":
        actual["operations"][3]["nonce"] = actual["operations"][1]["nonce"]
    elif fault == "missing-fast":
        actual["operations"][0]["pre_download_fast"] = []
    elif fault == "normalization":
        actual["operations"][1]["normalization"] = {}
    elif fault == "state":
        actual["operations"][1]["before"] = {}
    elif fault == "oracle":
        (tmp_path / "oracle-4200.bin").write_bytes(bytes(512))
    elif fault == "original-flag":
        actual["operations"][3]["live_complete"] = False
    elif fault == "pending":
        actual["operations"][0]["pending_hex"] = "00"
        actual["operations"][0]["notifications"].append("00")
    elif fault == "error":
        actual["capture_error"] = "lost capture"
    elif fault == "final-identity":
        actual["state_verification"] = {}
    elif fault == "prefill-producer":
        actual["operations"][0]["producer_attempted"] = True
    else:
        actual["operations"][0]["actions_verification"]["acks"] = 6
    with pytest.raises((ValueError, KeyError)):
        validate(tmp_path, actual, plan, baseline, oracles, ram=ram)


@pytest.mark.parametrize(
    "fault",
    [
        "offset",
        "same-nonce",
        "old-nonce",
        "RAM-address",
        "NOP",
        "mask",
        "order",
        "bool-budget",
        "bounds",
        "name",
    ],
)
def test_fixed_plan_rejects_expanded_or_mutated_capability_before_source_io(tmp_path, fault):
    _actual, plan, _baseline, oracles = fixture(tmp_path)
    if fault == "offset":
        plan["operations"][3]["nor_offset"] = 0x24400
    elif fault == "same-nonce":
        plan["operations"][3]["nonce"] = plan["operations"][1]["nonce"]
    elif fault == "old-nonce":
        plan["parent"]["prior_names"].append(plan["operations"][1]["nonce"])
    elif fault == "RAM-address":
        plan["operations"][0]["dump_command"] = C.RAM_DUMP.replace("402653184", "402653188")
    elif fault == "NOP":
        plan["operations"][0]["producer"] = "kernel version"
    elif fault == "mask":
        plan["content_policy"] = C.C.F.FORMAT_POLICY
    elif fault == "order":
        plan["operations"][:2] = reversed(plan["operations"][:2])
    elif fault == "bool-budget":
        plan["budget"]["nor_writes"] = False
    elif fault == "bounds":
        plan["ram_oracle"]["bytes"] = 512
    else:
        plan["name"] = "rc0000000000"
    with (
        patch.object(C, "RAM_SHA", C.A.A.sha(RAM)),
        patch.object(C.C.pins, "oracles", return_value=oracles),
        patch.object(C.C, "parent_gate") as parent,
        pytest.raises(ValueError),
    ):
        C.source_gate(plan, None)
    parent.assert_not_called()


def test_failed_whole_control_cannot_be_current_parent(tmp_path):
    actual, _plan, _baseline, _oracles = fixture(tmp_path)
    (tmp_path / "report.json").write_text(json.dumps(actual))
    with pytest.raises(ValueError, match="failed parent"):
        C.C.parent_gate(tmp_path, None)


@pytest.mark.parametrize("v2", [False, True])
def test_full_success_is_distinct_iterative_current_parent_for_future_owned_jobs(tmp_path, v2):
    import test_scratch_reuse_audit as history_fixture
    from test_sd_nor_probe import info

    root, anchor = tmp_path / "control", tmp_path / "anchor"
    with patch.object(history_fixture, "info", return_value=info(9)):
        actual, plan, baseline, oracles = fixture(root)
    if v2:
        from test_prefilled_nor_v2 import upgrade

        with patch.object(C.C.pins, "oracles", return_value=oracles):
            upgrade(root, actual, plan, baseline)
    (anchor / "second").mkdir(parents=True)
    original = {
        "profile": C.C.legacy.PROFILE,
        "ok": True,
        "after": plan["expected_before"],
        "ended_at": plan["parent"]["ended_at"],
    }
    anchor_plan, anchor_proof = {"prior_names": plan["parent"]["prior_names"]}, {"verified": True}
    C.C.S.save(anchor / "report.json", original)
    C.C.S.save(anchor / "plan.json", anchor_plan)
    (anchor / "second/download.bin").write_bytes(baseline)
    (anchor / "session.btsnoop").write_bytes(b"outer historical source fixture")
    pins = {name: C.A.A.sha((anchor / name).read_bytes()) for name in C.C.LEGACY_PINS}
    refs = {name: C.C.pins.pinned(anchor / name, sha)[1] for name, sha in pins.items()}
    plan["parent"] = C.C.source_summary(
        anchor, original, anchor_plan, anchor_proof, baseline, original["after"], refs
    )
    (root / "plan.json").write_text(json.dumps(plan))
    actual["plan"] = C.C.J.reference(root, root / "plan.json")
    actual["verification"] = validate(root, actual, plan, baseline, oracles)
    actual["ok"] = True
    C.C.S.save(root / "report.json", actual)
    with (
        patch.object(C.C, "LEGACY_PINS", pins),
        patch.object(C.C.old, "replay", return_value=anchor_proof),
        patch.object(C.C.pins, "oracles", return_value=oracles),
        patch.object(C, "RAM_SHA", C.A.A.sha(RAM)),
        patch.object(C, "ram_source", return_value=(RAM, plan["ram_oracle"])),
    ):
        current, state, source = C.C.parent_gate(root, None)
        assert current == (root / "second/download.bin").read_bytes()
        assert state == actual["after"] and source["profile"] == plan["profile"]
        assert source["verification"]["content_policy"] == C.C.F.STRICT_POLICY
        assert set(C.nonces(plan)).issubset(source["prior_names"])
        assert C.replay(root, None) == actual["verification"]
        following, previous = C.C.prepare(None, root, [0x26000])
        assert previous == current and C.C.source_gate(following, None) == current
        actual["ok"] = False
        (root / "report.json").write_text(json.dumps(actual))
        with pytest.raises(ValueError, match="failed parent"):
            C.C.parent_gate(root, None)


@pytest.mark.parametrize("fault", [None, "RAM-bytes", "RAM-tail", "copy-code", "copy-literal"])
def test_independent_ram_image_and_initialization_are_checked_before_live_io(tmp_path, fault):
    image = tmp_path / "synthetic-image"
    raw = bytearray(0xE0000)
    raw[slice(*C.RAM_SLICE)] = RAM
    regions = []
    for index, (start, end, _digest) in enumerate(C.COPY_REGIONS):
        data = bytes([index + 1]) * (end - start)
        raw[start:end] = data
        regions.append((start, end, C.A.A.sha(data)))
    if fault == "RAM-bytes":
        raw[C.RAM_SLICE[0]] ^= 1
    elif fault == "RAM-tail":
        raw[C.RAM_SLICE[1] - 1] = 0x47
    elif fault in ("copy-code", "copy-literal"):
        raw[regions[int(fault == "copy-literal")][0]] ^= 1
    image.write_bytes(raw)
    with (
        patch.object(C.C.pins, "pinned", return_value=(bytes(raw), {"file": str(image)})),
        patch.object(C, "RAM_SHA", C.A.A.sha(RAM)),
        patch.object(C, "COPY_REGIONS", tuple(regions)),
    ):
        if fault:
            with pytest.raises(ValueError):
                C.ram_source(image)
        else:
            actual, proof = C.ram_source(image)
            assert actual == RAM and proof["last_byte"] == "48"
            assert proof["permanent_ram_stability_assumed"] is False
            assert len(proof["static_initialization"]) == 2
