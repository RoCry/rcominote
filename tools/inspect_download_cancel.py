#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Emit bounded static STOP_GET_FILE evidence; no target execution or device I/O."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

IMAGE_SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
JS_SHA = "167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c"
BASE = 0x10000000
CODE = (
    ("context_getter", 0xA1B0, 0xA1B6),
    ("reply_frame_and_stream_write", 0xA888, 0xA936),
    ("reply_dispatch_prefix", 0xB114, 0xB142),
    ("reply_shared_send_and_free", 0xB16C, 0xB178),
    ("reply_free", 0xB2AA, 0xB2B6),
    ("download_and_cancel_reply_cases", 0xB2B6, 0xB2F8),
    ("stop_get_file", 0xB368, 0xB3A4),
    ("worker_initialization_and_cancel_reset", 0xB594, 0xB5C8),
    ("worker_terminal_paths_and_close", 0xB644, 0xB688),
    ("worker_start_reply_and_seek", 0xB688, 0xB6C6),
    ("worker_loop_and_terminal_selection", 0xB712, 0xB77C),
    ("download_scheduler", 0xB998, 0xBA1A),
    ("stream_write", 0x51980, 0x51AFE),
    ("link_state_getter", 0x6BE84, 0x6BE8A),
)


def checked(path: Path, expected: str) -> bytes:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Input SHA-256 mismatch: {path}")
    return raw


def main(image: Path, javascript: Path):
    raw = checked(image, IMAGE_SHA)
    source = checked(javascript, JS_SHA)
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    regions = []
    for label, start, end in CODE:
        body = raw[start:end]
        instructions = list(decoder.disasm(body, BASE + start))
        if sum(i.size for i in instructions) != len(body):
            raise ValueError(f"Incomplete decoding: {label}")
        regions.append(
            {
                "name": label,
                "start": hex(BASE + start),
                "end_exclusive": hex(BASE + end),
                "sha256": hashlib.sha256(body).hexdigest(),
                "instructions": [
                    {"address": hex(i.address), "bytes": i.bytes.hex(), "asm": f"{i.mnemonic} {i.op_str}"}
                    for i in instructions
                ],
            }
        )
    app = []
    for name, start, end in (
        ("send_command", 232509, 233642),
        ("download_file", 240849, 243257),
        ("stop_get_file", 244253, 244532),
    ):
        body = source[start:end]
        app.append(
            {
                "name": name,
                "start": start,
                "end_exclusive": end,
                "sha256": hashlib.sha256(body).hexdigest(),
                "source": body.decode(),
            }
        )
    print(
        json.dumps(
            {
                "scope": "Static selected code, official app; no execution, device I/O or cancel measurement",
                "image_sha256": IMAGE_SHA,
                "image_bytes": len(raw),
                "javascript_sha256": JS_SHA,
                "reply_tbb": {"address": "0x1000b142", "bytes": raw[0xB142:0xB14A].hex()},
                "literal_words": {
                    hex(BASE + offset): hex(struct.unpack_from("<I", raw, offset)[0])
                    for offset in (0xA1B8, 0xB3AC, 0xB7A0, 0xBA1C, 0x6BE8C)
                },
                "strings": {
                    hex(BASE + offset): raw[offset:].split(b"\0", 1)[0].decode()
                    for offset in (0xC22E9, 0xC23D4, 0xC2422)
                },
                "regions": regions,
                "app": app,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
