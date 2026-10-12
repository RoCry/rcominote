"""Target oracle: captured ACPT offsets; real boot captures altered only for rejection tests."""

import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rcominote import diagnostics, printk_tail
from rcominote.cli import app
from rcominote.nor_windows import analyze

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"
BOOT = EVIDENCE / "printk-nor-tail-second-2026-10-12.json"


def save(tmp_path, capture):
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(capture))
    return path


@pytest.mark.parametrize(
    ("target", "offset", "command"),
    [
        ("boot", 0, "dbg fread spi_flash 0"),
        ("backup-boot", 0x2000, "dbg fread spi_flash 0x2000"),
        ("system", 0x24000, "dbg fread spi_flash 0x24000"),
        ("dsp", 0x240000, "dbg fread spi_flash 0x240000"),
        ("record-dsp", 0x24D400, "dbg fread spi_flash 0x24d400"),
        ("record-dsp-header-end", 0x24D600, "dbg fread spi_flash 0x24d600"),
    ],
)
def test_named_targets_use_acpt_offsets_and_explicit_hex(target, offset, command):
    value = printk_tail.NorTarget(target)
    assert printk_tail.TARGET_OFFSETS[value] == offset
    assert [item for item in printk_tail.initial(value) if item.startswith("dbg fread ")] == [command]


def test_actual_legacy_capture_remains_boot():
    report = analyze([BOOT])
    assert (report["target"], report["offset"], report["producer"]) == ("boot", 0, "dbg fread spi_flash 0")


@pytest.mark.parametrize("offset", [0, 0x20000, "0x24000", True])
def test_mismatched_or_untyped_offset_rejected(tmp_path, offset):
    capture = json.loads(BOOT.read_text())
    capture.update(nor_target="system", nor_offset=offset)
    with pytest.raises(ValueError, match="NOR target and offset do not match"):
        analyze([save(tmp_path, capture)])


def test_relabeling_boot_as_system_without_matching_producer_rejected(tmp_path):
    capture = json.loads(BOOT.read_text())
    capture.update(nor_target="system", nor_offset=0x24000)
    with pytest.raises(ValueError, match="exactly one fixed system NOR producer"):
        analyze([save(tmp_path, capture)])


def test_mixed_targets_rejected_even_with_identical_captured_bytes(tmp_path):
    # A relabeled clone must never provide second-source coverage for boot.
    # This deliberately fabricates target metadata to test a rejection path;
    # it provides no evidence that a system read was performed.
    capture = json.loads(BOOT.read_text())
    capture.update(nor_target="system", nor_offset=0x24000)
    capture["fixed_text_commands"] = [
        "dbg fread spi_flash 0x24000" if command == "dbg fread spi_flash 0" else command
        for command in capture["fixed_text_commands"]
    ]
    with pytest.raises(ValueError, match="Cannot assemble mixed NOR targets"):
        analyze([BOOT, save(tmp_path, capture)])


def test_changed_commands_and_target_still_require_actual_shell_output(tmp_path):
    capture = json.loads(BOOT.read_text())
    capture.update(nor_target="system", nor_offset=0x24000)
    capture["fixed_text_commands"] = [
        "dbg fread spi_flash 0x24000" if command == "dbg fread spi_flash 0" else command
        for command in capture["fixed_text_commands"]
    ]
    with pytest.raises(ValueError, match="Captured NOR producer status/echo does not match"):
        analyze([save(tmp_path, capture)])


def test_non_tail_profile_refuses_nondefault_target_before_connection():
    with pytest.raises(ValueError, match="NOR target is only available with printk-nor-tail"):
        asyncio.run(
            diagnostics.capture_profile(diagnostics.Profile.logs, "not-connected", 1, nor_target="dsp")
        )


def test_arbitrary_cli_target_refused_before_connection(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "diag",
            "capture",
            "printk-nor-tail",
            "--out",
            str(tmp_path / "none.json"),
            "--nor-target",
            "0x24000",
        ],
    )
    assert result.exit_code == 2 and "Invalid value for '--nor-target'" in result.output
