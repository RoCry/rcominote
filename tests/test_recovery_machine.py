"""Independent oracle: actual shipped checker instructions and captured system bytes."""

import gzip
import hashlib
import json
import runpy
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

ORACLE = runpy.run_path("tools/check_recovery_image.py")
CHECK = ORACLE["check_image"]
MODEL_ERROR = ORACLE["ModelError"]
EVIDENCE = Path("docs/evidence/minimal-image-2026-10-13")
RECOVERY = Path("docs/evidence/recovery-complete-2026-10-13/recovery-decoded.bin").read_bytes()


@pytest.fixture(scope="module")
def original():
    data = gzip.decompress((EVIDENCE / "original-system.bin.gz").read_bytes())
    # Fixed independently acquired system, before this emulator existed.
    if hashlib.sha256(data).hexdigest() != "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f":
        raise ValueError("Captured system oracle changed")
    return data


def test_captured_original_is_admitted(original):
    result = CHECK(RECOVERY, original)
    assert (result["rc"], result["entry_out"], result["global_sp"]) == (0, "0x1002d819", "0x1002b40")


@pytest.mark.parametrize(
    ("offset", "expected_rc", "entry_out"),
    [(-1, -15, "0x1002d819"), (0x10, -14, "0x1002d819"), (0x204, -12, "0x1100000f")],
    ids=["body-failure-overwrites-entry", "header-failure-overwrites-entry", "even-entry-preserves-output"],
)
def test_actual_rejections_and_output_lifetime(original, offset, expected_rc, entry_out):
    damaged = bytearray(original)
    damaged[offset] ^= 1
    result = CHECK(RECOVERY, bytes(damaged))
    assert (result["rc"], result["entry_out"]) == (expected_rc, entry_out)


def test_missing_real_byte_is_model_failure_not_zero_padded_checksum_result(original):
    with pytest.raises(MODEL_ERROR, match="Out-of-contract read"):
        CHECK(RECOVERY, original[:-1])


def test_compiler_produced_m4_fixture_passes_shipped_gate():
    result = CHECK(RECOVERY, (EVIDENCE / "minimal-acth.bin").read_bytes())
    # Entry from independently linked GNU Arm ELF, not the wrapping function.
    assert (result["rc"], result["entry_out"]) == (0, "0x10000341")


def test_rejected_image_makes_cli_fail_with_machine_result(tmp_path):
    damaged = bytearray((EVIDENCE / "minimal-acth.bin").read_bytes())
    damaged[0x204] ^= 1
    candidate = tmp_path / "even-entry.bin"
    candidate.write_bytes(damaged)
    app = typer.Typer()
    app.command()(ORACLE["main"])
    result = CliRunner().invoke(
        app,
        ["docs/evidence/recovery-complete-2026-10-13/recovery-decoded.bin", str(candidate)],
    )
    assert (result.exit_code, json.loads(result.stdout)["rc"]) == (1, -12)
