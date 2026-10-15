"""Offline fixed-target, fresh same-address pair and immutable failure gates."""

import copy
import gzip
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import dual_unknown_pair as U
from rcominote.experiments import sd_nor_targets as T

PREFIX = b"\r\n[logsrv][I][679]: "


def echo(command):
    return f"logsrv: cmd({len(command) + 1}) {command}\n\r\n".encode()


def isolated_ring(operation, sector, *, previous=None):
    # Explicit synthetic ring: no runtime/private bytes are claimed here.
    status = b"\r\nfread 512b: offset=0x2200, buf=0x18010000\r\n"
    rows = b"".join(
        (f"{i:8x}: " + "".join(f"{b:2x} " for b in sector[i : i + 16]) + "\r\n").encode()
        for i in range(0, 512, 16)
    )
    body = status + b"\r\n" * 3 + rows + PREFIX + echo(T.BACKUP_PRODUCER)
    body += b"\n" + PREFIX + echo(operation["dump_command"])
    if previous:
        body = echo(previous) + bytes(100) + body
    return body.ljust(4096, b"\0")


def report_fixture():
    operations = []
    for index, operation_id in enumerate(("first", "second")):
        name = f"rc{index:010x}"
        path = f"/SD:/RECORDER/Call-{name}.mp3"
        operations.append(
            {
                "operation_id": operation_id,
                "phase": T.Phase.backup,
                "name": name,
                "device_path": path,
                "source_address": hex(S.probe.BUFFER),
                "source_bytes": 4096,
                "dump_command": f"dbg dumpbuf {S.probe.BUFFER} 4096 {path}",
                "producer": T.BACKUP_PRODUCER,
                "transport_profile": "interval6-ce1",
                "independent_oracle": False,
                "pair_verified": False,
                "ok": True,
                "live_complete": True,
                "actions_start": 10 + index * 50,
                "verified_end": 50 + index * 50,
            }
        )
    return {
        "profile": U.PROFILE,
        "serial": S.OWNED_SERIAL,
        "transport": {"policy": U.condition.POLICY},
        "coverage_basis": U.unknown.basis(),
        "independent_oracle": False,
        "final_audit_complete": True,
        "operations": operations,
    }


def save_pair(directory, report, sectors):
    for index, (operation, sector) in enumerate(zip(report["operations"], sectors, strict=True)):
        previous = report["operations"][0]["dump_command"] if index else None
        ring = isolated_ring(operation, sector, previous=previous)
        target = directory / S.operation_directory(operation)
        target.mkdir()
        (target / "download.bin").write_bytes(ring)
        (target / "sector.bin").write_bytes(sector)
        operation.update(download_bytes=4096, received_bytes=4096, download_sha256=S.audit.sha(ring))
        operation["verification"] = U.payload(report, operation, ring)


def test_same_phase_uses_two_distinct_directories_and_fresh_observations(tmp_path):
    report = report_fixture()
    sector = bytes(range(256)) * 2  # Do not presume unknown storage is allFF.
    save_pair(tmp_path, report, (sector, sector))
    verified = U.compare_pair(report, tmp_path)
    assert verified["pair_verified"] and verified["bytes"] == 512
    assert verified["independent_oracle"] is False
    assert [op["pair_verified"] for op in report["operations"]] == [False, False]
    assert (tmp_path / "first/sector.bin").read_bytes() == sector
    assert (tmp_path / "second/sector.bin").read_bytes() == sector


def test_fresh_complete_conflicting_reads_never_assemble(tmp_path):
    report = report_fixture()
    save_pair(tmp_path, report, (bytes(512), bytes([1]) * 512))
    with pytest.raises(ValueError, match="conflict"):
        U.compare_pair(report, tmp_path)
    assert len(list(tmp_path.glob("*/sector.bin"))) == 2


@pytest.mark.parametrize("fault", ["final_audit_complete", "error", "after_error", "final_evidence_error"])
def test_pair_helper_rejects_failed_or_unfinished_final_audit(tmp_path, fault):
    report = report_fixture()
    report[fault] = False if fault == "final_audit_complete" else "original failure"
    with pytest.raises(ValueError, match="Final session"):
        U.compare_pair(report, tmp_path)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("producer", "dbg fread spi_flash 0x2400"),
        ("operation_id", "../first"),
        ("phase", "boot"),
        ("source_bytes", 512),
        ("independent_oracle", True),
        ("pair_verified", True),
        ("oracle", {"sector_sha256": "0" * 64}),
    ],
)
def test_wrong_target_or_single_read_promotion_rejected(key, value):
    report = report_fixture()
    report["operations"][0][key] = value
    with pytest.raises(ValueError):
        U.recipe(report)


def test_duplicate_file_and_phase_directory_alias_rejected():
    report = report_fixture()
    report["operations"][1] = copy.deepcopy(report["operations"][0]) | {"operation_id": "second"}
    with pytest.raises(ValueError, match="different new SD"):
        U.recipe(report)
    with pytest.raises(ValueError, match="directory"):
        S.operation_directory({"phase": "backup-boot-block1"})


def test_second_requires_first_marker_and_cannot_reuse_first_ring():
    report = report_fixture()
    first, second = report["operations"]
    with pytest.raises(ValueError):
        U.payload(report, second, isolated_ring(first, bytes(512)))
    with pytest.raises(ValueError):
        U.payload(report, second, isolated_ring(second, bytes(512)))


def test_prepare_wrong_image_never_checks_parent_or_authorizes(tmp_path):
    image = tmp_path / "image.bin"
    image.write_bytes(b"wrong")
    with patch.object(U, "parent_gate") as parent, pytest.raises(ValueError, match="complete FW"):
        U.prepare(image, tmp_path)
    parent.assert_not_called()


def test_wrong_parent_hash_never_replays_private_chain(tmp_path):
    (tmp_path / "report.json").write_bytes(b"{}")
    (tmp_path / "session.btsnoop").write_bytes(b"wrong")
    with patch.object(S, "replay") as replay, pytest.raises(ValueError, match="exact successful"):
        U.parent_gate(tmp_path, tmp_path)
    replay.assert_not_called()


def test_prepare_nonce_collision_fails_without_regeneration(tmp_path):
    raw = gzip.decompress(Path("docs/evidence/minimal-image-2026-10-13/original-system.bin.gz").read_bytes())
    image = tmp_path / "image.bin"
    image.write_bytes(raw)
    with (
        patch.object(U, "parent_gate", return_value={"verified": True}),
        patch.object(U.secrets, "token_hex", return_value="0000000000") as nonce,
        pytest.raises(ValueError, match="different new SD"),
    ):
        U.prepare(image, tmp_path)
    assert nonce.call_count == 2


@pytest.mark.parametrize("fault", ["session_failed", "pair_missing", "operation_failed", "after_error"])
def test_failed_original_cannot_be_reclassified(tmp_path, fault):
    report = report_fixture() | {"ok": True, "pair_verified": True}
    if fault == "session_failed":
        report["ok"] = False
    elif fault == "pair_missing":
        report["pair_verified"] = False
    elif fault == "operation_failed":
        report["operations"][1]["ok"] = False
    else:
        report["after_error"] = "original failure"
    original = json.dumps(report).encode()
    (tmp_path / "report.json").write_bytes(original)
    with patch.object(U, "parent_gate") as parent, pytest.raises(ValueError, match="Original"):
        U.replay(tmp_path, tmp_path)
    parent.assert_not_called()
    assert (tmp_path / "report.json").read_bytes() == original
