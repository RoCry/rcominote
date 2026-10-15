#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["libarchive-c>=5,<6", "typer>=0.16,<1"]
# ///
"""Acquire/inspect pinned official Actions test packages; no vendor code/device execution."""

import json
import stat
import struct
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import UTC, datetime
from pathlib import Path

import typer
from inspect_maker_sample import digest, read_maker_fat

BASE = "https://tester.actions-semi.com/all/latest/download/"
SOURCES = {
    "index.html": ("index.html", "10d05b66469dbbd0c8f8f84574747bc21af77e4b4e3e65b789b2d3d2249c6a53"),
    "tester": (
        "files/ats3085c_bt_tester_128m-v0.0.3-b6fdbfea-230828.7z",
        "bbe5d8b5b8db020fd70d05a3e57b51de6566656de29f27e653c269b2383c5edb",
    ),
    "hardware": (
        "files/ATS3085C_Production_Test_Board_V1.3_20230822.7z",
        "2d14cf0cdc8155f712c62e998c7b6d03149c99ed70e137584e570e43c650bf3f",
    ),
    "dut": (
        "files/dut-test-fw-v0.0.3-5cfeced9-20230828.7z",
        "fb6a2944016644b58b0c878a05afe82959f1a721ff0f06a5e0346bed6650ed65",
    ),
}
FW_HASHES = {
    "tester": "e6eec01b76b2b9fcfd8e05b3636a582e051a537c2d853cf2737dc1ac1ff49bfe",
    "dut": "7acffc891f8df3d2e6b74b182fa0842ab4850279ad929c7b5b542c844a93473e",
}


def parse_atf(raw: bytes, *, modern: bool) -> tuple[dict, dict[str, bytes]]:
    """Two observed ACTTEST0 profiles, selected by caller, never guessed from CRC failure."""
    if len(raw) < 512 or raw[:8] != b"ACTTEST0":
        raise ValueError("Expected ACTTEST0 (digit zero), complete 512-byte header")
    count = struct.unpack_from("<I", raw, 12)[0]
    if not 0 < count <= 14:
        raise ValueError("Unsupported ATF directory count")
    report = {"profile": "tester_crc" if modern else "dut_legacy_observed", "magic": "ACTTEST0"}
    if modern:
        checks = {
            "header_crc": struct.unpack_from("<I", raw, 8)[0] == zlib.crc32(raw[12:512]),
            "body_crc": struct.unpack_from("<I", raw, 24)[0] == zlib.crc32(raw[512:]),
            "total_length": struct.unpack_from("<I", raw, 20)[0] == len(raw),
            "version": struct.unpack_from("<I", raw, 16)[0] == 0x01000000,
        }
        if not all(checks.values()):
            raise ValueError(f"ATF header/body validation failed: {checks}")
        report["checks"] = checks
    else:
        if struct.unpack_from("<I", raw, 8)[0] != 0x01000000 or any(raw[16:32]):
            raise ValueError("Wrong observed legacy ATF header")
        report["checks"] = "No header/body CRC or total-length validation in this observed profile"
    files, rows, end = {}, [], 512
    for index in range(count):
        pos = 32 + 32 * index
        name = raw[pos : pos + 12].split(b"\0", 1)[0].decode("ascii")
        if not name or name in {".", ".."} or any(c in name for c in "/\\:"):
            raise ValueError("Unsafe ATF filename")
        if name.casefold() in {n.casefold() for n in files}:
            raise ValueError("Duplicate ATF filename")
        offset, size = struct.unpack_from("<II", raw, pos + 16)
        crc = struct.unpack_from("<I", raw, pos + 28)[0]
        if offset % 512 or offset < end or not size or offset + size > len(raw):
            raise ValueError("ATF member overlaps header/previous member, or exceeds carrier")
        data = raw[offset : offset + size]
        computed = zlib.crc32(data)
        unverified = not modern and name == "config.txt" and crc == 0
        if computed != crc and not unverified:
            raise ValueError(f"ATF member CRC failed: {name}")
        files[name] = data
        rows.append(
            {
                "name": name,
                "offset": offset,
                "bytes": size,
                "sha256": digest(data),
                "stored_crc32": f"{crc:08x}",
                "computed_crc32": f"{computed:08x}",
                "crc_state": "unverified-zero-field" if unverified else "verified",
            }
        )
        end = offset + size
    report["members"] = rows
    return report, files


def split_type100(raw: bytes) -> tuple[dict, bytes, bytes]:
    if len(raw) < 16 or raw[:12] != b"100TMFWFSTCA":
        raise ValueError("Expected type100 inner package")
    length = struct.unpack_from("<I", raw, 12)[0]
    if not 512 <= length < len(raw) - 16:
        raise ValueError("Invalid type100 image length")
    image, database = raw[16 : 16 + length], raw[16 + length :]
    if len(database) < 2048 or database[:16] != bytes.fromhex("112233445566778899aabbccddeeff75"):
        raise ValueError("Unexpected wrapped database")
    if struct.unpack_from("<II", database, 16) != (len(database), 512) or database[24:26] != b"\x7e\xe1":
        raise ValueError("Wrapped database identity/length fields disagree")
    return (
        {
            "magic": "100TMFWFSTCA",
            "image_bytes": length,
            "image_sha256": digest(image),
            "database_bytes": len(database),
            "database_sha256": digest(database),
            "database_state": "wrapped; not decrypted or queried",
        },
        image,
        database,
    )


def archive_members(raw: bytes) -> dict[str, bytes]:
    import libarchive

    files = {}
    with libarchive.memory_reader(raw) as archive:
        for entry in archive:
            name = Path(entry.pathname)
            if name.is_absolute() or ".." in name.parts or "\\" in entry.pathname:
                raise ValueError("Unsafe archive member")
            if stat.S_ISDIR(entry.mode):
                continue
            if not stat.S_ISREG(entry.mode):
                raise ValueError("Nonregular archive member")
            if entry.pathname.casefold() in {n.casefold() for n in files}:
                raise ValueError("Duplicate archive member")
            data = b"".join(entry.get_blocks())
            if len(data) != entry.size:
                raise ValueError("Incomplete archive member")
            files[entry.pathname] = data
    return files


def inspect_package(raw: bytes, *, label: str) -> tuple[dict, dict[str, bytes]]:
    if label not in FW_HASHES or digest(raw) != FW_HASHES[label]:
        raise ValueError("Wrong pinned official firmware")
    report, outer = parse_atf(raw, modern=label == "tester")
    inner_name = "upgrade.fw" if label == "tester" else "UPGRADE.FW"
    inner, image, database = split_type100(outer[inner_name])
    manifest, files, fat = read_maker_fat(image, type100=True)
    if len(files) != {"tester": 56, "dut": 52}[label]:
        raise ValueError("Wrong official FAT inventory")
    for name, data in files.items():
        if name.endswith(".pyo") and data[:4] != b"\x03\xf3\x0d\x0a":
            raise ValueError("Expected Python2.7 bytecode")
        if name.endswith(".pyd"):
            if len(data) < 64 or data[:2] != b"MZ":
                raise ValueError("Expected PE host module")
            pos = struct.unpack_from("<I", data, 60)[0]
            if data[pos : pos + 6] != b"PE\0\0\x4c\x01":
                raise ValueError("Expected PE32 i386 host module")
    report.update(label=label, sha256=digest(raw), inner=inner, fat=fat, fat_members=manifest)
    report["opaque_members"] = [n for n in files if n.endswith(".encoded")]
    if label == "tester":
        xml = ET.fromstring(files["firmware.xml"])
        parts = [{field.tag: field.text for field in row} for row in xml.findall("./partitions/partition")]
        if xml.findtext("disk_size") != "0x1000000" or len(parts) != 21:
            raise ValueError("Wrong pinned tester XML layout")
        report["layout"] = {
            "description": xml.findtext("descirption"),
            "disk_size": "0x1000000",
            "partitions": parts,
        }
        param = files["param.bin"]
        if (param[:4], param[744:748], len(param)) != (b"ACPT", b"FVER", 1024):
            raise ValueError("Unexpected tester ACPT/FVER profile")
        if zlib.crc32(param[:740]) != struct.unpack_from("<I", param, 740)[0]:
            raise ValueError("Tester ACPT CRC failed")
        if zlib.crc32(param[744:868]) != struct.unpack_from("<I", param, 868)[0]:
            raise ValueError("Tester FVER CRC failed")
        report["parameter_identity"] = {
            "acpt_crc_valid": True,
            "fver_crc_valid": True,
            "partition_count": struct.unpack_from("<H", param, 8)[0],
            "version_name": param[760:824].split(b"\0", 1)[0].decode("ascii"),
            "board_name": param[824:856].split(b"\0", 1)[0].decode("ascii"),
            "boundary": "CRC-validated packaged metadata, not an observed device identity",
        }
    exports = {"outer/" + name: data for name, data in outer.items()}
    exports.update({"files/" + name: data for name, data in files.items()})
    exports.update({"type100-image.bin": image, "type100-database.bin": database})
    return report, exports


def save_files(output: Path, files: dict[str, bytes]):
    for name, data in files.items():
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            stream.write(data)


def main(output: Path, existing: Path | None = None):
    if output.exists():
        raise FileExistsError(f"Refusing existing output: {output}")
    output.mkdir(parents=True)
    receipts, archives, packages = [], [], []
    originals = output / "originals"
    originals.mkdir()
    for label, (relative, expected) in SOURCES.items():
        name, url = Path(relative).name, BASE + relative
        receipt = {"url": url, "file": name}
        if existing is None:
            receipt["started_utc"] = datetime.now(UTC).isoformat()
            request = urllib.request.Request(url, headers={"User-Agent": "rcominote-offline-research/1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
                receipt["final_url"] = response.url
                receipt["headers"] = {
                    key: response.headers.get(key)
                    for key in ("Content-Type", "Content-Length", "ETag", "Last-Modified")
                }
            receipt["finished_utc"] = datetime.now(UTC).isoformat()
        else:
            data = (existing / name).read_bytes()
            receipt["verified_existing_source"] = str(existing / name)
        if digest(data) != expected:
            raise ValueError(f"Official pinned source changed: {name}")
        receipt.update(bytes=len(data), sha256=expected)
        save_files(originals, {name: data})
        receipts.append(receipt)
        (output / "acquisition.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2) + "\n")
        if label == "index.html":
            continue
        members = archive_members(data)
        if len(members) != (3 if label == "hardware" else 1):
            raise ValueError("Unexpected official archive inventory")
        save_files(output / "unpacked" / label, members)
        archives.append(
            {
                "label": label,
                "members": [{"name": n, "bytes": len(d), "sha256": digest(d)} for n, d in members.items()],
            }
        )
        if label != "hardware":
            report, exports = inspect_package(next(iter(members.values())), label=label)
            save_files(output / "packages" / label, exports)
            packages.append(report)
    report = {
        "schema": 1,
        "scope": "Pinned public downloads/static archive, CRC, FAT/XOR reads only; no vendor/device execution",
        "sources": receipts,
        "archives": archives,
        "packages": packages,
        "limits": [
            "CRC is not authentication",
            "Wrapped DB and XYZ_121 files remain opaque",
            "Tester16MiB and DUT MIPS are not CoMi recovery images",
        ],
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    (output / "inspection.json").write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    typer.run(main)
