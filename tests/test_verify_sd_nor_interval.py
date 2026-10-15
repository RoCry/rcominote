"""Offline public NOR evidence rejects row and HCI-condition corruption."""

import copy
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "docs/evidence/sd-nor-interval-live-2026-10-14.json"


@pytest.fixture
def verifier(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    return importlib.import_module("verify_sd_nor_interval")


def test_published_safe_spans_match_existing_boot_oracle(verifier):
    _, result = verifier.published(RECEIPT)
    assert result["boot_sector_bytes"] == 512
    assert result["full_private_audit_replayed"] is False
    assert result["full_nor_backup"] is False


@pytest.mark.parametrize("fault", ["truncated", "shifted-offset", "missing-row", "status-offset"])
def test_bad_nor_rows_cannot_form_complete_sector(verifier, fault):
    data = json.loads(RECEIPT.read_bytes())
    ref = data["phases"]["boot"]["status_and_rows"]
    raw = (RECEIPT.parent / ref["file"]).read_bytes()
    match fault:
        case "truncated":
            raw = raw[:-1]
        case "shifted-offset":
            raw = raw.replace(b"      10:", b"      11:", 1)
        case "missing-row":
            raw = raw[:48] + raw[108:]
        case "status-offset":
            raw = raw.replace(b"offset=0x0", b"offset=0x1", 1)
    with pytest.raises(ValueError):
        verifier.boot_sector(raw)


@pytest.mark.parametrize("fault", ["ce-hints", "interval", "late-update", "second-update"])
def test_selected_hci_gate_rejects_changed_condition(verifier, fault):
    data = json.loads(RECEIPT.read_bytes())
    transport = copy.deepcopy(data["phases"]["boot"]["transport"])
    rows = transport["parameter_records"]
    match fault:
        case "ce-hints":
            packet = bytearray.fromhex(rows[2]["packet_hex"])
            packet[-4:] = b"\2\0\2\0"
            rows[2]["packet_hex"] = packet.hex()
        case "interval":
            packet = bytearray.fromhex(rows[4]["packet_hex"])
            packet[6:8] = b"\7\0"
            rows[4]["packet_hex"] = packet.hex()
        case "late-update":
            transport["download_start_us"] = transport["applied"]["timestamp_us"] - 1
        case "second-update":
            rows.insert(-1, copy.deepcopy(rows[4]))
    with pytest.raises(ValueError):
        verifier.parameters(verifier.parser(), transport)


def test_changed_compact_receipt_fails_before_following_paths(verifier, tmp_path):
    altered = tmp_path / "receipt.json"
    altered.write_bytes(RECEIPT.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Pinned NOR interval receipt changed"):
        verifier.published(altered)
