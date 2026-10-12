"""Resume the fixed, evidenced mapped-system image through bounded BLE sessions."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from .ble_target import OWNED_SERIAL
from .image_store import BODY_BYTES, CHUNK_BYTES, ImageStore
from .log_capture import capture
from .output import emit
from .range_readback import read_header, read_image_chunk

app = typer.Typer(no_args_is_help=True)


async def capture_saved(directory: Path, indices: tuple[int, ...]) -> dict:
    result = await capture(serial=OWNED_SERIAL, duration=1, image_header=True, image_chunks=indices)
    evidence = directory / "captures"
    evidence.mkdir(parents=True, exist_ok=True)
    path = evidence / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    with path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False)
    if not result["ok"]:
        raise RuntimeError(f"Incomplete image session; evidence retained at {path}; rerun to resume")
    return result


async def export_image(directory: Path, max_sessions: int) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    # Each invocation independently checks live identity, code guards and header.
    initial = await capture_saved(directory, ())
    store = ImageStore(directory / "chunks", read_header(initial))
    missing = store.missing_chunks()
    sessions = 0
    while missing and (not max_sessions or sessions < max_sessions):
        batch = missing[:8]
        result = await capture_saved(directory, tuple(offset // CHUNK_BYTES for offset, _ in batch))
        for offset, _ in batch:
            store.add_chunk(offset, read_image_chunk(result, offset // CHUNK_BYTES))
        sessions += 1
        missing = store.missing_chunks()
        emit(
            {
                "status": "reading",
                "sessions": sessions,
                "saved_body_bytes": BODY_BYTES - sum(n for _, n in missing),
                "remaining_chunks": len(missing),
            }
        )
    if missing:
        return {"status": "checkpoint", "remaining_chunks": len(missing), "directory": str(directory)}
    return store.finalize(directory / "mapped-system.bin")


@app.command("export")
def export_command(
    directory: Annotated[Path, typer.Option()],
    max_sessions: Annotated[int, typer.Option(min=0)] = 0,
):
    """Export fixed FW010004 mapped image; resume chunks, verify full checksum. No Flash writes."""
    emit(asyncio.run(export_image(directory, max_sessions)))
