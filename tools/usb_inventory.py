#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer>=0.16,<1"]
# ///
"""Snapshot/diff macOS USB registry descriptors; never open a device or send USB requests."""

import hashlib
import json
import plistlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


def parse_registry(raw: bytes) -> list[dict]:
    roots = plistlib.loads(raw)
    if not isinstance(roots, list):
        raise ValueError("Expected ioreg IOUSBHostDevice plist array")
    devices = {}

    def walk(nodes: list[dict]):
        for node in nodes:
            # Interfaces and storage driver nodes can repeat vendor/product IDs.
            # Only a device node establishes a separate physical USB identity.
            if node.get("IOObjectClass") == "IOUSBHostDevice":
                location = f"{node['locationID']:08x}"
                device = {
                    "location": location,
                    "vid_pid": f"{node['idVendor']:04x}:{node['idProduct']:04x}",
                    "product": node.get("USB Product Name", node.get("IORegistryEntryName")),
                    "manufacturer": node.get("USB Vendor Name"),
                    "serial": node.get("USB Serial Number"),
                    "device_class": node["bDeviceClass"],
                    "interfaces": sorted(
                        [
                            {
                                "number": child["bInterfaceNumber"],
                                "class": child["bInterfaceClass"],
                                "subclass": child["bInterfaceSubClass"],
                                "protocol": child["bInterfaceProtocol"],
                            }
                            for child in node.get("IORegistryEntryChildren", [])
                            if child.get("IOObjectClass") == "IOUSBHostInterface"
                        ],
                        key=lambda item: item["number"],
                    ),
                }
                if location in devices and devices[location] != device:
                    raise ValueError(f"Conflicting USB devices at location {location}; repeat capture")
                devices[location] = device
            walk(node.get("IORegistryEntryChildren", []))

    walk(roots)
    return [devices[key] for key in sorted(devices)]


def compare(before: list[dict], after: list[dict]) -> dict:
    def index(devices):
        result = {}
        for device in devices:
            key = (device["location"], device["vid_pid"], device["serial"])
            if key in result:
                raise ValueError(f"Duplicate USB identity: {key}")
            result[key] = device
        return result

    old, new = index(before), index(after)
    return {
        "removed": [value for key, value in old.items() if key not in new],
        "added": [value for key, value in new.items() if key not in old],
        "changed": [
            {"before": old[key], "after": value} for key, value in new.items() if key in old and old[key] != value
        ],
    }


@app.command()
def snapshot(
    out: Annotated[Path, typer.Option(help="New JSON file, refuses overwrite")],
    input_plist: Annotated[Path | None, typer.Option(help="Replay an existing ioreg plist offline")] = None,
):
    if out.exists():
        raise FileExistsError(f"Output exists: {out}; choose a new snapshot path")
    if input_plist is not None:
        raw = input_plist.read_bytes()
    else:
        if sys.platform != "darwin":
            raise RuntimeError("Live snapshots require macOS; use --input-plist for offline replay")
        raw = subprocess.run(
            ["ioreg", "-r", "-c", "IOUSBHostDevice", "-l", "-w", "0", "-a"],
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout
    result = {
        "schema": 1,
        "processed_at": datetime.now(UTC).isoformat(),
        "source": "ioreg IOUSBHostDevice; existing registry only",
        "replayed": input_plist is not None,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "devices": parse_registry(raw),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"devices": len(result["devices"]), "snapshot": str(out)}, ensure_ascii=False))


@app.command()
def diff(before: Path, after: Path):
    def read(path):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema") != 1 or not isinstance(value.get("devices"), list):
            raise ValueError(f"Not a USB inventory schema 1 snapshot: {path}")
        return value["devices"]

    print(json.dumps(compare(read(before), read(after)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
