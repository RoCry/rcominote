#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer>=0.16,<1"]
# ///
"""Check a physical 4 MiB NOR dump (flashrom / SWD) against the raw bytes already captured over BLE.

Milestone M1 oracle: a dump passes when every retained raw slice matches byte for byte at its
physical address, and both independent dumps are identical. Mapped/decoded images are not used.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence"
NOR_SIZE = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Slice:
    name: str
    offset: int
    path: Path


# Physical address -> retained raw capture. All were read over the firmware's own SPI API and
# paired/independently repeated; see docs/archive/nor-backup-coverage-2026-10-14.md for provenance.
KNOWN_SLICES = (
    Slice("boot0", 0x0000, EVIDENCE / "boot-complete-2026-10-12/raw.bin"),
    Slice("param0", 0x1000, EVIDENCE / "param-slots-2026-10-13/param0-raw.bin"),
    Slice("boot1", 0x2000, EVIDENCE / "final-boot-sector-live-2026-10-14/fw1_boot.bin"),
    Slice("param1", 0x3000, EVIDENCE / "param-slots-2026-10-13/param1-raw.bin"),
    Slice("recovery", 0x4000, EVIDENCE / "recovery-complete-2026-10-13/recovery-raw.bin"),
    Slice(
        "recovery-tail",
        0x13738,
        EVIDENCE / "nor-backup-coverage-2026-10-14/recovery-tail-0x13738-0x13800.bin",
    ),
    Slice("system-first4k", 0x24000, EVIDENCE / "system-first4k-raw-live-2026-10-14/system-first4k-raw.bin"),
    Slice("system-25000", 0x25000, EVIDENCE / "paired-nor25000-four-live-2026-10-14/nor25000-25800.bin"),
    Slice("record-dsp", 0x24D400, EVIDENCE / "record-dsp-complete-2026-10-12/aerecord.dsp"),
)

# From the ACPT partition table read back from the running firmware (docs/partition-readback.md).
PARTITIONS = (
    ("fw0_boot", 0x000000, 0x1000),
    ("fw0_para", 0x001000, 0x1000),
    ("fw1_boot", 0x002000, 0x1000),
    ("fw1_para", 0x003000, 0x1000),
    ("fw0_rec", 0x004000, 0x20000),
    ("fw0_sys", 0x024000, 0x1A5000),
    ("user_rw", 0x1C9000, 0x12000),
    ("fw0_sdfs", 0x1DB000, 0x10000),
    ("nvram_fa0", 0x1EB000, 0x1000),
    ("nvram_fa1", 0x1EC000, 0x2000),
    ("nvram_us", 0x1EE000, 0x2000),
    ("logbuf", 0x1F0000, 0x4000),
    ("evtbuf", 0x1F4000, 0x2000),
    ("coredump", 0x1F6000, 0xA000),
    ("res_a", 0x200000, 0x40000),
    ("sdfs_k", 0x240000, 0xB0000),
    ("fw0_temp", 0x2F0000, 0x100000),
    ("runtimel", 0x3F0000, 0x10000),
)

app = typer.Typer(add_completion=False)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compare_slices(dump: bytes, slices: tuple[Slice, ...] = KNOWN_SLICES) -> list[dict]:
    results = []
    for s in slices:
        expected = s.path.read_bytes()
        actual = dump[s.offset : s.offset + len(expected)]
        first_diff = next((i for i, (a, b) in enumerate(zip(actual, expected, strict=True)) if a != b), None)
        results.append(
            {
                "name": s.name,
                "offset": f"0x{s.offset:06x}",
                "bytes": len(expected),
                "match": first_diff is None,
                "first_diff": None if first_diff is None else f"0x{s.offset + first_diff:06x}",
            }
        )
    return results


def partition_summary(dump: bytes) -> list[dict]:
    rows = []
    for name, offset, size in PARTITIONS:
        chunk = dump[offset : offset + size]
        rows.append(
            {
                "name": name,
                "offset": f"0x{offset:06x}",
                "size": size,
                "ff_ratio": round(chunk.count(0xFF) / size, 4),
                "sha256": sha256(chunk),
            }
        )
    return rows


def verify(dump_a: bytes, dump_b: bytes | None) -> dict:
    if len(dump_a) != NOR_SIZE:
        raise ValueError(f"dump is {len(dump_a)} bytes, expected {NOR_SIZE}")
    ff = dump_a.count(0xFF)
    if ff == NOR_SIZE or dump_a.count(0x00) == NOR_SIZE:
        raise ValueError("dump is uniform 0xFF/0x00: programmer did not read the chip")
    slices = compare_slices(dump_a)
    report = {
        "sha256": sha256(dump_a),
        "ff_ratio": round(ff / NOR_SIZE, 4),
        "known_slices": slices,
        "all_known_match": all(s["match"] for s in slices),
        "partitions": partition_summary(dump_a),
    }
    if dump_b is not None:
        if len(dump_b) != NOR_SIZE:
            raise ValueError(f"second dump is {len(dump_b)} bytes, expected {NOR_SIZE}")
        diff = [i for i in range(0, NOR_SIZE, 4096) if dump_a[i : i + 4096] != dump_b[i : i + 4096]]
        report["second_dump_identical"] = not diff
        report["differing_4k_pages"] = [f"0x{i:06x}" for i in diff[:32]]
    report["ok"] = report["all_known_match"] and report.get("second_dump_identical", True)
    return report


@app.command()
def main(
    dump: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="First full 4 MiB read")],
    second: Annotated[
        Path | None, typer.Argument(exists=True, dir_okay=False, help="Independent second read")
    ] = None,
) -> None:
    """Print a JSON report; exit 1 unless every known slice matches and both reads agree."""
    report = verify(dump.read_bytes(), second.read_bytes() if second else None)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    raise typer.Exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    app()
