"""Offline public parameter gates and complete-data rejection; no private capture fixture."""

import copy
import gzip
import importlib
import json
from pathlib import Path

import pytest
from test_sd_nor_probe import info

from rcominote import protocol as P

RECEIPT = Path("docs/evidence/sd-interval-live-2026-10-14.json")


@pytest.fixture
def verifier(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("tools").resolve()))
    return importlib.import_module("verify_sd_interval")


@pytest.fixture
def public_copy(tmp_path):
    data = json.loads(RECEIPT.read_bytes())
    image = tmp_path / data["image"]["file"]
    image.parent.mkdir(parents=True)
    image.write_bytes((RECEIPT.parent / data["image"]["file"]).read_bytes())
    path = tmp_path / "receipt.json"
    path.write_bytes(RECEIPT.read_bytes())
    return path, data


def test_public_replay_validates_observed45ms_and_explicit_ce_hints(verifier, public_copy):
    path, _data = public_copy
    result = verifier.published(path)[2]
    assert result["baseline_interval_ms"] == 45
    assert result["applied_interval_ms"] == 7.5
    assert result["request_ce_length_hints"] == [1, 1]
    assert result["private_semantic_replay"] is False


@pytest.mark.parametrize("fault", ["ce", "status", "early-disconnect", "decoded", "offline-as-retry"])
def test_resealed_metadata_still_cannot_bypass_event_semantics(verifier, public_copy, monkeypatch, fault):
    path, data = public_copy
    H = verifier.local_module("test_interval_gate", "src/rcominote/experiments/hci_interval.py")
    if fault in ("ce", "status"):
        row = data["parameter_records"][2 if fault == "ce" else 3]
        packet = bytearray.fromhex(row["packet_hex"])
        packet[13 if fault == "ce" else 2] = 2 if fault == "ce" else 1
        row["packet_hex"] = packet.hex()
        row["decoded"] = H.decode(row["monitor_opcode"], bytes(packet)) | {
            "record": row["record"],
            "timestamp_us": row["timestamp_us"],
        }
        if fault == "ce":
            data["experiment"]["actual_hci_request"] = row["decoded"]
    elif fault == "early-disconnect":
        row = data["parameter_records"][-1]
        row["timestamp_us"] = data["experiment"]["download_end_us"] - 1
        row["decoded"]["timestamp_us"] = row["timestamp_us"]
    elif fault == "decoded":
        data["parameter_records"][4]["decoded"]["interval"] = 12
    else:
        data["attempt_accounting"]["device_trials"] = 2
    path.write_text(json.dumps(data))
    monkeypatch.setattr(verifier, "RECEIPT_SHA", verifier.sha(path.read_bytes()))
    with pytest.raises((ValueError, ConnectionError)):
        verifier.published(path)


@pytest.fixture
def transfer_fixture():
    image = gzip.decompress(
        Path("docs/evidence/minimal-image-2026-10-13/original-system.bin.gz").read_bytes()
    )
    oracle = image[0xDD500:0xDE500]
    identity = info()
    report = {"before": identity, "after": copy.deepcopy(identity)}
    packets = []

    def tx(command, payload=b""):
        packets.append(
            {"direction": "tx", "hex": (b"\x52\x22\0" + P.frame(command, payload)).hex(), "hci_records": [1]}
        )

    def rx(command, payload, record=2):
        packets.append(
            {
                "direction": "rx",
                "hex": (b"\x1b\x24\0" + P.frame(command, payload)).hex(),
                "hci_records": [record],
            }
        )

    def identity_cycle():
        for command, payload in [
            (1, b"C261CF0430"),
            (2, b"\0"),
            (5, bytes.fromhex(identity["device"]["raw"])),
        ]:
            tx(command)
            rx(command, payload)

    identity_cycle()
    tx(11, b"rc6ae65544fe".ljust(14, b"\0") + bytes(4))
    rx(11, b"\0\0\0\x10\0", 83)
    offset = 0
    for record, size in zip(range(84, 102), [244, 244, 24] + [244] * 14 + [168], strict=True):
        payload = oracle[offset : offset + size]
        packets.append({"direction": "rx", "hex": (b"\x1b\x2a\0" + payload).hex(), "hci_records": [record]})
        offset += size
    assert offset == 4096
    rx(11, b"\x02", 102)
    identity_cycle()
    return packets, report, oracle


def test_complete_hci_data_requires_declaration_exact_oracle_and_end(verifier, transfer_fixture):
    packets, report, oracle = transfer_fixture
    result = verifier.transfer(P, packets, report, oracle)
    assert (result["notifications"], result["bytes"], result["actions_commands"]) == (18, 4096, 0)


@pytest.mark.parametrize("fault", ["missing244", "changed-byte", "missing-end", "actions", "changed-info"])
def test_full_transfer_summary_cannot_hide_wire_loss_or_writes(verifier, transfer_fixture, fault):
    packets, report, oracle = transfer_fixture
    off = next(i for i, row in enumerate(packets) if row["hex"].startswith("1b2a00"))
    if fault == "missing244":
        packets.pop(off)
    elif fault == "changed-byte":
        packet = bytearray.fromhex(packets[off]["hex"])
        packet[3] ^= 1
        packets[off]["hex"] = packet.hex()
    elif fault == "missing-end":
        packets[:] = [row for row in packets if row["hci_records"] != [102]]
    elif fault == "actions":
        packets.append({"direction": "tx", "hex": "1216001d108105000002002000", "hci_records": [112]})
    else:
        report["after"] = info(free_decrease=1)
    with pytest.raises(ValueError):
        verifier.transfer(P, packets, report, oracle)


def test_readonly_state_rejects_even_consistent_capacity_change(verifier):
    with pytest.raises(ValueError, match="Read-only state changed"):
        verifier.state(P, info(), info(free_decrease=1))
