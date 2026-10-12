"""Actual capture oracle and resume-after-local-corruption failure sequence."""

import asyncio
import shutil
from pathlib import Path

import pytest

from rcominote.archive import nor_export
from rcominote.archive.dsp_export import export
from rcominote.archive.nor_export import collect, verified_block
from rcominote.nor_windows import analyze
from rcominote.printk_tail import NorTarget, block_offset

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/record-dsp-header-2026-10-12/second"


@pytest.mark.parametrize("block", [-1, 216, True, "1"])
def test_recording_file_extent_rejects_invalid_blocks(block):
    with pytest.raises(ValueError, match="NOR block"):
        block_offset(NorTarget.record_dsp, block)


def test_last_file_block_is_inside_known_sdfs_partition():
    # Directory: start0x24d400, length0x1ae44; last512 B read ends0x268400.
    assert block_offset(NorTarget.record_dsp, 215) == 0x268200


def test_other_targets_do_not_allow_arbitrary_offsets():
    with pytest.raises(ValueError, match="NOR block"):
        block_offset(NorTarget.backup_boot, 1)


def test_boot_extent_matches_captured_acpt_partition():
    # Actual fw0_boot: offset0, size0x1000. Eight512-byte blocks only.
    assert block_offset(NorTarget.boot, 7) == 0xE00
    with pytest.raises(ValueError, match="NOR block"):
        block_offset(NorTarget.boot, 8)


def test_resume_rechecks_evidence_and_rejects_corrupted_cached_sector(tmp_path):
    shutil.copytree(EVIDENCE, tmp_path / "attempt-000")
    raw = verified_block(tmp_path, 0)
    assert raw[:28].hex() == "786871790000030100000000000000018e0000001c020000f03e0000"
    (tmp_path / "sector.bin").write_bytes(b"\0" * 512)
    with pytest.raises(ValueError, match="differs from its evidence"):
        verified_block(tmp_path, 0)


def test_wrong_block_evidence_cannot_satisfy_resume(tmp_path):
    shutil.copytree(EVIDENCE, tmp_path / "attempt-000")
    with pytest.raises(ValueError, match="Wrong evidence target/offset"):
        verified_block(tmp_path, 1)


def test_actual_different_blocks_cannot_be_merged():
    third = EVIDENCE.parents[1] / "record-dsp-export-2026-10-12/window-00.json"
    with pytest.raises(ValueError, match="mixed NOR block offsets"):
        analyze([EVIDENCE / "window-00.json", third])


def test_invalid_export_limit_fails_before_creating_directory(tmp_path):
    out = tmp_path / "not-created"
    with pytest.raises(ValueError, match="max-new-blocks"):
        asyncio.run(export(out, serial="not-connected", max_new_blocks=217, attempts=3))
    assert not out.exists()


@pytest.mark.parametrize(
    ("total", "limit", "attempts", "error"),
    [
        (0, 1, 3, "total-blocks"),
        (True, 1, 3, "total-blocks"),
        (9, 1, 3, "NOR block"),
        (1, 2, 3, "max-new-blocks"),
        (1, True, 3, "max-new-blocks"),
        (1, 1, 6, "attempts"),
        (1, 1, True, "attempts"),
    ],
)
def test_collection_limits_fail_before_filesystem_or_capture(tmp_path, total, limit, attempts, error):
    out = tmp_path / "not-created"
    with pytest.raises(ValueError, match=error):
        asyncio.run(
            collect(
                out,
                target=NorTarget.boot,
                total_blocks=total,
                serial="not-connected",
                max_new_blocks=limit,
                attempts=attempts,
            )
        )
    assert not out.exists()


def test_partial_capture_retries_then_resumes_without_device_io(tmp_path, monkeypatch):
    """Real retained windows: first truncated acquisition, then full second acquisition."""
    calls = []

    async def capture(out, target, serial, block):
        calls.append(out.name)
        if len(calls) == 1:
            out.mkdir(exist_ok=False)
            shutil.copyfile(EVIDENCE / "window-00.json", out / "window-00.json")
        else:
            shutil.copytree(EVIDENCE, out)

    monkeypatch.setattr(nor_export, "capture_sector", capture)
    blocks = asyncio.run(
        collect(
            tmp_path,
            target=NorTarget.record_dsp,
            total_blocks=2,
            serial="not-connected",
            max_new_blocks=1,
            attempts=2,
        )
    )
    # Independent published full-file artifact agrees with reconstructed source windows.
    golden = EVIDENCE.parents[1] / "record-dsp-complete-2026-10-12/aerecord.dsp"
    assert blocks == [golden.read_bytes()[:512]]
    assert calls == ["attempt-000", "attempt-001"]

    async def unexpected_capture(*args, **kwargs):
        raise AssertionError("Verified retained evidence must not trigger another acquisition")

    monkeypatch.setattr(nor_export, "capture_sector", unexpected_capture)
    resumed = asyncio.run(
        collect(
            tmp_path,
            target=NorTarget.record_dsp,
            total_blocks=1,
            serial="not-connected",
            max_new_blocks=1,
            attempts=2,
        )
    )
    assert resumed == blocks
