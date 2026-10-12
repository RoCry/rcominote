"""Offline inspection of the fixed 16-byte CoMi sample; never connects to hardware."""

import hashlib
import json
import re
from pathlib import Path
from typing import Annotated

import typer
from capstone import CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB, Cs

ADDRESS = 0x1000BF20


def read_sample(path: Path) -> bytes:
    capture = json.loads(path.read_text())
    if capture.get("serial") != "C261CF0430" or not capture.get("ok"):
        raise ValueError(f"Not a completed owned-device capture: {path}")
    if "dbg mdb 1000bf20 10" not in capture.get("fixed_text_commands", []):
        raise ValueError(f"Capture lacks the fixed 16-byte read: {path}")
    text = "".join(frame.get("text", "") for frame in capture["frames"])
    rows = re.findall(r"(?m)^1000bf20: ((?:[0-9a-f]{2} ){15}[0-9a-f]{2}) {2,}", text)
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one complete 16-byte row; got {len(rows)}")
    return bytes.fromhex(rows[0])


def inspect_samples(first: Path, second: Path) -> dict:
    captures = [json.loads(path.read_text()) for path in (first, second)]
    identities = [(capture.get("serial"), capture.get("captured_at")) for capture in captures]
    if any(not identity[1] for identity in identities) or identities[0] == identities[1]:
        raise ValueError("Two distinct capture records are required; duplicate or missing capture identity")
    sample = read_sample(first)
    if read_sample(second) != sample:
        raise ValueError("Independent samples differ; refusing to treat them as stable code")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    instructions = [
        {
            "address": hex(ins.address),
            "bytes": ins.bytes.hex(),
            "mnemonic": ins.mnemonic,
            "operands": ins.op_str,
        }
        for ins in decoder.disasm(sample, ADDRESS)
    ]
    decoded = sum(len(bytes.fromhex(ins["bytes"])) for ins in instructions)
    return {
        "scope": "16 mapped bytes only; Thumb decoding is inference, not full firmware or physical flash backup",
        "capture_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in (first, second)],
        "address": hex(ADDRESS),
        "length": len(sample),
        "hex": sample.hex(),
        "sha256": hashlib.sha256(sample).hexdigest(),
        "independent_reads_match": True,
        "decoder": "Capstone 5.0.6, ARM Thumb little-endian",
        "decoded_bytes": decoded,
        "instructions": instructions,
        "limitations": ["Does not execute code", "No physical offset or image extent established"],
    }


def main(
    first: Path,
    second: Path,
    out: Annotated[Path, typer.Option(help="New JSON report")],
):
    if out.exists():
        raise FileExistsError(out)
    report = inspect_samples(first, second)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["decoded_bytes"] != report["length"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
