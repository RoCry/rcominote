"""Private staged backup of actual ACPT ID7; no configuration values on stdout.

Run from repo root: uv run -m rcominote.experiments.factory_rw SYSTEM
artifacts/NEW_DIR --create-sd-files. Default reads two512B segment prefixes.
--complete reuses accepted captures before reading remaining sectors.
--cached-only forbids device I/O. Existing failed captures never auto-retry.
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import typer

from rcominote.experiments.recovery_tail import checked_read, publish
from rcominote.experiments.sd_bridge import SHA, Source
from rcominote.experiments.sd_bridge import main as read_sector
from rcominote.nvram_image import inspect_headers, inspect_region
from rcominote.printk_tail import NorTarget

TARGET = NorTarget.factory_rw


def main(
    image: Path, out: Path, create_sd_files: bool = False, complete: bool = False, cached_only: bool = False
):
    """Read fixed8KiB factory-RW only; retain sensitive captures under ignored artifacts/."""
    private_root = Path(__file__).resolve().parents[3] / "artifacts"
    if not out.resolve().is_relative_to(private_root.resolve()):
        raise typer.BadParameter("Sensitive factory-RW captures must stay under repo artifacts/")
    if not create_sd_files and not cached_only:
        raise typer.BadParameter("Requires --create-sd-files; leaves two4KiB SD files per sector read")
    system = image.read_bytes()
    if hashlib.sha256(system).hexdigest() != SHA:
        raise ValueError("Requires independently verified FW010004 system image")
    if cached_only and not out.is_dir():
        raise FileNotFoundError("Cached capture directory missing; no device I/O")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    report = {
        "started_utc": datetime.now(UTC).isoformat(),
        "scope": "Fixed physical factory-RW only; no NOR writes, runtime selection or restore proof",
        "source_system_sha256": SHA,
        "private": True,
        "requested_complete_region": complete,
        "cached_only": cached_only,
        "completed_pairs": [],
        "new_sector_reads": 0,
        "raw_complete": False,
        "interpretation_complete": False,
    }
    started = time.monotonic()
    data: dict[int, bytes] = {}
    seen_names: set[str] = set()

    def save() -> None:
        report["elapsed_seconds"] = round(time.monotonic() - started, 6)
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    def pair(block: int) -> None:
        results = []
        for attempt in ("a", "b"):
            path = out / f"factory-rw-block-{block}-{attempt}"
            if not path.exists():
                if cached_only:
                    raise FileNotFoundError(f"Cached capture missing: {path}; no device I/O")
                read_sector(
                    image=image,
                    out=path,
                    create_sd_file=True,
                    source=Source.nor_ring,
                    nor_target=TARGET,
                    nor_block=block,
                )
                report["new_sector_reads"] += 1
            results.append(checked_read(path, block, image=system, target=TARGET))
        (first, first_names), (second, second_names) = results
        names = set(first_names + second_names)
        if len(names) != 4 or seen_names & names or first != second:
            raise ValueError(f"factory-RW block{block}: non-independent or conflicting captures")
        seen_names.update(names)
        data[block] = first
        report["completed_pairs"].append({"block": block, "sha256": hashlib.sha256(first).hexdigest()})
        save()
        print(f"Verified factory-RW block{block}/15, two independent reads", flush=True)

    try:
        for block in (0, 8):
            pair(block)
        publish(tuple((out / f"segment-{block // 8}-prefix.bin", data[block]) for block in (0, 8)))
        report["header_verification"] = inspect_headers(data[0], data[8])
        save()
        print("Factory-RW segment header gate passed", flush=True)
        if complete:
            for block in range(16):
                if block not in data:
                    pair(block)
            raw = b"".join(data[block] for block in range(16))
            # Raw backup remains useful even if strict reference interpretation rejects.
            publish(((out / "factory-rw-raw.bin", raw),))
            report["raw_complete"] = True
            report["region_verification"] = inspect_region(raw)
            report["interpretation_complete"] = True
        report["outcome"] = "passed"
    except BaseException as error:
        report |= {"outcome": "failed", "error": f"{type(error).__name__}: {error}"}
        raise
    finally:
        save()


if __name__ == "__main__":
    typer.run(main)
