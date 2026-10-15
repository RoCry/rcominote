"""One fixed RAM256 Actions stream at actually applied interval6; no storage I/O."""

import json
import re
import secrets
from pathlib import Path

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_control as RAM
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE
from rcominote.log_stream import Stream

PROFILE = "fixed-known-ram256-actions-applied6-v1"
NOR_PROFILE = "fixed-known-boot0-fread-f0-visibility-applied6-v1"
MDB = "dbg mdb 18000000 100"
VERSION = "kernel version"
MARKER = re.compile(r"afc[0-9a-f]{16}")
BUDGET = {
    "connections": 1,
    "ram_read_bytes": 256,
    "max_fillers": 8,
    "max_actions_writes": 13,
    "sd_writes": 0,
    "nor_writes": 0,
    "mmio_writes": 0,
    "ram_writes": 0,
    "new_files": 0,
    "active_seconds": 60,
    "monitor_seconds": 70,
    "cleanup_stop_seconds": 2,
    "new_raw_nor_coverage_bytes": 0,
}
FIELDS = (
    "profile",
    "marker",
    "marker_command",
    "mdb_command",
    "filler_command",
    "budget",
    "expected_before",
    "startup_policy",
    "status_event_policy",
)


def variant(plan):
    if plan.get("profile") == NOR_PROFILE:
        from rcominote.experiments import actions_fread_control

        return actions_fread_control
    if plan.get("profile") != PROFILE:
        raise ValueError("Unknown closed Actions measurement profile")
    return None


def fields(plan):
    return module.FIELDS if (module := variant(plan)) else FIELDS


def operation_id(plan):
    return "known-boot0-fread-f0" if variant(plan) else "known-ram256"


def state_reference(source):
    return {k: source[k] for k in ("directory", "profile", "ended_at", "latest_info", "verification")} | {
        "historical_report": source["references"]["report"],
        "historical_identity_only": True,
        "current_owned_file_verified": False,
    }


def validate_plan(plan):
    if module := variant(plan):
        return module.validate_plan(plan)
    if (
        plan.get("profile") != PROFILE
        or not isinstance(plan.get("marker"), str)
        or MARKER.fullmatch(plan["marker"]) is None
        or plan.get("marker_command") != "kernel uptime " + plan["marker"]
        or plan.get("mdb_command") != MDB
        or plan.get("filler_command") != VERSION
        or plan.get("budget") != BUDGET
        or any(type(v) is not int for v in plan["budget"].values())
        or plan.get("expected_before") != plan["state_reference"]["latest_info"]
        or plan["state_reference"]["profile"] != C.PREFILLED_PROFILE
        or plan["state_reference"].get("historical_identity_only") is not True
        or plan["state_reference"].get("current_owned_file_verified") is not False
        or plan.get("startup_policy") != C.startup.POLICY
        or plan.get("status_event_policy") != C.E.POLICY
        or plan["ram_oracle"].get("sha256") != RAM.RAM_SHA
        or plan["ram_oracle"].get("bytes") != 4096
        or plan.get("oracle_slice") != [0, 256]
        or type(plan.get("oracle_bytes")) is not int
        or plan["oracle_bytes"] != 256
    ):
        raise ValueError("Requires fixed bounded RAM256/afc marker/FAST-or-DEFAULT Actions control")
    A.verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    C.J.time_order(plan["state_reference"]["ended_at"], plan["planned_at"])


def prepare(image, parent):
    _baseline, state, source = C.parent_gate(parent, image)
    ram, proof = RAM.ram_source(image)
    marker = "afc" + secrets.token_hex(8)
    plan = {
        "profile": PROFILE,
        "marker": marker,
        "marker_command": "kernel uptime " + marker,
        "mdb_command": MDB,
        "filler_command": VERSION,
        "state_reference": state_reference(source),
        "expected_before": state,
        "ram_oracle": proof,
        "oracle_slice": [0, 256],
        "oracle_bytes": 256,
        "oracle_sha256": A.A.sha(ram[:256]),
        "budget": BUDGET.copy(),
        "startup_policy": C.startup.POLICY,
        "status_event_policy": C.E.POLICY,
        "planned_at": C.S.now(),
    }
    validate_plan(plan)
    return plan, ram[:256]


def source_gate(plan, image):
    if module := variant(plan):
        return module.source_gate(plan, image)
    validate_plan(plan)
    _baseline, state, source = C.parent_gate(Path(plan["state_reference"]["directory"]), image)
    ram, proof = RAM.ram_source(image)
    if (
        state_reference(source) != plan["state_reference"]
        or state != plan["expected_before"]
        or proof != plan["ram_oracle"]
        or A.A.sha(ram[:256]) != plan["oracle_sha256"]
    ):
        raise ValueError("Historical identity reference or independent RAM source changed")
    return ram[:256]


def packet(command):
    # Same no-newline console encoding as the original Linux short-read control.
    if not isinstance(command, str):
        raise TypeError("Fixed Actions command must be text")
    marker = command.removeprefix("kernel uptime ")
    if command not in (MDB, VERSION) and (
        not command.startswith("kernel uptime ") or MARKER.fullmatch(marker) is None
    ):
        raise ValueError("Only fixed MDB/version and declared afc marker commands permitted")
    raw = command.encode()
    payload = b"\x01" + len(raw).to_bytes(2, "little") + raw
    return b"\x1d\x10\x81" + len(payload).to_bytes(2, "little") + payload


def recipe(plan, fillers):
    if module := variant(plan):
        return module.recipe(plan, fillers)
    validate_plan(plan)
    if type(fillers) is not int or not 0 <= fillers <= 8:
        raise ValueError("At most eight fixed version fillers permitted")
    return [
        PREPARE,
        START,
        packet(plan["marker_command"]),
        packet(MDB),
        *([packet(VERSION)] * fillers),
        STOP,
    ]


def report(plan):
    validate_plan(plan)
    return {k: plan[k] for k in fields(plan)} | {
        "started_at": C.S.now(),
        "transport": {},
        "ok": False,
        "operation": {
            "operation_id": operation_id(plan),
            "phase": "not-started",
            "condition_applied": False,
            "fillers": 0,
        },
    }


def plan_gate(actual, plan, out):
    validate_plan(plan)
    if (
        actual["plan"]["file"] != "plan.json"
        or json.loads(C.J.check_reference(out, actual["plan"]).read_bytes()) != plan
        or any(actual.get(k) != plan[k] for k in fields(plan))
        or actual["operation"].get("operation_id") != operation_id(plan)
    ):
        raise ValueError("Actual Actions-fast control differs from immutable fixed plan")


def text_bytes(frames):
    result = bytearray()
    for frame in frames:
        if frame["command"] == 0xF0:
            raw = bytes.fromhex(frame["hex"])
            if frame.get("log_type") != 0 or raw[5] != 0:
                raise ValueError("Requires original text-type F0 bytes")
            result.extend(raw[8:])
    return bytes(result)


def echo_pattern(command):
    # F0 console echoes observed in Linux short-read; no newline normalization.
    return re.compile(
        rb"logsrv: cmd\(" + str(len(command)).encode() + rb"\) " + re.escape(command.encode()) + rb"\r\n\n"
    )


def parse(frames, plan, oracle, *, incomplete=False):
    if module := variant(plan):
        return module.parse(frames, plan, oracle, incomplete=incomplete)
    if len(oracle) != 256 or A.A.sha(oracle) != plan["oracle_sha256"]:
        raise ValueError("Independent complete RAM256 oracle changed")
    text = text_bytes(frames)
    markers = list(echo_pattern(plan["marker_command"]).finditer(text))
    if len(markers) > 1 or text.count(plan["marker"].encode()) > 1:
        raise ValueError("Fresh control marker duplicated")
    if not markers:
        if incomplete:
            return None
        raise ValueError("Missing fresh control marker in original F0 stream")
    origin = markers[0].end()
    echoes = list(echo_pattern(MDB).finditer(text, origin))
    if len(echoes) > 1:
        raise ValueError("Duplicate current MDB command; no chain selection")
    if not echoes:
        if incomplete:
            return None
        raise ValueError("Incomplete current RAM256 output/command echo")
    scope = text[origin : echoes[0].start()]
    start = scope.find(b"18000000: ")
    if start < 0 or scope[:start] != b"\r\n":
        raise ValueError("Current marker must directly precede canonical RAM rows")
    rows = scope[start:].split(b"\r\n")
    if len(rows) != 17 or rows[-1] != b"[logsrv][I][679]: ":
        raise ValueError("Requires sixteen contiguous current RAM rows then exact MDB echo")
    data = bytearray()
    for index, row in enumerate(rows[:16]):
        match = re.fullmatch(
            f"{0x18000000 + index * 16:08x}: ".encode()
            + rb"((?:[0-9a-f]{2} ){15}[0-9a-f]{2})    ([ -~]{16})",
            row,
        )
        if match is None:
            raise ValueError("RAM row address/order/hex/framing changed")
        chunk = bytes.fromhex(match[1].decode())
        if match[2] != bytes(b if 32 <= b <= 126 else 46 for b in chunk):
            raise ValueError("RAM row ASCII does not match original hex bytes")
        data.extend(chunk)
    if bytes(data) != oracle:
        raise ValueError("Current complete RAM256 differs from independent oracle")
    return {
        "verified": True,
        "bytes": 256,
        "sha256": A.A.sha(data),
        "marker_span": [markers[0].start(), origin],
        "rows_span": [origin + start, echoes[0].start() - len(b"[logsrv][I][679]: ")],
        "mdb_echo_span": [echoes[0].start(), echoes[0].end()],
        "rows": 16,
        "oracle_used_to_select_chain": False,
    }


def text_origin(actual, op, proof, tx, wire):
    # Bind original F0 payload bytes, not merely completion of a mixed frame.
    notes = [
        (i, bytes.fromhex(actual["att_packets"][i]["hex"])[3:])
        for i in A.E.indices(actual, op["actions_start"], op["actions_end"])
        if actual["att_packets"][i]["direction"] == "rx"
        and actual["att_packets"][i]["hex"].startswith("1b1800")
    ]
    raw = b"".join(value for _i, value in notes)
    if len(raw) > 65536 or len(notes) > 1024:
        raise ValueError("Original Actions evidence exceeds fixed stream bound")
    origins = [index for index, value in notes for _ in value]
    text_origins, offset = [], 0
    for frame in op["frames"]:
        value = bytes.fromhex(frame["hex"])
        if raw[offset : offset + len(value)] != value:
            raise ValueError("Original frame bytes do not cover notification stream")
        if frame["command"] == 0xF0:
            text_origins.extend(origins[offset + 8 : offset + len(value)])
        offset += len(value)
    if offset != len(raw):
        raise ValueError("Unconsumed original notification bytes")
    result = {}
    target_spans = (
        ("status_span", "rows_span", "producer_span", "target_span")
        if "producer_span" in proof
        else ("rows_span", "mdb_echo_span")
    )
    for key, command in [("marker_span", tx[2]), *((key, tx[3]) for key in target_spans)]:
        first, last = proof[key]
        selected = text_origins[first:last]
        if not selected or any(
            wire[i][0] <= wire[command][1] or wire[i][2] < wire[command][2] for i in selected
        ):
            raise ValueError("Current marker/RAM bytes precede their actual command on wire")
        result[key] = {
            "first_att_index": min(selected),
            "last_att_index": max(selected),
            "command_att_index": command,
        }
    return result


def validate(actual, out, plan, oracle, *, archived=False):
    if archived and actual.get("ok") is not True:
        raise ValueError("Original failed Actions-fast capture cannot be promoted")
    plan_gate(actual, plan, out)
    A.common.no_errors(actual)
    op = actual["operation"]
    expected = recipe(plan, op["fillers"])
    classification = actual["startup_classification"]
    count = 3 if classification["mode"] == "default" else 2
    observed, wire, events = A.envelope(actual, out, count)
    startup = observed["transactions"][0]
    if (
        classification != C.startup.classify(startup, policy=plan["startup_policy"])
        or actual["startup_settlement"] != startup
    ):
        raise ValueError("Startup classification differs from complete observed FAST/DEFAULT")
    A.E.bridge(actual, actual["before_span"][1], op["actions_start"])
    A.A.action_frames(actual, op, expected=expected)
    if (
        op.get("condition_applied") is not True
        or op.get("sd_write_attempted") is not False
        or op.get("live_complete") is not True
        or op.get("ack_count") != len(expected)
        or op.get("end_received") is not True
        or op.get("pending_hex") != ""
        or not op["frames"]
        or op["frames"][-1]["command"] != 0xF1
    ):
        raise ValueError("Original fixed readonly Actions condition/session incomplete")
    if actual["predecessor_state_verification"] != A.verify_state(
        plan["expected_before"], actual["before"], sd_write=False
    ):
        raise ValueError("Initial actual identity differs from admitted parent")
    rows = [
        {"index": i, **actual["att_packets"][i]}
        for i in A.E.indices(actual, op["actions_start"], op["actions_end"])
    ]
    tx = [row["index"] for row in rows if row["direction"] == "tx"]
    stream, ack2 = Stream(), None
    for row in rows:
        raw = bytes.fromhex(row["hex"])
        if row["direction"] == "rx" and raw[:3] == b"\x1b\x18\0":
            prior = stream.acks
            stream.feed(raw[3:])
            if prior < 2 <= stream.acks:
                ack2 = row["index"]
    normal = observed["transactions"][-1]
    A.common.transaction(normal, origin="host", parameters=(6, 6, 0, 500))
    fast = observed["transactions"][-2]
    A.common.transaction(fast, origin="remote", parameters=(6, 12, 0, 500))
    if op.get("activity_fast") != (observed["transactions"][1:2] if count == 3 else []):
        raise ValueError("Stored activity FAST differs from actual complete ledger")
    if count == 3 and not startup["update"]["record"] < fast["remote_request"]["records"][0]:
        raise ValueError("Activity FAST precedes original DEFAULT settlement")
    if (
        op["normalization"] != normal
        or ack2 is None
        or not startup["update"]["record"] < wire[tx[0]][0]
        or not max(wire[ack2][1], fast["update"]["record"])
        < normal["request"]["record"]
        < normal["update"]["record"]
        < wire[tx[2]][0]
        or not max(wire[ack2][2], fast["update"]["timestamp_us"])
        <= op["normalization_requested_us"]
        <= normal["request"]["timestamp_us"]
        or not normal["update"]["timestamp_us"] < wire[tx[2]][2]
        or op["burst_start"] != tx[2]
    ):
        raise ValueError("Applied6 must follow START ACK/settledFAST and precede fresh marker/MDB")
    proof = parse(op["frames"], plan, oracle)
    if proof != op["content_verification"]:
        raise ValueError("Original contiguous RAM content proof changed")
    origin = text_origin(actual, op, proof, tx, wire)
    A.final_identity(
        actual, wire, {"state": actual["before"], "boundary": op["actions_end"], "cursor": count}, count
    )
    C.J.time_order(
        plan["planned_at"], actual["started_at"], op["started_at"], op["ended_at"], actual["ended_at"]
    )
    result = {
        "verified": True,
        "connections": 1,
        "bytes": len(oracle),
        "content": proof,
        "text_origin": origin,
        "acks": len(expected),
        "fillers": op["fillers"],
        "parameter_transactions": count,
        "applied_interval": 6,
        "latency": 0,
        "timeout": 500,
        "requested_ce_hints": [1, 1],
        "sd_writes": 0,
        "nor_writes": 0,
        "new_raw_nor_coverage_bytes": 0,
        "status_events": events,
    }
    if archived and actual.get("verification") != result:
        raise ValueError("Original complete Actions-fast proof changed")
    return result


def replay(out, image):
    actual = json.loads((out / "report.json").read_bytes())
    if actual.get("ok") is not True:
        raise ValueError("Original failed Actions-fast control cannot be promoted")
    plan = json.loads(C.J.check_reference(out, actual["plan"]).read_bytes())
    return validate(actual, out, plan, source_gate(plan, image), archived=True)
