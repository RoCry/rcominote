"""Offline gates for fixed SD context/baseline/boot trials; never contacts hardware."""

import asyncio
import copy
import json
import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from rcominote import protocol as wire
from rcominote.experiments import sd_nor_probe as probe
from rcominote.log_probe import ACK, NOTIFY, PREPARE, WRITE

DISCOVERY = "091515000c1600d19f1b1f80f2b28ee8119af602309ae41700101800d19f1b1f80f2b28ee8119af603309ae4"
END = bytes.fromhex("1df1810000")
INFO_RAW = bytes.fromhex(
    "0000e8f20000e8ce0264000100040101ff78696e6b5f746573740000000000000000000000000009ff0300010000000000000000"
)


def info(free_decrease=0):
    raw = INFO_RAW[:4] + (59598 - free_decrease).to_bytes(4, "big") + INFO_RAW[8:]
    return {"serial": probe.OWNED_SERIAL, "bound": False, "device": wire.parse_device_info(raw)}


def receipt(name, address, size, *, source=None, phase=None):
    path = f"/SD:/RECORDER/Call-{name}.mp3"
    report = {
        "serial": probe.OWNED_SERIAL,
        "name": name,
        "device_path": path,
        "dump_command": f"dbg dumpbuf {address} {size} {path}",
        "source_address": hex(address),
        "source_bytes": size,
        "source_image_sha256": probe.IMAGE_SHA,
        "ok": True,
        "sd_write_attempted": True,
        "before": info(),
        "after": info(),
    }
    if source:
        report["source"] = source
    if phase:
        report["phase"] = phase.value
    return report


def attach_actions(report, *, producer=False):
    packets = [PREPARE, probe.START]
    if producer:
        report["producer"] = probe.PRODUCER
        packets.append(probe.console_packet(probe.PRODUCER))
    packets += [probe.console_packet(report["dump_command"]), probe.STOP]
    events = [
        ("tx", "02f700"),
        ("rx", "03f700"),
        ("tx", "08140019000328"),
        ("rx", DISCOVERY),
        ("tx", "0419001900"),
        ("rx", "050119000229"),
        ("tx", "1219000100"),
        ("rx", "13"),
    ]
    for packet in packets:
        events += [("tx", "121600" + packet.hex()), ("rx", "13"), ("rx", "1b1800" + ACK.hex())]
    events += [("rx", "1b1800" + END.hex())]
    report.update(
        att_packets=[
            {"direction": d, "hex": value, "monotonic_ns": i} for i, (d, value) in enumerate(events)
        ],
        log_characteristics=[
            {"declaration": 21, "properties": 12, "value": 22, "uuid": WRITE},
            {"declaration": 23, "properties": 16, "value": 24, "uuid": NOTIFY},
        ],
        writes=[{"hex": packet.hex(), "att_write_confirmed": True} for packet in packets],
        notifications=[ACK.hex()] * len(packets) + [END.hex()],
        frames=[{"command": 16, "hex": ACK.hex()}] * len(packets) + [{"command": 241, "hex": END.hex()}],
        log_session_complete=True,
        ack_count=len(packets),
        expected_ack_count=len(packets),
        end_received=True,
        pending_hex="",
    )
    return report


def save(directory, report, data=None):
    directory.mkdir()
    if data is not None:
        (directory / "download.bin").write_bytes(data)
        report.update(received_bytes=len(data), download_bytes=len(data), download_sha256=probe.sha(data))
    (directory / "report.json").write_text(json.dumps(report))
    return directory


@pytest.fixture
def guards(tmp_path, monkeypatch):
    image = (bytes(range(256)) * 3624)[:927632]
    monkeypatch.setattr(probe, "IMAGE_SHA", probe.sha(image))
    directories = []
    for i, (source, (address, size)) in enumerate(probe.GUARDS.items()):
        report = attach_actions(receipt(f"rc{i:010x}", address, size, source=source))
        data = image[address - 0x10000000 : address - 0x10000000 + size]
        report["expected_sha256"] = probe.sha(data)
        directories.append(save(tmp_path / source, report, data))
    return image, directories


def test_guard_oracles_and_original_actions_trace_required(guards):
    image, directories = guards
    assert len(probe.validate_guards(directories, image, None)) == 7
    path = directories[0] / "report.json"
    report = json.loads(path.read_text())
    report["att_packets"] = []  # Keep every successful summary and exact downloaded bytes.
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="ATT Actions writes"):
        probe.validate_guards(directories, image, None)


@pytest.mark.parametrize(
    "kind", ["duplicate", "partial", "wrong-byte", "failed", "wrong-command", "wrong-image"]
)
def test_guard_gate_rejects_incomplete_or_substituted_evidence(guards, kind):
    image, directories = guards
    path = directories[0] / "report.json"
    report = json.loads(path.read_text())
    if kind == "duplicate":
        directories[-1] = directories[0]
    elif kind == "partial":
        binary = directories[0] / "download.bin"
        binary.write_bytes(binary.read_bytes()[:-1])
    elif kind == "wrong-byte":
        binary = directories[0] / "download.bin"
        binary.write_bytes(b"\xff" + binary.read_bytes()[1:])
        report["download_sha256"] = probe.sha(binary.read_bytes())
    elif kind == "failed":
        report["ok"] = False
    elif kind == "wrong-command":
        report["dump_command"] = report["dump_command"].replace(" 32 ", " 64 ")
    else:
        image = image[:-1] + b"x"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        probe.validate_guards(directories, image, None)


def test_handler_download_only_requires_explicit_valid_write_parent(guards, tmp_path):
    image, directories = guards
    index = list(probe.GUARDS).index("handler")
    parent_dir = directories[index]
    child = json.loads((parent_dir / "report.json").read_text())
    parent_bytes = (parent_dir / "report.json").read_bytes()
    for key in (
        "att_packets",
        "log_characteristics",
        "writes",
        "notifications",
        "frames",
        "log_session_complete",
        "ack_count",
        "expected_ack_count",
        "end_received",
        "pending_hex",
    ):
        child.pop(key)
    child.update(download_only=True, sd_write_attempted=False, parent_report_sha256=probe.sha(parent_bytes))
    child_dir = save(tmp_path / "handler-read", child, (parent_dir / "download.bin").read_bytes())
    directories[index] = child_dir
    with pytest.raises(ValueError, match="explicit handler parent"):
        probe.validate_guards(directories, image, None)
    assert len(probe.validate_guards(directories, image, parent_dir)) == 7
    child["parent_report_sha256"] = "0" * 64
    (child_dir / "report.json").write_text(json.dumps(child))
    with pytest.raises(ValueError, match="parent hash"):
        probe.validate_guards(directories, image, parent_dir)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra-write",
        "write-command",
        "missing-response",
        "early-ack",
        "early-end",
        "no-discovery",
        "wrong-uuid",
        "pending",
    ],
)
def test_actions_rejects_summary_spoofing_and_extra_wire_traffic(mutation):
    report = attach_actions(receipt("rc0123456789", probe.CONTEXT, 28))
    trace = report["att_packets"]
    if mutation in {"extra-write", "write-command"}:
        opcode = "12" if mutation == "extra-write" else "52"
        trace.append({"direction": "tx", "hex": opcode + "1c00deadbeef", "monotonic_ns": 1000})
    elif mutation == "missing-response":
        trace[:] = [row for i, row in enumerate(trace) if i != 9]
    elif mutation in {"early-ack", "early-end"}:
        value = ACK if mutation == "early-ack" else END
        trace.insert(8, {"direction": "rx", "hex": "1b1800" + value.hex(), "monotonic_ns": 7})
    elif mutation == "no-discovery":
        trace[:] = [row for row in trace if row["hex"] != DISCOVERY]
    elif mutation == "wrong-uuid":
        report["log_characteristics"][0]["uuid"] = NOTIFY
    else:
        report["pending_hex"] = "1d"
    with pytest.raises(ValueError):
        probe.validate_actions(report)


def test_actions_allows_confirmed_exact_boot_producer_only():
    report = attach_actions(receipt("rc0123456789", probe.BUFFER, 4096), producer=True)
    probe.validate_actions(report, producer=True)
    report["producer"] = "dbg fread spi_flash 0x1000"
    with pytest.raises(ValueError, match="Only exact boot0"):
        probe.validate_actions(report, producer=True)


def test_complete_info_and_bounded_write_capacity_delta_required():
    report = receipt("rc0123456789", probe.CONTEXT, 28)
    report["after"] = info(free_decrease=1)
    probe.same_identity(report)
    assert report["state_verification"]["free_capacity_decrease"] == 1
    report["sd_write_attempted"] = False
    report.pop("state_verification")
    with pytest.raises(ValueError, match="Unexpected state change"):
        probe.same_identity(report)
    report.update(after=info(), sd_write_attempted=True)
    report["after"]["device"]["raw"] = "00"
    with pytest.raises(ValueError, match="complete52"):
        probe.same_identity(report)


@pytest.mark.parametrize("bad", ["size", "buffer", "capacity", "index", "flags"])
def test_context_is_fixed_struct_without_following_pointers(bad):
    data = bytearray(struct.pack("<5I", 0, 28, 28, 4096, probe.BUFFER) + b"\x01\0" + bytes(6))
    if bad == "size":
        data.pop()
    elif bad == "flags":
        data[21] = 1
    else:
        at, value = {"buffer": (16, probe.BUFFER + 4), "capacity": (12, 8192), "index": (4, 4097)}[bad]
        struct.pack_into("<I", data, at, value)
    with pytest.raises(ValueError):
        probe.context_fields(bytes(data))


def test_baseline_unique_circular_nonce_and_no_old_nor_rows():
    report = receipt("rc0123456789", probe.BUFFER, 4096, phase=probe.Phase.baseline)
    marker = report["dump_command"].encode()
    logical = (b"prefix\r\n" + marker).ljust(4096, b"x")
    cut = len(marker) // 2
    wrapped = logical[cut:] + logical[:cut]
    assert probe.validate_payload(report, wrapped)["no_nor_rows"]
    for data in (
        (marker + b"\r\n" + marker).ljust(4096, b"x"),
        (marker + b"\r\n       0: " + b" 0 " * 16 + b"\r\n").ljust(4096, b"x"),
    ):
        with pytest.raises(ValueError):
            probe.validate_payload(report, data)


def test_real_boot_ring_exact_oracle_and_nonce_binding():
    data = Path("docs/evidence/sd-bridge-2026-10-13/boot-ring-download.bin").read_bytes()
    report = {
        "phase": "boot",
        "dump_command": "dbg dumpbuf 402910729 4096 /SD:/RECORDER/Call-rcb61b078de5.mp3",
    }
    assert probe.validate_payload(report, data)["sector_sha256"] == probe.BOOT_SHA
    with pytest.raises(ValueError, match="found 0"):
        probe.validate_payload(report | {"dump_command": "different nonce"}, data)
    values = next(row[3].encode() for row in probe.ring_rows(data) if row[2] == 0)
    changed = data.replace(values, (b"ff " if values[:3] != b"ff " else b"ee ") + values[3:], 1)
    with pytest.raises(ValueError, match="independent oracle"):
        probe.validate_payload(report, changed)


def test_previous_context_and_baseline_hash_chain_cannot_be_substituted(guards, tmp_path):
    image, directories = guards
    verified = probe.validate_guards(directories, image, None)
    context = attach_actions(receipt("rc0000000100", probe.CONTEXT, 28, phase=probe.Phase.context))
    context["guards"] = verified
    payload = struct.pack("<5I", 0, 20, 20, 4096, probe.BUFFER) + b"\x01\0" + bytes(6)
    ctx_dir = save(tmp_path / "context", context, payload)
    link = probe.previous(ctx_dir, probe.Phase.context, verified, image, None)
    baseline = attach_actions(receipt("rc0000000101", probe.BUFFER, 4096, phase=probe.Phase.baseline))
    baseline.update(guards=verified, previous=link)
    baseline_dir = save(tmp_path / "baseline", baseline, baseline["dump_command"].encode().ljust(4096, b"x"))
    assert probe.previous(baseline_dir, probe.Phase.baseline, verified, image, None)["report_sha256"]
    context["extra_marker"] = "changed receipt, same payload"
    (ctx_dir / "report.json").write_text(json.dumps(context))
    with pytest.raises(ValueError, match="context parent file/hash changed"):
        probe.previous(baseline_dir, probe.Phase.baseline, verified, image, None)


@pytest.mark.parametrize(
    "phase,previous",
    [(probe.Phase.context, "unexpected"), (probe.Phase.baseline, None), (probe.Phase.boot, None)],
)
def test_main_phase_gates_fail_before_capture_and_save_receipt(guards, tmp_path, phase, previous):
    image, directories = guards
    path = tmp_path / "image.bin"
    path.write_bytes(image)
    out = tmp_path / "trial"
    with patch.object(probe, "capture", AsyncMock()) as capture:
        with pytest.raises(ValueError, match="previous|--previous"):
            probe.main(
                path,
                out,
                directories,
                create_sd_file=True,
                phase=phase,
                previous_path=Path(previous) if previous else None,
            )
        capture.assert_not_awaited()
    report = json.loads((out / "report.json").read_text())
    assert report["ok"] is False and report["sd_write_attempted"] is False and report["error"]


def test_producer_request_failure_never_runs_dump_or_download(tmp_path):
    report = receipt("rc0123456789", probe.BUFFER, 4096, phase=probe.Phase.boot)
    report.update(producer=probe.PRODUCER, sd_write_attempted=False)
    sent = []

    class Link:
        mtu = 247
        failed = False

        def __init__(self, *_args):
            self.ack = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, pdu, _expected):
            sent.append(pdu)
            if self.failed:
                raise ConnectionError("link unusable")
            if pdu == b"\x12\x16\0" + probe.console_packet(probe.PRODUCER):
                self.failed = True
                raise OSError("producer rejected")
            if pdu.startswith(b"\x12\x16\0"):
                self.ack.append(ACK)
            return b"\x13"

        async def next_notification(self):
            return 24, self.ack.pop(0)

    with (
        patch.object(probe.sd_bootstrap, "identity", AsyncMock(return_value=(info(), []))),
        patch.object(
            probe.sd_bootstrap, "find_device", AsyncMock(return_value=SimpleNamespace(address="test"))
        ),
        patch.object(probe.sd_bootstrap, "AttLink", Link),
        patch.object(probe.sd_bootstrap, "discover", AsyncMock(return_value=(22, 24, 25))),
        patch.object(probe.sd_bootstrap, "download_file", AsyncMock()) as download,
    ):
        with pytest.raises(OSError, match="producer rejected"):
            asyncio.run(probe.capture(report, tmp_path))
        download.assert_not_awaited()
    assert b"\x12\x16\0" + probe.console_packet(report["dump_command"]) not in sent
    assert report["sd_write_attempted"] is False and "after" in report


def test_fake_complete_summary_and_after_error_preserve_primary_failure(tmp_path):
    report = receipt("rc0123456789", probe.CONTEXT, 28, phase=probe.Phase.context)

    async def fake_write(target):
        target.update(attach_actions(copy.deepcopy(target)))
        target["att_packets"] = []

    with (
        patch.object(
            probe.sd_bootstrap, "identity", AsyncMock(side_effect=[(info(), []), OSError("after failed")])
        ),
        patch.object(probe.sd_bootstrap, "write_file", fake_write),
        patch.object(probe.sd_bootstrap, "download_file", AsyncMock()) as download,
    ):
        with pytest.raises(ValueError, match="ATT Actions writes"):
            asyncio.run(probe.capture(report, tmp_path))
        download.assert_not_awaited()
    assert report["after_error"] == "OSError: after failed"


def test_previous_boot_replays_producer_and_real_sector(tmp_path):
    data = Path("docs/evidence/sd-bridge-2026-10-13/boot-ring-download.bin").read_bytes()
    report = attach_actions(
        receipt("rcb61b078de5", probe.BUFFER, 4096, phase=probe.Phase.boot), producer=True
    )
    report.update(
        guards=[], download_bytes=len(data), received_bytes=len(data), download_sha256=probe.sha(data)
    )
    (tmp_path / "download.bin").write_bytes(data)
    (tmp_path / "report.json").write_text(json.dumps(report))
    assert probe.previous(tmp_path, probe.Phase.boot, [], b"", None)["download_sha256"] == probe.sha(data)
    report["producer"] = "dbg fread spi_flash 0x1000"
    (tmp_path / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="exact boot0 producer"):
        probe.previous(tmp_path, probe.Phase.boot, [], b"", None)
