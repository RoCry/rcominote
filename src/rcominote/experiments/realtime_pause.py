"""Create one short recording and compare realtime pause/resume bytes with storage.

Run: uv run -m rcominote.experiments.realtime_pause NEW_OUTPUT_DIRECTORY
Raw audio stays in that directory; report contains no audio payload.
"""

import asyncio
import hashlib
import json
import time
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.connection import Connection, export_recording
from rcominote.device_commands import change_recording, read_info
from rcominote.realtime import _stop_owned


async def measure(out: Path, report: dict) -> None:
    started = time.monotonic()
    phase = "idle"
    packets = report["packets"] = []
    transitions = report["transitions"] = []
    with (out / "realtime.bin").open("xb") as handle:

        def receive(data: bytes) -> int:
            count = handle.write(data)
            packets.append({"seconds": round(time.monotonic() - started, 6), "phase": phase, "bytes": count})
            return count

        async with Connection(await find_device(serial=OWNED_SERIAL, seconds=12)) as conn:
            report["identity"] = await read_info(conn, OWNED_SERIAL)
            if report["identity"]["device"]["recording_state"] != "idle":
                raise RuntimeError("Device is not idle; experiment did not start")
            async with conn.realtime_capture(receive) as capture:
                await capture.wait(1)
                if (await conn.device_info())["recording_state"] != "idle":
                    raise RuntimeError("Device became busy; experiment did not start")
                try:
                    for action, interval in (("start", 3), ("pause", 1), ("resume", 3), ("stop", 1)):
                        phase = f"{action}_command"
                        result = await change_recording(conn, action)
                        transitions.append(result | {"seconds": round(time.monotonic() - started, 6)})
                        phase = f"after_{action}"
                        await capture.wait(interval)
                        if action == "pause":
                            # Separate one-second transition tail from a stable paused interval.
                            phase = "paused_stable"
                            await capture.wait(3)
                    report["final_state"] = await conn.device_info()
                except BaseException as error:
                    try:
                        report["cleanup"] = await _stop_owned(conn)
                    except BaseException as cleanup_error:  # noqa: BLE001 - preserve cancellation cleanup failure
                        raise RuntimeError(
                            f"Experiment failed: {error}; cleanup failed: {cleanup_error}"
                        ) from error
                    raise
    names = {transition["name"] for transition in transitions}
    if len(names) != 1:
        raise RuntimeError(f"Recording identity changed during experiment: {names}")
    name = transitions[0]["name"]
    async with Connection(await find_device(serial=OWNED_SERIAL, seconds=12)) as conn:
        await read_info(conn, OWNED_SERIAL)
        entries = await conn.file_list()
        entry = next((entry for entry in entries if entry.name == name), None)
        if entry is None:
            raise RuntimeError("Owned recording absent from file list")
        report["download"] = await export_recording(conn, name, out, expected_size=entry.size)
    realtime = (out / "realtime.bin").read_bytes()
    offline = (out / f"{name}.mp3").read_bytes()
    report["comparison"] = {
        "realtime_bytes": len(realtime),
        "offline_bytes": len(offline),
        "realtime_sha256": hashlib.sha256(realtime).hexdigest(),
        "offline_sha256": hashlib.sha256(offline).hexdigest(),
        "equal": realtime == offline,
        "paused_stable_packets": sum(packet["phase"] == "paused_stable" for packet in packets),
    }
    if not realtime or realtime != offline:
        raise RuntimeError("Realtime capture is empty or differs from complete offline recording")


def main(out: Path):
    """Create, pause, resume and stop one recording on the owned idle CoMi."""
    out.mkdir(parents=True, exist_ok=False)
    report = {"scope": "one bounded pause/resume recording; no deletion or firmware operations"}
    try:
        asyncio.run(measure(out, report))
        report["outcome"] = "passed"
    except BaseException as error:
        report["outcome"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["comparison"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    typer.run(main)
