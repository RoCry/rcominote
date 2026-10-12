#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#   "pyelftools==0.32", "PyYAML==6.0.3", "pykwalify==1.8.0",
#   "packaging==25.0", "west==1.5.0", "setuptools==80.9.0",
# ]
# ///
"""Compile the pinned Actions reference application on Linux; never package or flash."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

SDK_COMMIT = "26f51e584940d5b141cd1d09d2629d69b595f579"
BOARD = "ats3089p_dev_watch_sdnand_8b"


def output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True, help="Public lv_port_actions_technology checkout")
    parser.add_argument("--toolchain", type=Path, required=True, help="GNU Arm Embedded 10.3-2021.10 directory")
    parser.add_argument("--out", type=Path, default=Path("artifacts/sdk-build"))
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("This verified build route targets Linux x86_64")
    if not 1 <= args.jobs <= 16:
        raise ValueError("--jobs must be between 1 and 16")
    source, toolchain, destination = args.sdk.resolve(), args.toolchain.resolve(), args.out.resolve()
    if output(["git", "-C", str(source), "rev-parse", "HEAD"]) != SDK_COMMIT:
        raise ValueError(f"SDK must be at {SDK_COMMIT}")
    if output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("SDK has tracked changes; use a clean checkout of the pinned source")
    compiler = toolchain / "bin/arm-none-eabi-gcc"
    compiler_version = output([str(compiler), "--version"]).splitlines()[0]
    if "10.3.1" not in compiler_version:
        raise ValueError(f"Expected GNU Arm 10.3.1, found {compiler_version}")
    sdk = source / "action_technology_sdk"
    zephyr = sdk / "zephyr"
    modules = sorted(
        str(path.parent.parent)
        for root in ("framework", "thirdparty")
        for path in (sdk / root).rglob("zephyr/module.yml")
    )
    if not modules:
        raise ValueError("No local SDK modules found")
    destination.mkdir(parents=True, exist_ok=True)
    environment = os.environ | {
        "ZEPHYR_BASE": str(zephyr),
        "ZEPHYR_TOOLCHAIN_VARIANT": "gnuarmemb",
        "GNUARMEMB_TOOLCHAIN_PATH": str(toolchain),
    }
    commands = [
        [
            "cmake",
            "-S",
            str(source / "hello_world"),
            "-B",
            str(destination),
            "-G",
            "Ninja",
            f"-DBOARD={BOARD}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            f"-DCMAKE_PROJECT_hello_world_INCLUDE={Path(__file__).with_name('sdk_output.cmake').resolve()}",
            "-DZEPHYR_MODULES=" + ";".join(modules),
        ],
        ["cmake", "--build", str(destination), "--parallel", str(args.jobs)],
    ]
    manifest = {
        "started_at": datetime.now(UTC).isoformat(),
        "sdk_commit": SDK_COMMIT,
        "board": BOARD,
        "application": "hello_world",
        "compiler": compiler_version,
        "python": sys.version,
        "cmake": output(["cmake", "--version"]).splitlines()[0],
        "ninja": output(["ninja", "--version"]),
        "python_packages": {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()},
        "commands": commands,
        "status": "running",
        "scope": "reference-board compilation only; no packaging or hardware operations",
    }
    manifest_path = destination / "build-manifest.json"
    log_path = destination / "build.log"
    try:
        with log_path.open("w", encoding="utf-8") as log:
            for command in commands:
                print(f"Running {command[0]} {command[1]}; log: {log_path}", flush=True)
                subprocess.run(command, env=environment, cwd=zephyr, stdout=log, stderr=subprocess.STDOUT, check=True)
        manifest["artifacts"] = {}
        for name in ("zephyr.elf", "zephyr.bin", "zephyr.hex", ".config"):
            path = destination / "zephyr" / name
            data = path.read_bytes()
            manifest["artifacts"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        manifest["sdk_tracked_changes"] = output(
            ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"]
        )
        if manifest["sdk_tracked_changes"]:
            raise RuntimeError("Build changed tracked SDK files; inspect build-manifest.json")
        manifest["status"] = "success"
    except Exception:
        manifest["status"] = "failed"
        if log_path.exists():
            print("\n".join(log_path.read_text(errors="replace").splitlines()[-60:]), file=sys.stderr)
        raise
    finally:
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        print(f"Build {manifest['status']}: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
