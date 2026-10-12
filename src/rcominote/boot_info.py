"""Candidate boot-info decoding; SDK field layout remains separate from observed bytes."""

import struct


def inspect_boot_info(data: bytes, partitions: dict) -> dict:
    if len(data) != 64:
        raise ValueError("SDK boot-info candidate requires exactly 64 bytes")
    words = struct.unpack("<16I", data)
    fields = {
        name: hex(words[index])
        for name, index in (
            ("mbrec_phy_addr", 0),
            ("param_save_addr", 1),
            ("system_phy_addr", 2),
            ("reboot_reason", 3),
            ("nand_id_offs", 4),
            ("nand_id_len", 5),
            ("boot_flags", 6),
            ("param_phy_addr", 9),
            ("nor_offset", 10),
            ("code_len", 11),
            ("dvfs", 13),
        )
    }
    entries = partitions["entries"]
    return {
        "scope": "SDK-layout interpretation of boot SRAM candidate, not instruction-proven field access",
        "candidate_address": "0x1000000",
        "candidate_fields": fields,
        "param_save_matches_observed_acpt": words[1] == 0x01000040,
        "system_matches": [
            entry["index"]
            for entry in entries
            if entry["type"] == 2 and int(entry["file_offset"], 16) == words[2]
        ],
        "param_matches": [
            entry["index"]
            for entry in entries
            if entry["type"] == 6 and int(entry["file_offset"], 16) == words[9]
        ],
        "nor_offset_matches_system": words[10] == words[2],
        "limitations": [
            "No reset or alternate boot observed",
            "Reserved words not interpreted",
            "Matching values do not prove all SDK fields or board identity",
            "No cache register, physical flash bytes, or image header read",
        ],
    }
