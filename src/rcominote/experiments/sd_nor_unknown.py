"""One unknown512-byte NOR target at0x2200; repeated acquisition, never an oracle."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from rcominote.experiments import sd_nor_targets as T
from rcominote.experiments.sd_bridge import sector_from_ring
from rcominote.partition_table import inspect_acpt

ACPT_SHA = "a071b0cdafad355eb05a71e96fc2cb6a5348ec8b5e11d0ac4dfe54d83671a144"
PREFIX_SHA = "9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def basis() -> dict:
    analysis = json.loads(Path("docs/evidence/partition-analysis-2026-10-12.json").read_bytes())
    blocks = sorted(
        (int(b["address"], 16), bytes.fromhex(b["hex"]))
        for b in analysis["blocks"]
        if 0x1000040 <= int(b["address"], 16) < 0x1000328
    )
    at, raw = 0x1000040, bytearray()
    for address, data in blocks:
        if address != at:
            raise ValueError("ACPT evidence has a gap or overlap")
        raw.extend(data)
        at += len(data)
    table = inspect_acpt(bytes(raw))
    if sha(raw) != ACPT_SHA or at != 0x1000328:
        raise ValueError("Actual fixed ACPT source changed")
    entry = table["entries"][2]
    if (entry["name"], entry["offset"], entry["size_bytes"], entry["storage_id"], entry["mirror_id"]) != (
        "fw1_boot",
        "0x2000",
        4096,
        0,
        1,
    ):
        raise ValueError("Actual backup boot partition differs")
    prefix = Path("docs/evidence/boot-recovery-prefixes-2026-10-12/backup-boot.bin").read_bytes()
    if len(prefix) != 512 or sha(prefix) != PREFIX_SHA:
        raise ValueError("Previously covered backup-boot prefix changed")
    return {
        "acpt_sha256": ACPT_SHA,
        "entry": entry,
        "previously_covered": [0x2000, 0x2200],
        "prefix_sha256": PREFIX_SHA,
        "new_range": [0x2200, 0x2400],
        "bytes": 512,
    }


def gate(first: Path, second: Path, image: bytes) -> dict:
    result = T.verify_pair(first, second, image)
    refs = []
    for directory in (first, second):
        raw = (directory / "report.json").read_bytes()
        refs.append({"directory": str(directory.resolve()), "report_sha256": sha(raw)})
    return {"first": refs[0], "second": refs[1], "verification": result}


def validate_gate(report: dict, image: bytes) -> None:
    previous = report["known_pair"]
    first, second = Path(previous["first"]["directory"]), Path(previous["second"]["directory"])
    if gate(first, second, image) != previous:
        raise ValueError("Known nonzero pair receipt/hash chain changed")
    if any(report["previous"][key] != previous["first"][key] for key in ("directory", "report_sha256")):
        raise ValueError("Unknown target previous differs from first known-pair parent")
    last = json.loads((second / "report.json").read_bytes())
    if datetime.fromisoformat(last["ended_at"]) > datetime.fromisoformat(report["started_at"]):
        raise ValueError("Unknown acquisition predates known nonzero pair gate")


def payload(report: dict, data: bytes) -> dict:
    T.validate_producer(report)
    if (
        report.get("coverage_basis") != basis()
        or report.get("independent_oracle") is not False
        or report.get("pair_verified") is not False
        or "oracle" in report
    ):
        raise ValueError("Unknown profile must retain coverage basis without claiming an oracle/pair")
    sector = sector_from_ring(
        data, nor_offset=0x2200, producer_command=T.BACKUP_PRODUCER, dump_command=report["dump_command"]
    )
    return {
        "sector_sha256": sha(sector),
        "sector_hex": sector.hex(),
        "verification_level": "complete-single-read-no-independent-oracle",
        "nor_offset": 0x2200,
    }


def verify_pair(first_dir: Path, second_dir: Path, image: bytes) -> dict:
    first, second = T.pair_reports(first_dir, second_dir, image, T.Phase.backup)
    if first["known_pair"] != second["known_pair"]:
        raise ValueError("Unknown pair requires the same verified nonzero gate")
    data = []
    for directory, report in ((first_dir, first), (second_dir, second)):
        verified = payload(report, (directory / "download.bin").read_bytes())
        if verified != report["verification"]:
            raise ValueError("Unknown sector summary differs from retained ring")
        data.append(bytes.fromhex(verified["sector_hex"]))
    if data[0] != data[1]:
        raise ValueError("Independent unknown sector reads conflict; retain both, do not assemble")
    return {
        "nor_offset": 0x2200,
        "bytes": 512,
        "independent_reads": 2,
        "sha256": sha(data[0]),
        "verification_level": "pair-verified",
        "pair_verified": True,
        "independent_oracle": False,
        "acquisitions": [
            {"directory": str(d.resolve()), "report_sha256": sha((d / "report.json").read_bytes())}
            for d in (first_dir, second_dir)
        ],
        "scope": "Only raw0x2200..0x2400; no full backup-boot or recovery claim",
    }
