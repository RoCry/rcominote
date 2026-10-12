"""Acquire only the missing fixed recovery tail, with paired independent reads."""

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL
from rcominote.code_guards import observed_block
from rcominote.experiments.sd_bridge import SHA, Source, require_idle, ring_rows, sector_from_ring
from rcominote.experiments.sd_bridge import main as read_sector
from rcominote.log_stream import Stream
from rcominote.printk_ring import BUFFER
from rcominote.printk_ring import GUARDS as RING_GUARDS
from rcominote.printk_state import GUARDS as STATE_GUARDS
from rcominote.printk_tail import GUARDS as FREAD_GUARDS
from rcominote.printk_tail import RECOVERY_BYTES, NorTarget, block_offset, producer
from rcominote.recovery_image import verify

PREFIX = Path("docs/evidence/recovery-raw-prefix-2026-10-12.bin")
PREFIX_SHA = "20a8547720d14eb92339643f48e93ce5248023e142457990076f95eca03a63e8"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_read(path: Path, block: int, *, image: bytes) -> tuple[bytes, tuple[str, str]]:
    report = json.loads((path / "report.json").read_text())
    baseline = json.loads((path / "baseline/report.json").read_text())
    for record in (baseline, report):
        for field in ("before", "after"):
            identity = record[field]
            if identity["serial"] != OWNED_SERIAL:
                raise ValueError(f"Capture identity differs: {path}")
            require_idle(identity)
        expected_path = f"/SD:/RECORDER/Call-{record['name']}.mp3"
        if (
            re.fullmatch(r"rc[0-9a-f]{10}", record["name"]) is None
            or record["device_path"] != expected_path
            or record["dump_command"] != f"dbg dumpbuf {BUFFER} 4096 {expected_path}"
        ):
            raise ValueError(f"Capture filename/command identity differs: {path}")
        if not record["ok"] or not record["log_session_complete"]:
            raise ValueError(f"Incomplete capture: {path}")
        if (
            record["source_image_sha256"] != SHA
            or record["source"] != Source.nor_ring
            or record["nor_target"] != NorTarget.recovery
            or record["nor_block"] != block
            or record["nor_offset"] != block_offset(NorTarget.recovery, block)
            or record["producer"] != producer(NorTarget.recovery, block)
        ):
            raise ValueError(f"Capture target/provenance differs: {path}")
        commands = record["fixed_text_commands"]
        reads = [command for command in commands if command.startswith("dbg fread ")]
        if reads != ([] if record.get("phase") == "baseline" else [record["producer"]]):
            raise ValueError(f"Unexpected producer sequence: {path}")
        stream = Stream()
        for frame in record["frames"]:
            stream.feed(bytes.fromhex(frame["hex"]))
        if (
            stream.frames != record["frames"]
            or not stream.ended
            or stream.pending
            or stream.acks != len(commands) + 3
        ):
            raise ValueError(f"Invalid frame/ACK/STOP/F1 record: {path}")
        ranges = [(0x10000000, 32), (0x10024A20, 64), (0x10024A60, 64), (0x10024AA0, 32)]
        ranges.extend(
            (address, len(bytes.fromhex(value)))
            for address, value in (*RING_GUARDS, *STATE_GUARDS, *FREAD_GUARDS)
        )
        for address, length in ranges:
            for offset in range(0, length, 16):
                count = min(16, length - offset)
                index = address + offset - 0x10000000
                if observed_block(stream.frames, address + offset, count) != image[index : index + count]:
                    raise ValueError(f"Capture code/header guard differs at {address + offset:#x}: {path}")
    before = (path / "baseline/download.bin").read_bytes()
    if digest(before) != baseline["download_sha256"] or len(before) != 4096:
        raise ValueError(f"Baseline bytes differ: {path}")
    if baseline["dump_command"].encode() not in before * 2 or any(
        0 <= start < 4096 for start, *_ in ring_rows(before)
    ):
        raise ValueError(f"Baseline is stale or contains old NOR rows: {path}")
    if (
        report["baseline"]["download_sha256"] != digest(before)
        or report["baseline"]["device_path"] != baseline["device_path"]
    ):
        raise ValueError(f"Baseline provenance link differs: {path}")
    raw = (path / "download.bin").read_bytes()
    if digest(raw) != report["download_sha256"]:
        raise ValueError(f"Downloaded bytes differ: {path}")
    sector = sector_from_ring(
        raw,
        nor_offset=report["nor_offset"],
        producer_command=report["producer"],
        dump_command=report["dump_command"],
    )
    if sector != (path / "sector.bin").read_bytes() or digest(sector) != report["sector_sha256"]:
        raise ValueError(f"Sector bytes differ: {path}")
    return sector, (baseline["name"], report["name"])


def publish(outputs: tuple[tuple[Path, bytes], ...]) -> None:
    for path, data in outputs:
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"Existing verified image differs: {path}")
    for path, data in outputs:
        if path.exists():
            continue
        descriptor, temporary_name = tempfile.mkstemp(prefix=".verified-", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, path)  # Atomic creation; never replace an existing output.
        finally:
            temporary.unlink()


def main(image: Path, out: Path, create_sd_files: bool = False):
    if not create_sd_files:
        raise typer.BadParameter("Requires --create-sd-files; leaves two4KiB SD files per read")
    system = image.read_bytes()
    if digest(system) != SHA:
        raise ValueError("Requires the fixed independent FW010004 system image")
    prefix = PREFIX.read_bytes()
    if digest(prefix) != PREFIX_SHA or len(prefix) != 48128:
        raise ValueError("Independent94-block recovery prefix changed")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "scope": "Complete recovery acquisition/checksum only; no execution, NOR write or restore proof",
        "prefix_sha256": PREFIX_SHA,
        "completed_pairs": [],
        "complete": False,
    }
    started = time.monotonic()
    tail = {}
    try:
        # Known boundary first; acquire the missing handoff's region early.
        for block in (93, *range(112, 124), *range(94, 112)):
            results = []
            for attempt in ("a", "b"):
                path = out / f"block-{block:03d}-{attempt}"
                if not path.exists():
                    read_sector(
                        image=image,
                        out=path,
                        create_sd_file=True,
                        source=Source.nor_ring,
                        nor_target=NorTarget.recovery,
                        nor_block=block,
                    )
                results.append(checked_read(path, block, image=system))
            (first, first_names), (second, second_names) = results
            if len(set(first_names + second_names)) != 4 or first != second:
                raise ValueError(f"Recovery block{block} has non-independent or conflicting reads")
            if block == 93 and first != prefix[-512:]:
                raise ValueError("Boundary control differs from independent known recovery block93")
            tail[block] = first
            report["completed_pairs"].append({"block": block, "sha256": digest(first)})
            print(f"Verified recovery block{block}/123, pair SHA256 {digest(first)}", flush=True)
            report["elapsed_seconds"] = time.monotonic() - started
            (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        raw = (prefix + b"".join(tail[block] for block in range(94, 124)))[:RECOVERY_BYTES]
        plain, verification = verify(raw)
        # Publish complete images only after the independent header/body checksum gate.
        publish(((out / "recovery-raw.bin", raw), (out / "recovery-decoded.bin", plain)))
        report.update(verification, complete=True, image_bytes=len(raw))
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    typer.run(main)
