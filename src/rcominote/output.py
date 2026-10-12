"""JSON results and new evidence files, with explicit overwrite refusal."""

import json
from pathlib import Path


def emit(value: object, out: Path | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as handle:
            handle.write(text)
    print(text, end="", flush=True)


def new_output(out: Path | None) -> None:
    if out is not None and out.exists():
        raise FileExistsError(f"Output already exists: {out}")
