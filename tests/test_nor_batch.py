"""Warm-session scoping and lost/invalid current context rows, using captured bytes."""

import asyncio
import json
from pathlib import Path

import pytest

from rcominote import printk_ring, printk_tail
from rcominote.log_stream import Stream
from rcominote.nor_batch import capture_remaining, guard_prefix

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence"


def actual_seed():
    return json.loads((EVIDENCE / "printk-nor-tail-second-2026-10-12.json").read_text())


def test_actual_wrapped_overwrite_is_not_counted_as_double_read():
    from rcominote.nor_windows import analyze

    directory = EVIDENCE / "nor-warm-sector-2026-10-12"
    report = analyze([directory / f"failed-window-{index:02}.json" for index in (6, 17)])
    assert "0xd0" in report["unconfirmed_rows"]
    assert "sector_hex" not in report


def test_warm_capture_matches_independent_cold_sector_golden():
    from rcominote.nor_windows import analyze

    report = analyze(sorted((EVIDENCE / "nor-warm-sector-2026-10-12").glob("window-*.json")))
    assert report["sha256"] == "72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec"


def test_wrapped_cold_capture_reads_both_halves_before_help():
    capture = json.loads((EVIDENCE / "nor-warm-sector-2026-10-12/failed-window-06.json").read_text())
    capture["tail_appended"] = False
    capture["fixed_text_commands"] = capture["fixed_text_commands"][
        : capture["fixed_text_commands"].index(printk_tail.MARKER) + 1
    ]
    printk_tail.append_tail(capture)
    assert capture["fixed_text_commands"][-3:] == ["dbg mdb 1803fd83 86", "dbg mdb 1803ee09 7a", "help"]


def test_shared_prefix_excludes_previous_producer_and_ram_payload():
    seed = actual_seed()
    prefix = guard_prefix(seed)
    assert len(prefix["frames"]) == 137  # Captured last fread-guard flush completion.
    assert "dbg fread spi_flash 0" not in prefix["fixed_text_commands"]
    assert printk_tail.MARKER not in prefix["range_frame_spans"]
    assert not any(command.startswith("dbg mdb 1803f") for command in prefix["fixed_text_commands"])
    assert "source_capture_sha256" not in prefix
    assert prefix["shared_session_started_at"] == seed["captured_at"]
    assert printk_ring.read(prefix | {"ok": True}, 0x100BB960, 16).hex() == (
        "636b0c10696b0c100000000049530210"
    )


def test_prefix_lists_are_owned_and_do_not_modify_seed():
    seed = actual_seed()
    prefix = guard_prefix(seed)
    prefix["frames"][0]["changed"] = True
    prefix["fixed_text_commands"].append("not a device command")
    prefix["range_frame_spans"]["dbg mdb 100bb960 10"][1] = 0
    assert "changed" not in seed["frames"][0]
    assert "not a device command" not in seed["fixed_text_commands"]
    assert seed["range_frame_spans"]["dbg mdb 100bb960 10"][1] == 137


@pytest.mark.parametrize("flags", ["00 00", "01 01"])
def test_current_context_flags_block_payload_even_if_shared_old_flags_valid(flags):
    seed = actual_seed()
    stream = Stream()
    sent = []
    frame = dict(seed["frames"][139])
    assert "09 ee 03 18 01 00" in frame["text"]
    frame["text"] = frame["text"].replace("09 ee 03 18 01 00", f"09 ee 03 18 {flags}")

    async def request(packet):
        command = packet[8:].decode("ascii")
        sent.append(command)
        if command == "dbg mdb 1800e008 1c":
            stream.frames.append(frame)

    async def pump(*, timeout):
        raise AssertionError("Complete captured context must be checked without another packet")

    with pytest.raises(ValueError, match="Current printk DMA ring init/panic flags"):
        asyncio.run(capture_remaining(seed, stream, request, pump, (0,)))
    assert sent == ["dbg fread spi_flash 0", "dbg mdb 1800e008 1c"]


def test_lost_second_context_row_cannot_reuse_shared_prefix_or_read_payload():
    seed = actual_seed()
    stream = Stream()
    sent = []
    frame = dict(seed["frames"][139])
    frame["text"] = "\r\n".join(
        line for line in frame["text"].split("\r\n") if not line.startswith("1800e018:")
    )

    async def request(packet):
        command = packet[8:].decode("ascii")
        sent.append(command)
        if command == "dbg mdb 1800e008 1c":
            stream.frames.append(frame)

    async def pump(*, timeout):
        raise TimeoutError("captured second context row lost")

    with pytest.raises(TimeoutError, match="second context row lost"):
        asyncio.run(capture_remaining(seed, stream, request, pump, (0,)))
    assert sent == ["dbg fread spi_flash 0", "dbg mdb 1800e008 1c"] + ["kernel version"] * 8
