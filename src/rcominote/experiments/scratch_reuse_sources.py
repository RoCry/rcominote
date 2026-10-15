"""Pinned scratch ownership, static candidate identity, independent oracles/state.

Offline only. Original complete download proves which dedicated file was ours;
the current device object still requires a full read/hash match before overwrite.
New uptime/dispatcher regions are static image evidence, not live code readback.
"""

import hashlib
import json
from pathlib import Path

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import boot_tail_job as chronology
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import sd_nor_targets as T
from rcominote.experiments import status_remaining_job as J
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.printk_ring import BUFFER

NAME = "rc52cc41f671"
BASELINE_SHA = "a2f7c04b495717e5b851f911f6dbf24471dfbde567c8124da65eb8c9e43b446d"
KNOWN_REPORT_SHA = "0f74ac3023f5635740e214ecc9b05bc5b84153dee89c5bb8d2c3201c1c28985d"
KNOWN_HCI_SHA = "fec7195c55d2df3ebe583a08357e54881e89f5115c5faa49ab6cab10284050ff"
FINAL_REPORT_SHA = "2becbfbe0845666929794e41f34763ff68d0d8f1b19f899a523e0a36f317cbcb"
FINAL_PAIR_SHA = "bb6829e10d6a0fd3b5e718a13357bea81b3df4ad5121f6eb9f895f553d7d943b"
FINAL_HCI_SHA = "4bcfd7739788efcddddd96714834ebeda641c8b8760b32feb78d107936da364f"
FULL_BOOT_SHA = "f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6"
IMAGE_SHA = S.probe.IMAGE_SHA
STATIC_RECEIPT = Path("docs/evidence/nor-scratch-reuse-static-2026-10-14.json")
STATIC_SHA = "44dcbfd27c270b44701a765874e1a3bd47388735ff4482f0d78c583d40826d36"
REGION_IDS = (
    "kernel_descriptor",
    "kernel_selector",
    "uptime_descriptor",
    "uptime_handler_complete",
    "uptime_format_pointer",
    "uptime_thunk",
    "uptime_clock_wrapper",
    "dispatcher_copy_descriptor",
    "dispatcher_arg_gate_and_call",
    "logsrv_echo_execute",
    "logsrv_buffer_literal",
    "logsrv_echo_format_literal",
    "shell_execute_copy",
    "dumpbuf_handler_complete",
    "vfs_open_flags",
    "vfs_open_dispatch",
    "vfs_write_dispatch",
    "fatfs_ops",
    "fatfs_open_adapter",
    "f_open_existing_mode",
    "f_open_initial_cursor",
    "fatfs_write_adapter",
    "f_write_position_size",
    "boyi_get_file_handler",
    "boyi_worker_open_paths",
    "boyi_worker_path_literals",
    "boyi_worker_size_seek",
    "boyi_worker_end_close",
    "uptime_name",
    "uptime_help",
    "uptime_format",
    "logsrv_echo_format",
    "recording_directory",
    "call_prefix",
    "note_prefix",
    "recording_path_format",
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def pinned(path: Path, digest: str) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    if sha(raw) != digest:
        raise ValueError(f"Pinned scratch-reuse source changed: {path}")
    return raw, {"file": str(path.resolve()), "bytes": len(raw), "sha256": digest}


def static_gate(image: Path) -> dict:
    raw, receipt = pinned(STATIC_RECEIPT, STATIC_SHA)
    proof = json.loads(raw)
    data, image_ref = pinned(image, IMAGE_SHA)
    regions = proof["regions"]
    if (
        len(data) != 927632
        or proof.get("schema") != "nor-scratch-reuse-static-v1"
        or proof.get("status") != "offline-static-candidate-not-live-validated"
        or proof["image"]["bytes"] != 927632
        or proof["image"]["sha256"] != IMAGE_SHA
        or proof["image"]["cpu_base"] != "0x10000000"
        or len(regions) != len(REGION_IDS)
        or {region["id"] for region in regions} != set(REGION_IDS)
    ):
        raise ValueError("Requires complete fixed image and all36 scratch-reuse static identity regions")
    for region in regions:
        start, end = [int(region[key], 16) - 0x10000000 for key in ("start", "end_exclusive")]
        if (
            not 0 <= start < end <= len(data)
            or type(region["bytes"]) is not int
            or end - start != region["bytes"]
            or data[start:end].hex() != region["hex"]
            or sha(data[start:end]) != region["sha256"]
        ):
            raise ValueError(f"Static scratch-reuse region differs from actual image: {region['id']}")
    return {
        "receipt": receipt,
        "image": image_ref,
        "cpu_base": "0x10000000",
        "verified_regions": len(regions),
        "regions": regions,
        "current_live_code_verified": False,
    }


def known_gate(directory: Path, image: Path) -> tuple[bytes, dict]:
    raw, report_ref = pinned(directory / "report.json", KNOWN_REPORT_SHA)
    _, hci_ref = pinned(directory / "session.btsnoop", KNOWN_HCI_SHA)
    baseline, baseline_ref = pinned(directory / "boot/download.bin", BASELINE_SHA)
    report = json.loads(raw)
    operations = report["operations"]
    if (
        report.get("profile") != "dual-known-boot0-recovery4200"
        or report.get("serial") != OWNED_SERIAL
        or report.get("source_image_sha256") != IMAGE_SHA
        or report.get("ok") is not True
        or len(operations) != 2
        or [op["phase"] for op in operations] != ["boot", "recovery-block1"]
        or len(baseline) != 4096
    ):
        raise ValueError("Requires original successful known pair and complete4096-byte owned-file baseline")
    boot = operations[0]
    path = f"/SD:/RECORDER/Call-{NAME}.mp3"
    expected = {
        "name": NAME,
        "phase": "boot",
        "device_path": path,
        "producer": T.PRODUCER,
        "source_address": hex(BUFFER),
        "source_bytes": 4096,
        "dump_command": f"dbg dumpbuf {BUFFER} 4096 {path}",
        "transport_profile": "interval6-ce1",
        "download_bytes": 4096,
        "received_bytes": 4096,
        "download_sha256": BASELINE_SHA,
    }
    if any(boot.get(key) != value for key, value in expected.items()) or any(
        boot.get(key) is not True for key in ("ok", "live_complete", "sd_write_attempted")
    ):
        raise ValueError("Scratch must be exact originally written and download-confirmed known boot file")
    result = S.replay(directory, image)
    if result != {
        "verified": True,
        "connections": 1,
        "targets": [0, 0x4200],
        "sector_sha256": [T.BOOT_SHA, T.RECOVERY_BLOCK_SHA],
    }:
        raise ValueError("Complete original known-pair replay differs from both independent target oracles")
    chronology.time_order(report["started_at"], report["ended_at"])
    verify_state(report["after"], report["after"], sd_write=False)
    return baseline, {
        "directory": str(directory.resolve()),
        "report_sha256": KNOWN_REPORT_SHA,
        "hci_sha256": KNOWN_HCI_SHA,
        "ended_at": report["ended_at"],
        "latest_info": report["after"],
        "verification": result,
        "baseline": baseline_ref,
        "references": {"report": report_ref, "capture": hci_ref},
    }


def state_gate(directory: Path, image: Path) -> tuple[dict, dict]:
    raw, report_ref = pinned(directory / "report.json", FINAL_REPORT_SHA)
    pair_raw, pair_ref = pinned(directory / "2e00/report.json", FINAL_PAIR_SHA)
    _, hci_ref = pinned(directory / "2e00/session.btsnoop", FINAL_HCI_SHA)
    report, pair = json.loads(raw), json.loads(pair_raw)
    result = J.replay(directory, image)
    if (
        report.get("ok") is not True
        or report.get("verification") != result
        or result.get("partition_range") != [0x2000, 0x3000]
        or result.get("partition_bytes") != 4096
        or result.get("partition_sha256") != FULL_BOOT_SHA
        or pair.get("ok") is not True
        or pair.get("pair_verified") is not True
        or pair.get("final_audit_complete") is not True
        or pair.get("source_image_sha256") != IMAGE_SHA
        or pair["after"]["device"]["free_capacity"] != 59589
    ):
        raise ValueError("Requires exact successful final-sector job and actual final59589 identity")
    info = pair["after"]
    verify_state(info, info, sd_write=False)
    chronology.time_order(report["started_at"], pair["started_at"], pair["ended_at"], report["ended_at"])
    return info, {
        "directory": str(directory.resolve()),
        "report_sha256": FINAL_REPORT_SHA,
        "pair_report_sha256": FINAL_PAIR_SHA,
        "hci_sha256": FINAL_HCI_SHA,
        "ended_at": report["ended_at"],
        "latest_info": info,
        "verification": result,
        "references": {"report": report_ref, "pair": pair_ref, "capture": hci_ref},
    }


def oracles() -> dict:
    result = {}
    for key, phase, source, bounds in (
        ("boot0", T.Phase.boot, Path("docs/evidence/boot-complete-2026-10-12/raw.bin"), [0, 512]),
        ("4200", T.Phase.recovery, T.RECOVERY_RAW, [512, 1024]),
    ):
        offset, data, proof = T.oracle(phase)
        raw = source.read_bytes()
        expected_offset, expected_sha = (0, T.BOOT_SHA) if key == "boot0" else (0x4200, T.RECOVERY_BLOCK_SHA)
        if (
            type(offset) is not int
            or offset != expected_offset
            or len(data) != 512
            or sha(data) != expected_sha
            or proof.get("sector_sha256") != expected_sha
            or raw[bounds[0] : bounds[1]] != data
        ):
            raise ValueError("Independent scratch-reuse target oracle source/slice changed")
        result[key] = {
            "nor_offset": offset,
            "bytes": len(data),
            "sha256": sha(data),
            "proof": proof,
            "source": {"file": str(source.resolve()), "bytes": len(raw), "sha256": sha(raw)},
            "slice": bounds,
        }
    return result


def verify(image: Path, known_parent: Path, state_parent: Path) -> tuple[bytes, dict, dict]:
    static = static_gate(image)
    baseline, known = known_gate(known_parent, image)
    info, state = state_gate(state_parent, image)
    chronology.time_order(known["ended_at"], state["ended_at"])
    return (
        baseline,
        info,
        {
            "known_parent": known,
            "state_parent": state,
            "static_identity": static,
            "oracles": oracles(),
            "current_object_live_download_required_before_overwrite": True,
            "same_file_overwrite_live_verified": False,
            "new_raw_nor_coverage_bytes": 0,
        },
    )
