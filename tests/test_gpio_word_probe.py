"""Offline fixed-word, parent geometry, exact formatting and failure-stop tests."""

import asyncio
import copy
import json
import re
import struct
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from test_logsrv_context_probe import guarded  # noqa: F401
from test_logsrv_slot_probe import parents  # noqa: F401
from test_logsrv_slot_probe import report as old_report
from test_logsrv_slot_probe import trace as old_trace
from test_sd_nor_probe import attach_actions, info, receipt, save

from rcominote.experiments import gpio_word_contract as G
from rcominote.experiments import gpio_word_probe as P
from rcominote.experiments import logsrv_context_probe as C
from rcominote.experiments import sd_bootstrap as B


def metadata(counter=205, length=139, stream=0x18011254):
    raw = bytearray(32)
    struct.pack_into("<I5B", raw, 0, stream, 3, 0, 0, counter, counter)
    struct.pack_into("<H", raw, 10 + 2 * (counter & 7), length)
    return bytes(raw)


def report(counter=205, pointer=0x180111FC, target=None):
    meta = metadata(counter)
    row = {
        "serial": G.OWNED_SERIAL,
        "source_image_sha256": G.IMAGE_SHA,
        "sd_write_attempted": False,
        "parents": {
            "pointer": {"pointer": hex(pointer)},
            "context": {"raw_hex": meta.hex(), "fields": G.fields(meta)},
        },
    }
    if target is not None:
        row["target"] = target.value
        if basis := G.read_basis(target):
            row["register_read_basis"] = basis
    with patch.object(P.secrets, "token_hex", side_effect=["0123456789", "1123456789", "2123456789"]):
        row["files"] = P.snapshots(row)
    return row


def payloads(row, value=0x410FC241):
    selected = G.geometry(row)
    ascii_column = bytes(byte if 32 <= byte <= 126 else 46 for byte in value.to_bytes(4, "little"))
    line = f"{G.address(row):08x}: {value:08x}".encode() + b" " * 31 + ascii_column + b"\r\n"
    body = b"\r\ndone dumping to " + row["files"][0]["device_path"].encode() + b"\r\n\r\n" + line
    meta = metadata(selected["counter"], len(body), selected["stream"])
    return [selected["pointer"].to_bytes(4, "little"), meta, (bytes(8) + body).ljust(512, b"\xcc")]


def trace(row):
    reference = old_trace(old_report())
    for key in (
        "log_characteristics",
        "att_packets",
        "writes",
        "notifications",
        "frames",
        "ack_count",
        "expected_ack_count",
        "end_received",
        "pending_hex",
        "log_session_complete",
    ):
        row[key] = copy.deepcopy(reference[key])
    packets = [G.PREPARE, G.START, *map(G.console_packet, G.commands(row)), G.STOP]
    row["writes"] = [{"hex": packet.hex(), "att_write_confirmed": True} for packet in packets]
    i = 0
    for event in row["att_packets"]:
        if event["direction"] == "tx" and event["hex"].startswith("121600"):
            event["hex"] = "121600" + packets[i].hex()
            i += 1
    assert i == 7


@pytest.fixture
def gpio_parents(parents, tmp_path):  # noqa: F811 - shared pytest fixture registration
    image, guards, slots, pointer, context, handler = parents
    word_guards = []
    for i, (address, size) in enumerate(G.WORD_GUARDS.items()):
        row = attach_actions(receipt(f"rc000000055{i}", address, size))
        raw = image[address - 0x10000000 : address - 0x10000000 + size]
        row.update(
            expected_sha256=G.sha(raw),
            started_at="2026-10-14T00:00:00+00:00",
            ended_at="2026-10-14T00:01:00+00:00",
        )
        word_guards.append(save(tmp_path / f"word{i}", row, raw))
    data = metadata()
    (context / "download.bin").write_bytes(data)
    path = context / "report.json"
    row = json.loads(path.read_bytes())
    row.update(download_sha256=G.sha(data), verification=C.context_fields(data))
    path.write_text(json.dumps(row))
    return image, guards, slots, word_guards, pointer, context, handler, "2026-10-14T00:06:00+00:00"


@pytest.mark.parametrize("counter", [0, 204, 205, 255])
def test_complete_counter_selects_bounded_slot_once(counter):
    row = report(counter)
    selection = G.geometry(row)
    assert selection["counter"] == counter
    assert selection["slot_address"] == 0x1800A9B0 + (counter & 7) * 512
    commands = G.commands(row)
    assert commands[1] == "dbg mdw 40068074 1"
    assert all(len((command + "\n").encode()) <= 63 for command in commands)
    trace(row)
    G.validate_actions(row)


@pytest.mark.parametrize("fault", [None, "word-byte", "late-word", "early-trial", "parent-hash", "stream"])
def test_guard_parent_chain_and_chronology(gpio_parents, fault):
    args = list(gpio_parents)
    word = args[3][0]
    context = args[5]
    if fault == "word-byte":
        (word / "download.bin").write_bytes(bytes(10))
    elif fault == "early-trial":
        args[-1] = "2026-10-14T00:04:30+00:00"
    elif fault in ("late-word", "parent-hash", "stream"):
        path = (word if fault == "late-word" else context) / "report.json"
        row = json.loads(path.read_bytes())
        if fault == "late-word":
            row.update(started_at="2026-10-14T00:05:00+00:00", ended_at="2026-10-14T00:06:00+00:00")
        elif fault == "parent-hash":
            row["previous"]["report_sha256"] = "0" * 64
        else:
            data = metadata(stream=0x40068074)
            (context / "download.bin").write_bytes(data)
            row.update(download_sha256=G.sha(data), verification=C.context_fields(data))
        path.write_text(json.dumps(row))
    if fault:
        with pytest.raises(ValueError):
            G.validate_parents(*args)
    else:
        result = G.validate_parents(*args)
        assert result["context"]["fields"]["wr"] == 205
        assert len(result["word_guards"]) == 2


@pytest.mark.parametrize("value", [0, 0xFFFFFFFF, 0x410FC241, 0x7E204100, 0x80001234])
def test_observed_word_has_no_prefilled_expected_register_value(value):
    row = report()
    result = G.verify_payload(row, *payloads(row, value))
    assert result["observed_word"] == value
    assert result["word_bytes_le"] == value.to_bytes(4, "little").hex()
    assert result["row_body_span"][1] - result["row_body_span"][0] == 55


def test_formatter_layout_matches_two_public_successful_word_reads():
    for name in ("cpuid-first-2026-10-12.json", "cpuid-second-2026-10-12.json"):
        old = json.loads((Path("docs/evidence") / name).read_bytes())
        assert old["ok"] and old["end_received"]
        text = "".join(frame.get("text", "") for frame in old["frames"])
        found = re.findall(r"(?m)^e000ed00: ([0-9a-f]{8}) {31}([ -~]{4})\r\n", text)
        assert found == [("410fc241", "A..A")]


@pytest.mark.parametrize("target", list(G.Target))
def test_exact_allowlisted_target_binds_command_trace_and_row(target):
    row = report(target=target)
    assert G.commands(row)[1] == f"dbg mdw {G.ADDRESSES[target]:08x} 1"
    trace(row)
    G.validate_actions(row)
    result = G.verify_payload(row, *payloads(row, value=0x80024000))
    assert result["address"] == hex(G.ADDRESSES[target])
    assert result["observed_word"] == 0x80024000
    assert all(len((command + "\n").encode()) <= 63 for command in G.commands(row))
    raw = payloads(row)
    prefix = f"{G.ADDRESSES[target]:08x}:".encode()
    raw[2] = raw[2].replace(prefix, b"40010308:")
    with pytest.raises(ValueError, match="target word row"):
        G.verify_payload(row, *raw)


@pytest.mark.parametrize("target", ["40010300", "map1-cpu", "gpio29-ctrl", "", None, 0x40010300])
def test_arbitrary_target_rejected_before_transport(target):
    row = report()
    row["target"] = target
    with pytest.raises(ValueError):
        G.commands(row)


def test_relabeling_target_cannot_reuse_actual_actions_or_proof():
    row = report(target=G.Target.map0_cpu)
    trace(row)
    row["target"] = G.Target.map0_offset.value
    with pytest.raises(ValueError, match="read basis"):
        G.commands(row)
    row["register_read_basis"] = G.read_basis(G.Target.map0_offset)
    with pytest.raises(ValueError):
        G.validate_actions(row)
    row["commands"] = G.commands(row)
    row["commands"][1] = "dbg mdw 40010304 2"
    with pytest.raises(ValueError):
        G.commands(row)


def test_mapping_proof_uses_exact_recovery_and_rejects_before_io(tmp_path):
    bad = tmp_path / "recovery.bin"
    data = bytearray(G.RECOVERY.read_bytes())
    data[0xE500] ^= 1
    bad.write_bytes(data)
    out = tmp_path / "failed"
    with patch.object(P, "capture", AsyncMock()) as capture:
        with pytest.raises(ValueError, match="exact checksum-verified"):
            P.main(
                image=tmp_path / "never-read-image",
                out=out,
                guard=[],
                slot_guard=[],
                word_guard=[],
                pointer_parent=tmp_path,
                context_parent=tmp_path,
                target=G.Target.map0_cpu,
                recovery_image=bad,
                create_sd_files=True,
            )
        capture.assert_not_called()
    failed = json.loads((out / "report.json").read_bytes())
    assert not failed["ok"] and not failed["sd_write_attempted"]
    assert "before" not in failed


@pytest.mark.parametrize(
    "fault",
    [
        "pointer",
        "counter",
        "stream",
        "other-slot",
        "drop",
        "spaces",
        "ascii",
        "newline",
        "row-before-marker",
        "duplicate",
        "outside",
        "echo-only",
    ],
)
def test_geometry_or_full_line_changes_fail_without_fallback(fault):
    row = report()
    pointer, meta, slot = payloads(row)
    if fault == "pointer":
        pointer = (0x18011200).to_bytes(4, "little")
    elif fault == "counter":
        meta = meta[:7] + bytes([213, 213]) + meta[9:]  # Same slot, wrong complete generation.
    elif fault == "stream":
        meta = (0x18012000).to_bytes(4, "little") + meta[4:]
    elif fault in ("other-slot", "drop"):
        raw = bytearray(meta)
        raw[10 if fault == "other-slot" else 28] = 1
        meta = bytes(raw)
    else:
        length = C.context_fields(meta)["slot_lengths"][5]
        body = slot[8 : 8 + length]
        if fault == "spaces":
            body = body.replace(b" " * 31, b" " * 30)
        elif fault == "ascii":
            body = body.replace(b"A..A", b"A..B")
        elif fault == "newline":
            body = body[:-2] + b"\n"
        elif fault == "row-before-marker":
            i = body.index(b"40068074:")
            body = body[i:] + body[:i]
        elif fault == "duplicate":
            body += body[body.index(b"40068074:") :]
        elif fault == "echo-only":
            body = body.replace(b"done dumping to ", b"logsrv: cmd(19) ")
        meta = metadata(length=len(body) - (1 if fault == "outside" else 0))
        slot = (bytes(8) + body).ljust(512, b"\xcc")
    with pytest.raises(ValueError):
        G.verify_payload(row, pointer, meta, slot)


def test_no_alternative_gpio_or_byte_read_in_declared_or_actual_sequence():
    for alternate in ("dbg mdw 40068078 1", "dbg mdw 40068074 2", "dbg mdb 40068074 4"):
        row = report()
        trace(row)
        for event in row["att_packets"]:
            if event["hex"] == "121600" + G.console_packet(G.MDW).hex():
                event["hex"] = "121600" + G.console_packet(alternate).hex()
        with pytest.raises(ValueError):
            G.validate_actions(row)
        row["commands"] = G.commands(row)
        row["commands"][1] = alternate
        with pytest.raises(ValueError):
            G.commands(row)


@pytest.mark.parametrize("fault", [None, "actions", "pointer", "counter", "short", "format", "after"])
def test_transport_failure_stops_preserves_slot_and_final_state(tmp_path, fault):
    row = report()
    data = payloads(row)
    calls = []

    async def write(actual, commands):
        assert commands[1] == G.MDW
        actual["sd_write_attempted"] = True
        trace(actual)
        if fault == "actions":
            actual["att_packets"].pop()

    async def download(item, directory, size):
        calls.append(item["role"])
        value = data[len(calls) - 1]
        if fault == "pointer" and item["role"] == "global":
            value = (0x18011200).to_bytes(4, "little")
        if fault == "counter" and item["role"] == "metadata":
            value = value[:7] + bytes([213, 213]) + value[9:]
        if item["role"] == "slot":
            if fault == "short":
                value = value[:-244]
            elif fault == "format":
                value = value.replace(b"A..A", b"A..B")
        (directory / "download.bin").write_bytes(value)
        if len(value) != size:
            raise RuntimeError("Short download")
        return value

    identity = AsyncMock(
        side_effect=[
            (info(), []),
            OSError("postcheck failed") if fault in ("short", "after") else (info(), []),
        ]
    )
    with (
        patch.object(B, "identity", identity),
        patch.object(B, "write_commands", side_effect=write),
        patch.object(B, "download_file", side_effect=download),
    ):
        if fault:
            with pytest.raises((RuntimeError, ValueError, OSError)) as error:
                asyncio.run(P.capture(row, tmp_path))
            if fault == "short":
                assert str(error.value) == "Short download"
                assert row["after_error"] == "OSError: postcheck failed"
        else:
            asyncio.run(P.capture(row, tmp_path))
    assert calls == {"actions": [], "pointer": ["global"], "counter": ["global", "metadata"]}.get(
        fault, ["global", "metadata", "slot"]
    )
    assert identity.await_count == 2
    if fault in ("format", "short"):
        assert len((tmp_path / "slot/download.bin").read_bytes()) == (268 if fault == "short" else 512)
