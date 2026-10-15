"""One read-only tail/barrier/full transfer trial on a single connection.

Tests connection history, without claiming a fast-interval fix. Never joins
partial transfers, retries, reconnects, sends Actions or writes a device file.
"""

import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.connection import Connection
from rcominote.device_commands import read_info
from rcominote.experiments.sd_bootstrap import IMAGE_SHA, ORACLE_SHA, verify_state
from rcominote.experiments.sd_nor_probe import validate_actions

NAME = "rc6ae65544fe"
SIZE = 4096
TAIL = 128
PARENT_SHA = "a76e99224ef2482f8749f1a4d7036774cd9eda761171ff5cd97c7ae83ffbd8a9"
DEVICE_PATH = f"/SD:/RECORDER/Call-{NAME}.mp3"
COMMAND = f"dbg dumpbuf 402653184 4096 {DEVICE_PATH}"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_inputs(image: Path, parent_ram_dir: Path) -> tuple[bytes, dict]:
    raw = image.read_bytes()
    if len(raw) != 927632 or sha(raw) != IMAGE_SHA:
        raise ValueError("Wrong independently verified FW010004 image")
    oracle = raw[0xDD500:0xDE500]
    if len(oracle) != SIZE or sha(oracle) != ORACLE_SHA:
        raise ValueError("Wrong independent RAM initialization oracle")
    receipt = (parent_ram_dir / "report.json").read_bytes()
    if sha(receipt) != PARENT_SHA:
        raise ValueError("Requires the exact original RAM bootstrap receipt")
    parent = json.loads(receipt)
    expected = {
        "serial": OWNED_SERIAL,
        "name": NAME,
        "device_path": DEVICE_PATH,
        "dump_command": COMMAND,
        "source_image_sha256": IMAGE_SHA,
        "expected_sha256": ORACLE_SHA,
    }
    if any(parent.get(key) != value for key, value in expected.items()):
        raise ValueError("Parent receipt differs from the fixed RAM source")
    if parent.get("sd_write_attempted") is not True or parent.get("after_error"):
        raise ValueError("Parent lacks completed write and final identity evidence")
    validate_actions(parent)
    state = verify_state(parent["before"], parent["after"], sd_write=True)
    return oracle, {
        "directory": str(parent_ram_dir.resolve()),
        "report_sha256": sha(receipt),
        "actions_verified": True,
        "state_verification": state,
    }


async def transfer(conn: Connection, out: Path, report: dict, phase: str, oracle: bytes) -> None:
    offset = SIZE - TAIL if phase == "tail" else 0
    expected = oracle[-TAIL:] if phase == "tail" else oracle
    row = {"offset": offset, "expected_bytes": len(expected), "started_ns": time.monotonic_ns()}
    report[phase] = row
    data = bytearray()

    def sink(chunk: bytes) -> int:
        if len(data) + len(chunk) > len(expected):
            row["rejected_chunk_hex"] = chunk.hex()
            raise ValueError("Download exceeds fixed phase size")
        data.extend(chunk)
        return len(chunk)

    try:
        row["download_bytes"] = await conn.download(NAME, sink, offset=offset)
        row["transfer_complete"] = True  # Connection requires declaration, exact suffix and end.
        if row["download_bytes"] != len(expected) or bytes(data) != expected:
            raise ValueError("Download differs from complete independent phase oracle")
        row["exact_match"] = True
    except BaseException as error:
        row["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        row.update(received_bytes=len(data), sha256=sha(data), ended_ns=time.monotonic_ns())
        with (out / f"{phase}.bin").open("xb") as handle:
            handle.write(data)


async def capture(report: dict, oracle: bytes, out: Path) -> None:
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    async with Connection(device) as conn:
        failure: BaseException | None = None
        try:
            report["before"] = await read_info(conn, OWNED_SERIAL)
            verify_state(report["before"], report["before"], sd_write=False)
            await transfer(conn, out, report, "tail", oracle)
            report["barrier"] = await read_info(conn, OWNED_SERIAL)
            report["barrier_verification"] = verify_state(report["before"], report["barrier"], sd_write=False)
            await transfer(conn, out, report, "full", oracle)
        except BaseException as error:
            failure = error
            raise
        finally:
            try:
                report["after"] = await read_info(conn, OWNED_SERIAL)
                report["state_verification"] = verify_state(report["before"], report["after"], sd_write=False)
            except BaseException as error:
                report["after_error"] = f"{type(error).__name__}: {error}"
                if failure is None:
                    raise


def main(image: Path, parent_ram_dir: Path, new_out: Path) -> None:
    oracle, parent = validate_inputs(image, parent_ram_dir)
    new_out.mkdir(parents=True, exist_ok=False)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "serial": OWNED_SERIAL,
        "name": NAME,
        "profile": "same-connection-tail128-info-full4096",
        "scope": "One read-only transfer-history trial; no Actions, SD write or firmware mutation",
        "source_image_sha256": IMAGE_SHA,
        "expected_sha256": ORACLE_SHA,
        "parent": parent,
        "sd_write_attempted": False,
        "ok": False,
    }
    try:
        asyncio.run(capture(report, oracle, new_out))
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = datetime.now(UTC).isoformat()
        with (new_out / "report.json").open("x") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"ok": True, "received_bytes": report["full"]["received_bytes"]}))


if __name__ == "__main__":
    typer.run(main)
