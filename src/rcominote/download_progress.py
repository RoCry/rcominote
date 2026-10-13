"""Interactive BLE export progress on stderr; stdout remains machine-readable JSON."""

import asyncio
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .connection import Connection
from .recording_export import export_recording


async def export_with_progress(
    conn: Connection, name: str, out: Path, expected_size: int, *, offset: int = 0
) -> dict:
    console = Console(stderr=True)
    total = expected_size - offset
    with Progress(
        TextColumn("{task.description}", markup=False),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        TextColumn("{task.fields[status]}"),
        console=console,
        disable=not console.is_terminal,
        refresh_per_second=4,
        expand=True,
    ) as progress:
        task = progress.add_task(name, total=total, status="Receiving")

        def received(count: int) -> None:
            progress.update(task, completed=count, status="Verifying" if count == total else "Receiving")

        try:
            result = await export_recording(
                conn, name, out, expected_size=expected_size, offset=offset, on_progress=received
            )
        except asyncio.CancelledError:
            progress.update(task, status="Cancelled")
            raise
        except Exception:
            progress.update(task, status="Failed")
            raise
        progress.update(task, status="Saved")
        return result
