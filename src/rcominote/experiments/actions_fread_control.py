"""Closed BOOT0 printk-to-Actions visibility control; never changes output routing.

ACK/status alone do not establish a successful NOR read. Only the complete fresh
512-byte chain can pass; missing printk output remains an inconclusive failure.
"""

import secrets
from pathlib import Path

from rcominote.experiments import actions_fast_control as C
from rcominote.experiments import nor_freshness as F
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE

PROFILE = C.NOR_PROFILE
PRODUCER = "dbg fread spi_flash 0"
BUDGET = {k: v for k, v in C.BUDGET.items() if k != "ram_read_bytes"} | {"nor_read_bytes": 512}
FIELDS = tuple(k for k in C.FIELDS if k != "mdb_command") + ("producer_command", "nor_offset")


def oracle_source():
    proof = C.C.pins.oracles()["boot0"]
    data = C.C.oracle({"oracles": {"boot0": proof}}, 0)
    return data, proof


def validate_plan(plan):
    if (
        plan.get("profile") != PROFILE
        or not isinstance(plan.get("marker"), str)
        or C.MARKER.fullmatch(plan["marker"]) is None
        or plan.get("marker_command") != "kernel uptime " + plan["marker"]
        or plan.get("producer_command") != PRODUCER
        or type(plan.get("nor_offset")) is not int
        or plan["nor_offset"] != 0
        or plan.get("filler_command") != C.VERSION
        or plan.get("budget") != BUDGET
        or any(type(v) is not int for v in plan["budget"].values())
        or plan.get("expected_before") != plan["state_reference"]["latest_info"]
        or plan["state_reference"]["profile"] != C.C.PREFILLED_PROFILE
        or plan["state_reference"].get("historical_identity_only") is not True
        or plan["state_reference"].get("current_owned_file_verified") is not False
        or plan.get("startup_policy") != C.C.startup.POLICY
        or plan.get("status_event_policy") != C.C.E.POLICY
        or type(plan.get("oracle_bytes")) is not int
        or plan["oracle_bytes"] != 512
        or plan.get("oracle_slice") != [0, 512]
        or plan.get("oracle_sha256") != plan["nor_oracle"].get("sha256")
        or plan["nor_oracle"].get("nor_offset") != 0
        or plan["nor_oracle"].get("bytes") != 512
        or any(k in plan for k in ("mdb_command", "ram_oracle"))
    ):
        raise ValueError("Requires fixed BOOT0 direct-F0 visibility control without storage exports")
    C.A.verify_state(plan["expected_before"], plan["expected_before"], sd_write=False)
    C.C.J.time_order(plan["state_reference"]["ended_at"], plan["planned_at"])


def prepare(image, parent):
    _historical_file, state, source = C.C.parent_gate(parent, image)
    oracle, proof = oracle_source()
    marker = "afc" + secrets.token_hex(8)
    plan = {
        "profile": PROFILE,
        "marker": marker,
        "marker_command": "kernel uptime " + marker,
        "producer_command": PRODUCER,
        "nor_offset": 0,
        "filler_command": C.VERSION,
        "state_reference": C.state_reference(source),
        "expected_before": state,
        "nor_oracle": proof,
        "oracle_slice": [0, 512],
        "oracle_bytes": 512,
        "oracle_sha256": C.A.A.sha(oracle),
        "budget": BUDGET.copy(),
        "startup_policy": C.C.startup.POLICY,
        "status_event_policy": C.C.E.POLICY,
        "planned_at": C.C.S.now(),
    }
    validate_plan(plan)
    return plan, oracle


def source_gate(plan, image):
    validate_plan(plan)
    _historical_file, state, source = C.C.parent_gate(Path(plan["state_reference"]["directory"]), image)
    oracle, proof = oracle_source()
    if (
        C.state_reference(source) != plan["state_reference"]
        or state != plan["expected_before"]
        or proof != plan["nor_oracle"]
        or C.A.A.sha(oracle) != plan["oracle_sha256"]
    ):
        raise ValueError("Historical identity or complete independent raw BOOT0 oracle changed")
    return oracle


def producer_packet():
    # Isolated NON-newline encoding; shared RAM and SD command allowlists stay fixed.
    raw = PRODUCER.encode()
    payload = b"\x01" + len(raw).to_bytes(2, "little") + raw
    return b"\x1d\x10\x81" + len(payload).to_bytes(2, "little") + payload


def recipe(plan, fillers):
    validate_plan(plan)
    if type(fillers) is not int or not 0 <= fillers <= 8:
        raise ValueError("At most eight fixed version fillers permitted")
    return [
        PREPARE,
        START,
        C.packet(plan["marker_command"]),
        producer_packet(),
        *([C.packet(C.VERSION)] * fillers),
        STOP,
    ]


def parse(frames, plan, oracle, *, incomplete=False):
    if len(oracle) != 512 or C.A.A.sha(oracle) != plan["oracle_sha256"]:
        raise ValueError("Complete independent BOOT0 raw oracle changed")
    text = C.text_bytes(frames)
    markers = list(C.echo_pattern(plan["marker_command"]).finditer(text))
    if len(markers) > 1 or text.count(plan["marker"].encode()) > 1:
        raise ValueError("Fresh control marker duplicated")
    if not markers:
        if incomplete:
            return None
        raise ValueError("Missing fresh control marker")
    echoes = list(C.echo_pattern(PRODUCER).finditer(text, markers[0].end()))
    if len(echoes) > 1 or text.count(b"dbg fread") > 1:
        raise ValueError("Only one current exact BOOT0 producer permitted")
    if not echoes:
        if incomplete:
            return None
        raise ValueError("Missing current exact fread command echo")
    scope = text[markers[0].end() : echoes[0].start()]
    statuses = list(F.STATUS.finditer(scope))
    if (
        len(statuses) != 1
        or len(list(F.STATUS.finditer(text))) != 1
        or F.FAILURE.search(text[markers[0].end() :])
    ):
        raise ValueError("Fresh scope requires one current status and no failure/error")
    status = statuses[0]
    start = status.end() + 6
    end = len(scope) - len(F.LOG_PREFIX)
    if (
        status.start() != 0
        or status[1] != b"0"
        or scope[status.end() : start] != b"\r\n" * 3
        or scope[end:] != F.LOG_PREFIX
    ):
        raise ValueError("Current BOOT0 status/row/producer framing changed")
    data = F._rows(scope, start, end)
    if data != oracle:
        raise ValueError("Complete current BOOT0 bytes differ from independent raw oracle")
    origin = markers[0].end()
    return {
        "verified": True,
        "bytes": 512,
        "sha256": C.A.A.sha(data),
        "marker_span": [markers[0].start(), origin],
        "status_span": [origin + status.start(), origin + status.end()],
        "rows_span": [origin + start, origin + end],
        "producer_span": [echoes[0].start(), echoes[0].end()],
        "target_span": [origin, echoes[0].end()],
        "rows": 32,
        "nor_offset": 0,
        "oracle_used_to_select_chain": False,
        "route_visibility": "complete-printk-body-observed-in-original-actions-f0",
        "missing_body_implies_nor_read_failure": False,
    }
