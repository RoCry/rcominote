"""Allowlisted configuration-word LDR32 observation through one logsrv slot."""

import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from rcominote.ble_target import OWNED_SERIAL
from rcominote.experiments import logsrv_context_probe as context
from rcominote.experiments import logsrv_slot_contract as slot
from rcominote.experiments.sd_bridge import console_packet
from rcominote.experiments.sd_nor_probe import IMAGE_SHA, command, downloaded, load, same_identity, sha
from rcominote.experiments.sd_nor_probe import validate_actions as single_actions
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE

ADDRESS = 0x40068074
MDW = "dbg mdw 40068074 1"
WORD_GUARDS = {0x100A18EE: 10, 0x100251AA: 24}
SLOT_BASE = 0x1800A9B0
RECOVERY_SHA = "19625b7b70eb8e4a91c889792c0ca383f51ea205629e67565b59c47d15e09906"
RECOVERY = (
    Path(__file__).resolve().parents[3] / "docs/evidence/recovery-complete-2026-10-13/recovery-decoded.bin"
)


class Target(StrEnum):
    gpio28 = "gpio28-ctrl"
    map0_cpu = "map0-cpu"
    map0_offset = "map0-offset"


ADDRESSES = {Target.gpio28: ADDRESS, Target.map0_cpu: 0x40010300, Target.map0_offset: 0x40010304}
READ_BASIS = {
    "recovery_sha256": RECOVERY_SHA,
    "scope": "Actual recovery ordinary LDR of slot0 configuration; no live mapping/alias proof",
    "regions": {"0xe4fa": "134d134a17682968", "0xe548": "0003014004030140"},
}


def read_basis(target: Target, recovery: Path | None = None) -> dict | None:
    """Verify fixed actual-image evidence before permitting either mapping-register read."""
    target = Target(target)
    if target == Target.gpio28:
        return None
    data = (recovery or RECOVERY).read_bytes()
    if len(data) != 63288 or sha(data) != RECOVERY_SHA:
        raise ValueError("Requires exact checksum-verified actual CoMi recovery image")
    for offset, expected in READ_BASIS["regions"].items():
        start, raw = int(offset, 16), bytes.fromhex(expected)
        if data[start : start + len(raw)] != raw:
            raise ValueError("Actual recovery slot0 LDR/literal evidence changed")
    return {**READ_BASIS, "target": target.value, "address": hex(ADDRESSES[target])}


def address(report: dict) -> int:
    target = Target(report.get("target", Target.gpio28))
    if target != Target.gpio28 and report.get("register_read_basis") != {
        **READ_BASIS,
        "target": target.value,
        "address": hex(ADDRESSES[target]),
    }:
        raise ValueError("Mapping target requires its exact actual-recovery read basis")
    return ADDRESSES[target]


def fields(data: bytes, *, expected: dict | None = None) -> dict:
    value = context.context_fields(data)
    stream = int(value["stream_pointer"], 16)
    if stream % 4 or not context.RAM_START <= stream <= context.RAM_END - 4:
        raise ValueError("Stream pointer outside bounded aligned RAM; never dereference replacement")
    if (value["flags_byte"], value["log_type"], value["new_log_type"], value["drop_count"]) != (3, 0, 0, 0):
        raise ValueError("Unexpected logsrv mode/flags/drop")
    if value["rd"] != value["wr"]:
        raise ValueError("Expected equal complete rd/wr counters")
    index = value["wr"] & 7
    lengths = value["slot_lengths"]
    if any(length for i, length in enumerate(lengths) if i != index):
        raise ValueError("Unexpected occupied alternate slot")
    if expected is not None:
        if any(
            value[key] != expected[key]
            for key in ("stream_pointer", "flags_byte", "log_type", "new_log_type", "rd", "wr", "drop_count")
        ):
            raise ValueError("Trial context changed from parent; no alternate slot selection")
        if not 1 <= lengths[index] <= 504:
            raise ValueError("Trial requires one bounded nonempty slot prefix")
    return value


def geometry(report: dict) -> dict:
    parent = report["parents"]
    pointer = context.pointer(int(parent["pointer"]["pointer"], 16).to_bytes(4, "little"))
    data = bytes.fromhex(parent["context"]["raw_hex"])
    actual = fields(data)
    if actual != parent["context"]["fields"]:
        raise ValueError("Parent metadata summary differs from its 32-byte source")
    counter = actual["wr"]
    return {
        "pointer": pointer,
        "stream": int(actual["stream_pointer"], 16),
        "counter": counter,
        "index": counter & 7,
        "slot_address": SLOT_BASE + (counter & 7) * 512,
    }


def sources(report: dict) -> tuple[tuple[str, int, int], ...]:
    selected = geometry(report)
    return (
        ("global", context.GLOBAL, 4),
        ("metadata", selected["pointer"], 32),
        ("slot", selected["slot_address"], 512),
    )


def commands(report: dict) -> list[str]:
    if (
        report["serial"] != OWNED_SERIAL
        or report["source_image_sha256"] != IMAGE_SHA
        or report.get("producer") is not None
        or any(report.get(key) for key in ("download_only", "tail_only"))
    ):
        raise ValueError("Requires the owned fixed configuration-word profile")
    selected_address = address(report)
    files = report["files"]
    if len(files) != 3:
        raise ValueError("Requires exactly three fixed RAM snapshot files")
    names, texts = set(), []
    for item, (role, source_address, size) in zip(files, sources(report), strict=True):
        if (item["role"], item["source_address"], item["source_bytes"]) != (role, hex(source_address), size):
            raise ValueError("Snapshot source differs from the parent-selected fixed slot")
        text = command(item, source_address, size)
        if item["name"] in names or len((text + "\n").encode()) > 63:
            raise ValueError("Duplicate snapshot name or command exceeds 63 bytes")
        names.add(item["name"])
        texts.append(text)
    result = [texts[0], f"dbg mdw {selected_address:08x} 1", texts[1], texts[2]]
    if "commands" in report and report["commands"] != result:
        raise ValueError("Declared sequence differs from fixed target command")
    return result


def validate_actions(report: dict) -> None:
    slot.validate_action_packets(report, [PREPARE, START, *map(console_packet, commands(report)), STOP])


def validate_parents(
    image: bytes,
    guards: list[Path],
    slot_guards: list[Path],
    word_guards: list[Path],
    pointer_parent: Path,
    context_parent: Path,
    handler_parent: Path | None,
    trial_started_at: str,
) -> dict:
    verified = context.validate_guards(guards, image, handler_parent)
    slots = slot.validate_slot_guards(slot_guards, image)
    words = slot.validate_code_guards(word_guards, image, WORD_GUARDS)
    pointer_start, pointer_end = slot.times(pointer_parent)
    context_start, context_end = slot.times(context_parent)
    trial = datetime.fromisoformat(trial_started_at)
    if (
        trial.utcoffset() is None
        or max(slot.times(path)[1] for path in [*guards, *slot_guards, *word_guards]) > pointer_start
        or pointer_end > context_start
        or context_end > trial
    ):
        raise ValueError("Chronology must be all guards→fresh pointer→fresh context→trial")
    pointer_link = context.previous(pointer_parent, verified)
    pointer = int(pointer_link["pointer"], 16)
    report, raw = load(context_parent)
    if (
        report.get("phase") != context.Phase.context
        or report.get("ok") is not True
        or report.get("error")
        or report["serial"] != OWNED_SERIAL
        or report["source_image_sha256"] != IMAGE_SHA
        or report["guards"] != verified
        or report["previous"] != pointer_link
        or report.get("sd_write_attempted") is not True
        or any(
            report.get(key) for key in ("download_only", "tail_only", "download_reused", "postcheck_parent")
        )
    ):
        raise ValueError("Context parent must be independently complete with matching pointer/guard chain")
    if context.request(report) != (pointer, 32):
        raise ValueError("Context source differs from validated pointer parent")
    same_identity(report)
    single_actions(report)
    data = downloaded(report, context_parent, 32)
    actual = fields(data)
    if report["verification"] != actual:
        raise ValueError("Context parent summary differs from raw bytes")
    return {
        "guards": verified,
        "slot_guards": slots,
        "word_guards": words,
        "pointer": pointer_link,
        "context": {
            "directory": str(context_parent.resolve()),
            "report_sha256": sha(raw),
            "raw_hex": data.hex(),
            "fields": actual,
        },
    }


def verify_payload(report: dict, global_data: bytes, meta_data: bytes, slot_data: bytes) -> dict:
    commands(report)
    selected = geometry(report)
    if context.pointer(global_data) != selected["pointer"]:
        raise ValueError("Current-pointer snapshot differs from parent; no replacement followed")
    actual = fields(meta_data, expected=report["parents"]["context"]["fields"])
    if len(slot_data) != 512:
        raise ValueError("Slot requires complete 512-byte transfer")
    length = actual["slot_lengths"][selected["index"]]
    body = slot_data[8 : 8 + length]
    marker = b"done dumping to " + report["files"][0]["device_path"].encode("ascii")
    markers = list(re.finditer(rb"(?m)^" + re.escape(marker) + rb"\r\n", body))
    prefix = f"{address(report):08x}:".encode("ascii")
    rows = list(re.finditer(rb"(?m)^" + prefix + rb" ([0-9a-f]{8}) {31}([\x20-\x7e]{4})\r\n", body))
    if (
        len(markers) != 1
        or body.count(marker) != 1
        or len(rows) != 1
        or body.count(prefix) != 1
        or markers[0].end() > rows[0].start()
    ):
        raise ValueError("Missing/duplicate/incomplete nonce→target word row within metadata prefix")
    row = rows[0]
    value = int(row[1], 16)
    expected_ascii = bytes(byte if 32 <= byte <= 126 else 46 for byte in value.to_bytes(4, "little"))
    if row[2] != expected_ascii or row.end() - row.start() != 55:
        raise ValueError("Word ASCII column differs from observed little-endian value")
    return {
        "address": hex(address(report)),
        "observed_word": value,
        "observed_hex": f"0x{value:08x}",
        "word_bytes_le": value.to_bytes(4, "little").hex(),
        "metadata": actual,
        "geometry": selected,
        "body_length": length,
        "marker_body_span": list(markers[0].span()),
        "row_body_span": list(row.span()),
        "row_sha256": sha(row[0]),
        "scope": (
            "One observed GPIO28 CTRL word; no physical pin identity, atomicity or still-partial claim"
            if address(report) == ADDRESS
            else "One observed slot0 configuration word; no raw alias, complete mapping or atomicity claim"
        ),
    }
