#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Audit pinned CoMi TX-chain byte windows; no target execution or hardware access."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/android-tx-path-2026-10-13.json"
BASE = 0x10000000


def main(image: Path):
    evidence = json.loads(EVIDENCE.read_text())
    raw = image.read_bytes()
    if (
        len(raw) != evidence["image"]["bytes"]
        or hashlib.sha256(raw).hexdigest() != evidence["image"]["sha256"]
    ):
        raise ValueError("Image differs from pinned CoMi system; no analysis performed")
    # Independently verify both static dispatch-table targets used in the report.
    if struct.unpack_from("<I", raw, 0x100BD7F8 + 0x1C - BASE)[0] != 0x100B194B:
        raise ValueError("Log stream writer dispatch pointer changed")
    driver = evidence["hci_driver_binding"]
    table = int(driver["table_address"], 0) - BASE
    if raw[table : table + 20].hex() != driver["table_hex"]:
        raise ValueError("HCI driver table changed")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    windows = []
    for name, first, last, digest in evidence["regions"]:
        start, end = int(first, 0), int(last, 0)
        if not BASE <= start < end <= BASE + len(raw):
            raise ValueError(f"Out-of-image evidence window: {name}")
        data = raw[start - BASE : end - BASE]
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Evidence window hash mismatch: {name}")
        windows.append(
            {
                "name": name,
                "start": first,
                "end_exclusive": last,
                "sha256": digest,
                "instructions": [
                    {
                        "address": f"0x{i.address:08x}",
                        "hex": i.bytes.hex(),
                        "text": f"{i.mnemonic} {i.op_str}",
                    }
                    for i in decoder.disasm(data, start)
                ],
            }
        )
    print(
        json.dumps(
            {
                "scope": "Pinned bytes and linear Thumb windows; literal pools/tables are not asserted executable",
                "evidence_sha256": hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),
                "image_sha256": evidence["image"]["sha256"],
                "dispatch_tables_verified": True,
                "windows": windows,
                "limits": "Hash checks reproduce bytes, not runtime branch selection, queue occupancy or incident attribution",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
