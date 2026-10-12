"""Bounded two-pass NOR sector acquisition in one verified BLE connection."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from . import log_capture, nor_windows
from .ble_target import OWNED_SERIAL
from .output import emit
from .printk_tail import NorTarget


def main(
    out: Annotated[Path, typer.Option()],
    nor_target: NorTarget = NorTarget.boot,
    serial: str = OWNED_SERIAL,
):
    """Capture two passes of11 fixed windows; publish512 B only if all rows agree."""
    out.mkdir(parents=True, exist_ok=False)
    result = asyncio.run(
        log_capture.capture(
            serial=serial,
            duration=1,
            printk_tail_probe=True,
            nor_target=nor_target,
            batch_windows=tuple(range(1, 11)) + tuple(range(11)),
        )
    )
    (out / "session.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if not result["ok"]:
        emit({"ok": False, "error": result.get("error"), "session": str(out / "session.json")})
        raise typer.Exit(1)
    first = {
        key: value for key, value in result.items() if key not in {"batch_records", "notifications", "writes"}
    }
    captures = [first, *result["batch_records"]]
    paths = []
    for index, capture in enumerate(captures):
        path = out / f"window-{index:02}.json"
        path.write_text(json.dumps(capture, ensure_ascii=False, separators=(",", ":")) + "\n")
        paths.append(path)
    report = nor_windows.analyze(paths)
    report["shared_connection"] = True
    report["elapsed_seconds"] = result["notifications"][-1]["seconds"]
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if report["complete"]:
        (out / "sector.bin").write_bytes(bytes.fromhex(report["sector_hex"]))
    emit(
        {key: value for key, value in report.items() if key not in {"rows", "sector_hex"}}
        | {"directory": str(out)}
    )
    if not report["complete"]:
        raise typer.Exit(1)
