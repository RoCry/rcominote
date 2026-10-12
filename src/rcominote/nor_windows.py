"""Offline assembly of repeated, guarded fixed NOR-target log windows."""

import hashlib
import json
import re
from pathlib import Path

from . import printk_tail
from .output import emit

ROWS = tuple(range(0, 512, 16))
# Actual fread uses "%8x: ", sixteen "%2x ", then CRLF. Width two
# deliberately permits a space followed by one hex digit (e.g. " c ").
LINE = re.compile(r"(?<=\r\n)( {0,7}[0-9a-f]{1,8}): ((?:(?:[0-9a-f]{2}| [0-9a-f]) ){16})\r\n")


def _rows(text: str) -> list[tuple[int, bytes]]:
    rows = []
    # Never trust the first fragment: an actual truncated "1d0:" became "0:".
    # Both delimiters must occur inside the independently read RAM window.
    for match in LINE.finditer(text):
        prefix, values = match.groups()
        offset = int(prefix, 16)
        if offset in ROWS and prefix == f"{offset:8x}":
            rows.append((offset, bytes(int(token, 16) for token in values.split())))
    return rows


def analyze(paths: list[Path]) -> dict:
    """Revalidate each capture; count a row once per conservative source identity.

    Every input is parsed, including duplicates: duplicates cannot conceal a
    conflict. Identity aliases merge transitively across file bytes, original
    capture digests, and the owned-device serial / capture timestamp pair.
    """
    if not paths:
        raise ValueError("At least one guarded NOR window capture is required")
    parents = list(range(len(paths)))
    identities: dict[tuple[str, ...], int] = {}
    records = []

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for index, path in enumerate(paths):
        raw = path.read_bytes()
        try:
            capture = json.loads(raw)
            value = printk_tail.verify_producer(capture)
            if records and value.value != records[0]["target"]:
                raise ValueError("Cannot assemble mixed NOR targets")
            tail = printk_tail.inspect(capture)
            if records and tail["offset"] != records[0]["offset"]:
                raise ValueError("Cannot assemble mixed NOR block offsets")
            aliases = [("digest", hashlib.sha256(raw).hexdigest())]
            if digest := capture.get("source_capture_sha256"):
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise ValueError("Invalid original capture SHA-256")
                aliases.append(("digest", digest))
            if captured_at := capture.get("captured_at"):
                if not isinstance(captured_at, str):
                    raise ValueError("Invalid capture timestamp")
                aliases.append(("timestamp", capture["serial"], captured_at))
            for alias in aliases:
                if alias in identities:
                    parents[root(index)] = root(identities[alias])
                identities[alias] = index
            records.append(
                {
                    "path": str(path),
                    "target": tail["target"],
                    "offset": tail["offset"],
                    "producer": tail["producer"],
                    "rows": _rows(tail["text"]),
                }
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid NOR window capture {path}: {error}") from error

    variants: dict[int, dict[bytes, set[int]]] = {offset: {} for offset in ROWS}
    for index, record in enumerate(records):
        for offset, data in record["rows"]:
            variants[offset].setdefault(data, set()).add(root(index))
    conflicts = [hex(offset) for offset, values in variants.items() if len(values) > 1]
    missing = [hex(offset) for offset, values in variants.items() if not values]
    unconfirmed = [
        hex(offset)
        for offset, values in variants.items()
        if len(values) == 1 and len(next(iter(values.values()))) < 2
    ]
    complete = not (conflicts or missing or unconfirmed)
    report = {
        "scope": "Guarded, non-atomic fixed NOR-target log rows; no full-device backup or recovery proof",
        "producer": records[0]["producer"],
        "target": records[0]["target"],
        "offset": records[0]["offset"],
        "input_files": len(paths),
        "distinct_sources": len({root(index) for index in range(len(paths))}),
        "required_rows": 32,
        "observed_rows": sum(bool(values) for values in variants.values()),
        "confirmed_rows": sum(
            len(values) == 1 and len(next(iter(values.values()))) >= 2 for values in variants.values()
        ),
        "missing_rows": missing,
        "unconfirmed_rows": unconfirmed,
        "conflicts": conflicts,
        "complete": complete,
        "rows": [
            {
                "offset": hex(offset),
                "variants": [
                    {"hex": data.hex(), "sources": len(sources)} for data, sources in values.items()
                ],
            }
            for offset, values in variants.items()
            if values
        ],
    }
    if complete:
        data = b"".join(next(iter(variants[offset])) for offset in ROWS)
        report.update(sector_hex=data.hex(), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    return report


def main(captures: list[Path], out: Path | None = None):
    """Inspect NOR windows offline; --out writes 512 bytes only after double coverage."""
    report = analyze(captures)
    if out is not None:
        if not report["complete"]:
            raise ValueError(
                f"NOR sector incomplete: missing={report['missing_rows']}, "
                f"unconfirmed={report['unconfirmed_rows']}, conflicts={report['conflicts']}"
            )
        with out.open("xb") as handle:
            handle.write(bytes.fromhex(report["sector_hex"]))
        report["output"] = str(out)
    emit(report)
