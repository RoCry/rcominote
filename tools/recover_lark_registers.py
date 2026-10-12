#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["pyelftools==0.32", "typer>=0.16,<1"]
# ///
"""Recover partial LARK register layouts from pinned debugger DWARF; host-only."""

import hashlib
import json
import re
from pathlib import Path

import typer
from elftools.elf.elffile import ELFFile

HASHES = {
    "flash": "588386943adff3ea2ea8163fa5148b4686d5e3a568acd632028c46628bfb3584",
    "sd": "ccfb3ffc17ce11e853c6539ccc1810657709c48cb72f7d1ab775915874b7c4ee",
}
REGISTERS = {
    "CMUA_Type",
    "CMUD_Type",
    "GPIO_Type",
    "MEM_Type",
    "PMU_Type",
    "RMU_Type",
    "RTC_Type",
    "SPI0CACHE_Type",
    "SPI0_Type",
    "SPI1CACHE_Type",
    "SPI1_Type",
    "UART_Type",
}
CORE = {"SCB_Type", "NVIC_Type"}
SDK = "https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579"
LOADER = "action_technology_sdk/zephyr/tools/flash_loader/JLink/Devices/Actions/LARK"


def value(die, name):
    try:
        return die.attributes[name].value
    except KeyError as error:
        raise ValueError(f"Missing {name} at DIE{die.offset:#x}") from error


def identifier(raw: bytes) -> str:
    name = raw.decode("ascii")
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
        raise ValueError(f"Invalid C identifier {name!r}")
    return name


def scalar(die) -> dict:
    """Only fixed integer/array types, preserving explicit const/volatile."""
    qualifiers, dimensions = set(), []
    while die.tag != "DW_TAG_base_type":
        match die.tag:
            case "DW_TAG_typedef":
                pass
            case "DW_TAG_const_type":
                qualifiers.add("const")
            case "DW_TAG_volatile_type":
                qualifiers.add("volatile")
            case "DW_TAG_array_type":
                bounds = list(die.iter_children())
                if not bounds:
                    raise ValueError("Array has no bounds")
                for bound in bounds:
                    if bound.tag != "DW_TAG_subrange_type":
                        raise ValueError("Unexpected array child")
                    if bound.attributes.get("DW_AT_lower_bound") and value(bound, "DW_AT_lower_bound") != 0:
                        raise ValueError("Nonzero array lower bound")
                    count = value(bound, "DW_AT_upper_bound") + 1
                    if not isinstance(count, int) or count <= 0:
                        raise ValueError("Invalid array bound")
                    dimensions.append(count)
            case _:
                raise ValueError(f"Unsupported member type {die.tag} at {die.offset:#x}")
        die = die.get_DIE_from_attribute("DW_AT_type")
    size, encoding = value(die, "DW_AT_byte_size"), value(die, "DW_AT_encoding")
    if size not in (1, 2, 4) or encoding not in (5, 7, 8):
        raise ValueError(f"Unsupported integer size/encoding {size}/{encoding}")
    count = 1
    for dimension in dimensions:
        count *= dimension
    return {
        "c_type": f"{'u' if encoding in (7, 8) else ''}int{size * 8}_t",
        "qualifiers": sorted(qualifiers),
        "dimensions": dimensions,
        "element_bytes": size,
        "bytes": size * count,
    }


def layout(die) -> dict:
    while die.tag == "DW_TAG_typedef":
        die = die.get_DIE_from_attribute("DW_AT_type")
    size = value(die, "DW_AT_byte_size")
    if die.tag == "DW_TAG_enumeration_type":
        return {
            "kind": "enum",
            "bytes": size,
            "values": [
                {"name": identifier(value(child, "DW_AT_name")), "value": value(child, "DW_AT_const_value")}
                for child in die.iter_children()
                if child.tag == "DW_TAG_enumerator"
            ],
        }
    if die.tag != "DW_TAG_structure_type":
        raise ValueError(f"Expected struct, got {die.tag}")
    members, end = [], 0
    for child in die.iter_children():
        if child.tag != "DW_TAG_member" or any("bit_" in key for key in child.attributes):
            raise ValueError("Unsupported struct child/bitfield")
        field = scalar(child.get_DIE_from_attribute("DW_AT_type"))
        offset = value(child, "DW_AT_data_member_location")
        if not isinstance(offset, int) or offset != end:
            raise ValueError("Implicit padding/overlap unsupported; never invent reserved fields")
        members.append({"name": identifier(value(child, "DW_AT_name")), "offset": offset, **field})
        end = offset + field["bytes"]
    if not members or end != size:
        raise ValueError("Empty struct or implicit tail padding unsupported")
    return {"kind": "struct", "bytes": size, "members": members}


def extract(path: Path, role: str) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != HASHES[role]:
        raise ValueError(f"{role} ELF hash mismatch")
    types = {}
    with path.open("rb") as handle:
        elf = ELFFile(handle)
        if elf.elfclass != 32 or not elf.little_endian or elf["e_machine"] != "EM_ARM":
            raise ValueError("Requires ARM32 little-endian ELF")
        if not elf.has_dwarf_info():
            raise ValueError("Missing DWARF")
        dwarf = elf.get_dwarf_info()
        for cu in dwarf.iter_CUs():
            lines = dwarf.line_program_for_CU(cu)
            for die in cu.iter_DIEs():
                if die.tag != "DW_TAG_typedef" or "DW_AT_name" not in die.attributes:
                    continue
                name = value(die, "DW_AT_name").decode("ascii")
                if name not in REGISTERS | CORE | {"IRQn_Type"}:
                    continue
                recovered = layout(die)
                if lines is None or lines.header.version != 3:
                    raise ValueError("Requires pinned DWARF3 line table")
                source = lines.header.file_entry[value(die, "DW_AT_decl_file") - 1].name.decode("ascii")
                provenance = {
                    "typedef_die": hex(die.offset),
                    "cu_offset": hex(cu.cu_offset),
                    "source_file": source,
                    "source_line": value(die, "DW_AT_decl_line"),
                }
                if name in types:
                    if types[name]["layout"] != recovered:
                        raise ValueError(f"Conflicting {role} definitions for {name}")
                    types[name]["occurrences"].append(provenance)
                else:
                    types[name] = {"layout": recovered, "occurrences": [provenance]}
    if not types:
        raise ValueError("No expected types recovered")
    return {"sha256": digest, "url": f"{SDK}/{LOADER}/lark_{role}.elf", "types": types}


def render(types: dict) -> tuple[str, str]:
    header = [
        "/* Generated from pinned LARK loader DWARF; NOT a CoMi BSP.",
        " * Only field layouts and IRQ values. No MMIO bases, bit semantics, startup or pin map.",
        " * See docs/lark-register-recovery.md. Do not edit generated files. */",
        "#ifndef RCOMINOTE_LARK_REGISTER_LAYOUTS_H",
        "#define RCOMINOTE_LARK_REGISTER_LAYOUTS_H",
        "#include <stdint.h>",
        "",
    ]
    assertions = [
        "/* Host/compiler layout check only; no device code or I/O. */",
        '#include "lark_registers.h"',
        "#include <stddef.h>",
        "",
    ]
    for name in sorted(REGISTERS):
        recovered = types[name]["layout"]
        c_name = "rc_lark_" + name.removesuffix("_Type")
        header.extend([f"/* Source {name}, {recovered['bytes']} bytes. */", "typedef struct {"])
        assertions.append(f'_Static_assert(sizeof({c_name}) == {recovered["bytes"]}, "{c_name} size");')
        for member in recovered["members"]:
            declaration = " ".join([*member["qualifiers"], member["c_type"], member["name"]])
            declaration += "".join(f"[{dimension}]" for dimension in member["dimensions"])
            header.append(f"    {declaration}; /* +0x{member['offset']:x} */")
            assertions.append(
                f"_Static_assert(offsetof({c_name}, {member['name']}) == {member['offset']}, "
                f'"{c_name}.{member["name"]}");'
            )
        header.extend([f"}} {c_name};", ""])
    irq = types["IRQn_Type"]["layout"]
    header.extend(
        [f"/* Source IRQn_Type size={irq['bytes']}; values only, no enum ABI typedef. */", "enum {"]
    )
    header.extend(f"    RC_LARK_{item['name']} = {item['value']}," for item in irq["values"])
    header.extend(["};", "", "#endif", ""])
    return "\n".join(header), "\n".join(assertions) + "\n"


def main(flash: Path, sd: Path, out: Path):
    """Fresh output required; validate both full inputs before writing anything."""
    sources = {"flash": extract(flash, "flash"), "sd": extract(sd, "sd")}
    left, right = sources["flash"]["types"], sources["sd"]["types"]
    if set(left) != REGISTERS | CORE | {"IRQn_Type"}:
        raise ValueError("Flash type coverage changed")
    shared = sorted(set(left) & set(right))
    if len(shared) != 9:
        raise ValueError("Expected9 shared types")
    for name in shared:
        if left[name]["layout"] != right[name]["layout"]:
            raise ValueError(f"Cross-ELF layout mismatch: {name}")
    header, assertions = render(left)
    report = {
        "scope": "Partial reference definitions; not full lark.h, silicon confirmation or CoMi BSP",
        "sources": sources,
        "shared_equal_types": shared,
        "emitted_register_structs": sorted(REGISTERS),
        "irq_values": len(left["IRQn_Type"]["layout"]["values"]),
        "not_recovered": [
            "MMIO bases/macros",
            "register bit semantics",
            "startup/vector bindings",
            "clock/reset IDs",
            "CoMi wiring",
            "full ROM extent",
        ],
        "outputs": {
            "lark_registers.h": hashlib.sha256(header.encode()).hexdigest(),
            "lark_layout_assertions.c": hashlib.sha256(assertions.encode()).hexdigest(),
        },
    }
    out.mkdir(parents=True, exist_ok=False)
    for name, content in (
        ("lark_registers.h", header),
        ("lark_layout_assertions.c", assertions),
        ("layouts.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
    ):
        (out / name).write_text(content)
    print(f"Recovered12 register layouts, {report['irq_values']} IRQ values; {len(shared)} types agree")


if __name__ == "__main__":
    typer.run(main)
