#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer>=0.16,<1"]
# ///
"""Acquire a pinned public recorder source subset; no device access or SDK execution."""

import base64
import hashlib
import json
import subprocess
import time
from pathlib import Path

import typer

REPOSITORY = "szsheep/rec_jx3"
REVISION = "6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b"
API = f"https://gitee.com/api/v5/repos/{REPOSITORY}"
PREFIXES = (
    "application/rec_card/src/",
    "application/rec_card/boards/",
    "application/app_demo/bt_recorder_demo/src/",
)
FILES = {
    "application/rec_card/CMakeLists.txt",
    "application/rec_card/Kconfig",
    "application/rec_card/nvram.prop",
    "application/rec_card/prj.conf",
    "application/rec_card/ksdfs/aeRECORD.dsp",
    "application/rec_card/fs_sdfs/sdfs_k/aeRECORD.dsp",
    "application/rec_card/prebuild/fw_configuration.cfg",
    "framework/media/codec_config.c",
    "zephyr/soc/arm/actions/leopard/Kconfig.series",
    "bootloader/soc/arm/actions/leopard/Kconfig.series",
}


def get_json(url: str) -> dict:
    result = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "60", url],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"Download failed: {url}: {result.stderr.decode().strip()}")
    return json.loads(result.stdout)


def acquire(output: Path, tree_file: Path | None = None) -> None:
    """Fetch source/configs/schematic; resume only locally hash-verified files. No SDK execution."""
    tree = (
        json.loads(tree_file.read_bytes())
        if tree_file is not None
        else get_json(f"{API}/git/trees/{REVISION}?recursive=1")
    )
    if tree.get("sha") != REVISION or tree.get("truncated") is not False or not tree.get("tree"):
        raise RuntimeError("API tree must be complete, nonempty and pinned to the exact revision")
    entries = [
        entry
        for entry in tree["tree"]
        if entry["type"] == "blob" and (entry["path"] in FILES or entry["path"].startswith(PREFIXES))
    ]
    if not entries or not FILES.issubset({entry["path"] for entry in entries}):
        raise RuntimeError("Pinned tree is missing required source anchors")
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        raise typer.BadParameter(f"Completed manifest already exists: {manifest_path}")
    next_request = 0.0

    def fetch(entry: dict) -> dict:
        nonlocal next_request
        path = Path(entry["path"])
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"Unsafe source path: {path}")
        target = output / path
        if target.exists():
            data = target.read_bytes()
        else:
            # Keep API requests below 50/minute; stop immediately on the first error.
            time.sleep(max(0, next_request - time.monotonic()))
            next_request = time.monotonic() + 1.3
            blob = get_json(f"{API}/git/blobs/{entry['sha']}")
            if blob.get("encoding") != "base64":
                raise RuntimeError(f"Unexpected blob encoding: {path}")
            data = base64.b64decode("".join(blob["content"].split()), validate=True)
        git_hash = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if git_hash != entry["sha"]:
            raise RuntimeError(f"Git blob hash mismatch: {path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {
            "path": str(path),
            "git_blob_sha1": git_hash,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    # Failure leaves partial files without a success manifest; a later run verifies before reuse.
    records = []
    for entry in entries:
        records.append(fetch(entry))
        if len(records) % 20 == 0:
            typer.echo(f"Verified {len(records)}/{len(entries)} blobs")
    manifest = {
        "repository": f"https://gitee.com/{REPOSITORY}",
        "revision": REVISION,
        "scope": {"prefixes": PREFIXES, "files": sorted(FILES)},
        "complete_repository": False,
        "files": sorted(records, key=lambda record: record["path"]),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"Verified {len(records)} pinned blobs in {output}; SDK code was not executed")


if __name__ == "__main__":
    typer.run(acquire)
