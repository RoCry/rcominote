"""Unknown0x2200 is never prefilled or called oracle-verified; no hardware."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from test_sd_nor_targets import recovery

from rcominote.experiments import sd_bootstrap as B
from rcominote.experiments import sd_nor_probe as P
from rcominote.experiments import sd_nor_targets as T
from rcominote.experiments import sd_nor_unknown as U


def report(name="rc0123456789"):
    r = recovery()
    old, new = P.console_packet(T.RECOVERY_PRODUCER), P.console_packet(T.BACKUP_PRODUCER)
    r.update(
        phase=T.Phase.backup.value,
        producer=T.BACKUP_PRODUCER,
        independent_oracle=False,
        pair_verified=False,
        coverage_basis=U.basis(),
    )
    r.pop("oracle")
    r["writes"][2]["hex"] = new.hex()
    for row in r["att_packets"]:
        if row["hex"] == "121600" + old.hex():
            row["hex"] = "121600" + new.hex()
    if name != r["name"]:
        # Pair tests below mock prior transport replay; marker/source still genuine.
        r["dump_command"] = r["dump_command"].replace(r["name"], name)
        r["device_path"] = r["device_path"].replace(r["name"], name)
        r["name"] = name
    return r


def ring(r, sector, offset=0x2200):
    raw = f"\r\nfread 512b: offset=0x{offset:x}, buf=0x18010000\r\n".encode()
    for at in range(0, 512, 16):
        raw += (f"{at:8x}: " + "".join(f"{b:2x} " for b in sector[at : at + 16]) + "\r\n").encode()
    for cmd in (T.BACKUP_PRODUCER, r["dump_command"]):
        raw += f"logsrv: cmd({len(cmd)}) {cmd}\n\r\n".encode()
    return raw.ljust(4096, b"x")


def test_actual_acpt_range_and_old_prefix_are_not_new_oracle():
    basis = U.basis()
    assert basis["entry"]["name"] == "fw1_boot"
    assert basis["previously_covered"] == [0x2000, 0x2200]
    assert basis["new_range"] == [0x2200, 0x2400]
    with pytest.raises(ValueError, match="No raw NOR oracle"):
        T.oracle(T.Phase.backup)
    with patch.object(U, "ACPT_SHA", "0" * 64), pytest.raises(ValueError, match="ACPT"):
        U.basis()


@pytest.mark.parametrize("data", [bytes(512), b"\xff" * 512, bytes(range(256)) * 2])
def test_unknown_single_read_accepts_observed_bytes_without_expected_value(data):
    r = report()
    P.validate_actions(r, producer=True)
    parsed = P.validate_payload(r, ring(r, data))
    assert bytes.fromhex(parsed["sector_hex"]) == data
    assert parsed["verification_level"] == "complete-single-read-no-independent-oracle"
    assert r["pair_verified"] is False and r["independent_oracle"] is False


@pytest.mark.parametrize("fault", ["offset", "producer", "nonce", "oracle", "pair", "range", "missing-row"])
def test_unknown_requires_exact_attribution_and_no_success_promotion(fault):
    r = report()
    raw = ring(r, bytes(512))
    if fault == "offset":
        raw = raw.replace(b"offset=0x2200", b"offset=0x2000")
    elif fault == "producer":
        raw = raw.replace(T.BACKUP_PRODUCER.encode(), T.RECOVERY_PRODUCER.encode())
    elif fault == "nonce":
        raw = raw.replace(r["name"].encode(), b"rc0000000000")
    elif fault == "oracle":
        r["oracle"] = {"invented": True}
    elif fault == "pair":
        r["pair_verified"] = True
    elif fault == "range":
        r["coverage_basis"]["new_range"] = [0x2200, 0x2600]
    else:
        raw = raw.replace(b"      10: ", b"      11: ")
    with pytest.raises(ValueError):
        P.validate_payload(r, raw)


def test_unknown_write_allowlist_never_accepts_another_offset():
    r = report()
    with patch.object(B, "write_commands", AsyncMock()) as write:
        asyncio.run(B.write_file(r))
        write.assert_awaited_once_with(r, [T.BACKUP_PRODUCER, r["dump_command"]])
        r["producer"] = "dbg fread spi_flash 0x2400"
        with pytest.raises(ValueError):
            asyncio.run(B.write_file(r))
        assert write.await_count == 1


def test_missing_known_pair_second_fails_before_oracle_claim_or_capture(tmp_path):
    r = report()
    r["guards"] = []
    with (
        patch.object(P, "previous", return_value={}),
        patch.object(P, "load", return_value=({"transport_profile": T.Transport.interval}, b"")),
        pytest.raises(ValueError, match="known-pair-second"),
    ):
        T.prepare(r, b"", tmp_path, None, None)
    assert "oracle" not in r


def test_known_pair_hashes_and_chronology_are_bound(tmp_path):
    dirs = [tmp_path / "first", tmp_path / "second"]
    for directory in dirs:
        directory.mkdir()
        (directory / "report.json").write_text(json.dumps({"ended_at": "2026-10-14T00:01:00+00:00"}))
    r = report()
    with patch.object(
        T, "verify_pair", return_value={"nor_offset": 0x4200, "independent_reads": 2}
    ) as verify:
        r["known_pair"] = U.gate(*dirs, b"")
        r["previous"] = r["known_pair"]["first"] | {"download_sha256": "retained"}
        r["started_at"] = "2026-10-14T00:02:00+00:00"
        U.validate_gate(r, b"")
        assert verify.call_count == 2
        early = r | {"started_at": "2026-10-14T00:00:00+00:00"}
        with pytest.raises(ValueError, match="predates"):
            U.validate_gate(early, b"")
        (dirs[1] / "report.json").write_text(json.dumps({"ended_at": "2026-10-14T00:00:59+00:00"}))
        with pytest.raises(ValueError, match="hash chain"):
            U.validate_gate(r, b"")


@pytest.mark.parametrize("conflict", [False, True])
def test_pair_replays_first_then_requires_all512_equal_without_oracle(tmp_path, conflict):
    first, second = report(), report("rc1234567890")
    for index, r in enumerate((first, second)):
        r["known_pair"] = {"same-parent": True}
        data = bytes(range(256)) * 2
        if index == 1 and conflict:
            data = b"\xff" + data[1:]
        directory = tmp_path / str(index)
        directory.mkdir()
        raw = ring(r, data)
        (directory / "download.bin").write_bytes(raw)
        r["verification"] = U.payload(r, raw)
        (directory / "report.json").write_text(json.dumps(r))
    with patch.object(T, "pair_reports", return_value=(first, second)) as replay:
        if conflict:
            with pytest.raises(ValueError, match="conflict"):
                U.verify_pair(tmp_path / "0", tmp_path / "1", b"")
        else:
            result = U.verify_pair(tmp_path / "0", tmp_path / "1", b"")
            assert result["verification_level"] == "pair-verified"
            assert result["independent_oracle"] is False
        replay.assert_called_once_with(tmp_path / "0", tmp_path / "1", b"", T.Phase.backup)
