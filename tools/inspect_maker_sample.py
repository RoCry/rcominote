#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer>=0.16,<1"]
# ///
"""Recover the pinned SDK maker sample offline; never load or execute its members."""

import hashlib
import json
import sqlite3
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import typer

SDK_COMMIT = "26f51e584940d5b141cd1d09d2629d69b595f579"
MAKER = Path("action_technology_sdk/bootloader/tools/utils/linux-x86_64/maker")
HASHES = {
    "temp.img": "cfe8fb89359d4f1106deaa0b9e7a951059edb92e679eed1791ab8e716b0ffd82",
    "sample.db": "95a805b74ceed01ca824da306c3aab9ea58317d73286a4a4c705fd11ce5867f5",
    "libFileSystem.so": "ed073d9e40f5bc831c94c1a4c25d5fc889390cdcf4e3d1ce387aed39ea27ca1d",
}
ANCHORS = {
    "Launch.pyo": "eabc353622249764b8b9ac5ee9da8c026d7e579cece4e1fad2489f4ed5403754",
    "firmware.xml": "f2794d9955489cf723dcbf12eb9c10ba6a63ccd287c999a1ae04e1cba4138833",
    "product.ini": "8a36aa4fe5bbfa13efe7036ac1c7ea731bc4d71051ec34dedb2364b7c9b83cb6",
    "boot_recovery.app": "00f30f32e754e1b33110b0f98a2b9387ffc4808ccf049ea260e2e326a1cd39f1",
}
SELECTION_TABLES = (
    "CHIP_NAME",
    "CHIPID",
    "BOARD_NAME",
    "SDK_VER",
    "FW_VERSION",
    "USB_ADFU_PROTOCOL_SWITCH",
    "ADFU",
    "ADFUS",
    "ADFUS_U",
    "STORAGE_ID_FILE",
    "VID",
    "PID",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def long_name(rows: list[bytes], short: bytes) -> str:
    checksum = 0
    for char in short:
        checksum = (((checksum & 1) << 7) + (checksum >> 1) + char) & 255
    count = rows[0][0] & 31
    if (
        rows[0][0] != count | 64
        or [r[0] & 31 for r in rows] != list(range(count, 0, -1))
        or any(r[13] != checksum or r[12] != 0 or r[26:28] != b"\0\0" for r in rows)
    ):
        raise ValueError("Malformed FAT long filename")
    raw = b"".join(r[1:11] + r[14:26] + r[28:32] for r in reversed(rows))
    return raw.decode("utf-16-le").split("\0", 1)[0].rstrip("\uffff")


def read_maker_fat(raw: bytes, *, type100: bool = False) -> tuple[list[dict], dict[str, bytes], dict]:
    """Read the observed maker FAT profile; preserve unsupported blocks explicitly."""
    if len(raw) < 512:
        raise ValueError("Truncated maker image")
    if type100 and (
        raw[:11] != b"ACTS-FWT001" or raw[496:512] != bytes.fromhex("112233445566778899aabbccddeeff75")
    ):
        raise ValueError("Unexpected type100 boot-sector markers")
    bps, spc, reserved, nfats = struct.unpack_from("<HBHB", raw, 11)
    fsize = struct.unpack_from("<I", raw, 36)[0]
    root = struct.unpack_from("<I", raw, 44)[0]
    signature = b"\xff\x75" if type100 else b"\x55\xaa"
    if (bps, spc, reserved, nfats, fsize, root, raw[510:512]) != (512, 8, 32, 2, 2044, 2, signature):
        raise ValueError("Unexpected FAT32 profile")
    fat = raw[reserved * bps : (reserved + fsize) * bps]
    if fat != raw[(reserved + fsize) * bps : (reserved + 2 * fsize) * bps]:
        raise ValueError("FAT copies disagree")
    data_start = (reserved + nfats * fsize) * bps
    cluster_size = spc * bps

    def chain(first: int):
        seen = set()
        while first < 0x0FFFFFF8:
            if first < 2 or first in seen or (first + 1) * 4 > len(fat):
                raise ValueError("Invalid or cyclic FAT cluster chain")
            seen.add(first)
            off = data_start + (first - 2) * cluster_size
            if off + cluster_size > len(raw):
                raise ValueError("Cluster exceeds retained image; no implicit zero filling")
            yield first, raw[off : off + cluster_size]
            first = struct.unpack_from("<I", fat, first * 4)[0] & 0x0FFFFFFF

    manifest, files, lfn = [], {}, []
    for _, block in chain(root):
        for off in range(0, len(block), 32):
            row = block[off : off + 32]
            if row[0] == 0:
                break
            if row[0] == 229:
                lfn = []
                continue
            if row[11] == 15:
                lfn.append(row)
                continue
            if row[11] & 8:
                lfn = []
                continue
            short = row[:11]
            name = short[:8].decode("ascii").rstrip() + "." + short[8:].decode("ascii").rstrip()
            name = long_name(lfn, short) if lfn else name.rstrip(".")
            lfn = []
            if any(c in name for c in "/\\:") or not name.endswith("~0") or row[11] & 16:
                raise ValueError(f"Unexpected sample member/path: {name!r}")
            first = (struct.unpack_from("<H", row, 20)[0] << 16) | struct.unpack_from("<H", row, 26)[0]
            size = struct.unpack_from("<I", row, 28)[0]
            chunks = list(chain(first))
            encoded = b"".join(data for _, data in chunks)
            if not size <= len(encoded) < size + cluster_size:
                raise ValueError(f"File length/chain mismatch: {name}")
            encoded = encoded[:size]
            opaque = encoded.startswith(bytes.fromhex("112233445566778899aabbccddeeff"))
            # libFileSystem.so XorEncrypt@0x26c72; ReadBlock dispatch@0x26f32.
            decoded = encoded if opaque else bytes(char ^ 0x38 for char in encoded)
            logical = name.removesuffix("~0")
            output = logical + ".encoded" if opaque else logical
            if output.casefold() in {key.casefold() for key in files}:
                raise ValueError("Duplicate sample filename")
            files[output] = decoded
            record = {
                "name": logical,
                "stored_name": name,
                "bytes": size,
                "encoded_sha256": digest(encoded),
                "clusters": [c for c, _ in chunks],
            }
            if opaque:
                record.update(output_name=output, representation="XYZ_121-unimplemented")
            else:
                record.update(decoded_sha256=digest(decoded), decoded_first16_hex=decoded[:16].hex())
            manifest.append(record)
        else:
            continue
        break
    return (
        manifest,
        files,
        {
            "retained_bytes": len(raw),
            "declared_volume_bytes": struct.unpack_from("<I", raw, 32)[0] * bps,
            "data_start": data_start,
            "cluster_bytes": cluster_size,
            "fat_copies_identical": True,
            "boundary": "Trimmed used-data carrier, not a complete FAT volume or target NOR dump",
        },
    )


def read_sample_fat(raw: bytes) -> tuple[list[dict], dict[str, bytes], dict]:
    result = read_maker_fat(raw)
    _, files, _ = result
    if len(files) != 43:
        raise ValueError(f"Expected 43 sample files, got {len(files)}")
    if any(name.endswith(".encoded") for name in files):
        raise ValueError("Unexpected XYZ_121 block in pinned SDK sample")
    for name, sha in ANCHORS.items():
        if digest(files[name]) != sha:
            raise ValueError(f"Decoded oracle mismatch: {name}")
    return result


def inspect_sdk(sdk: Path) -> tuple[dict, dict[str, bytes]]:
    maker = sdk / MAKER
    sources = {}
    for name, sha in HASHES.items():
        raw = (maker / name).read_bytes()
        if digest(raw) != sha:
            raise ValueError(f"Wrong pinned SDK source: {name}")
        sources[name] = {"bytes": len(raw), "sha256": sha, "path": str(MAKER / name)}
    manifest, files, fat = read_sample_fat((maker / "temp.img").read_bytes())
    with sqlite3.connect(f"{(maker / 'sample.db').resolve().as_uri()}?mode=ro&immutable=1", uri=True) as db:
        metadata = db.execute("select Keyword, FileName, FileLength, typeof(File) from FileTable").fetchall()
        if len(metadata) != 31 or len({r[1] for r in metadata}) != 31:
            raise ValueError("Unexpected FileTable inventory")
        for keyword, name, size, kind in metadata:
            if keyword != "SCRIPT_PYD" or kind != "null" or len(files[name]) != size:
                raise ValueError(f"FileTable/member mismatch: {name}")
        selection = {name: db.execute(f'SELECT * FROM "{name}"').fetchall() for name in SELECTION_TABLES}
        if any(selection.values()):
            raise ValueError("Expected empty sample transport/board configuration")
        types = {
            name: db.execute(f'SELECT * FROM "{name}"').fetchall() for name in ("SDK_TYPE", "SCRIPT_TYPE")
        }
    matches = {}
    for name in ("boot_recovery.app", "adfus.bin", "adfus_u.bin"):
        relative = Path("action_technology_sdk/bootloader/tools/prebuilt/lark/common/bin") / name
        if (sdk / relative).read_bytes() != files[name]:
            raise ValueError(f"Previously inspected LARK helper differs: {name}")
        matches[name] = str(relative)
    xml = ET.fromstring(files["firmware.xml"])
    partitions = [{child.tag: child.text for child in row} for row in xml.findall("./partitions/partition")]
    if len(partitions) != 11 or xml.findtext("disk_size") != "0x200000":
        raise ValueError("Unexpected pinned sample layout")
    return {
        "schema": 1,
        "sdk_commit": SDK_COMMIT,
        "scope": "Static bytes, read-only SQLite, FAT extraction and XOR only; no vendor code/device execution",
        "sources": sources,
        "fat": fat,
        "files": manifest,
        "file_table": {"rows": len(metadata), "all_names_and_lengths_match": True, "payload_column": "NULL"},
        "empty_selection_tables": list(selection),
        "sample_types": types,
        "exact_existing_helper_matches": matches,
        "sample_layout": {
            "description": xml.findtext("descirption"),
            "disk_size": xml.findtext("disk_size"),
            "partitions": partitions,
        },
        "sample_product_ini": files["product.ini"].decode("utf-8"),
        "limits": [
            "FileTable supplies names/lengths, no cryptographic content oracle",
            "Empty selection tables cannot bind host modules to ATS3085L or CoMi",
            "Sample XML is LARK 2MiB/11 partitions, not CoMi 4MiB/18 partitions",
            "No production envelope database transform or XYZ_121 implementation",
        ],
    }, files


def main(sdk: Path, output: Path | None = None):
    report, files = inspect_sdk(sdk)
    if output is not None:
        output.mkdir(parents=True, exist_ok=False)
        for name, data in files.items():
            (output / name).write_bytes(data)
        (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    typer.run(main)
