#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Offline compact/public or full/private replay of the sole interval6 RAM transfer."""

import argparse
import gzip
import importlib.util
import json
import sys
from pathlib import Path

from verify_linux_mtu128 import owned_att, records
from verify_sd_bootstrap import actions, require, sha

RECEIPT_SHA = "7d08bdce90ba924f93976fb9a3497d7bdb60c08a18cf6ebb0140dd3bae9f94ca"
IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
ORACLE_SHA = "35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b"
PARENT_SHA = "a76e99224ef2482f8749f1a4d7036774cd9eda761171ff5cd97c7ae83ffbd8a9"
ROOT = Path(__file__).resolve().parents[1]


def local_module(name: str, path: str):
    """Load existing stdlib-only parser directly, without device/package imports."""
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    require(spec is not None and spec.loader is not None, "Missing local parser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def parameter_gate(H, events: list[dict], experiment: dict) -> dict:
    require([row["record"] for row in events] == [3, 18, 77, 78, 79, 114], "Wrong selected event records")
    require(
        [row["kind"] for row in events]
        == ["controller", "connect", "request", "status", "update", "disconnect"],
        "Wrong selected parameter-event sequence",
    )
    link = experiment["link"]
    require(
        link["handle"] == 2048 and link["controller"] == "hci0" and link["peer"] == H.PEER,
        "Wrong owned socket link",
    )
    requested = experiment["update_requested_us"]
    baseline = H.current(
        [row for row in events if row["timestamp_us"] < requested], link["handle"], link["local"]
    )
    require(
        baseline == experiment["baseline"]
        and (baseline["interval"], baseline["latency"], baseline["timeout"]) == (36, 0, 500),
        "Baseline was not observed45ms/lat0/timeout500",
    )
    through = [row for row in events if row["timestamp_us"] <= experiment["download_end_us"]]
    applied = H.applied(through, link["handle"], link["local"], baseline, requested)
    require(
        applied == experiment["applied"] and events[2] == experiment["actual_hci_request"],
        "Actual HCI update/request differs",
    )
    require(
        requested
        <= events[2]["timestamp_us"]
        < events[3]["timestamp_us"]
        < applied["timestamp_us"]
        <= experiment["download_start_us"]
        < experiment["download_end_us"]
        < events[-1]["timestamp_us"],
        "Update/data/cleanup chronology changed",
    )
    require(
        events[-1]["status"] == 0 and events[-1]["handle"] == link["handle"], "Unexpected cleanup disconnect"
    )
    return applied


def state(P, before: dict, after: dict) -> dict:
    for info in (before, after):
        payload = bytes.fromhex(info["device"]["raw"])
        require(
            info["serial"] == "C261CF0430"
            and len(payload) == 52
            and P.parse_device_info(payload) == info["device"]
            and info["device"]["version"] == "010004"
            and info["device"]["recording_state"] == "idle",
            "Requires complete consistent owned idle FW010004 info",
        )
    require(before == after, "Read-only state changed")
    free = before["device"]["free_capacity"]
    return {
        "other_state_equal": True,
        "free_capacity_unit": "MiB (integer firmware report)",
        "free_capacity_before": free,
        "free_capacity_after": free,
        "free_capacity_decrease": 0,
        "allowed_decrease": 0,
    }


def transfer(P, packets: list[dict], report: dict, oracle: bytes) -> dict:
    """Reuse ACL reassembly; validate fixed Boyi sequence, declaration/data/end, identities."""
    controls, writes, data = [], [], []
    for row in packets:
        pdu = bytes.fromhex(row["hex"])
        if row["direction"] == "tx":
            if pdu[0] == 0x12:
                require(
                    pdu in [bytes.fromhex("1225000100"), bytes.fromhex("122b000100")],
                    "Unexpected ATT Write Request/Actions",
                )
            elif pdu[0] == 0x52:
                require(pdu[1:3] == b"\x22\0", "Unexpected write-command handle")
                command, payload = P.parse(pdu[3:])
                writes.append((command, payload))
            else:
                require(pdu[0] in [2, 3, 4, 8, 16], "Unexpected transmitted ATT opcode")
        elif pdu[0] == 0x1B:
            handle = int.from_bytes(pdu[1:3], "little")
            if handle == 42:
                data.append((row["hci_records"], pdu[3:]))
            else:
                require(handle == 36, "Unexpected notification/Actions handle")
                command, payload = P.parse(pdu[3:])
                controls.append((command, payload, row["hci_records"]))
    require(
        [cmd for cmd, _ in writes] == [1, 2, 5, 11, 1, 2, 5]
        and all(not payload for cmd, payload in writes if cmd != 11),
        "Unexpected application request sequence",
    )
    require(
        writes[3][1] == b"rc6ae65544fe".ljust(14, b"\0") + bytes(4),
        "Requires exactly one existing-file offset0 request",
    )
    require(
        [cmd for cmd, _, _ in controls] == [1, 2, 5, 11, 11, 1, 2, 5], "Unexpected control-response sequence"
    )
    require(
        controls[3][1] == b"\0\0\0\x10\0"
        and controls[4][1] == b"\x02"
        and controls[3][2] == [83]
        and controls[4][2] == [102],
        "Missing4096 declaration/explicit end",
    )
    require(
        len(data) == 18 and [n for group, _ in data for n in group] == list(range(84, 102)),
        "Missing or extra owned transfer notifications",
    )
    downloaded = b"".join(value for _, value in data)
    require(
        downloaded == oracle and sha(downloaded) == ORACLE_SHA, "Full HCI data differs from4096-byte oracle"
    )
    for start, key in [(0, "before"), (5, "after")]:
        serial = controls[start][1].decode("ascii")
        bound = controls[start + 1][1]
        require(bound in [b"\0", b"\x01"], "Invalid bind state")
        info = {
            "serial": serial,
            "bound": bool(bound[0]),
            "device": P.parse_device_info(controls[start + 2][1]),
        }
        require(info == report[key], "HCI identity differs from report")
    return {
        "notifications": 18,
        "lengths": [len(value) for _, value in data],
        "bytes": len(downloaded),
        "sha256": sha(downloaded),
        "declaration_record": 83,
        "end_record": 102,
        "application_commands": [cmd for cmd, _ in writes],
        "actions_commands": 0,
    }


def published(receipt: Path) -> tuple[dict, bytes, dict]:
    raw = receipt.read_bytes()
    require(sha(raw) == RECEIPT_SHA, "Pinned interval receipt changed")
    data = json.loads(raw)
    for path, expected in data["parser_sources"].items():
        require(sha((ROOT / path).read_bytes()) == expected, "Parser source changed: " + path)
    H = local_module("interval_hci_evidence", "src/rcominote/experiments/hci_interval.py")
    image = gzip.decompress((receipt.parent / data["image"]["file"]).read_bytes())
    require(len(image) == 927632 and sha(image) == IMAGE_SHA, "Wrong complete image oracle")
    oracle = image[0xDD500:0xDE500]
    require(len(oracle) == 4096 and sha(oracle) == ORACLE_SHA, "Wrong RAM4096 image slice")
    events = []
    for row in data["parameter_records"]:
        require(row["controller_index"] == 0, "Wrong HCI controller")
        value = H.decode(row["monitor_opcode"], bytes.fromhex(row["packet_hex"]))
        require(value is not None, "Selected record has no parameter event")
        value |= {"record": row["record"], "timestamp_us": row["timestamp_us"]}
        require(value == row["decoded"], "Decoded selected event differs from bytes")
        events.append(value)
    experiment = data["experiment"]
    parameter_gate(H, events, experiment)
    require(
        experiment["original_ok"] is True
        and experiment["condition"] == "verified-through-download"
        and experiment["sd_write_attempted"] is False,
        "Experiment did not fully pass",
    )
    full = experiment["full"]
    require(
        full["offset"] == 0
        and full["expected_bytes"] == full["download_bytes"] == full["received_bytes"] == 4096
        and full["transfer_complete"] is True
        and full["exact_match"] is True
        and full["sha256"] == ORACLE_SHA,
        "Incomplete compact full transfer",
    )
    parent = data["parent"]
    require(
        parent["source_report"]["sha256"] == PARENT_SHA
        and parent["original_ok"] is False
        and parent["actions"]
        == {"confirmed_writes": 4, "ack_count": 4, "f1_received": True, "pending_bytes": 0}
        and parent["state"]["other_state_equal"] is True
        and parent["state"]["free_capacity_decrease"] == 0,
        "Original failed-download parent creation/state contract changed",
    )
    require(
        experiment["state"]
        == {
            "other_state_equal": True,
            "free_capacity_unit": "MiB (integer firmware report)",
            "free_capacity_before": 59593,
            "free_capacity_after": 59593,
            "free_capacity_decrease": 0,
            "allowed_decrease": 0,
        },
        "Read-only state summary changed",
    )
    failure = data["offline_failure"]
    require(
        failure["original_ok"] is False
        and failure["device_io"] is False
        and failure["update_attempted"] is False
        and failure["sd_write_attempted"] is False
        and failure["error"] == "ValueError: Expected one nonempty password line",
        "Authentication-preflight failure is not a hardware retry",
    )
    require(
        data["attempt_accounting"]
        == {"invocations": 2, "device_trials": 1, "offline_failures": 1, "retries_after_device_trial": 0},
        "Wrong trial accounting",
    )
    return (
        data,
        oracle,
        {
            "compact_public_replay_verified": True,
            "private_semantic_replay": False,
            "baseline_interval_ms": 45,
            "applied_interval_ms": 7.5,
            "request_ce_length_hints": [1, 1],
            "latency": 0,
            "timeout_units10ms": 500,
            "full_exact_bytes": 4096,
            "oracle_sha256": ORACLE_SHA,
            "parameter_records": [row["record"] for row in events],
            "scope": "One observed policy trial; not interval-only or controlled historical comparison",
        },
    )


def original(receipt: Path, private_root: Path) -> dict:
    data, oracle, result = published(receipt)
    for name, expected in data["private_sources"].items():
        raw = (private_root / name).read_bytes()
        require(
            len(raw) == expected["bytes"] and sha(raw) == expected["sha256"],
            "Private source changed: " + name,
        )
    experiment = data["experiment"]
    directory = private_root / experiment["source_directory"]
    report = json.loads((directory / "report.json").read_bytes())
    hci = (directory / "session.btsnoop").read_bytes()
    require((directory / "full.bin").read_bytes() == oracle, "Saved full file differs from oracle")
    require(
        report["ok"] is True
        and not any(report.get(key) for key in ["error", "after_error", "hci_final_error"])
        and report["sd_write_attempted"] is False
        and report["condition"] == "verified-through-download"
        and report["update_attempted"] is True
        and report["prior_hci_request"] is None,
        "Original trial status/profile differs",
    )
    require(
        all(
            report[key] == experiment[key]
            for key in [
                "link",
                "baseline",
                "actual_hci_request",
                "applied",
                "update_requested_us",
                "download_start_us",
                "download_end_us",
                "full",
            ]
        ),
        "Compact experiment differs from original",
    )
    H = local_module("interval_hci_private", "src/rcominote/experiments/hci_interval.py")
    P = local_module("interval_boyi_private", "src/rcominote/protocol.py")
    snoop = H.Snoop()
    snoop.feed(hci, final=True)
    require(
        snoop.records == 115
        and len(hci) == 8554
        and report["hci_capture"] == {"bytes": 8554, "sha256": sha(hci), "records": 115},
        "Original HCI capture summary differs",
    )
    parameter_gate(H, snoop.events, experiment)
    actual_records = [
        {
            "record": number,
            "controller_index": index,
            "monitor_opcode": opcode,
            "timestamp_us": stamp,
            "packet_hex": payload.hex(),
            "decoded": event,
        }
        for number, index, opcode, stamp, payload in records(hci)
        for event in snoop.events
        if event["record"] == number
    ]
    require(actual_records == data["parameter_records"], "Public selected HCI bytes differ from full capture")
    packets, _ = owned_att(hci, expected_lifetime=(115, 18, 114))
    summary = transfer(P, packets, report, oracle)
    require(summary == data["owned_transfer"], "Compact transfer differs from complete owned HCI")
    require(
        state(P, report["before"], report["after"]) == report["state_verification"] == experiment["state"],
        "Full original state differs",
    )
    parent_path = private_root / data["parent"]["source_report"]["file"]
    parent = json.loads(parent_path.read_bytes())
    require(
        parent["ok"] is False
        and parent["sd_write_attempted"] is True
        and parent["source_image_sha256"] == IMAGE_SHA
        and parent["expected_sha256"] == ORACLE_SHA,
        "Parent historical status/oracle changed",
    )
    command = "dbg dumpbuf 402653184 4096 /SD:/RECORDER/Call-rc6ae65544fe.mp3"
    proof = actions(parent, command)
    require(
        proof["ack_count"] == 4
        and parent["dump_command"] == command
        and parent["name"] == report["name"] == "rc6ae65544fe"
        and report["parent"]["report_sha256"] == PARENT_SHA
        and report["parent"]["actions_verified"] is True,
        "Original file parent binding differs",
    )
    # This original write's before/after info is equal; allow its declared write accounting.
    parent_state = state(P, parent["before"], parent["after"])
    parent_state["allowed_decrease"] = 1
    require(
        parent_state == report["parent"]["state_verification"] == data["parent"]["state"],
        "Original parent state summary differs",
    )
    failed = json.loads((private_root / data["offline_failure"]["source_report"]["file"]).read_bytes())
    failed_dir = (private_root / data["offline_failure"]["source_report"]["file"]).parent
    require(
        not any((failed_dir / name).exists() for name in ["session.btsnoop", "full.bin"]),
        "Offline authorization failure has unexpected capture/download",
    )
    require(
        failed["ok"] is False
        and failed["update_attempted"] is False
        and failed["sd_write_attempted"] is False
        and failed["error"] == data["offline_failure"]["error"]
        and not any(key in failed for key in ["before", "after", "link", "hci_capture", "full"]),
        "Offline invocation unexpectedly performed device work",
    )
    result.update(
        private_semantic_replay=True,
        private_source_hashes_verified=len(data["private_sources"]),
        owned_transfer=summary,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--private-root", type=Path)
    args = parser.parse_args()
    result = (
        original(args.receipt, args.private_root)
        if args.private_root is not None
        else published(args.receipt)[2]
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
