"""Fixed0x4200 receipt extension; share boot receipt parsers, never device I/O."""

import json
import re
from datetime import datetime
from pathlib import Path

from verify_sd_nor_interval import (
    RECEIPT_SHA as BOOT_RECEIPT_SHA,
)
from verify_sd_nor_interval import (
    parameters,
    parser,
    sector_rows,
    state,
)
from verify_sd_nor_interval import (
    published as boot_published,
)
from verify_sd_nor_progress import raw_file, require, sha

RECEIPT_SHA = "f5e59a7a24c8da64ba1c12976e69a39196a69028755439d01f5209c442e74490"
RAW_SHA = "14a899d181c38430931649169671a4812fa44e7a32978f2c3beded51472b1a01"
SECTOR_SHA = "51327e9d7a7d8d4c3538c83688753b5f99735b85e981756effb63efd1dc33713"
PRODUCER = "dbg fread spi_flash 0x4200"


def published(receipt: Path) -> tuple[dict, dict]:
    raw = receipt.read_bytes()
    require(sha(raw) == RECEIPT_SHA, "Pinned fixed0x4200 receipt changed")
    data = json.loads(raw)
    require(
        (data["schema"], data["target"], data["serial"]) == (2, "recovery-block1", "C261CF0430"),
        "Wrong fixed nonzero target/schema",
    )
    parent_ref = data["boot_parent_bundle"]
    require(parent_ref["sha256"] == BOOT_RECEIPT_SHA, "Wrong boot parent receipt")
    parent, _ = boot_published(receipt.parent / parent_ref["file"])
    oracle_ref = data["oracle"]
    require(
        oracle_ref["bytes"] == 63288
        and oracle_ref["sha256"] == RAW_SHA
        and oracle_ref["slice"] == [512, 1024]
        and oracle_ref["slice_sha256"] == SECTOR_SHA,
        "Wrong complete raw recovery oracle/slice",
    )
    oracle = raw_file(receipt.parent, oracle_ref)[512:1024]
    require(len(oracle) == 512 and sha(oracle) == SECTOR_SHA, "Raw recovery oracle slice changed")
    observations = data["observations"]
    require(len(observations) == 2, "Requires two independent observations")
    H = parser()
    samples = []
    sectors = []
    for row in observations:
        require(
            row["phase"] == "recovery-block1"
            and row["original_ok"] is True
            and row["producer"] == PRODUCER
            and row["source_address"] == "0x1803ee09"
            and row["source_bytes"] == 4096
            and row["full_ring_published"] is False,
            "Wrong fixed producer/ring/status",
        )
        require(
            row["previous_report_sha256"] == parent["phases"]["boot"]["source_report"]["sha256"],
            "Observation lacks independently verified boot parent",
        )
        require(
            row["actions"]
            == {"confirmed_writes": 5, "ack_count": 5, "f1_received": True, "pending_bytes": 0},
            "Incomplete compact producer Actions proof",
        )
        state(row["state"], write=True)
        parameters(H, row["transport"], early_stop=True)
        state(row["transport"]["state_verification"], write=False)
        require(
            row["download"]["bytes"] == 4096
            and row["sector"]["bytes"] == 512
            and row["sector"]["sha256"] == SECTOR_SHA,
            "Incomplete full ring/sector receipt",
        )
        require(
            re.fullmatch(
                r"dbg dumpbuf 402910729 4096 /SD:/RECORDER/Call-rc[0-9a-f]{10}\.mp3", row["dump_command"]
            ),
            "Wrong fixed ring export command",
        )
        from verify_sd_nor_interval import marker

        marker(raw_file(receipt.parent, row["producer_marker"]), PRODUCER)
        marker(raw_file(receipt.parent, row["dump_marker"]), row["dump_command"])
        sector = sector_rows(raw_file(receipt.parent, row["status_and_rows"]), 0x4200)
        require(sector == oracle, "Nonzero NOR sector differs from complete independent oracle")
        sectors.append(sector)
        spans = [row[key]["ring_span"] for key in ("status_and_rows", "producer_marker", "dump_marker")]
        require(
            all(0 <= start < end <= 4096 for start, end in spans)
            and spans[0][1] <= spans[1][0] < spans[1][1] <= spans[2][0],
            "Status/rows/producer/current-marker bounds changed",
        )
        for key in ("status_and_rows", "producer_marker", "dump_marker"):
            sample = row[key]
            require(
                sample["ring_span"][1] - sample["ring_span"][0] == sample["bytes"],
                "Selected span size differs",
            )
            samples.append(sample)
    first, second = observations
    require(
        sectors[0] == sectors[1]
        and first["dump_command"] != second["dump_command"]
        and first["source_report"]["file"] != second["source_report"]["file"]
        and first["source_report"]["sha256"] != second["source_report"]["sha256"]
        and first["download"]["file"] != second["download"]["file"]
        and first["transport"]["hci_capture"]["sha256"] != second["transport"]["hci_capture"]["sha256"]
        and datetime.fromisoformat(first["ended_at"]) <= datetime.fromisoformat(second["started_at"])
        and first["transport"]["download_end_us"] < second["transport"]["update_requested_us"],
        "Pair lacks independently ordered producer/file/transport identities",
    )
    require(
        data["pair"] == {"nor_offset": 0x4200, "bytes": 512, "independent_reads": 2, "sha256": SECTOR_SHA}
        and data["new_sd_files"] == 2
        and data["retained_sd_test_files_total"] == 47
        and sum(s["bytes"] for s in samples) == data["public_new_raw_bytes"] == 4194,
        "Wrong fixed pair/public/residue summary",
    )
    return data, {
        "compact_public_replay_verified": True,
        "nor_offset": "0x4200",
        "unique_sector_bytes": 512,
        "independent_reads": 2,
        "sector_sha256": SECTOR_SHA,
        "public_new_raw_bytes": 4194,
        "full_private_audit_replayed": False,
        "full_nor_backup": False,
    }


def private_pair(data: dict, root: Path) -> int:
    from rcominote.experiments import sd_nor_targets as targets

    directories = [root / row["source_report"]["file"] for row in data["observations"]]
    result = targets.verify_pair(
        directories[0].parent,
        directories[1].parent,
        (root / "artifacts/mapped-system-20261012.bin").read_bytes(),
    )
    require(result == data["pair"], "Full private pair semantic result differs")
    return len(data["private_sources"])
