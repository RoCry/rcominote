#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["pyelftools", "requests", "typer>=0.16,<1"]
# ///
"""Run pinned Blutter offline analysis; never launch APK or generated instrumentation."""

import runpy
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

COMMIT = "4a60ac648bf448c5a7596437243bcd0b9376fdf0"


def main(
    apk: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    out: Path,
    blutter_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)],
):
    root = blutter_dir.resolve()
    actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if actual != COMMIT:
        raise ValueError(f"Expected Blutter {COMMIT}, got {actual}")
    subprocess.run(["git", "-C", str(root), "diff", "--exit-code", "HEAD", "--"], check=True)
    if out.exists():
        raise FileExistsError(f"Refusing existing output: {out}")
    sys.path.insert(0, str(root))
    sys.argv = [str(root / "blutter.py"), str(apk.resolve()), str(out.resolve())]
    runpy.run_path(str(root / "blutter.py"), run_name="__main__")


if __name__ == "__main__":
    typer.run(main)
