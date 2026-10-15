"""One owned connection, exactly two fresh raw0x2200 reads; no oracle or bulk API."""

import asyncio
import json
import secrets
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import typer

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import dual_interval as condition
from rcominote.experiments import dual_nor_probe as session
from rcominote.experiments import sd_nor_probe as probe
from rcominote.experiments import sd_nor_targets as targets
from rcominote.experiments import sd_nor_unknown as unknown
from rcominote.experiments.hci_interval_io import authorize
from rcominote.experiments.hci_monitor import Snoop

PROFILE = condition.EARLY_PROFILE
PARENT_SHA = "0f74ac3023f5635740e214ecc9b05bc5b84153dee89c5bb8d2c3201c1c28985d"
PARENT_HCI_SHA = "fec7195c55d2df3ebe583a08357e54881e89f5115c5faa49ab6cab10284050ff"


def parent_gate(directory: Path, image: Path) -> dict:
    receipt = (directory / "report.json").read_bytes()
    capture = (directory / "session.btsnoop").read_bytes()
    if session.audit.sha(receipt) != PARENT_SHA or session.audit.sha(capture) != PARENT_HCI_SHA:
        raise ValueError("Requires the exact successful known-target dual session")
    result = session.replay(directory, image)
    return {
        "directory": str(directory.resolve()),
        "report_sha256": PARENT_SHA,
        "hci_sha256": PARENT_HCI_SHA,
        "verification": result,
    }


def operation_fields(operation: dict) -> None:
    if operation.get("operation_id") not in ("first", "second"):
        raise ValueError("Requires distinct fixed first/second operation IDs")
    if (
        operation.get("phase") != targets.Phase.backup
        or operation.get("producer") != targets.BACKUP_PRODUCER
        or operation.get("source_address") != hex(probe.BUFFER)
        or operation.get("source_bytes") != 4096
        or operation.get("transport_profile") != "interval6-ce1"
        or operation.get("independent_oracle") is not False
        or operation.get("pair_verified") is not False
        or "oracle" in operation
    ):
        raise ValueError("Only fixed raw0x2200 single-read observations without an oracle are permitted")
    probe.command(operation, probe.BUFFER, 4096)
    targets.validate_producer(operation)


def recipe(report: dict) -> None:
    if report.get("profile") != PROFILE or report.get("serial") != OWNED_SERIAL:
        raise ValueError("Wrong unknown-pair profile or owned serial")
    if report.get("transport", {}).get("policy") != condition.POLICY:
        raise ValueError("Unknown-pair requires explicit early6/0/500 normalization")
    if report.get("coverage_basis") != unknown.basis() or report.get("independent_oracle") is not False:
        raise ValueError("Actual ACPT coverage basis changed or an unknown oracle was claimed")
    operations = report["operations"]
    if len(operations) != 2 or [op.get("operation_id") for op in operations] != ["first", "second"]:
        raise ValueError("Requires exactly first then second raw0x2200 operations")
    for operation in operations:
        operation_fields(operation)
    if operations[0]["name"] == operations[1]["name"]:
        raise ValueError("Independent producers require different new SD paths/nonces")


def prepare(image: Path, known_parent: Path) -> dict:
    data = image.read_bytes()
    if len(data) != 927632 or session.audit.sha(data) != probe.IMAGE_SHA:
        raise ValueError("Requires fixed complete FW010004 system image")
    parent = parent_gate(known_parent, image)
    operations = []
    for operation_id in ("first", "second"):
        name = "rc" + secrets.token_hex(5)
        path = f"/SD:/RECORDER/Call-{name}.mp3"
        operations.append(
            {
                "operation_id": operation_id,
                "phase": targets.Phase.backup,
                "name": name,
                "device_path": path,
                "source_address": hex(probe.BUFFER),
                "source_bytes": 4096,
                "dump_command": f"dbg dumpbuf {probe.BUFFER} 4096 {path}",
                "producer": targets.BACKUP_PRODUCER,
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
        "coverage_basis": unknown.basis(),
        "independent_oracle": False,
        "pair_verified": False,
        "policy": "Two independent producer executions, early6/0/500 before identity and first Actions",
        "operations": operations,
        "ok": False,
        "transport": {"update_attempted": False, "policy": condition.POLICY},
    }
    recipe(report)
    return report


def payload(report: dict, operation: dict, ring: bytes) -> dict:
    from rcominote.experiments.nor_freshness import parse_ring

    recipe(report)
    operation_fields(operation)
    operations = report["operations"]
    index = 0 if operation["operation_id"] == "first" else 1
    if operation != operations[index]:
        raise ValueError("Payload operation differs from its actual session recipe")
    previous = operations[0]["dump_command"] if index else None
    sector, freshness = parse_ring(
        ring,
        nor_offset=0x2200,
        producer_command=targets.BACKUP_PRODUCER,
        dump_command=operation["dump_command"],
        previous_dump=previous,
    )
    return {
        "sector_sha256": session.audit.sha(sector),
        "sector_hex": sector.hex(),
        "verification_level": "fresh-complete-single-read-no-independent-oracle",
        "nor_offset": 0x2200,
        "freshness": freshness,
    }


def compare_pair(report: dict, directory: Path, *, validate=recipe, parse=payload) -> dict:
    validate(report)
    if report.get("final_audit_complete") is not True or any(
        value for key, value in report.items() if key.endswith("error")
    ):
        raise ValueError("Final session identity/state/HCI audit must pass without errors before pairing")
    sectors, offsets = [], []
    first, second = report["operations"]
    if not first.get("live_complete") or not second.get("live_complete"):
        raise ValueError("Both independent executions must finish their actual barriers")
    if first["verified_end"] > second["actions_start"]:
        raise ValueError("Independent producer execution spans overlap")
    for operation in (first, second):
        if operation.get("ok") is not True:
            raise ValueError("Both full Actions/Boyi/HCI/identity audits must pass before pairing")
        path = directory / session.operation_directory(operation)
        ring = probe.downloaded(operation, path, 4096)
        observed = parse(report, operation, ring)
        if observed != operation["verification"]:
            raise ValueError("Fresh raw observation differs from retained complete ring")
        sector = bytes.fromhex(observed["sector_hex"])
        if (path / "sector.bin").read_bytes() != sector:
            raise ValueError("Retained512-byte sector differs from original ring rows")
        sectors.append(sector)
        offsets.append(observed["nor_offset"])
    if offsets[0] != offsets[1]:
        raise ValueError("Independent reads target different NOR offsets")
    if sectors[0] != sectors[1]:
        raise ValueError("Two fresh raw reads conflict; retain both, do not assemble")
    return {
        "pair_verified": True,
        "independent_oracle": False,
        "independent_producer_executions": 2,
        "connections": 1,
        "nor_range": [offsets[0], offsets[0] + 512],
        "bytes": 512,
        "sha256": session.audit.sha(sectors[0]),
    }


def replay(directory: Path, image: Path) -> dict:
    report = json.loads((directory / "report.json").read_bytes())
    if (
        report.get("ok") is not True
        or report.get("pair_verified") is not True
        or any(value for key, value in report.items() if key.endswith("error"))
        or not all(op.get("ok") is True for op in report["operations"])
    ):
        raise ValueError("Original unknown-pair session did not fully pass; keep failures unchanged")
    recipe(report)
    if report["source_image_sha256"] != probe.IMAGE_SHA:
        raise ValueError("Source image identity changed")
    parent = parent_gate(Path(report["parent"]["directory"]), image)
    if parent != report["parent"]:
        raise ValueError("Successful dual parent chain changed")
    original_parent = json.loads((Path(parent["directory"]) / "report.json").read_bytes())
    if datetime.fromisoformat(original_parent["ended_at"]) > datetime.fromisoformat(report["started_at"]):
        raise ValueError("Unknown acquisition predates its successful dual parent")
    raw = (directory / "session.btsnoop").read_bytes()
    parser = Snoop()
    parser.feed(raw, final=True)
    expected = {"bytes": len(raw), "sha256": session.audit.sha(raw), "records": parser.records}
    if report["hci_capture"] != expected:
        raise ValueError("Unknown-pair full HCI capture changed")
    session.finalize(report, directory, SimpleNamespace(path=directory / "session.btsnoop", snoop=parser))
    result = compare_pair(report, directory)
    if report.get("pair_verification") != result:
        raise ValueError("Pair summary differs from two complete fresh observations")
    return result


def main(image: Path, known_parent: Path, new_out: Path, sudo_password_stdin: bool = False) -> None:
    report = prepare(image, known_parent)
    new_out.mkdir(parents=True, exist_ok=False, mode=0o700)
    for operation in report["operations"]:
        (new_out / session.operation_directory(operation)).mkdir(mode=0o700)
    try:
        authorize(password_stdin=sudo_password_stdin)
        asyncio.run(session.capture(report, new_out))
        report["pair_verification"] = compare_pair(report, new_out)
        report["pair_verified"] = True
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = session.now()
        session.save(new_out / "report.json", report)
    print(json.dumps({"ok": True, "pair_verified": True, "new_verified_bytes": 512}))


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
