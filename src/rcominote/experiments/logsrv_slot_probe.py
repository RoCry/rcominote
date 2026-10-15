"""One fixed known-mdb16→slot4→SD trial; retain three bounded scratch files.

No alternate slot, retries, filler, NOR/MMIO access or mode-switch command.
Pointer equality is checked after download, never claimed as an earlier live gate.
"""

import asyncio
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import logsrv_context_probe as context
from rcominote.experiments import logsrv_slot_contract as contract
from rcominote.experiments import sd_bootstrap
from rcominote.experiments.sd_nor_probe import IMAGE_SHA, same_identity


def snapshots() -> list[dict]:
    files = []
    for role, address, size in contract.FILES:
        name = "rc" + secrets.token_hex(5)
        path = f"/SD:/RECORDER/Call-{name}.mp3"
        files.append(
            {
                "role": role,
                "name": name,
                "device_path": path,
                "source_address": hex(address),
                "source_bytes": size,
                "dump_command": f"dbg dumpbuf {address} {size} {path}",
            }
        )
    return files


async def capture(report: dict, out: Path) -> None:
    commands = contract.commands(report)
    report["before"], report["files_before"] = await sd_bootstrap.identity()
    same_identity({"before": report["before"], "after": report["before"], "sd_write_attempted": False})
    failure: BaseException | None = None
    try:
        existing = {row["name"] for row in report["files_before"]}
        if any(row["name"] in existing for row in report["files"]):
            raise FileExistsError("Scratch name already listed; no SD write attempted")
        await sd_bootstrap.write_commands(report, commands)
        contract.validate_actions(report)
        data = []
        for item in report["files"]:
            directory = out / item["role"]
            directory.mkdir(exist_ok=False)
            payload = await sd_bootstrap.download_file(item, directory, item["source_bytes"])
            data.append(payload)
            if item["role"] == "global" and context.pointer(payload) != contract.POINTER:
                raise ValueError("Current-pointer snapshot changed; no further downloads")
            if item["role"] == "metadata":
                contract.metadata(payload)
        report["verification"] = contract.verify_payload(report, *data)
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
    slot_guard: Annotated[list[Path], typer.Option("--slot-guard")],
    pointer_parent: Annotated[Path, typer.Option()],
    context_parent: Annotated[Path, typer.Option()],
    handler_parent: Path | None = None,
    create_sd_files: bool = False,
) -> None:
    if not create_sd_files:
        raise typer.BadParameter("Requires --create-sd-files; retains three non-audio SD scratch files")
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "serial": OWNED_SERIAL,
        "profile": "fixed-slot4-known-mdb16",
        "source_image_sha256": IMAGE_SHA,
        "files": snapshots(),
        "sd_write_attempted": False,
        "ok": False,
        "scope": "One known XIP16 read and three RAM→SD snapshots; no alternate slot or firmware mutation",
        "residue_policy": "Retain three non-audio SD files and filesystem metadata; no automatic deletion",
        "limitations": [
            "Pointer equality is checked after file downloads; not current allocator ownership proof",
            "Metadata and body sampled at different times; no atomic snapshot or still-partial claim",
            "Strict failure stops this trial; no retry, fragment repair, alternate slot or GPIO escalation",
        ],
    }
    try:
        report["parents"] = contract.validate_parents(
            image.read_bytes(), guard, slot_guard, pointer_parent, context_parent, handler_parent
        )
        report["commands"] = contract.commands(report)
        asyncio.run(capture(report, out))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = datetime.now(UTC).isoformat()
        with (out / "report.json").open("x") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ok": True, "verification": report["verification"]}, ensure_ascii=False))


if __name__ == "__main__":
    typer.run(main)
