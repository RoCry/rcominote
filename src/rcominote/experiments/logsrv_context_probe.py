"""Two separate small SD snapshots: fixed logsrv pointer, then bounded context32.

No arbitrary address, producer, slot read, mdb, MMIO write or mode selection.
The second read follows a historical pointer; alignment/RAM bounds do not establish
current allocator ownership. Sampling emits logs; the saved bytes precede STOP.
"""

import asyncio
import gzip
import json
import secrets
import struct
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import sd_bootstrap
from rcominote.experiments.sd_nor_probe import (
    IMAGE_SHA,
    command,
    downloaded,
    load,
    same_identity,
    sha,
    validate_actions,
)

GLOBAL = 0x1800A9AC
PUBLIC_RECEIPT_SHA = "90473a21b77b898c9e96b449208ab409bb831b03684e21f6e7d3c63bbcca3051"
RAM_START, RAM_END, OBJECT_BYTES = 0x18003CA0, 0x18045250, 80
GUARDS = {
    0x10000000: 32,
    0x10024A20: 160,
    0x1000BF82: 32,
    0x1000C0C8: 16,
    0x1009AA24: 48,
}


class Phase(StrEnum):
    pointer = "pointer"
    context = "context"


def pointer(data: bytes) -> int:
    if len(data) != 4:
        raise ValueError("Pointer snapshot must contain exactly4 bytes")
    value = int.from_bytes(data, "little")
    if value % 4 or not RAM_START <= value <= RAM_END - OBJECT_BYTES:
        raise ValueError("Pointer outside aligned initialized RAM/object80 bound; no dereference")
    return value


def context_fields(data: bytes) -> dict:
    """Decode historical bytes only; rd/wr are uint8 counters, not slot indices.

    Bytes9/26:28 are padding; stream pointer is reported without following it.
    Length<=504 checks structural plausibility, not allocation ownership, atomicity
    or slot-body freshness. STOP later clears metadata, not the saved SD snapshot.
    """
    if len(data) != 32:
        raise ValueError("Context snapshot must contain exactly32 bytes")
    lengths = list(struct.unpack_from("<8H", data, 10))
    if any(length > 504 for length in lengths):
        raise ValueError("Context slot length exceeds audited504-byte capacity")
    return {
        "stream_pointer": hex(int.from_bytes(data[:4], "little")),
        "flags_byte": data[4],
        "log_type": data[5],
        "new_log_type": data[6],
        "rd": data[7],
        "wr": data[8],
        "slot_lengths": lengths,
        "drop_count": int.from_bytes(data[28:32], "little"),
        "interpretation": "Historical pre-STOP bytes; no atomicity/current pointer/partial-slot claim",
    }


def replay_public(receipt: Path) -> dict:
    """Offline compact replay using tracked bytes/image; no private report or I/O.

    Full ATT/state checks occurred against private original reports before export.
    This function replays their pinned compact receipt and public byte oracles.
    """

    def check(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)

    raw = receipt.read_bytes()
    check(sha(raw) == PUBLIC_RECEIPT_SHA, "Pinned logsrv compact receipt changed")
    data = json.loads(raw)
    check(data["serial"] == OWNED_SERIAL, "Wrong owned identity")
    image = gzip.decompress((receipt.parent / data["image"]["file"]).read_bytes())
    check(
        len(image) == data["image"]["decompressed_bytes"] == 927632
        and sha(image) == data["image"]["decompressed_sha256"] == IMAGE_SHA,
        "Wrong full image oracle",
    )

    def sample(row: dict) -> bytes:
        value = (receipt.parent / row["raw"]["file"]).read_bytes()
        size = row["bytes"] if "bytes" in row else row["source_bytes"]
        check(len(value) == row["raw"]["bytes"] == size, "Wrong public sample size")
        check(sha(value) == row["raw"]["sha256"], "Public sample hash mismatch")
        return value

    guards = data["guards"]
    check(
        len(guards) == 5 and {int(row["address"], 16): row["bytes"] for row in guards} == GUARDS,
        "Wrong fixed guard profile",
    )
    for row in guards:
        offset = int(row["address"], 16) - 0x10000000
        check(sample(row) == image[offset : offset + row["bytes"]], "Live guard differs from image")
        check(
            (row["write_parent"] is not None) == row["download_only"] == (row["address"] == "0x10024a20"),
            "Wrong handler parent binding",
        )
    report_hashes = [row["source_report"]["sha256"] for row in guards]
    for row in guards + [data["pointer"], data["context"]]:
        check(
            row["original_ok"] is True
            and row["actions"]
            == {
                "confirmed_writes": 4,
                "ack_count": 4,
                "f1_received": True,
                "pending_bytes": 0,
                "sequence": "PREPARE,START,one fixed dumpbuf,STOP",
            },
            "Incomplete compact Actions proof",
        )
        state = row["state"]
        check(
            state["other_state_equal"] is True
            and state["free_capacity_before"] - state["free_capacity_after"]
            == state["free_capacity_decrease"]
            and 0 <= state["free_capacity_decrease"] <= state["allowed_decrease"] <= 1,
            "Unexpected compact state comparison",
        )
    pointer_row, context_row = data["pointer"], data["context"]
    value = pointer(sample(pointer_row))
    check(
        pointer_row["source_address"] == hex(GLOBAL)
        and pointer_row["source_bytes"] == 4
        and pointer_row["fields"] == {"pointer": hex(value), "allocation_bound_bytes": OBJECT_BYTES},
        "Wrong bounded global pointer",
    )
    check(
        context_row["source_address"] == hex(value)
        and context_row["source_bytes"] == 32
        and context_row["pointer_parent_sha256"] == pointer_row["source_report"]["sha256"],
        "Wrong context pointer-parent binding",
    )
    fields = context_fields(sample(context_row))
    check(fields == context_row["fields"], "Context fields differ from original32 bytes")
    for row in (pointer_row, context_row):
        check(
            row["guard_report_sha256"] == report_hashes
            and row["snapshot_before_stop"] is True
            and row["download_reused"] is False,
            "Wrong historical snapshot/guard contract",
        )
    check(data["public_new_raw_bytes"] == 32 + 16 + 48 + 4 + 32 == 132, "Wrong public raw count")
    return {
        "compact_public_replay_verified": True,
        "private_packet_audit_rerun": False,
        "pointer": hex(value),
        "context_fields": fields,
        "new_public_bytes": 132,
        "historical_context_only": True,
    }


def validate_guards(directories: list[Path], image: bytes, handler_parent: Path | None) -> list[dict]:
    if len(image) != 927632 or sha(image) != IMAGE_SHA:
        raise ValueError("Wrong independently verified FW010004 image")
    if len(directories) != len(GUARDS) or len({p.resolve() for p in directories}) != len(GUARDS):
        raise ValueError("Requires five distinct complete fixed code-guard directories")
    verified, seen, names = [], set(), set()
    for directory in directories:
        report, raw = load(directory)
        address = int(report["source_address"], 16)
        size = GUARDS.get(address)
        if (
            size is None
            or address in seen
            or report["name"] in names
            or report["serial"] != OWNED_SERIAL
            or report["source_image_sha256"] != IMAGE_SHA
            or report["source_bytes"] != size
            or report.get("ok") is not True
            or report.get("error")
            or report.get("tail_only")
        ):
            raise ValueError("Guard is not one complete owned fixed code range")
        seen.add(address)
        names.add(report["name"])
        command(report, address, size)
        same_identity(report)
        oracle = image[address - 0x10000000 : address - 0x10000000 + size]
        if downloaded(report, directory, size) != oracle or report["expected_sha256"] != sha(oracle):
            raise ValueError("Live code guard differs from pinned image")
        parent_link = None
        if report.get("download_only"):
            if address != 0x10024A20 or handler_parent is None or report["sd_write_attempted"] is not False:
                raise ValueError("Read-only handler requires explicit write parent")
            if any(k in report for k in ("att_packets", "writes", "notifications", "frames", "producer")):
                raise ValueError("Read-only handler cannot contain Actions evidence")
            parent, parent_raw = load(handler_parent)
            if (
                sha(parent_raw) != report["parent_report_sha256"]
                or any(
                    parent[k] != report[k]
                    for k in (
                        "name",
                        "dump_command",
                        "device_path",
                        "serial",
                        "source_image_sha256",
                        "source_address",
                        "source_bytes",
                    )
                )
                or parent.get("sd_write_attempted") is not True
            ):
                raise ValueError("Handler write parent hash/source mismatch")
            same_identity(parent)
            validate_actions(parent)
            parent_link = {"directory": str(handler_parent.resolve()), "report_sha256": sha(parent_raw)}
        else:
            if report["sd_write_attempted"] is not True:
                raise ValueError("Guard must retain its SD write evidence")
            validate_actions(report)
        verified.append(
            {
                "address": hex(address),
                "bytes": size,
                "directory": str(directory.resolve()),
                "report_sha256": sha(raw),
                "write_parent": parent_link,
            }
        )
    return sorted(verified, key=lambda row: row["address"])


def previous(directory: Path, guards: list[dict]) -> dict:
    report, raw = load(directory)
    if (
        report.get("phase") != Phase.pointer
        or report.get("ok") is not True
        or report.get("error")
        or report.get("previous") is not None
        or report.get("download_only")
        or report.get("download_reused")
        or report["serial"] != OWNED_SERIAL
        or report["source_image_sha256"] != IMAGE_SHA
        or report["source_address"] != hex(GLOBAL)
        or report["source_bytes"] != 4
        or report["sd_write_attempted"] is not True
        or report["guards"] != guards
    ):
        raise ValueError("Requires complete independent pointer phase with identical guards")
    command(report, GLOBAL, 4)
    same_identity(report)
    validate_actions(report)
    value = pointer(downloaded(report, directory, 4))
    if report["verification"] != {"pointer": hex(value), "allocation_bound_bytes": OBJECT_BYTES}:
        raise ValueError("Pointer verification summary differs from raw4 bytes")
    return {"directory": str(directory.resolve()), "report_sha256": sha(raw), "pointer": hex(value)}


def request(report: dict) -> tuple[int, int]:
    if report.get("producer") is not None or report.get("download_only") or report.get("tail_only"):
        raise ValueError("Only one fixed dumpbuf snapshot is permitted")
    if report["phase"] == Phase.pointer and report.get("previous") is None:
        address, size = GLOBAL, 4
    elif report["phase"] == Phase.context:
        address, size = pointer(int(report["previous"]["pointer"], 16).to_bytes(4, "little")), 32
    else:
        raise ValueError("Only separate pointer/context phases are permitted")
    if report["source_address"] != hex(address) or report["source_bytes"] != size:
        raise ValueError("Snapshot source differs from fixed phase")
    command(report, address, size)
    return address, size


async def capture(report: dict, out: Path) -> None:
    _address, size = request(report)
    report["before"], report["files_before"] = await sd_bootstrap.identity()
    same_identity({"before": report["before"], "after": report["before"], "sd_write_attempted": False})
    failure: BaseException | None = None
    try:
        if report["name"] in {entry["name"] for entry in report["files_before"]}:
            raise FileExistsError("Scratch name already listed; no SD write attempted")
        await sd_bootstrap.write_file(report)
        validate_actions(report)
        await sd_bootstrap.download_file(report, out, size)
        data = downloaded(report, out, size)
        report["verification"] = (
            {"pointer": hex(pointer(data)), "allocation_bound_bytes": OBJECT_BYTES}
            if report["phase"] == Phase.pointer
            else context_fields(data)
        )
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            report["after"], report["files_after"] = await sd_bootstrap.identity()
            same_identity(report)
        except BaseException as error:
            report["after_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


def main(
    image: Path,
    out: Path,
    guard: Annotated[list[Path], typer.Option("--guard")],
    create_sd_file: bool = False,
    phase: Phase = Phase.pointer,
    previous_path: Annotated[Path | None, typer.Option("--previous")] = None,
    handler_parent: Path | None = None,
) -> None:
    if not create_sd_file:
        raise typer.BadParameter("Requires --create-sd-file; retains one non-audio SD scratch file")
    out.mkdir(parents=True, exist_ok=False)
    name = "rc" + secrets.token_hex(5)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "serial": OWNED_SERIAL,
        "phase": phase.value,
        "name": name,
        "device_path": f"/SD:/RECORDER/Call-{name}.mp3",
        "source_image_sha256": IMAGE_SHA,
        "sd_write_attempted": False,
        "ok": False,
        "scope": "Independent global4 or bounded context32 snapshot; no other memory/producer/mode selection",
        "residue_policy": "Retain non-audio SD scratch file and filesystem metadata; no automatic deletion",
        "limitations": [
            "Historical pointer bounds do not prove current allocator ownership; no revalidation read",
            "Snapshot occurs before STOP; sampling emits logs; no atomic or partial-slot claim",
        ],
    }
    try:
        report["guards"] = validate_guards(guard, image.read_bytes(), handler_parent)
        if phase == Phase.pointer:
            if previous_path is not None:
                raise ValueError("Pointer phase does not accept --previous")
            address, size = GLOBAL, 4
        elif phase == Phase.context and previous_path is not None:
            report["previous"] = previous(previous_path, report["guards"])
            address, size = int(report["previous"]["pointer"], 16), 32
        else:
            raise ValueError("Context phase requires independently completed --previous pointer phase")
        report.update(
            source_address=hex(address),
            source_bytes=size,
            dump_command=f"dbg dumpbuf {address} {size} {report['device_path']}",
        )
        request(report)
        asyncio.run(capture(report, out))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = datetime.now(UTC).isoformat()
        with (out / "report.json").open("x") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ok": True, "phase": phase.value, "verification": report["verification"]}))


if __name__ == "__main__":
    typer.run(main)
