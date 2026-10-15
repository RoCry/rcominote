"""Offline evidence-chain, command, partial-slot and failure-stop checks."""

import asyncio
import json
import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_logsrv_context_probe import guarded  # noqa: F401
from test_sd_nor_probe import ACK, DISCOVERY, END, attach_actions, info, receipt, save

from rcominote.experiments import logsrv_context_probe as C
from rcominote.experiments import logsrv_slot_contract as K
from rcominote.experiments import logsrv_slot_probe as S
from rcominote.experiments import sd_bootstrap as B


def report():
    with patch.object(S.secrets, "token_hex", side_effect=["0123456789", "1123456789", "2123456789"]):
        return {
            "serial": K.OWNED_SERIAL,
            "source_image_sha256": K.IMAGE_SHA,
            "files": S.snapshots(),
            "sd_write_attempted": False,
        }


def meta(length=139):
    raw = bytearray(32)
    struct.pack_into("<I5B", raw, 0, K.STREAM, 3, 0, 0, K.INDEX, K.INDEX)
    struct.pack_into("<H", raw, 18, length)
    return bytes(raw)


def payloads(row):
    body = b"\r\ndone dumping to " + row["files"][0]["device_path"].encode() + b"\r\n\r\n" + K.ROW
    return [K.POINTER.to_bytes(4, "little"), meta(len(body)), (b"\0" * 8 + body).ljust(512, b"\xcc")]


def trace(row):
    packets = [K.PREPARE, K.START, *map(K.console_packet, K.commands(row)), K.STOP]
    discovery = [
        ("tx", "02f700"),
        ("rx", "03f700"),
        ("tx", "08140019000328"),
        ("rx", DISCOVERY),
        ("tx", "0419001900"),
        ("rx", "050119000229"),
        ("tx", "1219000100"),
        ("rx", "13"),
    ]
    events = discovery + [
        event
        for packet in packets
        for event in (("tx", "121600" + packet.hex()), ("rx", "13"), ("rx", "1b1800" + ACK.hex()))
    ]
    events += [("rx", "1b1800" + END.hex())]
    row.update(
        log_characteristics=[
            {"declaration": 21, "properties": 12, "value": 22, "uuid": K.WRITE},
            {"declaration": 23, "properties": 16, "value": 24, "uuid": K.NOTIFY},
        ],
        att_packets=[{"direction": d, "hex": raw, "monotonic_ns": i} for i, (d, raw) in enumerate(events)],
        writes=[{"hex": packet.hex(), "att_write_confirmed": True} for packet in packets],
        notifications=[ACK.hex()] * 7 + [END.hex()],
        frames=[{"command": 16, "hex": ACK.hex()}] * 7 + [{"command": 241, "hex": END.hex()}],
        ack_count=7,
        expected_ack_count=7,
        end_received=True,
        pending_hex="",
        log_session_complete=True,
    )
    return row


@pytest.fixture
def parents(guarded, tmp_path):  # noqa: F811 - pytest fixture imported for registration
    image_path, guards = guarded
    image = image_path.read_bytes()
    for directory in guards:
        path = directory / "report.json"
        row = json.loads(path.read_bytes())
        row.update(started_at="2026-10-14T00:00:00+00:00", ended_at="2026-10-14T00:01:00+00:00")
        path.write_text(json.dumps(row))
    verified = C.validate_guards(guards, image, None)
    pointer = attach_actions(receipt("rc0000000111", C.GLOBAL, 4, phase=C.Phase.pointer))
    pointer.update(
        guards=verified,
        verification={"pointer": hex(K.POINTER), "allocation_bound_bytes": 80},
        started_at="2026-10-14T00:02:00+00:00",
        ended_at="2026-10-14T00:03:00+00:00",
    )
    pointer_dir = save(tmp_path / "pointer", pointer, K.POINTER.to_bytes(4, "little"))
    context = attach_actions(receipt("rc0000000222", K.POINTER, 32, phase=C.Phase.context))
    context.update(
        guards=verified,
        previous=C.previous(pointer_dir, verified),
        verification=C.context_fields(meta()),
        started_at="2026-10-14T00:04:00+00:00",
        ended_at="2026-10-14T00:05:00+00:00",
    )
    context_dir = save(tmp_path / "context", context, meta())
    slot_dirs = []
    for i, (address, size) in enumerate(K.SLOT_GUARDS.items()):
        guard = attach_actions(receipt(f"rc000000033{i}", address, size))
        raw = image[address - 0x10000000 : address - 0x10000000 + size]
        guard["expected_sha256"] = K.sha(raw)
        guard.update(started_at="2026-10-14T00:00:00+00:00", ended_at="2026-10-14T00:01:00+00:00")
        slot_dirs.append(save(tmp_path / f"slot-guard{i}", guard, raw))
    return image, guards, slot_dirs, pointer_dir, context_dir, None


def test_exact_existing_public_mdb_row_not_guessed_formatter():
    raw = json.loads(Path("docs/evidence/linux-short-read-2026-10-13.json").read_bytes())

    def texts(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "text" and isinstance(child, str):
                    yield child
                else:
                    yield from texts(child)
        elif isinstance(value, list):
            for child in value:
                yield from texts(child)

    assert sum(text.count(K.ROW.decode()) for text in texts(raw)) == 1
    assert K.sha(K.ROW) == "effbb4720cffe87d0eec702e52f3aa17693d8c1f4fca72e347f232218503f12d"


@pytest.mark.parametrize("fault", [None, "counter", "chain", "pointer", "actions", "guard-byte"])
def test_full_parent_chain_rejects_changed_counter_without_slot_substitution(parents, fault):
    _, _, slots, pointer, context, _ = parents
    path = (pointer if fault == "pointer" else context) / "report.json"
    row = json.loads(path.read_bytes())
    if fault == "counter":
        raw = bytearray(meta())
        raw[7:9] = bytes([212, 212])  # Still slot4, deliberately wrong generation.
        (context / "download.bin").write_bytes(raw)
        row.update(download_sha256=K.sha(raw), verification=C.context_fields(bytes(raw)))
    elif fault == "chain":
        row["previous"]["report_sha256"] = "0" * 64
    elif fault == "pointer":
        row["ok"] = False
    elif fault == "actions":
        row["att_packets"] = []
    elif fault == "guard-byte":
        (slots[0] / "download.bin").write_bytes(bytes(32))
    if fault:
        path.write_text(json.dumps(row))
        with pytest.raises(ValueError):
            K.validate_parents(*parents)
    else:
        assert K.validate_parents(*parents)["context"]["fields"]["wr"] == 204


@pytest.mark.parametrize("fault", ["old-context", "guard-after-pointer", "naive", "reverse"])
def test_parent_chronology_rejects_old204_context_even_with_same_bytes(parents, fault):
    path = (parents[2][0] if fault == "guard-after-pointer" else parents[4]) / "report.json"
    row = json.loads(path.read_bytes())
    if fault == "old-context":
        row.update(started_at="2026-10-13T00:00:00+00:00", ended_at="2026-10-13T00:01:00+00:00")
    elif fault == "guard-after-pointer":
        row.update(started_at="2026-10-14T00:05:00+00:00", ended_at="2026-10-14T00:06:00+00:00")
    elif fault == "naive":
        row["started_at"] = "2026-10-14T00:04:00"
    else:
        row["ended_at"] = "2026-10-14T00:03:00+00:00"
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="chronology"):
        K.validate_parents(*parents)


@pytest.mark.parametrize("fault", ["source", "size", "duplicate", "producer", "command", "count"])
def test_no_arbitrary_source_or_extra_commands(fault):
    row = report()
    if fault == "source":
        row["files"][2]["source_address"] = hex(K.SLOT + 512)
    elif fault == "size":
        row["files"][2]["source_bytes"] = 4096
    elif fault == "duplicate":
        row["files"][1] = row["files"][0]
    elif fault == "producer":
        row["producer"] = "dbg fread spi_flash 0"
    elif fault == "command":
        row["files"][0]["dump_command"] += "; help"
    else:
        row["files"].pop()
    with pytest.raises(ValueError):
        K.commands(row)


def test_complete_fixed_sequence_and_command_budget():
    row = trace(report())
    K.validate_actions(row)
    assert len(row["writes"]) == 7
    assert K.commands(row)[1] == "dbg mdb 1000ab40 10"
    assert all(len((cmd + "\n").encode()) <= 63 for cmd in K.commands(row))


@pytest.mark.parametrize("fault", ["end", "response", "notify", "frames", "extra-write", "cleanup"])
def test_actions_trace_must_reconstruct_exact_session(fault):
    row = trace(report())
    if fault == "end":
        row["att_packets"].pop()
    elif fault == "response":
        row["att_packets"].pop(9)
    elif fault == "notify":
        row["att_packets"][-1]["hex"] = "1b1900" + END.hex()
    elif fault == "frames":
        row["frames"].pop()
    elif fault == "extra-write":
        row["writes"].append(row["writes"][0])
    else:
        row["cleanup_error"] = "STOP failed"
    with pytest.raises(ValueError):
        K.validate_actions(row)


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "pointer",
        "length",
        "metadata",
        "reversed",
        "duplicate",
        "ascii",
        "newline",
        "outside",
        "echo-only",
    ],
)
def test_prefix_bound_complete_nonce_then_exact_row(fault):
    row = report()
    global_data, metadata, slot = payloads(row)
    if fault == "pointer":
        global_data = (K.POINTER + 4).to_bytes(4, "little")
    elif fault == "length":
        slot = slot[:-1]
    elif fault == "metadata":
        metadata = bytes([0]) + metadata[1:]
    elif fault in ("reversed", "duplicate", "ascii", "newline", "outside", "echo-only"):
        body = slot[8 : 8 + K.metadata(metadata)["slot_lengths"][4]]
        if fault == "reversed":
            body = K.ROW + body.replace(K.ROW, b"")
        elif fault == "duplicate":
            body += K.ROW
        elif fault == "ascii":
            body = body.replace(b"^4...", b"x4...")
        elif fault == "newline":
            body = body[:-2]
        elif fault == "echo-only":
            body = body.replace(b"done dumping to ", b"logsrv: cmd(19) dbg dumpbuf ")
        metadata = meta(len(body) - (1 if fault == "outside" else 0))
        slot = (bytes(8) + body).ljust(512, b"\0")
    if fault:
        with pytest.raises(ValueError):
            K.verify_payload(row, global_data, metadata, slot)
    else:
        result = K.verify_payload(row, global_data, metadata, slot)
        assert result["known_bytes_hex"] == K.ORACLE.hex()
        assert result["row_body_span"][1] <= result["body_length"]


@pytest.mark.parametrize("fault", [None, "actions", "global", "metadata", "slot-short", "content", "after"])
def test_capture_stops_without_retry_and_preserves_raw_before_content_failure(tmp_path, fault):
    row = report()
    data = payloads(row)
    calls = []

    async def write(actual, commands):
        assert commands == K.commands(actual)
        actual["sd_write_attempted"] = True
        trace(actual)
        if fault == "actions":
            actual["att_packets"].pop()

    async def download(item, directory, size):
        calls.append(item["role"])
        value = data[len(calls) - 1]
        if fault == "global" and item["role"] == "global":
            value = (K.POINTER + 4).to_bytes(4, "little")
        if fault == "metadata" and item["role"] == "metadata":
            value = value[:7] + bytes([205, 205]) + value[9:]
        if fault in ("slot-short", "content") and item["role"] == "slot":
            value = value[:-244] if fault == "slot-short" else bytes(512)
        (directory / "download.bin").write_bytes(value)
        if len(value) != size:
            raise RuntimeError("Short download")
        return value

    identity = AsyncMock(
        side_effect=[
            (info(), []),
            OSError("after unavailable") if fault in ("after", "slot-short") else (info(), []),
        ]
    )
    with (
        patch.object(B, "identity", identity),
        patch.object(B, "write_commands", side_effect=write),
        patch.object(B, "download_file", side_effect=download),
    ):
        if fault:
            with pytest.raises((ValueError, RuntimeError, OSError)) as error:
                asyncio.run(S.capture(row, tmp_path))
            if fault == "slot-short":
                assert str(error.value) == "Short download"
                assert row["after_error"] == "OSError: after unavailable"
        else:
            asyncio.run(S.capture(row, tmp_path))
    assert calls == {"actions": [], "global": ["global"], "metadata": ["global", "metadata"]}.get(
        fault, ["global", "metadata", "slot"]
    )
    assert identity.await_count == 2
    if fault == "content":
        assert (tmp_path / "slot/download.bin").read_bytes() == bytes(512)
    if fault == "slot-short":
        assert len((tmp_path / "slot/download.bin").read_bytes()) == 268


def test_internal_transport_sends_stop_after_failed_mdb_without_remaining_dumps():
    row = report()
    packets = []
    queue = asyncio.Queue()

    class Link:
        mtu = 247

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def request(self, raw, _expected):
            if raw[:3] != bytes.fromhex("121600"):
                return b""
            packet = raw[3:]
            packets.append(packet)
            if packet == K.console_packet(K.MDB):
                raise RuntimeError("mdb ATT failure")
            queue.put_nowait((24, ACK))
            if packet == K.STOP:
                queue.put_nowait((24, END))
            return b"\x13"

        async def next_notification(self):
            return await queue.get()

    with (
        patch.object(B, "find_device", AsyncMock(return_value=SimpleNamespace(address="fixed"))),
        patch.object(B, "AttLink", return_value=Link()),
        patch.object(B, "discover", AsyncMock(return_value=(22, 24, 25))),
        pytest.raises(RuntimeError, match="mdb ATT failure"),
    ):
        asyncio.run(B.write_commands(row, K.commands(row)))
    assert packets == [
        K.PREPARE,
        K.START,
        K.console_packet(K.commands(row)[0]),
        K.console_packet(K.MDB),
        K.STOP,
    ]
    assert row["sd_write_attempted"] is True
    assert not row.get("log_session_complete")
