#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Read the pinned official ATS3085C socket symbol and its typed wire endpoints.

KiCad ac8691a64afa0a78d04f0073e82896bcdec82657 PADS v13 schema/mapper.
Declarations in this reference design do not identify CoMi wiring or silicon.
Stdout contains JSON only; no vendor program or device operation.
"""

import hashlib
import json
import struct
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "artifacts/actions-official-20261013"
META_SHA = "9ea7e8ff78a548379b9c2bea0440039f98af580015f6c38f78155a3fe2b91d92"
SCH_SHA = "078718b5601da3f33e8d5f1a75f147fa1f913d0e716e1c395a49443dc279a68a"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    metadata = (BASE / "hardware/schematic-records.json").read_bytes()
    if sha(metadata) != META_SHA:
        raise ValueError("Pinned schematic directory metadata changed")
    document = json.loads(metadata)
    raw = (BASE / document["source"]).read_bytes()
    if sha(raw) != SCH_SHA or raw[:6] != bytes.fromhex("00fe0d000000"):
        raise ValueError("Requires exact official PADS Logic v13 schematic")

    def read(offset: int, size: int) -> bytes:
        if not 0 <= offset <= len(raw) - size:
            raise ValueError(f"Record outside schematic: offset={offset}, size={size}")
        return raw[offset : offset + size]

    def unpack(offset: int, fmt: str) -> tuple:
        return struct.unpack("<" + fmt, read(offset, struct.calcsize("<" + fmt)))

    def word(offset: int) -> int:
        return unpack(offset, "H")[0]

    def dword(offset: int) -> int:
        return unpack(offset, "I")[0]

    def string(offset: int, size: int) -> str:
        return read(offset, size).split(b"\0", 1)[0].decode("ascii")

    def evidence(offset: int, size: int) -> dict:
        data = read(offset, size)
        return {"offset": offset, "bytes": size, "sha256": sha(data), "hex": data.hex()}

    sheet = document["sheets"][2]
    pools = {entry["controller"]: entry for entry in sheet["pools"]}
    for controller, width in {7: 108, 8: 26, 9: 76, 10: 12, 11: 24, 15: 136, 16: 12, 21: 40, 22: 8}.items():
        if pools[controller]["bytes"] != pools[controller]["count"] * width:
            raise ValueError(f"Unexpected controller {controller} record width")
    placement = next(item for item in sheet["placements"] if item["reference"] == "U2")
    offset = placement["offset"]
    x, y, rotation, mirror = unpack(offset + 32, "4H")
    if rotation != 0 or mirror != 0:
        raise ValueError("This bounded decoder requires the unrotated, unmirrored U2 instance")
    part = pools[9]["offset"] + word(offset + 66) * 76
    decal = pools[7]["offset"] + word(offset + 68) * 108
    if string(part, 44) != "ATS3085C_SOCKET" or string(decal, 38) != "ATS3085C_SOCKET":
        raise ValueError("U2 no longer resolves to ATS3085C_SOCKET")
    gate = pools[10]["offset"] + dword(part + 44) * 12
    count = word(offset + 76)
    if word(offset + 74) != 0 or count != 69 or word(gate + 8) != count or raw[decal + 42] != count:
        raise ValueError("U2 must have exactly one selected 69-pin gate")
    if word(gate) != word(offset + 68):
        raise ValueError("Gate and placement resolve to different used decals")
    pin_base, name_base = dword(part + 48), dword(part + 60)
    terminal_base, placed_base = word(decal + 44), dword(offset + 20)
    if terminal_base + count > pools[8]["count"] or pin_base + count > pools[11]["count"]:
        raise ValueError("U2 pin slice leaves its controller")
    pins, positions = [], {}
    for index in range(count):
        pin = pools[11]["offset"] + (pin_base + index) * 24
        terminal = pools[8]["offset"] + (terminal_base + index) * 26
        placed = pools[16]["offset"] + (placed_base + index) * 12
        if word(placed + 4) != index:
            raise ValueError("Placed pin ordinal differs from its gate order")
        name_offset = name_base + dword(pin)
        if not 0 <= name_offset < pools[14]["bytes"]:
            raise ValueError("U2 pin name leaves its string heap")
        name = string(pools[14]["offset"] + name_offset, pools[14]["bytes"] - name_offset)
        dx, dy = unpack(terminal + 2, "2h")
        # KiCad decodeCoordinate/decodeTerminalCoordinate/transformedPinPosition.
        position = (4 * (x + dx) - 198144, 4 * (y + dy) - 198144)
        if position in positions:
            raise ValueError("Ambiguous U2 pin coordinate")
        positions[position] = index
        pins.append(
            {
                "number": string(pin + 4, 16),
                "name": name,
                "position_mapper_units": list(position),
                "part_pin": evidence(pin, 24),
                "symbol_terminal": evidence(terminal, 26),
                "placed_pin": evidence(placed, 12),
                "connections": [],
            }
        )
    if {pin["number"] for pin in pins} != {str(i) for i in range(1, 70)}:
        raise ValueError("Declared U2 physical pin numbers are not exactly 1..69")
    nets = {item["record"]: item["name"] for item in document["global_nets"]}
    for index in range(pools[21]["count"]):
        connection = pools[21]["offset"] + index * 40
        start = dword(connection + 4)
        end = dword(connection + 44) if index + 1 < pools[21]["count"] else pools[22]["count"]
        if not 0 <= start < end <= pools[22]["count"] or end - start < 2:
            raise ValueError("Connection lacks bounded first/last endpoint vertices")
        for field, vertex_index in ((12, start), (14, end - 1)):
            if word(connection + field) != placement["record"]:
                continue
            vertex = pools[22]["offset"] + vertex_index * 8
            vx, vy = unpack(vertex + 4, "2H")
            position = (vx * 4 - 198144, vy * 4 - 198144)
            if position not in positions:
                raise ValueError("Typed U2 connection endpoint has no matching symbol pin")
            pins[positions[position]]["connections"].append(
                {
                    "net": nets[dword(connection + 8)],
                    "wire": evidence(connection, 40),
                    "endpoint_vertex": evidence(vertex, 8),
                }
            )
    if any(len(pin["connections"]) != 1 for pin in pins):
        raise ValueError("Expected exactly one typed wire endpoint for each of 69 U2 pins")
    print(
        json.dumps(
            {
                "source": document["source"],
                "source_sha256": SCH_SHA,
                "directory_metadata_sha256": META_SHA,
                "schema_commit": "ac8691a64afa0a78d04f0073e82896bcdec82657",
                "schema_sha256": "5fbf89c94d8b4cd799425e7acef8a0f946b277a16251e82ed858a7105f02faa9",
                "mapper_sha256": "c14ad99d8c57ec6379a55bedbaa88ffc5ec7b00d1b80c4d6f2c55ddeb7edd95f",
                "scope": "Official U2 socket symbol declarations and typed schematic wires only; no CoMi/silicon/copper/ROM-exit claim",
                "placement": evidence(offset, 136),
                "part_type": evidence(part, 76),
                "used_decal": evidence(decal, 108),
                "gate": evidence(gate, 12),
                "pins": sorted(pins, key=lambda item: int(item["number"])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
