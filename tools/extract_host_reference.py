#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["libarchive-c>=5,<6", "typer>=0.16,<1"]
# ///
"""Recover two hash-pinned host DLLs from the reference installer; never load them."""

import hashlib
import json
from pathlib import Path

import libarchive
import typer

ARCHIVE_SHA = "cec0aa29b8d77ba0a58178bb37d4790f621b2e500c918cd9cdc778094f450bf4"
CAB_PATH = "config_tool_1.28.01_20230825/en/MSI.CAB"
CAB_SHA = "d5b2d15da4b270761c5dea3ac01fef2c1d05ed691e95c94dd4c944c4ba023115"
MEMBERS = {
    "Hardware_C.dll": (
        "_9BCB15E5A1BB42DB86BA70283C2C61AC",
        "541df654824561537be4e0a500ad7a7997ba9df848dfae4c9202a29dc65fcc5b",
    ),
    "HardwareEx.dll": (
        "_4923F4C44C934041949A68CEC2211D57",
        "986582c243fb0f300c41c483cbc3100f6ff897057b4cace0d30510624a769aa3",
    ),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def recover(source: Path) -> tuple[dict, dict[str, bytes]]:
    if digest(source.read_bytes()) != ARCHIVE_SHA:
        raise ValueError("Wrong pinned config_tool.rar")
    cab = None
    with libarchive.file_reader(str(source)) as archive:
        for entry in archive:
            if entry.pathname == CAB_PATH:
                if cab is not None:
                    raise ValueError("Duplicate English MSI.CAB")
                cab = b"".join(entry.get_blocks())
    if cab is None or digest(cab) != CAB_SHA:
        raise ValueError("Missing or changed English MSI.CAB")
    payloads = {}
    names = {member: name for name, (member, _) in MEMBERS.items()}
    with libarchive.memory_reader(cab) as archive:
        for entry in archive:
            # Consume shared CAB compression state even for unselected members.
            data = b"".join(entry.get_blocks())
            if entry.pathname not in names:
                continue
            name = names[entry.pathname]
            if name in payloads:
                raise ValueError(f"Duplicate DLL member: {name}")
            if digest(data) != MEMBERS[name][1]:
                raise ValueError(f"Changed DLL: {name}")
            payloads[name] = data
    if set(payloads) != set(MEMBERS):
        raise ValueError("Missing pinned host DLLs")
    return {
        "schema": 1,
        "scope": "Static archive reads only; no installer, DLL, driver or target execution",
        "archive_sha256": ARCHIVE_SHA,
        "cab_member": CAB_PATH,
        "cab_sha256": CAB_SHA,
        "files": [
            {"name": name, "member": MEMBERS[name][0], "sha256": digest(data), "bytes": len(data)}
            for name, data in sorted(payloads.items())
        ],
        "boundary": "Reference installer host DLLs; not proof that a CoMi package loads these versions",
    }, payloads


def main(source: Path, output: Path):
    if output.exists():
        raise FileExistsError(f"Refusing existing output: {output}")
    report, payloads = recover(source)
    output.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        (output / name).write_bytes(data)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    (output / "manifest.json").write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    typer.run(main)
