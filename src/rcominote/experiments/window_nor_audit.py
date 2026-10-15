"""Offline NOR pair window audit; no receipt mutation, device I/O or pairing claim."""

from pathlib import Path

from rcominote import protocol as P
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import param_window as parameters
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as events
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state

FAST = (6, 12, 0, 500)
SLOW = (32, 48, 4, 600)


def default_activity_fast(report, operation, previous, fast, wire):
    """Request not before current Actions; no claim of exclusive causation."""
    common.transaction(fast, origin="remote", parameters=FAST)
    first, _ = events.edge(report, operation["actions_start"], operation["actions_end"])
    request = fast["remote_request"]["records"][0]
    if not previous["update"]["record"] < wire[first][0] <= request:
        raise ValueError("DEFAULT first FAST request precedes Actions or prior settlement")
    return {
        "actions_first_record": wire[first][0],
        "remote_request_first_record": request,
        "request_not_before_actions": True,
    }


def listed_nonce_gate(report):
    count = common.file_list(report)
    planned = {operation["name"] for operation in report["operations"]}
    start, end = report["file_list_span"]
    for row in events.rows(report, start, end)[1:]:
        _, payload = P.parse(bytes.fromhex(row["hex"])[3:])
        if payload[:1] == b"\0" and P.parse_file_entry(payload).name in planned:
            raise ValueError("Planned nonce collides with an actual visible file-list entry")
    return count  # The visible inventory is not a complete scratch-file directory.


def parameter_stage(transactions, cursor, operation, previous, *, first_fast_required=False):
    fast = operation["pre_download_fast"]
    required = operation["operation_id"] == "second" or first_fast_required
    if not isinstance(fast, list) or len(fast) not in ((1,) if required else (0, 1)):
        raise ValueError("DEFAULT first Actions and every second Actions require exactly one FAST")
    if fast != transactions[cursor : cursor + len(fast)]:
        raise ValueError("Actions FAST proof differs from its actual next transaction")
    for item in fast:
        common.transaction(item, origin="remote", parameters=FAST)
        if not previous["update"]["record"] < item["remote_request"]["records"][0]:
            raise ValueError("Actions FAST precedes the previous actual settlement")
        previous = item
    cursor += len(fast)
    if cursor + 2 > len(transactions):
        raise ValueError("Missing normalization or EOF SLOW transaction")
    normalization, slow = transactions[cursor : cursor + 2]
    common.transaction(normalization, origin="host", parameters=(6, 6, 0, 500))
    common.transaction(slow, origin="remote", parameters=SLOW)
    if operation["normalization"] != normalization or operation["slow_settlement"] != slow:
        raise ValueError("Operation parameter receipts do not match actual transaction order")
    if not (
        previous["update"]["record"] < normalization["request"]["record"]
        and previous["update"]["timestamp_us"]
        <= operation["normalization_requested_us"]
        <= normalization["request"]["timestamp_us"]
    ):
        raise ValueError("Host normalization did not follow completed prior negotiation")
    return normalization, slow, cursor + 2


def download_window(wire, operation, normalization, slow, *, report=None):
    first, last = operation["download_start"], operation["download_end"] - 1
    barrier_first, actions_last = operation["after_span"][0], operation["actions_end"] - 1
    if report is not None:
        first, last = events.edge(report, operation["download_start"], operation["download_end"])
        barrier_first, _ = events.edge(report, *operation["after_span"])
        _, actions_last = events.edge(report, operation["actions_start"], operation["actions_end"])
    start, end, barrier = wire[first], wire[last], wire[barrier_first]
    if not (
        wire[actions_last][1]
        < normalization["request"]["record"]
        < normalization["update"]["record"]
        < start[0]
        <= slow["remote_request"]["records"][0]
        and end[1] < slow["update"]["record"] < barrier[0]
        and normalization["update"]["timestamp_us"] < start[2] <= slow["remote_request"]["timestamp_us"]
        and end[2] < slow["update"]["timestamp_us"] < barrier[2]
    ):
        raise ValueError("Download parameter window or actual Actions/settlement/barrier order failed")


def validate(report: dict, out: Path, image: Path) -> dict:
    """Accept a live candidate only after all wire/file checks; do not set its success flags."""
    from rcominote.experiments import window_nor_contract as contract

    common.no_errors(report)
    _, event_proof = events.verify(report)
    contract.recipe(report)
    contract.validate_parents(report, image)
    if report["monitor_exit"] != 0 or report["monitor_stop"] != {
        "signal": "SIGINT",
        "requested": True,
        "delivery": "sent",
    }:
        raise ValueError("Capture must exit cleanly after the owned SIGINT")
    raw = (out / "session.btsnoop").read_bytes()
    observed = parameters.inspect(raw, link=report["transport"]["link"], final=True)
    if observed["pending"] or report["hci_capture"] != {
        "bytes": len(raw),
        "sha256": A.sha(raw),
        "records": observed["records"],
    }:
        raise ValueError("Changed capture or incomplete parameter negotiation")
    transactions = observed["transactions"]
    if len(transactions) not in (6, 7):
        raise ValueError("Requires the complete bounded six/seven-transaction NOR policy")
    if A.setup(report) != report["gatt_proof"] or dual_hci.bind(report, raw) != report["att_hci_binding"]:
        raise ValueError("Actual session GATT or complete ATT/HCI binding changed")
    wire = common.wire_positions(report, raw)
    if any(event["record"] <= max(p[1] for p in wire) for event in observed["disconnects"]):
        raise ValueError("Owned disconnect precedes the final actual ATT packet")
    initial = common.span(report, report["before_span"])
    events.bridge(report, report["setup_end"], initial[0])
    A.identity(report, report, "before")
    verify_state(report["before"], report["before"], sd_write=False)
    if "expected_before" in report:
        predecessor = verify_state(report["expected_before"], report["before"], sd_write=False)
        if report.get("predecessor_state_verification") != predecessor:
            raise ValueError("Initial state differs from its required predecessor verification")
    elif "predecessor_state_verification" in report:
        raise ValueError("Predecessor verification requires an explicit expected_before state")
    count = listed_nonce_gate(report)
    warm = transactions[0]
    if "startup_policy" in report:
        classification = startup.classify(warm, policy=report["startup_policy"])
        if report.get("startup_classification") != classification:
            raise ValueError("Startup classification differs from actual original transaction")
        default_start = classification["mode"] == "default"
    else:
        common.transaction(warm, origin="remote", parameters=FAST)
        if "startup_classification" in report:
            raise ValueError("Startup classification requires explicit startup_policy")
        default_start = False
    if report["startup_settlement"] != warm:
        raise ValueError("Startup settlement differs from the actual complete transaction")
    before, boundary, cursor, previous = report["before"], report["file_list_span"][1], 1, warm
    for operation in report["operations"]:
        if (
            operation.get("live_complete") is not True
            or operation.get("sd_write_attempted") is not True
            or operation["before"] != before
        ):
            raise ValueError("Incomplete operation or a gap/reused boundary in actual Actions/download trace")
        events.bridge(report, boundary, operation["actions_start"])
        events.bridge(report, operation["actions_end"], operation["download_start"])
        if A.actions(report, operation) != operation["actions_verification"]:
            raise ValueError("Complete five-ACK/F1 Actions proof changed")
        if default_start and operation["operation_id"] == "first":
            if len(operation["pre_download_fast"]) != 1 or operation.get(
                "default_activity_fast_verification"
            ) != default_activity_fast(report, operation, warm, operation["pre_download_fast"][0], wire):
                raise ValueError("DEFAULT first Actions requires original causal FAST proof")
        elif "default_activity_fast_verification" in operation:
            raise ValueError("DEFAULT first Actions proof is not valid at this stage")
        if operation["operation_id"] == "first":
            action_first, _ = events.edge(report, operation["actions_start"], operation["actions_end"])
            if not (
                warm["update"]["record"] < wire[action_first][0]
                and warm["update"]["timestamp_us"] < wire[action_first][2]
            ):
                raise ValueError("First Actions preceded actual startup settlement")
        normalization, slow, cursor = parameter_stage(
            transactions,
            cursor,
            operation,
            previous,
            first_fast_required=default_start and operation["operation_id"] == "first",
        )
        directory = out / operation["operation_id"]  # contract restricts first/second, never arbitrary paths.
        ring = (directory / "download.bin").read_bytes()
        if (operation["download_bytes"], operation["received_bytes"], operation["download_sha256"]) != (
            4096,
            4096,
            A.sha(ring),
        ) or len(ring) != 4096:
            raise ValueError("Each retained NOR log must be one complete4096-byte download")
        if A.download(report, operation, ring) != operation["download_verification"]:
            raise ValueError("Actual complete Boyi download proof changed")
        decoded = contract.payload(report, operation, ring)
        if decoded != operation["verification"] or (directory / "sector.bin").read_bytes() != bytes.fromhex(
            decoded["sector_hex"]
        ):
            raise ValueError("Saved NOR sector differs from fresh rows in its own complete log")
        after_span = common.span(report, operation["after_span"])
        events.bridge(report, operation["download_end"], after_span[0])
        if after_span[1] != operation["verified_end"]:
            raise ValueError("Operation identity is not its immediate actual post-download barrier")
        download_window(wire, operation, normalization, slow, report=report)
        A.identity(report, operation, "after")
        if operation["state_verification"] != verify_state(before, operation["after"], sd_write=True):
            raise ValueError("Per-operation state exceeds one bounded SD export")
        before, boundary, previous = operation["after"], operation["verified_end"], slow
    if cursor != len(transactions):
        raise ValueError("Unconsumed extra parameter transaction")
    final_span = common.span(report, report["after_span"])
    events.bridge(report, boundary, final_span[0])
    events.bridge(report, final_span[1], len(report["att_packets"]))
    A.identity(report, report, "after")
    if report["state_verification"] != verify_state(before, report["after"], sd_write=False):
        raise ValueError("Final identity differs from last completed operation state")
    result = {
        "verified": True,
        "connections": 1,
        "parameter_transactions": len(transactions),
        "listed_count": count,
        "sd_writes": 2,
        "new_raw_nor_coverage_bytes": 0,
    }
    if events.enabled(report):
        result["status_events"] = event_proof
    return result
