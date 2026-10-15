#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Offline fixed SD experiment verification; never contacts Bluetooth/devices.

original IMAGE DIRECTORIES... checks complete private reports against the pinned
mapped image. published RECEIPT checks public tiny binaries and fixed oracle hashes
without the complete image. Neither mode repairs or joins incomplete downloads.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
PUBLIC_RECEIPT_SHA = "1ef2626c2f9c717660d6650cd1e270ac4154623027904d3c7285fd489450c62c"
PROFILES = {
    "ram": (0x18000000, 4096, 0xDD500, "35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b"),
    "header": (0x10000000, 32, 0, "2337540c74a6aa8984eb481c2fea27a80d12cfd4c24c5300db820f86a733f486"),
    "handler": (0x10024A20, 160, 0x24A20, "3f76f18c95ed6dfd6711681465491669ee48448b229eacfefb85aa9033ce68ab"),
    "tail": (
        0x18000000,
        128,
        0xDD500 + 3968,
        "4df945cc5444f4b5bf12834aa20aac25d070113c55d36ec4e244fadc02c4272f",
    ),
}
REPORTS = {
    "live-sd-bootstrap-20261013": (
        "ram",
        "a76e99224ef2482f8749f1a4d7036774cd9eda761171ff5cd97c7ae83ffbd8a9",
        None,
    ),
    "live-sd-tail128-20261013": (
        "tail",
        "201729075c502aaf0459a9f3820f1f35502675eade65dfd36a7cb2bf7c438b1b",
        "ram-tail128.bin",
    ),
    "live-sd-xip32-a-20261013": (
        "header",
        "d15d2cfbd877869b9c495d3351e9066bcc8c6eb07a3734b0a7cd98349fbcfe5d",
        None,
    ),
    "live-sd-xip32-b-20261013": (
        "header",
        "a81ed32e2085c24ec36218a8e5639a2e28ea8bb6a68fcc64a3ed394df6ccb4b3",
        "header-b32.bin",
    ),
    "live-sd-xip32-c-20261013": (
        "header",
        "f2311da2a613b77e915829e00f09fa9c9ac83e831d05883298290deb466e4b51",
        "header-c32.bin",
    ),
    "live-sd-handler160-20261013": (
        "handler",
        "0052c1abe23014cf35cfab7a5035e8b028c31f39060955e65d63a2d2bd3f80a9",
        None,
    ),
    "live-sd-handler160-read-20261013": (
        "handler",
        "47436e18770417c02fd8d5c04aedae0220ad93157faaacd57ec9c362fe2dc1ea",
        None,
    ),
    "live-sd-handler160-read-b-20261013": (
        "handler",
        "755527b171e70842f36e0a3437cff11714bc4cb3e4efd1bf1485fc2c6d22f89d",
        "handler160.bin",
    ),
}
ACK = "1d108107007f0400a0860100"
END = "1df1810000"
PREPARE, START, STOP = ("1d108105000002000100", "1d108105000002002000", "1d108105000002002100")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_sha(value: dict) -> str:
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def console(command: str) -> str:
    payload = command.encode("ascii") + b"\n"
    body = b"\x01" + len(payload).to_bytes(2, "little") + payload
    return (b"\x1d\x10\x81" + len(body).to_bytes(2, "little") + body).hex()


def actions(report: dict, command: str) -> dict:
    expected = [PREPARE, START, console(command), STOP]
    require(
        report.get("writes") == [{"hex": value, "att_write_confirmed": True} for value in expected],
        "Expected exactly four confirmed Actions writes and one fixed dumpbuf command",
    )
    require(report.get("notifications") == [ACK] * 4 + [END], "Expected four ACKs and empty F1")
    require(
        report.get("frames") == [{"command": 16, "hex": ACK}] * 4 + [{"command": 241, "hex": END}],
        "Unexpected strict Actions frames",
    )
    require(
        report.get("log_session_complete") is True
        and report.get("ack_count") == 4
        and report.get("expected_ack_count") == 4
        and report.get("end_received") is True
        and report.get("pending_hex") == "",
        "Incomplete Actions cleanup",
    )
    app_writes, notifications, pending, confirmations = [], [], False, 0
    for packet in report["att_packets"]:
        pdu = bytes.fromhex(packet["hex"])
        require(bool(pdu) and packet["direction"] in {"tx", "rx"}, "Malformed ATT trace entry")
        if packet["direction"] == "tx":
            if pdu[0] == 0x12:
                require(not pending, "Overlapping ATT Write Requests")
                pending = True
                handle = int.from_bytes(pdu[1:3], "little")
                if handle == 0x19:
                    require(pdu.hex() == "1219000100", "Unexpected CCCD write")
                else:
                    require(handle == 0x16, "Unexpected application write handle")
                    app_writes.append(pdu[3:].hex())
            else:
                require(pdu[0] in {2, 3, 4, 8, 16}, "Unexpected transmitted ATT opcode")
        elif pdu[0] == 0x13:
            require(pdu == b"\x13" and pending, "Unmatched/malformed Write Response")
            pending = False
            confirmations += 1
        elif pdu[0] == 0x1B:
            require(pdu[1:3] == b"\x18\0", "Unexpected notification handle")
            notifications.append(pdu[3:].hex())
    require(app_writes == expected and notifications == [ACK] * 4 + [END], "ATT/application trace mismatch")
    require(confirmations == 5 and not pending, "Expected CCCD plus four application Write Responses")
    return {
        "write_hex": expected,
        "att_write_responses_including_cccd": confirmations,
        "notification_hex": notifications,
        "ack_count": 4,
        "f1_received": True,
        "pending_hex": "",
    }


def original(image: Path, directories: list[Path]) -> dict:
    raw = image.read_bytes()
    require(sha(raw) == IMAGE_SHA, "Wrong complete mapped CoMi system image")
    require(
        len(directories) == len(REPORTS) and {p.name for p in directories} == set(REPORTS),
        "Pass each of the eight fixed experiment directories exactly once",
    )
    results = []
    for directory in sorted(directories, key=lambda p: p.name):
        profile, report_sha, public_binary = REPORTS[directory.name]
        report_bytes = (directory / "report.json").read_bytes()
        require(sha(report_bytes) == report_sha, f"Pinned report changed: {directory.name}")
        report = json.loads(report_bytes)
        address, size, offset, oracle_sha = PROFILES[profile]
        oracle = raw[offset : offset + size]
        require(len(oracle) == size and sha(oracle) == oracle_sha, f"Independent {profile} oracle changed")
        require(
            report["source_image_sha256"] == IMAGE_SHA and report["expected_sha256"] == oracle_sha,
            "Receipt oracle identity mismatch",
        )
        require(
            report["serial"] == "C261CF0430" and re.fullmatch(r"rc[0-9a-f]{10}", report["name"]) is not None,
            "Expected owned serial and generated experiment name",
        )
        path = f"/SD:/RECORDER/Call-{report['name']}.mp3"
        require(report["device_path"] == path, "Unexpected test-file device path")
        command_size = 4096 if profile == "tail" else size
        command = f"dbg dumpbuf {address} {command_size} {path}"
        require(report["dump_command"] == command, "Command differs from fixed source profile")
        preflight = directory.name in {"live-sd-xip32-a-20261013", "live-sd-handler160-read-20261013"}
        tail = profile == "tail"
        download_only = report.get("download_only", False)
        require(
            report["sd_write_attempted"] is (not preflight and not tail and not download_only),
            "SD attempt accounting differs",
        )
        entry = {
            "experiment": directory.name,
            "source_report_sha256": report_sha,
            "name": report["name"],
            "device_path": path,
            "profile": profile,
            "source_address": f"0x{address:08x}",
            "source_bytes": size,
            "image_oracle_offset": offset,
            "expected_sha256": oracle_sha,
            "dump_command": command,
            "sd_write_attempted": report["sd_write_attempted"],
            "ok": report["ok"],
            "error": report.get("error"),
            "actions": None,
            "info": None,
            "download": None,
            "download_only": download_only or tail,
        }
        if download_only or tail:
            parent_name = "live-sd-bootstrap-20261013" if tail else "live-sd-handler160-20261013"
            parent_directory = next(p for p in directories if p.name == parent_name)
            parent_bytes = (parent_directory / "report.json").read_bytes()
            require(
                report["parent_report_sha256"] == sha(parent_bytes) == REPORTS[parent_name][1],
                "Read-only receipt must bind the pinned complete Actions parent",
            )
            parent = json.loads(parent_bytes)
            require(
                all(
                    report[key] == parent[key]
                    for key in ("name", "device_path", "dump_command", "source_image_sha256")
                ),
                "Read-only name/path/command/source differs from parent",
            )
            actions(report=parent, command=parent["dump_command"])
            if not tail:
                require(
                    all(
                        report[key] == parent[key]
                        for key in ("source", "source_address", "source_bytes", "expected_sha256")
                    ),
                    "Read-only source profile differs from parent",
                )
            entry["parent_experiment"] = parent_name
            entry["parent_report_sha256"] = report["parent_report_sha256"]
        if preflight:
            require(
                report["error"] == "OSError: [Errno 38] LE ATT connect failed", "Expected preflight failure"
            )
            require(
                not any(k in report for k in ("before", "after", "att_packets", "writes")),
                "Unexpected preflight activity",
            )
        else:
            require(report["before"] == report["after"], "Complete before/after info differs")
            require(report["before"]["device"]["recording_state"] == "idle", "Expected idle recording state")
            info = report["before"]
            require(len(bytes.fromhex(info["device"]["raw"])) == 52, "Expected complete52-byte info")
            entry["info"] = {
                "before_sha256": canonical_sha(info),
                "after_sha256": canonical_sha(report["after"]),
                "complete_before_after_equal": True,
                "raw52_sha256": sha(bytes.fromhex(info["device"]["raw"])),
                "recording_state": "idle",
                "version": info["device"]["version"],
            }
            if tail or download_only:
                if tail:
                    require(
                        report.get("tail_only") is True and report["offset"] == 3968, "Tail offset differs"
                    )
                    entry["existing_file_offset"] = 3968
                else:
                    entry["existing_file_offset"] = 0
                require(
                    not any(k in report for k in ("att_packets", "writes", "frames")),
                    "Read-only existing-file download must not run Actions",
                )
            else:
                entry["actions"] = actions(report=report, command=command)
        binary = directory / "download.bin"
        if report["ok"]:
            data = binary.read_bytes()
            require(
                data == oracle and sha(data) == oracle_sha, "Downloaded data does not match independent image"
            )
            require(
                report.get("download_bytes") == report.get("received_bytes") == len(data)
                and report.get("download_sha256") == oracle_sha
                and report.get("exact_match") is True,
                "Download accounting differs",
            )
            require(
                public_binary is not None and report.get("error") is None, "Unexpected successful profile"
            )
            entry["download"] = {
                "bytes": len(data),
                "sha256": sha(data),
                "exact_image_oracle_match": True,
                "public_file": f"sd-bootstrap-2026-10-13/{public_binary}",
            }
        else:
            require(not binary.exists(), "Failed experiment unexpectedly retained bytes")
            require(public_binary is None, "Expected fixed successful download")
            entry["partial_bytes_retained"] = False
            if profile == "ram":
                require(
                    report["error"] == "RuntimeError: Short download: 3852/4096 bytes", "RAM failure changed"
                )
                entry["failed_download"] = {
                    "reported_received_bytes": 3852,
                    "requested_bytes": 4096,
                    "reported_deficit_bytes": 244,
                    "reconstructed": False,
                }
            elif profile == "handler":
                require(
                    report["error"] == "OSError: [Errno 38] LE ATT connect failed", "Handler failure changed"
                )
        results.append(entry)
    return {
        "schema_version": 1,
        "source_image_sha256": IMAGE_SHA,
        "source_image_bytes": len(raw),
        "scope": "Fixed own non-audio SD experiment files only; private recording-file lists omitted",
        "experiments": results,
        "comparison_verified": True,
        "limits": [
            "RAM4096 full-file transfer failed at3852; missing partial was not retained or patched with tail128",
            "Successful32-byte XIP headers are mapped system bytes, not raw NOR or an independent recovery backup",
            "Handler160 initial download connection failed; subsequent parent-bound read-only download exactly matched160-byte oracle",
            "Actions evidence is retained socket ATT trace; no independent HCI comparison claimed",
            "Equal complete before/after info does not prove unchanged hidden state; SD test files intentionally retained",
            "Full reports contain private recording lists and remain ignored; no full btsnoop/monitor published",
        ],
    }


def published(receipt: Path) -> dict:
    receipt_bytes = receipt.read_bytes()
    require(sha(receipt_bytes) == PUBLIC_RECEIPT_SHA, "Pinned public receipt changed")
    data = json.loads(receipt_bytes)
    require(
        data["source_image_sha256"] == IMAGE_SHA and data["comparison_verified"] is True,
        "Wrong public receipt",
    )
    require(
        {entry["experiment"] for entry in data["experiments"]} == set(REPORTS)
        and len(data["experiments"]) == len(REPORTS),
        "Public experiment set differs",
    )
    checked = []
    entries = {entry["experiment"]: entry for entry in data["experiments"]}
    for entry in data["experiments"]:
        profile, report_sha, public_binary = REPORTS[entry["experiment"]]
        address, size, offset, oracle_sha = PROFILES[profile]
        require(
            entry["source_report_sha256"] == report_sha
            and entry["profile"] == profile
            and entry["source_address"] == f"0x{address:08x}"
            and entry["source_bytes"] == size
            and entry["image_oracle_offset"] == offset
            and entry["expected_sha256"] == oracle_sha,
            "Public fixed identity/range mismatch",
        )
        if entry["info"] is not None:
            info = entry["info"]
            require(
                info["complete_before_after_equal"] is True
                and info["before_sha256"] == info["after_sha256"]
                and info["recording_state"] == "idle",
                "Public info equality accounting differs",
            )
        if entry["actions"] is not None:
            proof = entry["actions"]
            require(
                proof["write_hex"] == [PREPARE, START, console(entry["dump_command"]), STOP]
                and proof["att_write_responses_including_cccd"] == 5
                and proof["notification_hex"] == [ACK] * 4 + [END]
                and proof["ack_count"] == 4
                and proof["f1_received"] is True
                and proof["pending_hex"] == "",
                "Public Actions cleanup proof differs",
            )
        if entry["download_only"]:
            parent = entries[entry["parent_experiment"]]
            require(
                parent["actions"] is not None
                and entry["parent_report_sha256"] == parent["source_report_sha256"]
                and all(entry[key] == parent[key] for key in ("name", "device_path", "dump_command"))
                and entry["actions"] is None
                and entry["sd_write_attempted"] is False,
                "Public read-only parent binding differs",
            )
        download = entry["download"]
        if public_binary is None:
            require(download is None and entry["ok"] is False, "Unexpected successful public experiment")
            continue
        require(
            entry["ok"] is True
            and download["bytes"] == size
            and download["sha256"] == oracle_sha
            and download["public_file"] == f"sd-bootstrap-2026-10-13/{public_binary}",
            "Public download metadata differs",
        )
        raw = (receipt.parent / download["public_file"]).read_bytes()
        require(
            len(raw) == size and sha(raw) == oracle_sha, "Public downloaded raw differs from fixed oracle"
        )
        checked.append(download)
    return {
        "public_receipt_verified": True,
        "downloads_verified": checked,
        "limits": [
            "Public replay checks fixed hashes and compact receipts, not complete private reports or full image",
            "Complete independent image/original socket-trace comparison requires original mode",
            "No joining failed RAM transfer with independent tail; mapped XIP is not raw NOR",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    source = commands.add_parser("original")
    source.add_argument("image", type=Path)
    source.add_argument("directories", nargs="+", type=Path)
    public = commands.add_parser("published")
    public.add_argument("receipt", type=Path)
    args = parser.parse_args()
    result = (
        original(image=args.image, directories=args.directories)
        if args.mode == "original"
        else published(receipt=args.receipt)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
