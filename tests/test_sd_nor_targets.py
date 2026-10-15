"""Fixed nonzero raw profile: oracle provenance, command isolation and pair identity."""

import asyncio
import copy
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from test_sd_nor_probe import attach_actions, receipt

from rcominote.experiments import sd_bootstrap as bootstrap
from rcominote.experiments import sd_nor_probe as probe
from rcominote.experiments import sd_nor_targets as targets


def recovery():
    report = receipt("rc0123456789", probe.BUFFER, 4096, phase=probe.Phase.recovery)
    report.update(
        producer=targets.RECOVERY_PRODUCER,
        transport_profile=probe.Transport.interval,
        oracle=targets.oracle(probe.Phase.recovery)[2],
    )
    # Build real Actions framing with the existing fixture, then replace only its
    # boot producer value and packet with this fixed new profile's exact command.
    attach_actions(report, producer=True)
    old, new = probe.console_packet(probe.PRODUCER), probe.console_packet(targets.RECOVERY_PRODUCER)
    report["producer"] = targets.RECOVERY_PRODUCER
    report["writes"][2]["hex"] = new.hex()
    for row in report["att_packets"]:
        if row["hex"] == "121600" + old.hex():
            row["hex"] = "121600" + new.hex()
    return report


def ring(report):
    offset, oracle, _ = targets.oracle(probe.Phase.recovery)
    data = f"\r\nfread 512b: offset=0x{offset:x}, buf=0x18010000\r\n".encode()
    for start in range(0, 512, 16):
        data += (f"{start:8x}: " + "".join(f"{b:2x} " for b in oracle[start : start + 16]) + "\r\n").encode()
    for command in (targets.RECOVERY_PRODUCER, report["dump_command"]):
        data += f"logsrv: cmd({len(command)}) {command}\n\r\n".encode()
    return data.ljust(4096, b"x")


def test_fixed_raw_recovery_oracle_full_file_and_slice():
    offset, data, manifest = targets.oracle(probe.Phase.recovery)
    assert (offset, len(data), probe.sha(data)) == (0x4200, 512, targets.RECOVERY_BLOCK_SHA)
    assert manifest["bytes"] == 63288 and manifest["sha256"] == targets.RECOVERY_SHA
    assert data != targets.oracle(probe.Phase.boot)[1]
    with (
        patch.object(Path, "read_bytes", return_value=b"x" * 63288),
        pytest.raises(ValueError, match="Complete raw recovery"),
    ):
        targets.oracle(probe.Phase.recovery)


def test_exact_nonzero_actions_and_raw_sector_oracle():
    report = recovery()
    probe.validate_actions(report, producer=True)
    assert probe.validate_payload(report, ring(report))["sector_sha256"] == targets.RECOVERY_BLOCK_SHA
    for fault in ("offset", "producer", "oracle", "sector"):
        actual = copy.deepcopy(report)
        raw = ring(report)
        if fault == "offset":
            raw = raw.replace(b"offset=0x4200", b"offset=0x4000")
        elif fault == "producer":
            raw = raw.replace(b"dbg fread spi_flash 0x4200", b"dbg fread spi_flash 0x4000")
        elif fault == "oracle":
            actual["oracle"]["sha256"] = "0" * 64
        else:
            raw = raw.replace(b"       0: ", b"       1: ", 1)
        with pytest.raises(ValueError):
            probe.validate_payload(actual, raw)


@pytest.mark.parametrize(
    "key,value",
    [
        ("producer", "dbg fread spi_flash 0x4400"),
        ("phase", "boot"),
        ("transport_profile", "natural"),
        ("source_bytes", 512),
        ("source_address", "0x18000000"),
        ("dump_command", "dbg dumpbuf 0 4096 x"),
    ],
)
def test_write_allowlist_rejects_cross_profile_or_arbitrary_offset_before_io(key, value):
    report = recovery()
    report[key] = value
    with patch.object(bootstrap, "write_commands", AsyncMock()) as write:
        with pytest.raises(ValueError):
            asyncio.run(bootstrap.write_file(report))
        write.assert_not_called()


def test_write_allowed_exact_profile_preserves_single_producer():
    report = recovery()
    with patch.object(bootstrap, "write_commands", AsyncMock()) as write:
        asyncio.run(bootstrap.write_file(report))
        write.assert_awaited_once_with(report, [targets.RECOVERY_PRODUCER, report["dump_command"]])


def test_recovery_natural_cli_rejected_before_any_output(tmp_path):
    with pytest.raises(Exception, match="require interval"):
        probe.main(
            tmp_path,
            tmp_path / "new",
            [],
            create_sd_file=True,
            phase=probe.Phase.recovery,
            transport=probe.Transport.natural,
        )
    assert not (tmp_path / "new").exists()


def test_double_read_requires_two_replayed_new_producer_acquisitions(tmp_path):
    first = recovery()
    first.update(
        guards=[],
        previous={"report_sha256": "shared boot"},
        started_at="2026-10-14T00:00:00+00:00",
        ended_at="2026-10-14T00:01:00+00:00",
        transport={"update_requested_us": 10},
        verification=probe.validate_payload(first, ring(first)),
    )
    second = copy.deepcopy(first)
    second.update(
        name="rc1234567890",
        device_path="/SD:/RECORDER/Call-rc1234567890.mp3",
        dump_command=f"dbg dumpbuf {probe.BUFFER} 4096 /SD:/RECORDER/Call-rc1234567890.mp3",
        started_at="2026-10-14T00:02:00+00:00",
        ended_at="2026-10-14T00:03:00+00:00",
        transport={"update_requested_us": 20},
    )
    with patch.object(probe, "validate_guards", return_value=[]), patch.object(probe, "previous") as previous:
        with patch.object(probe, "load", side_effect=[(first, b""), (second, b"")]):
            assert targets.verify_pair(tmp_path / "a", tmp_path / "b", b"")["independent_reads"] == 2
        assert previous.call_count == 2
        for key, value in (
            ("name", first["name"]),
            ("started_at", first["started_at"]),
            ("previous", {}),
            ("transport", first["transport"]),
        ):
            changed = second | {key: value}
            with (
                patch.object(probe, "load", side_effect=[(first, b""), (changed, b"")]),
                pytest.raises(ValueError),
            ):
                targets.verify_pair(tmp_path / "a", tmp_path / "b", b"")
