"""Fixed instruction-evidenced console state; never follows returned pointers."""

import json
from pathlib import Path

from .code_references import read_block
from .output import emit
from .range_readback import read_header, scoped_capture

GUARDS = (
    (0x10020628, "0b6801330b60014b1b681847c8180018"),
    (0x10026ED0, "04e00018"),
    (0x10026E6C, "30b5184d2c7e95b002460b461cb9f9f7"),
)
RAM_READS = ((0x1800E004, 4), (0x1800E01C, 2), (0x180018C8, 4))
READS = tuple((address, len(bytes.fromhex(value))) for address, value in GUARDS) + RAM_READS


def _read(capture: dict, address: int, length: int) -> bytes:
    command = f"dbg mdb {address:x} {length:x}"
    return read_block(scoped_capture(capture, command), address, length)


def verify_guards(capture: dict) -> None:
    read_header(capture)
    for address, expected in GUARDS:
        if _read(capture, address, len(bytes.fromhex(expected))).hex() != expected:
            raise ValueError(f"Printk code/literal changed at {address:#x}; RAM reads not applicable")


def inspect_state(capture: dict) -> dict:
    verify_guards(capture)
    device, flags, hook = (_read(capture, address, length) for address, length in RAM_READS)
    init, panic = flags
    return {
        "scope": "Separate non-atomic console RAM reads; no pointer following or Flash read",
        "device_pointer": hex(int.from_bytes(device, "little")),
        "init": init,
        "panic": panic,
        "character_hook": hex(int.from_bytes(hook, "little")),
        "branch_from_flags": "character_hook" if not init else "panic_fallback" if panic else "dma_buffer",
        "limits": ["Flags can change after capture", "No physical output or raw Flash data observed"],
    }


def main(capture: Path):
    """Revalidate fixed console-state evidence offline; no device connection."""
    emit(inspect_state(json.loads(capture.read_text())))
