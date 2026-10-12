"""Exercise the actual CLI's SIGINT export path on the owned idle recorder.

Run: uv run -m rcominote.experiments.download_cancel NEW_DIR BASELINE_MANIFEST
Baseline manifest must identify an earlier complete recording export. No retry,
recording mutation or firmware operation; audio and raw CLI output stay in NEW_DIR.
"""

import hashlib
import json
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def fingerprint(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def cli(out: Path, label: str, args: list[str], report: dict, *, interrupt_size: int = 0) -> dict | list:
    command = [sys.executable, "-m", "rcominote.cli", *args, "--serial", OWNED_SERIAL, "--seconds", "8"]
    observation = {"label": label, "arguments": command[3:], "sigint_sent": False}
    report["commands"].append(observation)
    started = time.monotonic()
    stdout, stderr = out / f"{label}.stdout.json", out / f"{label}.stderr.txt"
    with (
        stdout.open("xb") as output,
        stderr.open("xb") as errors,
        subprocess.Popen(command, stdout=output, stderr=errors) as process,
    ):
        try:
            deadline = started + 45
            while process.poll() is None:
                if interrupt_size and not observation["sigint_sent"]:
                    for partial in (out / "cancelled").glob(".*.part"):
                        try:
                            size = partial.stat().st_size
                        except FileNotFoundError:
                            continue
                        if 0 < size < interrupt_size:
                            process.send_signal(signal.SIGINT)
                            observation |= {
                                "sigint_sent": True,
                                "trigger_file_bytes": size,
                                "trigger_seconds": round(time.monotonic() - started, 6),
                            }
                            break
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"{label}: CLI exceeded 45 seconds")
                time.sleep(0.002 if interrupt_size else 0.02)
        finally:
            if process.poll() is None:
                observation["forced_process_cleanup"] = True
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            observation |= {
                "exit_code": process.returncode,
                "elapsed_seconds": round(time.monotonic() - started, 6),
            }
    require(
        process.returncode == (130 if interrupt_size else 0),
        f"{label}: unexpected exit {process.returncode}; inspect {stdout} and {stderr}",
    )
    if interrupt_size:
        require(observation["sigint_sent"], "Download finished before SIGINT; cancellation was not exercised")
    return json.loads(stdout.read_text())


def measure(out: Path, baseline_manifest: Path, report: dict) -> None:
    manifest = json.loads(baseline_manifest.read_text())
    require(
        manifest.get("offset", 0) == 0
        and manifest.get("scope", "complete_recording") == "complete_recording"
        and manifest.get("status") != "cancelled",
        "Baseline must be an earlier complete export, not a partial or offset download",
    )
    name = manifest["name"]
    baseline = Path(manifest["path"]).read_bytes()
    require(
        fingerprint(baseline) == {"bytes": manifest["bytes"], "sha256": manifest["sha256"]},
        "Earlier complete export no longer matches its saved manifest",
    )
    report["baseline"] = {"name": name, **fingerprint(baseline)}
    before = cli(out, "before-info", ["info"], report)
    report["before"] = before
    require(before["device"]["recording_state"] == "idle", "Device is busy; experiment did not start")
    require(before["device"]["version"] == "010004", "Device firmware differs from the reviewed contract")
    files = cli(out, "before-files", ["files"], report)
    report["files_before"] = files
    require(
        any(entry["name"] == name and entry["size"] == len(baseline) for entry in files),
        "Baseline recording absent or listed size changed",
    )
    cancelled_dir = out / "cancelled"
    cancelled = cli(
        out,
        "cancel",
        ["download", name, "--out", str(cancelled_dir)],
        report,
        interrupt_size=len(baseline),
    )
    report["cancel"] = cancelled
    require(cancelled["status"] == "cancelled", "CLI did not report cancellation")
    require(
        all(
            cancelled["stop"][key] is True
            for key in ("request_attempted", "request_sent", "response_received")
        )
        and cancelled["stop"]["error"] is None,
        "STOP request/reply not observed successfully; retain evidence as an incomplete cancellation trial",
    )
    require(cancelled["stop"]["worker_exit_verified"] is False, "STOP reply does not verify worker exit")
    partial = Path(cancelled["partial_path"]).read_bytes()
    require(0 < len(partial) < len(baseline), "Preserved file is not an incomplete nonempty prefix")
    require(partial == baseline[: len(partial)], "Canceled bytes differ from the independent complete export")
    require(
        fingerprint(partial) == {"bytes": cancelled["bytes"], "sha256": cancelled["sha256"]},
        "Canceled file differs from reported length or hash",
    )
    require(json.loads(Path(cancelled["manifest_path"]).read_text()) == cancelled, "Saved metadata differs")
    require(not list(cancelled_dir.glob("*.mp3")), "Canceled download incorrectly published a complete MP3")
    require(not list(cancelled_dir.glob(".*.part")), "Temporary file was left behind")
    report["partial_comparison"] = {**fingerprint(partial), "equals_baseline_prefix": True}
    complete = cli(out, "complete", ["download", name, "--out", str(out / "complete")], report)
    downloaded = Path(complete["path"]).read_bytes()
    require(downloaded == baseline, "Fresh-connection complete download differs from the earlier baseline")
    report["complete_comparison"] = {**fingerprint(downloaded), "equals_baseline": True}
    suffix = cli(
        out,
        "suffix",
        ["download", name, "--out", str(out / "suffix"), "--offset", str(len(partial))],
        report,
    )
    downloaded_suffix = Path(suffix["path"]).read_bytes()
    require(downloaded_suffix == baseline[len(partial) :], "Fresh-connection offset download differs")
    report["suffix_comparison"] = {
        "offset": len(partial),
        **fingerprint(downloaded_suffix),
        "equals_baseline_suffix": True,
        "automatic_resume": False,
    }
    after = cli(out, "after-info", ["info"], report)
    report["after"] = after
    require(
        after["serial"] == before["serial"] and after["bound"] == before["bound"], "Identity/binding changed"
    )
    stable_keys = (
        "version",
        "recording_state",
        "total_capacity",
        "free_capacity",
        "usb_mode",
        "mode",
        "indicator_light",
        "noise_reduction",
        "voice_control",
        "segment_duration",
        "screen_backlight",
    )
    require(all(before["device"][key] == after["device"][key] for key in stable_keys), "Device state changed")
    files_after = cli(out, "after-files", ["files"], report)
    report["files_after"] = files_after
    require(files_after == files, "Recording list changed")
    report["unchanged"] = {"device_fields": stable_keys, "recording_list": True}


def main(out: Path, baseline_manifest: Path):
    """Cancel one CLI download, compare saved bytes and fresh downloads with an earlier export."""
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "started_utc": datetime.now(UTC).isoformat(),
        "scope": "one real CLI SIGINT; read-only recording exports; separate BLE connection per command",
        "commands": [],
    }
    try:
        measure(out, baseline_manifest, report)
        report["outcome"] = "passed"
    except BaseException as error:
        report |= {"outcome": "failed", "error": f"{type(error).__name__}: {error}"}
        raise
    finally:
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    typer.run(main)
