"""Replay captured warm-window bytes, then lose a later window or final F1."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest

from rcominote import nor_batch, nor_batch_cli
from rcominote.log_stream import Stream
from rcominote.printk_tail import NorTarget
from rcominote.readback_verify import finish_capture

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/nor-warm-sector-2026-10-12"


def actual(index):
    return json.loads((EVIDENCE / f"window-{index:02}.json").read_text())


def test_completed_window_survives_later_timeout():
    seed, recorded = actual(0), actual(1)
    prefix = nor_batch.guard_prefix(recorded)
    frames = iter(recorded["frames"][len(prefix["frames"]) :])
    commands = iter(recorded["fixed_text_commands"][len(prefix["fixed_text_commands"]) :])
    stream = Stream()
    replay_finished = False

    async def request(packet):
        nonlocal replay_finished
        command = packet[8:].decode("ascii")
        if replay_finished:
            raise TimeoutError("next captured window lost")
        assert command == next(commands)
        for frame in frames:
            stream.feed(bytes.fromhex(frame["hex"]))
            if frame["command"] == 0x10:
                break
        else:
            raise AssertionError("Captured command ACK missing")
        if command == "help":
            replay_finished = True

    async def pump(*, timeout):
        frame = next(frames)
        stream.feed(bytes.fromhex(frame["hex"]))

    with pytest.raises(TimeoutError, match="next captured window lost"):
        asyncio.run(nor_batch.capture_remaining(seed, stream, request, pump, (1, 2)))
    assert len(seed["batch_records"]) == 1
    assert seed["batch_records"][0]["console_tail"]["hex"] == recorded["console_tail"]["hex"]


def finalized(*, lost_end=False, invalid_window=False, invalid_seed=False):
    result = actual(0)
    result["batch_records"] = [actual(1)]
    result["batch_error"] = "TimeoutError: later window"
    # Committed scoped fixtures omit notification timing; no timing claim here.
    result["notifications"] = [{"seconds": 0.0}]
    if invalid_seed:
        result["fixed_text_commands"].remove("dbg mdb 100bb960 10")
    if invalid_window:
        bad = actual(2)
        bad["frames"] = bad["frames"][: bad["range_frame_spans"]["dbg mdb 1800e008 1c"][0]]
        result["batch_records"].append(bad)
    stream = Stream()
    for frame in result["frames"]:
        if not lost_end or frame["command"] != 0xF1:
            stream.feed(bytes.fromhex(frame["hex"]))
    finish_capture(result, stream, stream.acks)
    return result


def test_late_batch_error_keeps_verified_seed_and_window():
    result = finalized()
    assert not result["ok"]
    assert result["readback_complete"]
    assert result["batch_records"][0]["ok"]


def test_lost_end_rejects_partial_windows():
    result = finalized(lost_end=True)
    assert not result["transport_ok"]
    assert not result["batch_records"][0]["ok"]


@pytest.mark.parametrize("lost_end, expected", [(False, 2), (True, 0)])
def test_cli_publishes_only_individually_verified_windows(monkeypatch, tmp_path, lost_end, expected):
    result = finalized(lost_end=lost_end, invalid_window=True)

    async def capture(**kwargs):
        return deepcopy(result)

    monkeypatch.setattr(nor_batch_cli.log_capture, "capture", capture)
    out = tmp_path / "attempt"
    report = asyncio.run(nor_batch_cli.capture_sector(out, NorTarget.boot, "C261CF0430"))
    assert not report["complete"]
    assert len(list(out.glob("window-*.json"))) == expected
    assert not (out / "sector.bin").exists()


def test_failed_seed_guard_rejects_partial_windows():
    result = finalized(invalid_seed=True)
    assert not result["readback_complete"]
    assert not result["batch_records"][0]["ok"]
