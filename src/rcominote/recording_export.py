"""Atomic recording export and explicitly labeled prefixes after user cancellation."""

import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .connection import Connection, recording_output_name
from .download_cancel import DownloadCancelled


async def export_recording(
    conn: Connection, name: str, out: Path, expected_size: int | None = None, *, offset: int = 0
) -> dict:
    """Publish a complete requested range without replacing an existing file.

    SHA-256 identifies local bytes; the device supplies no hash oracle. Only
    explicit cancellation preserves a labeled prefix, never a complete MP3.
    """
    filename = recording_output_name(name, offset)
    if expected_size is not None and expected_size < 0:
        raise ValueError("Expected recording size must be nonnegative")
    if expected_size is not None and offset > expected_size:
        raise ValueError("Recording offset exceeds listed file size")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / filename
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Recording output already exists: {target}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{name}.offset-{offset}.", suffix=".part", dir=out)
    part = Path(temporary)
    digest = hashlib.sha256()
    written_bytes = 0
    try:
        with os.fdopen(descriptor, "wb") as handle:

            def write(data: bytes) -> int:
                nonlocal written_bytes
                count = handle.write(data)
                digest.update(data[:count])
                written_bytes += count
                return count

            try:
                received = await conn.download(name, write, offset=offset)
            except asyncio.CancelledError as cancellation:
                # Cancellation can also interrupt the initial GATT write or wait
                # for the transaction lock, before download enters its data loop.
                error = (
                    cancellation
                    if isinstance(cancellation, DownloadCancelled)
                    else DownloadCancelled(
                        name=name,
                        offset=offset,
                        received=written_bytes,
                        declared_size=None,
                        stop_result={
                            "request_attempted": False,
                            "request_sent": False,
                            "response_received": False,
                            "error": None,
                            "worker_exit_verified": False,
                        },
                    )
                )
                report = {
                    "ok": False,
                    "status": "cancelled",
                    "name": name,
                    "offset": offset,
                    "bytes": written_bytes,
                    "listed_size": expected_size,
                    "declared_size": error.declared_size,
                    "sha256": digest.hexdigest(),
                    "partial_path": None,
                    "manifest_path": None,
                    "scope": "incomplete_recording_suffix" if offset else "incomplete_recording_prefix",
                    "stop": error.stop_result,
                    "automatic_resume": False,
                }
                error.export_result = report
                if written_bytes:
                    manifest: Path | None = None
                    try:
                        handle.flush()
                        os.fsync(handle.fileno())
                        partial = part.with_name(part.name[1:].removesuffix(".part") + ".partial.bin")
                        os.link(part, partial)
                        report["partial_path"] = str(partial)
                        manifest = partial.with_suffix(".json")
                        with manifest.open("x", encoding="utf-8") as metadata:
                            json.dump(
                                report | {"manifest_path": str(manifest)},
                                metadata,
                                ensure_ascii=False,
                                indent=2,
                            )
                            metadata.write("\n")
                            metadata.flush()
                            os.fsync(metadata.fileno())
                        report["manifest_path"] = str(manifest)
                    except OSError as save_error:
                        raise OSError(
                            f"Canceled download save failed: {save_error}; "
                            f"preserved partial={report['partial_path']}; "
                            f"metadata={manifest} may be incomplete"
                        ) from save_error
                raise error
            if expected_size is not None and received + offset != expected_size:
                raise ValueError(f"File-list size changed: expected {expected_size}, received {received}")
            handle.flush()
            os.fsync(handle.fileno())
        # Same filesystem: link atomically refuses an existing destination.
        os.link(part, target)
        return {
            "name": name,
            "path": str(target),
            "bytes": received,
            "sha256": digest.hexdigest(),
            "offset": offset,
            "scope": "recording_suffix" if offset else "complete_recording",
        }
    finally:
        part.unlink(missing_ok=True)
