"""Acquire only the two actual4KiB boot parameter slots, with a staged CRC gate.

Run: uv run -m rcominote.experiments.param_slots SYSTEM NEW_DIR --create-sd-files
Default: two1KiB prefixes. --complete revalidates retained captures and, only
after prefix acceptance, acquires remaining bytes. --cached-only forbids device
I/O. Failed captures never retry.
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
from rcominote.printk_tail import NorTarget

TARGETS = (NorTarget.param0, NorTarget.param1)


def main(
    image: Path, out: Path, create_sd_files: bool = False, complete: bool = False, cached_only: bool = False
):
    """Back up fixed boot metadata; never enter recovery, run uploaded code or write NOR."""
    if not create_sd_files and not cached_only:
        raise typer.BadParameter("Requires --create-sd-files; leaves two4KiB SD files per sector read")
    system = image.read_bytes()
    if hashlib.sha256(system).hexdigest() != SHA:
        raise ValueError("Requires independently verified FW010004 system image")
    if cached_only and not out.is_dir():
        raise FileNotFoundError("Cached capture directory does not exist; no device I/O")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "started_utc": datetime.now(UTC).isoformat(),
        "scope": "Physical boot parameter slots only; no execution, NOR write or restoration proof",
        "source_system_sha256": SHA,
        "requested_complete_slots": complete,
        "cached_only": cached_only,
        "completed_pairs": [],
        "new_sector_reads": 0,
        "complete": False,
    }
    started = time.monotonic()
    data: dict[NorTarget, dict[int, bytes]] = {target: {} for target in TARGETS}
    seen_names: set[str] = set()

    def save() -> None:
        report["elapsed_seconds"] = round(time.monotonic() - started, 6)
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    def pair(target: NorTarget, block: int) -> None:
        results = []
        for attempt in ("a", "b"):
            path = out / f"{target}-block-{block}-{attempt}"
            if not path.exists():
                if cached_only:
                    raise FileNotFoundError(f"Cached capture missing: {path}; no device I/O")
                read_sector(
                    image=image,
                    out=path,
                    create_sd_file=True,
                    source=Source.nor_ring,
                    nor_target=target,
                    nor_block=block,
                )
                report["new_sector_reads"] += 1
            results.append(checked_read(path, block, image=system, target=target))
        (first, first_names), (second, second_names) = results
        names = set(first_names + second_names)
        if len(names) != 4 or seen_names & names or first != second:
            raise ValueError(f"{target} block{block}: non-independent or conflicting captures")
        seen_names.update(names)
        data[target][block] = first
        report["completed_pairs"].append(
            {"target": target, "block": block, "sha256": hashlib.sha256(first).hexdigest()}
        )
        save()
        print(f"Verified {target} block{block}/7, two independent reads", flush=True)

    try:
        for target in TARGETS:
            for block in range(2):
                pair(target, block)
        prefixes = [b"".join(data[target][block] for block in range(2)) for target in TARGETS]
        publish(
            tuple(
                (out / f"{target}-prefix-raw.bin", raw) for target, raw in zip(TARGETS, prefixes, strict=True)
            )
        )
        # Import here allows capture-only tooling inspection without a parser import.
        from rcominote.param_image import inspect_slots

        report["prefix_verification"] = inspect_slots(*prefixes)
        save()
        print("Both parameter prefixes interpreted; staged CRC gate passed", flush=True)
        if complete:
            for target in TARGETS:
                for block in range(2, 8):
                    pair(target, block)
            raw_slots = [b"".join(data[target][block] for block in range(8)) for target in TARGETS]
            report["slot_verification"] = inspect_slots(*raw_slots)
            publish(
                tuple(
                    (out / f"{target}-raw.bin", raw) for target, raw in zip(TARGETS, raw_slots, strict=True)
                )
            )
            report["complete"] = True
        report["outcome"] = "passed"
    except BaseException as error:
        report |= {"outcome": "failed", "error": f"{type(error).__name__}: {error}"}
        raise
    finally:
        save()


if __name__ == "__main__":
    typer.run(main)
