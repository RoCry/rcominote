#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["capstone==5.0.6", "typer>=0.16,<1"]
# ///
"""Extract actual SD pin/power/width instruction evidence offline, never access a device."""

import hashlib
import json
import struct
from pathlib import Path

import typer
from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs

SHA = "ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f"
WINDOWS = (
    ("mmc1_descriptor", 0x100BA100, 0x100BA118, False),
    ("mmc1_config_and_api", 0x100BC3BC, 0x100BC3F0, False),
    ("mmc_init", 0x10033DB8, 0x10033EFA, True),
    ("mmc_init_literals", 0x10033EFC, 0x10033F40, False),
    ("bus_width_setter", 0x100A4F3C, 0x100A4F6C, True),
    ("capability_getter", 0x100A4F6C, 0x100A4F72, True),
    ("scan_initial_width", 0x10032E4C, 0x10032E84, True),
    ("scan_clock_and_width_negotiation", 0x100330DC, 0x10033146, True),
    ("scan_mmc_clock_branch", 0x100331B2, 0x100331B8, True),
    ("scan_literals", 0x100331B8, 0x100331E0, False),
    ("clock_function", 0x10033C4C, 0x10033C84, True),
    ("clock_thresholds", 0x10033C84, 0x10033C90, False),
    ("three_pin_table", 0x100BBF14, 0x100BBF2C, False),
    ("sd_descriptor", 0x100BA160, 0x100BA178, False),
    ("sd_config", 0x100BC398, 0x100BC3A0, False),
    ("board_sd_pinmux_info", 0x1002DCFC, 0x1002DD06, True),
    ("board_sd_pinmux_literal", 0x1002DD08, 0x1002DD0C, False),
    ("sd_storage_init", 0x10033838, 0x10033982, True),
    ("sd_storage_init_literals", 0x10033984, 0x100339B4, False),
    ("sd_pins_to_output_low", 0x10032B24, 0x10032BD8, True),
    ("gpio_config_and_write_wrappers", 0x100A4E90, 0x100A4EC8, True),
    ("mmc_irq_callback", 0x100A4FA6, 0x100A4FBC, True),
)


def inspect(source: Path) -> dict:
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA:
        raise ValueError("Wrong actual CoMi system SHA256")
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    windows = []
    for name, start, end, code in WINDOWS:
        raw = data[start - 0x10000000 : end - 0x10000000]
        row = {
            "name": name,
            "start": f"0x{start:08x}",
            "end_exclusive": f"0x{end:08x}",
            "hex": raw.hex(),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        if code:
            decoded = list(decoder.disasm(raw, start))
            if sum(i.size for i in decoded) != len(raw):
                raise ValueError(f"Incomplete code window: {name}")
            row["instructions"] = [
                {"address": f"0x{i.address:08x}", "instruction": f"{i.mnemonic} {i.op_str}"} for i in decoded
            ]
        else:
            row["u32_le"] = [f"0x{x:08x}" for x in struct.unpack(f"<{len(raw) // 4}I", raw)]
        windows.append(row)
    return {
        "source": str(source),
        "size": len(data),
        "sha256": SHA,
        "method": "Offline Capstone5.0.6; code windows exclude pools; no runtime/MMIO read",
        "windows": windows,
    }


def main(source: Path):
    print(json.dumps(inspect(source), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    typer.run(main)
