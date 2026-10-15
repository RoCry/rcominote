"""Offline contract for six fixed fw1_boot tail sectors; no device operations.

Each sector requires two new producer executions and the shared complete
Actions/Boyi/HCI/identity audit. This module parses single observations only;
it neither pairs them nor treats previously observed FF bytes as a new oracle.
"""

import secrets
from pathlib import Path

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import dual_interval as condition
from rcominote.experiments import dual_nor_probe as session
from rcominote.experiments import dual_unknown_pair as unknown_pair
from rcominote.experiments import sd_nor_probe as probe
from rcominote.experiments import sd_nor_unknown as unknown
from rcominote.experiments.nor_freshness import parse_ring

PROFILE = "fixed-fw1-boot-tail-pair"
OFFSETS = tuple(range(0x2400, 0x3000, 512))
PHASE = "backup-boot-tail"
PARENT_SHA = "77f75c84d50e1f03b1a698ac1cd610f897a0242d07d7a600463ec8dbcd1822b0"
PARENT_HCI_SHA = "6cb3671a79982b7bdb4f2de0374d8d42dbc1ed540e6f48cfc1ed30021d8ad184"
CHUNK = Path("docs/evidence/dual-unknown2200-2026-10-14/sector.bin")
CHUNK_SHA = "9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d"


def offset_gate(offset: int) -> None:
    if type(offset) is not int or offset not in OFFSETS:
        raise ValueError("Requires one fixed aligned fw1_boot tail offset0x2400..0x2e00")


def parent_gate(directory: Path, image: Path) -> dict:
    receipt = (directory / "report.json").read_bytes()
    capture = (directory / "session.btsnoop").read_bytes()
    if session.audit.sha(receipt) != PARENT_SHA or session.audit.sha(capture) != PARENT_HCI_SHA:
        raise ValueError("Requires the exact successful early raw0x2200 pair parent")
    result = unknown_pair.replay(directory, image)
    return {
        "directory": str(directory.resolve()),
        "report_sha256": PARENT_SHA,
        "hci_sha256": PARENT_HCI_SHA,
        "verification": result,
    }


def coverage_basis() -> dict:
    previous = unknown.basis()  # Actual ACPT fw1_boot entry and pinned original prefix.
    chunk = CHUNK.read_bytes()
    if len(chunk) != 512 or session.audit.sha(chunk) != CHUNK_SHA:
        raise ValueError("Published raw0x2200 chunk changed; no tail coverage inferred")
    return {
        "acpt_sha256": previous["acpt_sha256"],
        "entry": previous["entry"],
        "previously_covered": [0x2000, 0x2400],
        "prefix_sha256": previous["prefix_sha256"],
        "chunk2200": {"path": str(CHUNK), "bytes": 512, "sha256": CHUNK_SHA},
        "new_range": [OFFSETS[0], OFFSETS[-1] + 512],
        "bytes": len(OFFSETS) * 512,
        "independent_oracle": False,
    }


def recipe(report: dict) -> None:
    if report.get("profile") != PROFILE or report.get("serial") != OWNED_SERIAL:
        raise ValueError("Wrong fixed boot-tail profile or owned serial")
    if report.get("transport", {}).get("policy") != condition.POLICY:
        raise ValueError("Boot-tail requires the fixed early normalization policy")
    common_recipe(report)


def common_recipe(report: dict) -> None:
    """Shared physical target/producer constraints; no transport policy adapter."""
    if report.get("serial") != OWNED_SERIAL:
        raise ValueError("Wrong owned serial for fixed boot-tail target")
    offset_gate(report.get("nor_offset"))
    if (
        report.get("source_image_sha256") != probe.IMAGE_SHA
        or report.get("coverage_basis") != coverage_basis()
        or report.get("independent_oracle") is not False
        or "oracle" in report
    ):
        raise ValueError("Boot-tail source, ACPT basis or no-oracle contract changed")
    operations = report["operations"]
    if len(operations) != 2 or [op.get("operation_id") for op in operations] != ["first", "second"]:
        raise ValueError("Requires exactly first then second independent boot-tail executions")
    for operation in operations:
        if (
            operation.get("phase") != PHASE
            or operation.get("producer") != f"dbg fread spi_flash {hex(report['nor_offset'])}"
            or operation.get("source_address") != hex(probe.BUFFER)
            or type(operation.get("source_bytes")) is not int
            or operation["source_bytes"] != 4096
            or operation.get("transport_profile") != "interval6-ce1"
            or operation.get("independent_oracle") is not False
            or operation.get("pair_verified") is not False
            or "oracle" in operation
        ):
            raise ValueError(
                "Only exact fixed-sector producer, ring4096 and unpaired/no-oracle reads permitted"
            )
        probe.command(operation, probe.BUFFER, 4096)
    if operations[0]["name"] == operations[1]["name"]:
        raise ValueError("Independent producers require different new SD paths/nonces")


def prepare(image: Path, parent_dir: Path, offset: int) -> dict:
    offset_gate(offset)
    data = image.read_bytes()
    if len(data) != 927632 or session.audit.sha(data) != probe.IMAGE_SHA:
        raise ValueError("Requires fixed complete FW010004 system image")
    parent = parent_gate(parent_dir, image)
    operations = []
    for operation_id in ("first", "second"):
        name = "rc" + secrets.token_hex(5)
        path = f"/SD:/RECORDER/Call-{name}.mp3"
        operations.append(
            {
                "operation_id": operation_id,
                "phase": PHASE,
                "name": name,
                "device_path": path,
                "source_address": hex(probe.BUFFER),
                "source_bytes": 4096,
                "dump_command": f"dbg dumpbuf {probe.BUFFER} 4096 {path}",
                "producer": f"dbg fread spi_flash {hex(offset)}",
                "transport_profile": "interval6-ce1",
                "independent_oracle": False,
                "pair_verified": False,
                "sd_write_attempted": False,
                "ok": False,
            }
        )
    report = {
        "profile": PROFILE,
        "started_at": session.now(),
        "serial": OWNED_SERIAL,
        "source_image_sha256": probe.IMAGE_SHA,
        "parent": parent,
        "coverage_basis": coverage_basis(),
        "nor_offset": offset,
        "independent_oracle": False,
        "pair_verified": False,
        "policy": "Two fresh executions of one fixed fw1_boot tail sector; early6/0/500 before identity/Actions",
        "operations": operations,
        "ok": False,
        "transport": {"update_attempted": False, "policy": condition.POLICY},
    }
    recipe(report)
    return report


def payload(report: dict, operation: dict, ring: bytes) -> dict:
    recipe(report)
    return parse_payload(report, operation, ring)


def parse_payload(report: dict, operation: dict, ring: bytes, *, allow_composer_fps2: bool = False) -> dict:
    """Parse a member operation after its caller validates the complete recipe."""
    operations = report["operations"]
    index = 0 if operation.get("operation_id") == "first" else 1
    if operation != operations[index]:
        raise ValueError("Payload operation differs from its actual fixed-sector session recipe")
    sector, freshness = parse_ring(
        ring,
        nor_offset=report["nor_offset"],
        producer_command=operation["producer"],
        dump_command=operation["dump_command"],
        previous_dump=operations[0]["dump_command"] if index else None,
        allow_composer_fps2=allow_composer_fps2,
    )
    return {
        "sector_sha256": session.audit.sha(sector),
        "sector_hex": sector.hex(),
        "verification_level": "fresh-complete-single-read-no-independent-oracle",
        "nor_offset": report["nor_offset"],
        "freshness": freshness,
    }
