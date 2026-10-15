#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Inspect pinned official ATS3085C test-board schematic; never execute firmware.

Schema: KiCad ac8691a64afa0a78d04f0073e82896bcdec82657,
eeschema/sch_io/pads/pads_sch_binary_parser.cpp and pads_sch_binary.ksy.
Only selected one-gate symbols and their explicit typed wire endpoints are decoded.
Recovered reference-board pin numbers do not establish CoMi physical wiring.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

SHA = "078718b5601da3f33e8d5f1a75f147fa1f913d0e716e1c395a49443dc279a68a"
SELECTED = {
    "U2",
    "UN1",
    "JU2",
    "J11",
    "J27",
    "J1",
    "J2",
    "J4",
    "J5",
    "RK9",
    "RK10",
    "KK1",
    "KK2",
    "KK3",
    "KK4",
    "KK5",
    "RN7",
    "RK8",
}


def decode(source: Path) -> dict:
    b = source.read_bytes()
    if hashlib.sha256(b).hexdigest() != SHA:
        raise ValueError(f"source SHA256 mismatch: expected {SHA}")

    def unpack(off: int, fmt: str) -> tuple:
        if not 0 <= off <= len(b) - struct.calcsize("<" + fmt):
            raise ValueError(f"typed read outside source: offset={off:#x}, format={fmt}")
        return struct.unpack_from("<" + fmt, b, off)

    def read(off: int, fmt: str = "I") -> int:
        return unpack(off=off, fmt=fmt)[0]

    def text(off: int, size: int) -> str:
        if not 0 <= off <= len(b) - size or size <= 0:
            raise ValueError(f"ASCII field outside source: offset={off:#x}, bytes={size}")
        raw = b[off : off + size]
        if b"\x00" not in raw:
            raise ValueError(f"unterminated ASCII field at {off:#x}")
        return raw.split(b"\x00", 1)[0].decode("ascii")

    def evidence(off: int, size: int) -> dict:
        if not 0 <= off <= len(b) - size or size <= 0:
            raise ValueError(f"evidence range outside source: offset={off:#x}, bytes={size}")
        raw = b[off : off + size]
        return {"offset": off, "bytes": size, "raw_hex": raw.hex(), "sha256": hashlib.sha256(raw).hexdigest()}

    def point(off: int) -> tuple[int, int]:
        return (read(off, "H") * 4 - 198144, read(off + 2, "H") * 4 - 198144)

    def transform(off: int, terminal: int) -> tuple[int, int]:
        x, y = (read(terminal + 2, "h") * 4, read(terminal + 4, "h") * 4)
        angle, mirror = (read(off + 36, "H"), read(off + 38, "H"))
        if not (angle in [0, 900, 1800, 2700] and mirror < 4):
            raise ValueError("invalid schematic record: angle in [0, 900, 1800, 2700] and mirror < 4")
        if angle == 900:
            x, y = (-y, x)
        elif angle == 1800:
            x, y = (-x, -y)
        elif angle == 2700:
            x, y = (y, -x)
        if mirror & 1:
            x = -x
        if mirror & 2:
            y = -y
        px, py = point(off + 32)
        return (px + x, py + y)

    outer = []
    pos = 596
    if not b[:6] == bytes.fromhex("00fe0d000000"):
        raise ValueError("expected PADS Logic v13 header")
    if not b[-42:-4] == b"{F4997D70-AF8A-11D0-A373-000000000000}":
        raise ValueError("invalid schematic footer")
    if not read(592) == 36:
        raise ValueError("invalid schematic record: read(592) == 36")
    for i in range(20):
        allocated, count, used = unpack(off=32 + i * 28 + 4, fmt="III")
        if not (used <= allocated and (count != 0 or used == 0)):
            raise ValueError("invalid schematic record: used <= allocated and (count != 0 or used == 0)")
        offset = None if i == 0 else pos
        outer.append({"controller": i, "count": count, "bytes": used, "offset": offset})
        if i:
            pos += used
            if not pos <= len(b) - 42:
                raise ValueError("invalid schematic record: pos <= len(b) - 42")
    pool = outer[8]
    if not outer[4]["bytes"] == outer[4]["count"] * 2:
        raise ValueError("invalid schematic record: outer[4]['bytes'] == outer[4]['count'] * 2")
    if not pool["bytes"] == pool["count"] * 88:
        raise ValueError("invalid schematic record: pool['bytes'] == pool['count'] * 88")
    nets = []
    for i in range(pool["count"]):
        offset = pool["offset"] + i * 88
        if not (read(offset + 20, "H") == 0 and read(offset + 80) == 4294967295):
            raise ValueError(
                "invalid schematic record: read(offset + 20, 'H') == 0 and read(offset + 80) == 4294967295"
            )
        membership_start, _alias_offset = unpack(off=offset + 4, fmt="II")
        membership_count, aliases = unpack(off=offset + 16, fmt="HH")
        if not (membership_count == 65535 or membership_start + membership_count <= outer[4]["count"]):
            raise ValueError(
                "invalid schematic record: membership_count == 65535 or membership_start + membership_count <= outer[4]['count']"
            )
        nets.append(
            {
                "record": i,
                "offset": offset,
                "name_offset": offset + 24,
                "name": text(offset + 24, 56),
                "membership_count": membership_count,
                "tombstone": membership_count == 65535,
                "alias_count": aliases,
            }
        )
    sheets = []
    for sheet in range(outer[3]["count"]):
        start = pos
        if unpack(off=start, fmt="III") != (20, 5, 20):
            raise ValueError("invalid schematic record: struct.unpack_from('<III', b, start) == (20, 5, 20)")
        if not read(start + 16) == 0:
            raise ValueError("invalid schematic record: read(start + 16) == 0")
        pos += 20 + 24 * 28
        pools = []
        for i in range(23):
            allocated, count, used = unpack(off=start + 20 + i * 28 + 8, fmt="III")
            if not (used <= allocated and (count != 0 or used == 0)):
                raise ValueError("invalid schematic record: used <= allocated and (count != 0 or used == 0)")
            pools.append({"controller": i + 1, "count": count, "bytes": used, "offset": pos})
            pos += used
            if not pos <= len(b) - 42:
                raise ValueError("invalid schematic record: pos <= len(b) - 42")
        placements = []
        pool = pools[14]
        if not pool["bytes"] == pool["count"] * 136:
            raise ValueError("invalid schematic record: pool['bytes'] == pool['count'] * 136")
        for i in range(pool["count"]):
            off = pool["offset"] + i * 136
            placements.append(
                {
                    "record": i,
                    "offset": off,
                    "reference_offset": off + 94,
                    "reference": text(off + 94, 40),
                    "pin_count": read(off + 76, "H"),
                }
            )
        sheets.append(
            {
                "sheet_index": sheet,
                "offset": start,
                "bytes": pos - start,
                "pools": pools,
                "placements": placements,
            }
        )
    if not read(len(b) - 4) == pos:
        raise ValueError("invalid schematic record: read(len(b) - 4) == pos")
    j = {"sheets": sheets, "global_nets": nets, "outer_pools": outer}
    symbols = []
    for sheet in j["sheets"]:
        pools = sheet["pools"]

        def record(index: int, number: int, stride: int, pools: list[dict] = pools) -> int:
            pool = pools[index]
            if not pool["bytes"] == pool["count"] * stride:
                raise ValueError("invalid schematic record: pool['bytes'] == pool['count'] * stride")
            if not 0 <= number < pool["count"]:
                raise ValueError("invalid schematic record: 0 <= number < pool['count']")
            return pool["offset"] + number * stride

        selected = {}
        for placement in sheet["placements"]:
            if placement["reference"] not in SELECTED:
                continue
            off = placement["offset"]
            part = record(8, read(off + 66, "H"), 76)
            if not (read(part + 68, "H") == 1 and read(off + 74, "H") == 0):
                raise ValueError("selected symbol must have one gate")
            gate = record(9, read(part + 44), 12)
            decal_handle = read(off + 68, "H")
            if not read(gate, "H") == decal_handle:
                raise ValueError("invalid schematic record: read(gate, 'H') == decal_handle")
            decal = record(6, decal_handle, 108)
            definition = record(2, read(decal + 48), 80)
            if not text(decal, 40) == text(definition, 38):
                raise ValueError("invalid schematic record: text(decal, 40) == text(definition, 38)")
            count = read(off + 76, "H")
            if not count == read(gate + 8, "H") == read(decal + 42, "B"):
                raise ValueError(
                    "invalid schematic record: count == read(gate + 8, 'H') == read(decal + 42, 'B')"
                )
            pin_start, terminal_start = (read(part + 48), read(decal + 44, "H"))
            name_base = read(part + 60)
            symbol = {
                "sheet_index": sheet["sheet_index"],
                "placement_record": placement["record"],
                "reference": placement["reference"],
                "part_type": text(part, 44),
                "placement": evidence(off, 136),
                "part_type_record": evidence(part, 76),
                "gate": evidence(gate, 12),
                "used_decal": evidence(decal, 108),
                "definition": evidence(definition, 80),
                "pins": [],
            }
            for k in range(count):
                pin = record(10, pin_start + k, 24)
                terminal = record(7, terminal_start + k, 26)
                placed = record(15, read(off + 20) + k, 12)
                if not read(placed + 4, "H") == k:
                    raise ValueError("invalid schematic record: read(placed + 4, 'H') == k")
                name_offset = read(pin)
                name, name_ev = ("", None)
                if name_offset != 4294967295:
                    heap = pools[13]
                    relative = name_base + name_offset
                    if not relative < heap["bytes"]:
                        raise ValueError("invalid schematic record: relative < heap['bytes']")
                    absolute = heap["offset"] + relative
                    name = text(absolute, heap["bytes"] - relative)
                    name_ev = evidence(absolute, len(name.encode()) + 1)
                symbol["pins"].append(
                    {
                        "ordinal": k,
                        "number": text(pin + 4, 16),
                        "name": name,
                        "position": transform(off, terminal),
                        "part_pin": evidence(pin, 24),
                        "terminal": evidence(terminal, 26),
                        "placed_pin": evidence(placed, 12),
                        "pin_name": name_ev,
                        "connections": [],
                    }
                )
            if not len({tuple(p["position"]) for p in symbol["pins"]}) == count:
                raise ValueError(
                    "invalid schematic record: len({tuple(p['position']) for p in symbol['pins']}) == count"
                )
            selected[placement["record"]] = symbol
            symbols.append(symbol)
        starts = []
        for idx, stride in [(17, 44), (20, 40)]:
            for k in range(pools[idx]["count"]):
                off = record(idx, k, stride)
                starts.append((read(off + 4), idx, k))
        starts.sort()
        if starts and starts[0][0] != 0:
            raise ValueError("connectivity vertex ownership must begin at record 0")
        ends = {}
        for n, (start, idx, k) in enumerate(starts):
            end = starts[n + 1][0] if n + 1 < len(starts) else pools[21]["count"]
            if not start < end <= pools[21]["count"]:
                raise ValueError("invalid schematic record: start < end <= pools[21]['count']")
            ends[idx, k] = (start, end)
        for k in range(pools[20]["count"]):
            off = record(20, k, 40)
            net_handle = read(off + 8)
            if not net_handle < len(j["global_nets"]):
                raise ValueError("invalid schematic record: net_handle < len(j['global_nets'])")
            net = j["global_nets"][net_handle]
            if net["tombstone"]:
                raise ValueError("invalid schematic record: not net['tombstone']")
            membership = read(net["offset"] + 4)
            outer = j["outer_pools"][4]
            memberships = [
                read(outer["offset"] + (membership + n) * 2, "H") for n in range(net["membership_count"])
            ]
            if not sheet["sheet_index"] in memberships:
                raise ValueError("invalid schematic record: sheet['sheet_index'] in memberships")
            marker = read(off + 34, "H")
            if not (2 <= marker >> 8 <= 6 and marker & 255 in [0, 252, 253]):
                raise ValueError(
                    "invalid schematic record: 2 <= marker >> 8 <= 6 and marker & 255 in [0, 252, 253]"
                )
            start, end = ends[20, k]
            if not end - start >= 2:
                raise ValueError("invalid schematic record: end - start >= 2")
            for endpoint, vertex in [(0, start), (1, end - 1)]:
                handle = read(off + 12 + endpoint * 2, "H")
                if handle >> 12 != 0 or handle & 4095 not in selected:
                    continue
                symbol = selected[handle & 4095]
                vertex_off = record(21, vertex, 8)
                if not read(vertex_off) == 0:
                    raise ValueError("invalid schematic record: read(vertex_off) == 0")
                vertex_point = point(vertex_off + 4)
                matches = [pin for pin in symbol["pins"] if tuple(pin["position"]) == vertex_point]
                if not len(matches) == 1:
                    raise ValueError((symbol["reference"], k, endpoint, vertex_point))
                matches[0]["connections"].append(
                    {
                        "record": k,
                        "endpoint_index": endpoint,
                        "net_record": net_handle,
                        "net_name": net["name"],
                        "connection": evidence(off, 40),
                        "vertex": evidence(vertex_off, 8),
                        "global_net": evidence(net["offset"], 88),
                    }
                )
    for symbol in symbols:
        for pin in symbol["pins"]:
            if not len({c["net_record"] for c in pin["connections"]}) <= 1:
                raise ValueError(
                    "invalid schematic record: len({c['net_record'] for c in pin['connections']}) <= 1"
                )
        if symbol["reference"] == "U2":
            if not sorted(int(pin["number"]) for pin in symbol["pins"]) == list(range(1, 70)):
                raise ValueError(
                    "invalid schematic record: sorted((int(pin['number']) for pin in symbol['pins'])) == list(range(1, 70))"
                )
            if not all(pin["connections"] for pin in symbol["pins"]):
                raise ValueError(
                    "invalid schematic record: all((pin['connections'] for pin in symbol['pins']))"
                )
    return {
        "source": str(source.resolve()),
        "source_sha256": SHA,
        "schema_commit": "ac8691a64afa0a78d04f0073e82896bcdec82657",
        "coverage": "Pinned ATS3085C official test-board PADS Logic v13 only: bounded directory, selected one-gate symbols, explicit wire endpoints matched to transformed numbered/named pins; raw evidence retained. No generic CAD support.",
        "symbols": symbols,
        "limitation": "Selected one-gate symbols only. Symbol pin numbers are schematic observations. CoMi physical package/contact mapping remains unverified; official board circuit is not a CoMi pinout. No runtime function or reset/ADFU behavior established.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_sch", type=Path, help="Original pinned official production-test-board .sch")
    parser.add_argument("new_output_json", type=Path, help="New evidence JSON; existing path is refused")
    args = parser.parse_args()
    if args.new_output_json.exists():
        parser.error(f"output already exists: {args.new_output_json}")
    try:
        result = decode(source=args.source_sch)
        with args.new_output_json.open("x", encoding="utf-8") as out:
            out.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, UnicodeError, struct.error) as error:
        parser.exit(status=1, message=f"pinmap inspection failed: {error}\n")
    print(f"Wrote {len(result['symbols'])} selected reference-board symbols to {args.new_output_json}")


if __name__ == "__main__":
    main()
