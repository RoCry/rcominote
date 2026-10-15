#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Offline safe-span replay; --private-root adds full package semantic audits.

Public mode verifies selected bytes and pinned receipts. It cannot independently
prove absence of rows in the unpublished baseline or HCI events omitted publicly.
Private mode validates complete Actions, identities, rings and HCI captures.
Neither mode accesses a device, repairs missing bytes or reconstructs a full ring.
"""

import argparse
import importlib.util
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

from verify_sd_nor_progress import RECEIPT_SHA as GUARD_SHA
from verify_sd_nor_progress import published as guards_published
from verify_sd_nor_progress import raw_file, require, sha

RECEIPT_SHA = "34ccb6c8345f8afdc8939c11b6a8bc414db1cbb5283e29d9fed52109f55cf447"
BOOT_SHA = "72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec"
ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(rb"( {0,7}[0-9a-f]{1,8}): ((?:(?:[0-9a-f]{2}| [0-9a-f]) ){16})\r\n")


def parser():
    path = ROOT / "src/rcominote/experiments/hci_interval.py"
    spec = importlib.util.spec_from_file_location("nor_interval_hci", path)
    require(spec is not None and spec.loader is not None, "Missing stdlib HCI parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parameters(H, transport: dict, *, early_stop: bool = False) -> None:
    events = []
    for row in transport["parameter_records"]:
        event = H.decode(row["monitor_opcode"], bytes.fromhex(row["packet_hex"]))
        require(event is not None, "Selected HCI record lacks parameter event")
        events.append(event | {"record": row["record"], "timestamp_us": row["timestamp_us"]})
    expected = ["controller", "connect", "request", "status", "update"]
    if not early_stop or len(events) == 6:
        expected += ["disconnect"]
    require(
        [e["kind"] for e in events] == expected
        and [e["record"] for e in events[:5]] == [3, 18, 77, 78, 79]
        and (early_stop or events[-1]["record"] == 115),
        "Unexpected selected HCI events",
    )
    link = transport["link"]
    require(
        link["controller"] == "hci0" and link["peer"] == H.PEER and link["handle"] == 2048,
        "Wrong owned transport link",
    )
    requested, start, end = (
        transport[k] for k in ("update_requested_us", "download_start_us", "download_end_us")
    )
    baseline = H.current([e for e in events if e["timestamp_us"] < requested], link["handle"], link["local"])
    require(
        baseline == transport["baseline"]
        and (baseline["interval"], baseline["latency"], baseline["timeout"]) == (36, 0, 500),
        "Wrong baseline parameter state",
    )
    applied = H.applied(
        [e for e in events if e["timestamp_us"] <= end], link["handle"], link["local"], baseline, requested
    )
    require(
        applied == transport["applied"] and events[2] == transport["actual_hci_request"],
        "Applied/request bytes differ from metadata",
    )
    require(
        requested
        <= events[2]["timestamp_us"]
        < events[3]["timestamp_us"]
        < applied["timestamp_us"]
        <= start
        < end,
        "Update/download/cleanup chronology changed",
    )
    if events[-1]["kind"] == "disconnect":
        require(end < events[-1]["timestamp_us"], "Disconnect precedes download completion")
    if early_stop:
        require(
            transport["capture_last_timestamp_us"] >= end
            and transport["monitor_exit"] in (0, 130)
            and transport["monitor_stop"] == {"signal": "SIGINT", "requested": True, "delivery": "sent"},
            "Early close lacks capture coverage/owned SIGINT receipt",
        )
    require(
        transport["profile"] == "interval6-ce1" and transport["condition"] == "verified-through-download",
        "Incomplete parameter condition",
    )


def state(value: dict, *, write: bool) -> None:
    require(
        value["other_state_equal"] is True
        and value["allowed_decrease"] == int(write)
        and value["free_capacity_before"] - value["free_capacity_after"]
        == value["free_capacity_decrease"]
        == 0
        and value["free_capacity_before"] == 59593,
        "Unexpected compact state comparison",
    )


def marker(raw: bytes, command: str) -> None:
    require(
        re.fullmatch(rb"logsrv: cmd\([0-9]+\) " + re.escape(command.encode()) + rb"\n\r\n", raw) is not None,
        "Current command marker differs",
    )


def sector_rows(raw: bytes, nor_offset: int) -> bytes:
    require(nor_offset in (0, 0x4200), "Only fixed boot0/recovery-block1 offsets permitted")
    status = re.match(rf"\r\nfread 512b: offset=0x{nor_offset:x}, buf=0x[0-9a-f]+\r\n(?:\r\n)*".encode(), raw)
    require(status is not None, "Missing fixed boot0 status")
    rows = list(LINE.finditer(raw, status.end()))
    require(
        len(rows) == 32 and rows[0].start() == status.end() and rows[-1].end() == len(raw),
        "Requires complete bounded32-row region",
    )
    for index, row in enumerate(rows):
        require(
            row[1] == f"{index * 16:8x}".encode() and (index == 0 or rows[index - 1].end() == row.start()),
            "Missing, shifted or discontinuous NOR row",
        )
    return bytes(int(token, 16) for row in rows for token in row[2].split())


def boot_sector(raw: bytes) -> bytes:
    return sector_rows(raw, 0)


def published(receipt: Path) -> tuple[dict, dict]:
    raw = receipt.read_bytes()
    require(sha(raw) == RECEIPT_SHA, "Pinned NOR interval receipt changed")
    data = json.loads(raw)
    require(data["schema"] == 1 and data["serial"] == "C261CF0430", "Wrong receipt target/schema")
    for name, expected in data["parser_sources"].items():
        require(sha((ROOT / name).read_bytes()) == expected, "Parser source changed")
    guard_ref = data["guard_bundle"]
    guard_path = receipt.parent / guard_ref["file"]
    require(
        sha(guard_path.read_bytes()) == guard_ref["sha256"] == GUARD_SHA, "Wrong prerequisite guard bundle"
    )
    guard_data, _ = guards_published(guard_path)
    guard_hashes = sorted(row["source_report_sha256"] for row in guard_data["guards"])
    H = parser()
    failure = data["failed_context"]
    require(
        failure["original_ok"] is False
        and failure["sd_write_attempted"] is False
        and failure["actions_commands"] == 0
        and failure["payload_reused"] is False
        and failure["error"] == "TimeoutError: [Errno 110] Connection timed out",
        "Failed original context must remain zero-write failure",
    )
    state(failure["state"], write=False)
    phases = data["phases"]
    require(set(phases) == {"context-b", "baseline", "boot"}, "Wrong phase set")
    public = []
    for name, row in phases.items():
        count = 5 if name == "boot" else 4
        require(
            row["original_ok"] is True
            and row["actions"]
            == {"confirmed_writes": count, "ack_count": count, "f1_received": True, "pending_bytes": 0},
            "Incomplete compact Actions proof",
        )
        state(row["state"], write=True)
        require(sorted(row["guards_report_sha256"]) == guard_hashes, "Guard parent chain changed")
        address, size = (0x1800E008, 28) if name == "context-b" else (0x1803EE09, 4096)
        require(
            row["source_address"] == hex(address)
            and row["source_bytes"] == size
            and row["download"]["file"].endswith(f"/{name}/download.bin"),
            "Wrong fixed phase source",
        )
        require(
            re.fullmatch(
                rf"dbg dumpbuf {address} {size} /SD:/RECORDER/Call-rc[0-9a-f]{{10}}\.mp3", row["dump_command"]
            ),
            "Wrong fixed phase command",
        )
        if name == "context-b":
            body = raw_file(receipt.parent, row["raw"])
            require(
                len(body) == 28
                and struct.unpack("<5I", body[:20]) == (1284, 1284, 0, 4096, 0x1803EE09)
                and body[20:22] == b"\1\0"
                and row["fields"]["raw_hex"] == body.hex(),
                "Fresh context differs",
            )
            public.append(row["raw"])
            continue
        parameters(H, row["transport"])
        state(row["transport"]["state_verification"], write=False)
        require(row["full_ring_published"] is False, "Full private ring must stay unpublished")
        marker(raw_file(receipt.parent, row["dump_marker"]), row["dump_command"])
        public.append(row["dump_marker"])
        parent = phases["context-b" if name == "baseline" else "baseline"]
        require(
            row["previous_report_sha256"] == parent["source_report"]["sha256"], "Fresh phase parent changed"
        )
    baseline, boot = phases["baseline"], phases["boot"]
    require(
        baseline["full_private_payload_verification"] == {"unique_current_marker": True, "no_nor_rows": True},
        "Private baseline audit declaration changed",
    )
    require(boot["producer"] == "dbg fread spi_flash 0", "Only fixed boot0 producer permitted")
    marker(raw_file(receipt.parent, boot["producer_marker"]), boot["producer"])
    region = raw_file(receipt.parent, boot["status_and_rows"])
    sector = boot_sector(region)
    oracle_ref = data["boot_oracle"]
    require(
        (oracle_ref["slice_offset"], oracle_ref["slice_bytes"], oracle_ref["slice_sha256"])
        == (0, 512, BOOT_SHA),
        "Wrong independent boot oracle slice",
    )
    oracle = raw_file(receipt.parent, oracle_ref)[:512]
    require(
        len(sector) == 512 and sha(sector) == BOOT_SHA and sector == oracle,
        "Boot sector differs from independent oracle",
    )
    public += [boot["producer_marker"], boot["status_and_rows"]]
    spans = [boot[key]["ring_span"] for key in ("status_and_rows", "producer_marker", "dump_marker")]
    require(
        all(0 <= start < end <= 4096 for start, end in spans)
        and spans[0][1] <= spans[1][0] < spans[1][1] <= spans[2][0]
        and spans[-1][1] - spans[0][0] <= 4096,
        "Producer/status/rows/current-marker bounds changed",
    )
    for row in public:
        if "ring_span" in row:
            require(row["ring_span"][1] - row["ring_span"][0] == row["bytes"], "Selected span length differs")
    require(
        sum(row["bytes"] for row in public) == data["public_new_raw_bytes"] == 2198
        and data["new_sd_files"] == 3
        and data["retained_sd_test_files_total"] == 45,
        "Wrong public byte/residue counts",
    )
    require(
        all(
            data["private_audit"][key] is True
            for key in (
                "performed_offline",
                "full_actions_and_identity",
                "full_hci_parameter_condition",
                "complete_private_payloads",
            )
        )
        and data["private_audit"]["device_io"] is False,
        "Wrong private audit scope",
    )
    return data, {
        "compact_public_replay_verified": True,
        "public_new_raw_bytes": 2198,
        "boot_sector_bytes": 512,
        "boot_sector_sha256": BOOT_SHA,
        "full_private_audit_replayed": False,
        "full_nor_backup": False,
    }


def private_audit(data: dict, root: Path) -> int:
    for name, expected in data["private_sources"].items():
        raw = (root / name).read_bytes()
        require(
            len(raw) == expected["bytes"] and sha(raw) == expected["sha256"],
            "Private source changed: " + name,
        )
    if data["schema"] == 2:
        from sd_nor_interval_extension import private_pair

        return private_pair(data, root)
    sys.path.insert(0, str(root / "src"))
    from rcominote.experiments import sd_nor_interval as I
    from rcominote.experiments import sd_nor_probe as P

    base = root / "artifacts/nor-sd-interval6-20261014"
    image = (root / "artifacts/mapped-system-20261012.bin").read_bytes()
    context, _ = P.load(base / "context-b")
    handler = root / "artifacts/live-sd-handler160-20261013"
    guards = P.validate_guards([Path(g["directory"]) for g in context["guards"]], image, handler)
    baseline = P.previous(base / "baseline", P.Phase.baseline, guards, image, handler)
    report, _ = P.load(base / "boot")
    require(
        report["previous"] == baseline
        and report["guards"] == guards
        and report["source_image_sha256"] == P.IMAGE_SHA
        and report["ok"] is True
        and not report.get("error")
        and report["sd_write_attempted"] is True,
        "Boot private parent/identity/status changed",
    )
    P.same_identity(report)
    P.command(report, P.BUFFER, 4096)
    P.validate_actions(report, producer=True)
    ring = P.downloaded(report, base / "boot", 4096)
    require(
        P.validate_payload(report, ring) == report["verification"], "Boot private payload summary differs"
    )
    I.replay(report["transport"], base / "boot")
    require(
        (base / "boot/sector.bin").read_bytes().hex() == report["verification"]["sector_hex"],
        "Private sector differs",
    )
    failed, _ = P.load(base / "context")
    require(
        failed["ok"] is False
        and failed["sd_write_attempted"] is False
        and failed["error"] == data["failed_context"]["error"]
        and not any(
            bytes.fromhex(r["hex"])[0] in (0x12, 0x52)
            for r in failed["att_packets"]
            if r["direction"] == "tx"
        )
        and not any(k in failed for k in ("writes", "frames", "notifications", "download_bytes")),
        "Failed original context contains writes/Actions/download",
    )
    P.same_identity(failed)
    return len(data["private_sources"])


def private(data: dict, root: Path) -> int:
    # The public standalone script deliberately has no third-party dependencies.
    # Full package validators run in the already-installed project environment.
    code = (
        "import json,sys; from pathlib import Path; "
        "sys.path.insert(0, str(Path(sys.argv[1])/'tools')); "
        "from verify_sd_nor_interval import private_audit; "
        "print(private_audit(json.load(sys.stdin), Path(sys.argv[1])))"
    )
    result = subprocess.run(
        ["uv", "run", "--directory", str(root), "--no-sync", "python", "-c", code, str(root)],
        input=json.dumps(data, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("Full private semantic replay failed: " + result.stderr.strip())
    return int(result.stdout.strip())


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("receipt", type=Path)
    cli.add_argument("--private-root", type=Path)
    args = cli.parse_args()
    from sd_nor_interval_extension import RECEIPT_SHA as EXTENSION_SHA
    from sd_nor_interval_extension import published as extension_published

    data, result = (
        extension_published(args.receipt)
        if sha(args.receipt.read_bytes()) == EXTENSION_SHA
        else published(args.receipt)
    )
    if args.private_root is not None:
        result |= {
            "private_hashes_verified": private(data, args.private_root.resolve()),
            "full_private_audit_replayed": True,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
