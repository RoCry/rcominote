"""Two known raw NOR targets and one unknown512 profile; no arbitrary/bulk interface."""

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from rcominote.printk_ring import BUFFER

BOOT_SHA = "72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec"
PRODUCER = "dbg fread spi_flash 0"
RECOVERY_PRODUCER = "dbg fread spi_flash 0x4200"
BACKUP_PRODUCER = "dbg fread spi_flash 0x2200"
RECOVERY_RAW = Path("docs/evidence/recovery-complete-2026-10-13/recovery-raw.bin")
RECOVERY_SHA = "14a899d181c38430931649169671a4812fa44e7a32978f2c3beded51472b1a01"
RECOVERY_BLOCK_SHA = "51327e9d7a7d8d4c3538c83688753b5f99735b85e981756effb63efd1dc33713"


class Phase(StrEnum):
    context = "context"
    baseline = "baseline"
    boot = "boot"
    recovery = "recovery-block1"
    backup = "backup-boot-block1"


class Transport(StrEnum):
    natural = "natural"
    interval = "interval6-ce1"


PRODUCER_PHASES = (Phase.boot, Phase.recovery, Phase.backup)
PARENT_PHASE = {
    Phase.baseline: Phase.context,
    Phase.boot: Phase.baseline,
    Phase.recovery: Phase.boot,
    Phase.backup: Phase.recovery,
}


def producer(phase: str) -> str:
    return {Phase.boot: PRODUCER, Phase.recovery: RECOVERY_PRODUCER, Phase.backup: BACKUP_PRODUCER}[
        Phase(phase)
    ]


def validate_producer(report: dict) -> None:
    command = report.get("producer")
    if command is None:
        if report.get("phase") in PRODUCER_PHASES:
            raise ValueError("Fixed NOR phase requires its producer")
        return
    phase = Phase(report.get("phase", Phase.boot))
    expected = producer(phase) if phase in PRODUCER_PHASES else None
    if command != expected:
        raise ValueError(
            "Only exact boot0 producer or explicit recovery-block1/backup-boot-block1 profile is permitted"
        )
    if phase in (Phase.recovery, Phase.backup):
        name = report["name"]
        path = f"/SD:/RECORDER/Call-{name}.mp3"
        if (
            report.get("transport_profile") != Transport.interval
            or report.get("source_address") != hex(BUFFER)
            or report.get("source_bytes") != 4096
            or not re.fullmatch(r"rc[0-9a-f]{10}", name)
            or report.get("device_path") != path
            or report.get("dump_command") != f"dbg dumpbuf {BUFFER} 4096 {path}"
        ):
            raise ValueError("Nonzero fixed NOR profile requires fixed ring/nonce/interval profile")


def oracle(phase: str) -> tuple[int, bytes, dict]:
    phase = Phase(phase)
    if phase == Phase.boot:
        raw = Path("docs/evidence/boot-complete-2026-10-12/raw.bin").read_bytes()[:512]
        if len(raw) != 512 or hashlib.sha256(raw).hexdigest() != BOOT_SHA:
            raise ValueError("Boot0 independent oracle changed")
        return 0, raw, {"sector_sha256": BOOT_SHA}
    if phase != Phase.recovery:
        raise ValueError("No raw NOR oracle for nonproducer phase")
    raw = RECOVERY_RAW.read_bytes()
    if len(raw) != 63288 or hashlib.sha256(raw).hexdigest() != RECOVERY_SHA:
        raise ValueError("Complete raw recovery oracle changed")
    data = raw[512:1024]
    if hashlib.sha256(data).hexdigest() != RECOVERY_BLOCK_SHA:
        raise ValueError("Raw recovery-block1 oracle changed")
    return (
        0x4200,
        data,
        {
            "path": str(RECOVERY_RAW),
            "bytes": 63288,
            "sha256": RECOVERY_SHA,
            "slice": [512, 1024],
            "nor_offset": 0x4200,
            "sector_sha256": RECOVERY_BLOCK_SHA,
        },
    )


def pair_reports(first_dir: Path, second_dir: Path, image: bytes, phase: Phase) -> tuple[dict, dict]:
    """Internal offline replay and identity gate; caller checks expected phase content."""
    from rcominote.experiments import sd_nor_probe as probe

    first, _ = probe.load(first_dir)
    second, _ = probe.load(second_dir)
    refs = first["guards"]
    parents = [Path(r["write_parent"]["directory"]) for r in refs if r.get("write_parent")]
    if len(parents) > 1:
        raise ValueError("Unexpected guard parent chain")
    handler = parents[0] if parents else None
    guards = probe.validate_guards([Path(r["directory"]) for r in refs], image, handler)
    for directory in (first_dir, second_dir):
        probe.previous(directory, phase, guards, image, handler)
    for report in (first, second):
        if report.get("phase") != phase or report.get("ok") is not True:
            raise ValueError("Pair requires two successful fixed-profile trials")
        validate_producer(report)
    if first["name"] == second["name"] or first["previous"] != second["previous"]:
        raise ValueError("Pair requires two new SD files and the same verified boot parent")
    if datetime.fromisoformat(first["ended_at"]) > datetime.fromisoformat(second["started_at"]):
        raise ValueError("Pair producer acquisitions must be independently ordered")
    if first["transport"]["update_requested_us"] >= second["transport"]["update_requested_us"]:
        raise ValueError("Pair transport acquisition identities are not independent")
    return first, second


def verify_pair(first_dir: Path, second_dir: Path, image: bytes) -> dict:
    """Offline known-oracle pair gate; no device access or automatic acquisitions."""
    first, second = pair_reports(first_dir, second_dir, image, Phase.recovery)
    expected = oracle(Phase.recovery)[1]
    if any(bytes.fromhex(r["verification"]["sector_hex"]) != expected for r in (first, second)):
        raise ValueError("Pair differs from complete independent raw oracle")
    return {"nor_offset": 0x4200, "bytes": 512, "independent_reads": 2, "sha256": RECOVERY_BLOCK_SHA}


def prepare(
    report: dict, image: bytes, previous_path: Path | None, handler: Path | None, second: Path | None
) -> None:
    """All parent/oracle checks precede authorization and device I/O."""
    from rcominote.experiments import sd_nor_probe as probe

    phase = Phase(report["phase"])
    if second is not None and phase != Phase.backup:
        raise ValueError("Known-pair second parent is only for backup-boot-block1")
    if phase == Phase.context:
        if previous_path is not None:
            raise ValueError("Context phase does not accept --previous")
        return
    if previous_path is None:
        raise ValueError("Requires independently completed --previous phase")
    report["previous"] = probe.previous(previous_path, PARENT_PHASE[phase], report["guards"], image, handler)
    if phase not in PRODUCER_PHASES:
        return
    report["producer"] = producer(phase)
    if report["transport_profile"] == Transport.interval:
        parent, _ = probe.load(previous_path)
        if parent.get("transport_profile") != Transport.interval:
            raise ValueError("Interval producer requires an independently successful interval parent")
    if phase == Phase.backup:
        from rcominote.experiments import sd_nor_unknown as unknown

        if second is None:
            raise ValueError("Backup-block1 requires --known-pair-second")
        report.update(
            coverage_basis=unknown.basis(),
            known_pair=unknown.gate(previous_path, second, image),
            independent_oracle=False,
            pair_verified=False,
            acquisition_level="single-complete-read",
        )
        unknown.validate_gate(report, image)
    else:
        report["oracle"] = oracle(phase)[2]
