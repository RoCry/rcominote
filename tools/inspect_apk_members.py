#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer>=0.16,<1"]
# ///
"""Inventory APK members and name-selected firmware candidates without executing code."""

import hashlib
import json
import re
from pathlib import Path
from typing import Annotated
from zipfile import ZipFile

import typer

PATTERN = re.compile(
    r"firmware|\bota\b|upgrade|update|\.(bin|fw|img|hex|dfu|uf2|fwp|rom|pack|pak|zip)$", re.IGNORECASE
)


def main(
    apk: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    out: Annotated[Path, typer.Option()],
):
    if out.exists():
        raise FileExistsError(f"Refusing existing output: {out}")
    rows, candidates = [], []
    with apk.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    with ZipFile(apk) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            row = {"name": member.filename, "size": member.file_size, "crc32": f"{member.CRC:08x}"}
            rows.append(row)
            if PATTERN.search(member.filename):
                with archive.open(member) as handle:
                    prefix = handle.read(32)
                    content_hash = hashlib.sha256(prefix)
                    while chunk := handle.read(1024 * 1024):
                        content_hash.update(chunk)
                candidates.append(row | {"sha256": content_hash.hexdigest(), "first32_hex": prefix.hex()})
    report = {
        "apk_sha256": digest,
        "scope": "Member names only; opaque or embedded firmware is not excluded",
        "members": rows,
        "candidates_by_name": candidates,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    typer.echo(json.dumps({"members": len(rows), "candidates": candidates}, ensure_ascii=False))


if __name__ == "__main__":
    typer.run(main)
