"""Offline provenance of the historical raw0x2000 prefix; never infer other sectors.

Replays22 guarded non-atomic windows, requiring32 rows with independent double
coverage. This is historical per-row evidence, not a modern full-ring pair.
All archive/report/prefix bytes are pinned before parsing; no extraction or I/O
with a device, and no files written.
"""

import hashlib
import json
import tarfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from rcominote import nor_windows

BASE = Path("docs/evidence/boot-recovery-prefixes-2026-10-12")
ARCHIVE = BASE / "windows.tar.gz"
REPORT = BASE / "backup-boot-report.json"
PREFIX = BASE / "backup-boot.bin"
ARCHIVE_SHA = "39cf27f47ed3c7375f9f2c779129cbe92c177678954ed09358fdc63a87ef4509"
REPORT_SHA = "71aec0c983c6ab379c37c14aaf1249b8a17215c1e2c4506377097e68e4c1f4d4"
PREFIX_SHA = "9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d"


@dataclass(frozen=True, slots=True)
class MemoryWindow:
    """Only the read_bytes/string interface used by the existing analyzer."""

    name: str
    raw: bytes

    def read_bytes(self) -> bytes:
        return self.raw

    def __str__(self) -> str:
        return self.name


def pinned(path: Path, expected_sha: str) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha:
        raise ValueError(f"Pinned backup-boot evidence changed: {path}")
    return raw, {"file": str(path), "bytes": len(raw), "sha256": digest}


def verify() -> tuple[bytes, dict]:
    archive, archive_ref = pinned(path=ARCHIVE, expected_sha=ARCHIVE_SHA)
    report_raw, report_ref = pinned(path=REPORT, expected_sha=REPORT_SHA)
    prefix, prefix_ref = pinned(path=PREFIX, expected_sha=PREFIX_SHA)
    if len(prefix) != 512:
        raise ValueError("Historical backup-boot prefix must be exactly512 bytes")
    expected = json.loads(report_raw)
    with tarfile.open(fileobj=BytesIO(archive), mode="r:gz") as tar:
        members = [
            member
            for member in tar.getmembers()
            if member.isfile() and member.name.startswith("backup-boot/") and member.name.endswith(".json")
        ]
        if len(members) != 22 or len({member.name for member in members}) != 22:
            raise ValueError("Requires22 distinct regular backup-boot JSON archive members")
        windows = []
        for member in members:
            stream = tar.extractfile(member)
            if stream is None:
                raise ValueError(f"Missing regular archived window: {member.name}")
            with stream:
                windows.append(MemoryWindow(name=f"{ARCHIVE}!{member.name}", raw=stream.read()))
    observed = nor_windows.analyze(windows)
    required = {
        "target": "backup-boot",
        "producer": "dbg fread spi_flash 0x2000",
        "offset": 0x2000,
        "input_files": 22,
        "distinct_sources": 22,
        "required_rows": 32,
        "observed_rows": 32,
        "confirmed_rows": 32,
        "missing_rows": [],
        "unconfirmed_rows": [],
        "conflicts": [],
        "bytes": 512,
        "sha256": PREFIX_SHA,
    }
    if (
        not isinstance(observed, dict)
        or observed.get("complete") is not True
        or any(observed.get(key) != value for key, value in required.items())
    ):
        raise ValueError("Historical replay lacks complete fixed0x2000 double coverage")
    if observed != expected:
        raise ValueError("Historical replay differs from the complete pinned backup-boot report")
    data = bytes.fromhex(observed["sector_hex"])
    if len(data) != 512 or data != prefix:
        raise ValueError("Reassembled historical sector differs from the original prefix bytes")
    summary = {
        "target": "backup-boot",
        "producer": required["producer"],
        "nor_range": [0x2000, 0x2200],
        "bytes": len(data),
        "sha256": PREFIX_SHA,
        "complete": True,
        "input_windows": len(windows),
        "distinct_sources": observed["distinct_sources"],
        "confirmed_rows": observed["confirmed_rows"],
        "min_sources_per_row": min(row["variants"][0]["sources"] for row in observed["rows"]),
        "source_kind": "Historical guarded non-atomic per-row double coverage",
        "sources": {"archive": archive_ref, "report": report_ref, "prefix": prefix_ref},
    }
    return data, summary
