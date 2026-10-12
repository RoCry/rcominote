"""Interpret the captured FW010004 TBB dispatcher; no device access."""

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

BASE = 0x1000B3B4
TABLE = 0x1000B410
TABLE_END = 0x1000B44A
DEFAULT = 0x1000B544


def inspect_dispatch(code: bytes) -> dict:
    """Require observed bounds/TBB encoding before interpreting inline table bytes."""
    if len(code) != 0x1A4:
        raise ValueError("Expected complete 420-byte dispatcher span")
    if code[0x50:0x5C].hex() != "7b1e392b00f29c80dfe803f0":
        raise ValueError("Dispatcher bounds/TBB instructions changed")
    table = code[TABLE - BASE : TABLE_END - BASE]
    cases = []
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    for command, offset in enumerate(table, start=1):
        target = TABLE + 2 * offset
        if not TABLE_END <= target <= DEFAULT or target % 2:
            raise ValueError(f"Command {command:#x} points outside captured case code: {target:#x}")
        row = {"command": hex(command), "case_address": hex(target), "default": target == DEFAULT}
        if target != DEFAULT:
            data = code[target - BASE :]
            if data.startswith(bytes.fromhex("21463046")):
                row["arguments"] = "command_and_length_and_payload, incoming_u8_length"
            elif data.startswith(bytes.fromhex("a11ec9b2b01c")):
                row["arguments"] = "payload, u8(incoming_length - 2)"
            else:
                raise ValueError(f"Unknown case argument setup at {target:#x}")
            calls = []
            for ins in decoder.disasm(data, target):
                if ins.mnemonic == "bl":
                    calls.append(ins.op_str.removeprefix("#"))
                if ins.mnemonic == "b":
                    row["return_branch"] = ins.op_str.removeprefix("#")
                    break
            if len(calls) != 1 or "return_branch" not in row:
                raise ValueError(f"Expected one direct call and return branch at {target:#x}")
            row["callee"] = calls[0]
        cases.append(row)
    return {
        "table_address": hex(TABLE),
        "table_hex": table.hex(),
        "index": "u32(command - 1), unsigned range <= 0x39",
        "target": "0x1000b410 + 2 * table[index]",
        "outside_range": hex(DEFAULT),
        "cases": cases,
        "limitations": [
            "Reachable only when preceding call at 0x1000b3d8 returns a value other than 0x54",
            "Callee addresses do not establish command semantics or firmware access",
            "No unrecognized command was sent to the device",
        ],
    }
