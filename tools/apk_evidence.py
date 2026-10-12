#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Inventory pinned CoMi APKs and extract inert JS evidence; never run app code."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

SAMPLES = {
    "b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118": "1.1.2",
    "8aade0a4ca1f9e25b9ebbd51dee97702bf0954e5a66adcf91312b4331414ace7": "1.2.4",
}
MEMBER = "assets/public/assets/index-Btih_BUR.js"
MEMBER_SHA256 = "167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c"
RANGES = {
    "boyi-constants-frame": (217000, 219700),
    "boyi-status-event": (220292, 220822),
    "boyi-device-info": (235121, 236080),
    "boyi-send-command": (232509, 233700),
    "boyi-usb-setter": (245602, 245936),
    "mova-constants": (253400, 255573),
    "mova-usb-constructor": (258794, 259002),
    "mova-usb-setter": (275210, 275510),
    "mova-recorder-surface": (277400, 279350),
    "device-manager": (279350, 281000),
    "auto-enable-usb-effect": (386500, 387100),
}
TERMS = (
    b"SET_USB_MODE",
    b"CHAR_OTA_WRITE",
    b"TRIGGER_OTA",
    b"OTA_FILE_TRANSFER",
    b"firmware",
    "固件".encode(),
)
IMAGE_NAME = re.compile(r"firmware|\.(?:bin|fw|hex|img|dfu|ufw|upd)$", re.I)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect(apk: Path, out: Path) -> dict:
    apk_hash = digest(apk.read_bytes())
    if apk_hash not in SAMPLES:
        raise ValueError(f"Unrecognized APK SHA-256: {apk_hash}; no evidence extracted")
    if out.exists():
        raise FileExistsError(f"Output already exists: {out}; select a new directory")
    manifest = {
        "schema": 1,
        "sample": SAMPLES[apk_hash],
        "apk_sha256": apk_hash,
        "apk_bytes": apk.stat().st_size,
        "offset_convention": "zero-based byte offsets in decompressed ZIP member; end exclusive",
        "coverage": (
            "ZIP inventory + literal matches in UTF-8 assets .js/.json/.html; no DEX/native/decryption/runtime analysis"
        ),
        "inventory": [],
        "asset_text_matches": [],
        "image_name_candidates": [],
        "snippets": [],
    }
    extracted = {}
    with ZipFile(apk) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            data = archive.read(entry)
            row = {
                "member": entry.filename,
                "bytes": len(data),
                "sha256": digest(data),
            }
            manifest["inventory"].append(row)
            if IMAGE_NAME.search(entry.filename):
                manifest["image_name_candidates"].append({**row, "first_32_bytes_hex": data[:32].hex()})
            if entry.filename.startswith("assets/") and entry.filename.endswith((".js", ".json", ".html")):
                data.decode("utf-8")  # Fail early; don't silently omit opaque text.
                for term in TERMS:
                    offsets = [m.start() for m in re.finditer(re.escape(term), data)]
                    if offsets:
                        manifest["asset_text_matches"].append(
                            {"member": entry.filename, "term": term.decode(), "byte_offsets": offsets}
                        )
            if entry.filename == MEMBER:
                if row["sha256"] != MEMBER_SHA256:
                    raise ValueError(f"Unexpected JS SHA-256: {row['sha256']}")
                extracted["device-index.js"] = data
                for label, (start, end) in RANGES.items():
                    snippet = data[start:end]
                    filename = f"{label}.txt"
                    extracted[filename] = snippet
                    manifest["snippets"].append(
                        {
                            "label": label,
                            "member": MEMBER,
                            "member_sha256": row["sha256"],
                            "start": start,
                            "end": end,
                            "sha256": digest(snippet),
                            "output": filename,
                        }
                    )
    if SAMPLES[apk_hash] == "1.1.2" and not extracted:
        raise ValueError(f"Pinned sample missing required member: {MEMBER}")
    out.mkdir(parents=True)
    for filename, data in extracted.items():
        (out / filename).write_bytes(data)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path, help="Local APK; never fetched or executed")
    parser.add_argument("--out", required=True, type=Path, help="New output directory (use ignored artifacts/)")
    args = parser.parse_args()
    try:
        manifest = inspect(apk=args.apk, out=args.out)
    except (OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    print(
        f"CoMi {manifest['sample']}: {len(manifest['inventory'])} members; "
        f"{len(manifest['snippets'])} snippets; manifest: {args.out / 'manifest.json'}"
    )


if __name__ == "__main__":
    main()
