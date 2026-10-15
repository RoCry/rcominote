"""Full original seed/DEFAULT/activity/RAM trace audit; no receipt mutation."""

import json
from itertools import pairwise
from pathlib import Path

from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import param_window as parameters
from rcominote.experiments import startup_ram_contract as C
from rcominote.experiments import status_event as E
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments import window_ram_probe as R
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.log_capture import START, STOP
from rcominote.log_probe import PREPARE


def pulse(report: dict, operation: dict) -> dict:
    if operation.get("sd_write_attempted") is not False or any(
        key in operation for key in ("producer", "dump_command", "source_address", "source_bytes")
    ):
        raise ValueError("Activity pulse permits only PREPARE/START/STOP; no console body or SD write")
    return A.action_frames(report, operation, expected=[PREPARE, START, STOP])


def activity_fast(report: dict, op: dict, previous: dict, fast: dict, wire: list) -> dict:
    """Check original ordering; earlier identity may still have scheduled deferred FAST."""
    common.transaction(fast, origin="remote", parameters=C.startup.FAST)
    first, _ = E.edge(report, op["actions_start"], op["actions_end"])
    request = fast["remote_request"]["records"][0]
    if not previous["update"]["record"] < wire[first][0] <= request:
        raise ValueError("FAST request precedes pulse or pulse precedes actual previous settlement")
    return {
        "pulse_first_record": wire[first][0],
        "remote_request_first_record": request,
        "request_not_before_pulse": True,
    }


def session(report: dict, directory: Path, *, kind: str) -> tuple[dict, list, dict]:
    common.no_errors(report)
    if (
        report.get("profile") != f"{C.PROFILE}/{kind}"
        or report.get("sd_write_attempted") is not False
        or report.get("status_event_policy") != E.POLICY
        or report.get("startup_policy") != (C.startup.LEGACY_POLICY if kind == "seed" else C.startup.POLICY)
        or report.get("monitor_exit") != 0
        or report.get("monitor_stop") != {"signal": "SIGINT", "requested": True, "delivery": "sent"}
    ):
        raise ValueError("Fixed read-only seed/data profile or clean monitor receipt changed")
    _, events = E.verify(report)
    rows = report["att_packets"]
    if any(type(row["monotonic_ns"]) is not int for row in rows) or any(
        first["monotonic_ns"] > second["monotonic_ns"] for first, second in pairwise(rows)
    ):
        raise ValueError("Original host ATT timestamps must be complete and monotonic")
    raw = (directory / "session.btsnoop").read_bytes()
    observed = parameters.inspect(raw, link=report["transport"]["link"], final=True)
    if (
        observed["pending"]
        or report["hci_capture"] != {"bytes": len(raw), "sha256": A.sha(raw), "records": observed["records"]}
        or report["gatt_proof"] != A.setup(report)
        or report["att_hci_binding"] != dual_hci.bind(report, raw)
    ):
        raise ValueError("Incomplete or changed original GATT/ATT/HCI/parameter capture")
    wire = common.wire_positions(report, raw)
    disconnects = observed["disconnects"]
    if (
        len(disconnects) != 1
        or disconnects[0]["status"] != 0
        or disconnects[0]["reason"] != 0x16
        or disconnects[0]["record"] <= max(row[1] for row in wire)
        or report.get("disconnect_observation")
        != {"observed": True, "event": disconnects[0], "max_wait_seconds": 8}
    ):
        raise ValueError("Requires actual normal disconnect after final ATT and bounded close observation")
    requested, completed, recorded = [
        report[key] for key in ("close_requested_us", "close_completed_us", "disconnect_observed_us")
    ]
    if (
        any(type(value) is not int for value in (requested, completed, recorded))
        or not requested <= completed <= recorded <= completed + 8_000_000
        or not requested <= disconnects[0]["timestamp_us"] <= completed + 8_000_000
    ):
        raise ValueError("Actual disconnect/observation exceeds original bounded post-close timing")
    E.bridge(report, report["setup_end"], report["before_span"][0])
    A.identity(report, report, "before")
    proof = verify_state(report["expected_before"], report["before"], sd_write=False)
    if report["predecessor_state_verification"] != proof:
        raise ValueError("Actual initial identity differs from required read-only predecessor")
    return observed, wire, events


def seed(report: dict, directory: Path) -> dict:
    observed, wire, events = session(report, directory, kind="seed")
    if report["operations"] or len(observed["transactions"]) != 1:
        raise ValueError("Seed permits one actual remote FAST settlement, no Actions/downloads")
    transaction = observed["transactions"][0]
    classification = C.startup.classify(transaction)
    if (
        report["startup_settlement"] != transaction
        or report["startup_classification"] != classification
        or classification["mode"] != "fast"
    ):
        raise ValueError("Seed requires strict original remote FAST")
    E.bridge(report, report["before_span"][1], report["after_span"][0])
    A.identity(report, report, "after")
    E.bridge(report, report["after_span"][1], len(report["att_packets"]))
    after_first, _ = E.edge(report, *report["after_span"])
    if transaction["update"]["record"] >= wire[after_first][0]:
        raise ValueError("Seed final identity must follow complete actual FAST settlement")
    if report["state_verification"] != verify_state(report["before"], report["after"], sd_write=False):
        raise ValueError("Seed final read-only state proof changed")
    return {"verified": True, "connections": 1, "parameter_transactions": 1, "status_events": events}


def data(report: dict, directory: Path, oracle: bytes) -> dict:
    observed, wire, events = session(report, directory, kind="data")
    transactions = observed["transactions"]
    if len(transactions) != 7 or [op["operation_id"] for op in report["operations"]] != ["first", "second"]:
        raise ValueError("Requires DEFAULT followed by exactly two FAST/host/SLOW windows")
    startup = transactions[0]
    classification = C.startup.classify(startup, policy=C.startup.POLICY)
    if (
        classification["mode"] != "default"
        or report["startup_settlement"] != startup
        or report["startup_classification"] != classification
    ):
        raise ValueError("Data control requires actual DEFAULT; FAST never counts as DEFAULT tested")
    boundary = report["before_span"][1]
    if common.file_list(report) != report["listed_count"]:
        raise ValueError("Original file-list proof changed")
    E.bridge(report, boundary, report["file_list_span"][0])
    boundary, state, previous = report["file_list_span"][1], report["before"], startup
    proofs = []
    for index, op in enumerate(report["operations"]):
        fast, normalization, slow = transactions[1 + index * 3 : 4 + index * 3]
        common.transaction(normalization, origin="host", parameters=(6, 6, 0, 500))
        common.transaction(slow, origin="remote", parameters=R.SLOW)
        J.time_order(report["started_at"], op["started_at"], op["ended_at"], report["ended_at"])
        if index:
            J.time_order(report["operations"][index - 1]["ended_at"], op["started_at"])
        if (
            op.get("live_complete") is not True
            or op.get("name") != C.RAM.NAME
            or op["before"] != state
            or op["activity_fast"] != fast
            or op["normalization"] != normalization
            or op["slow_settlement"] != slow
        ):
            raise ValueError("Fixed RAM window prestate/name or actual parameter stage changed")
        E.bridge(report, boundary, op["actions_start"])
        proof = pulse(report, op)
        if op["actions_verification"] != proof or op["activity_fast_verification"] != activity_fast(
            report, op, previous, fast, wire
        ):
            raise ValueError("Original activity pulse or FAST ordering proof changed")
        E.bridge(report, op["actions_end"], op["download_start"])
        _, actions_last = E.edge(report, op["actions_start"], op["actions_end"])
        first, last = E.edge(report, op["download_start"], op["download_end"])
        barrier_first, _ = E.edge(report, *op["after_span"])
        if not (
            max(wire[actions_last][1], fast["update"]["record"])
            < normalization["request"]["record"]
            < normalization["update"]["record"]
            < wire[first][0]
            <= slow["remote_request"]["records"][0]
            and wire[last][1] < slow["update"]["record"] < wire[barrier_first][0]
            and fast["update"]["timestamp_us"]
            <= op["normalization_requested_us"]
            <= normalization["request"]["timestamp_us"]
            and normalization["update"]["timestamp_us"]
            < wire[first][2]
            <= slow["remote_request"]["timestamp_us"]
            and wire[last][2] < slow["update"]["timestamp_us"] < wire[barrier_first][2]
        ):
            raise ValueError("Pulse/FAST/normalization/download/SLOW/identity wire order changed")
        raw = (directory / op["operation_id"] / "download.bin").read_bytes()
        if raw != oracle or (op["download_bytes"], op["received_bytes"], op["download_sha256"]) != (
            4096,
            4096,
            A.sha(oracle),
        ):
            raise ValueError("Both actual downloads must equal the complete independent RAM oracle")
        if op["download_trace_verification"] != A.download(
            report, op, raw, minimum_start=report["setup_end"]
        ):
            raise ValueError("Actual complete Boyi download proof changed")
        E.bridge(report, op["download_end"], op["after_span"][0])
        A.identity(report, op, "after")
        if op["verified_end"] != op["after_span"][1] or op["state_verification"] != verify_state(
            state, op["after"], sd_write=False
        ):
            raise ValueError("Complete actual read-only per-download identity barrier changed")
        boundary, state, previous = op["verified_end"], op["after"], slow
        proofs.append({"operation": op["operation_id"], "bytes": 4096, "sha256": A.sha(raw)})
    E.bridge(report, boundary, report["after_span"][0])
    A.identity(report, report, "after")
    E.bridge(report, report["after_span"][1], len(report["att_packets"]))
    if report["state_verification"] != verify_state(report["before"], report["after"], sd_write=False):
        raise ValueError("Final actual read-only identity state changed")
    return {
        "verified": True,
        "connections": 1,
        "startup_mode": "default",
        "parameter_transactions": 7,
        "activity_pulses": 2,
        "downloads": proofs,
        "status_events": events,
        "sd_writes": 0,
        "new_raw_nor_coverage_bytes": 0,
    }


def validate(job: dict, directory: Path, image: Path) -> dict:
    common.no_errors(job)
    if job.get("profile") != C.PROFILE or set(job["phases"]) != set(C.PHASES):
        raise ValueError("Requires both original seed and data phases")
    if job["plan"]["file"] != "plan.json":
        raise ValueError("Immutable control plan path changed")
    plan = json.loads(J.check_reference(directory, job["plan"]).read_bytes())
    oracle = C.source_gate(plan, image)
    reports = {}
    for kind in C.PHASES:
        if job["phases"][kind]["file"] != f"{kind}/report.json":
            raise ValueError("Original phase receipt path changed")
        report = json.loads(J.check_reference(directory, job["phases"][kind]).read_bytes())
        if report.get("ok") is not True or any(op.get("ok") is not True for op in report["operations"]):
            raise ValueError("Original failed phase cannot pass control replay")
        reports[kind] = report
    first, second = reports["seed"], reports["data"]
    if first["expected_before"] != plan["expected_before"] or second["expected_before"] != first["after"]:
        raise ValueError("Actual seed/data initial state anchor changed")
    J.time_order(
        plan["state_parent"]["ended_at"],
        plan["planned_at"],
        job["started_at"],
        first["started_at"],
        first["ended_at"],
        second["started_at"],
        second["ended_at"],
        job["ended_at"],
    )
    seed_proof = seed(first, directory / "seed")
    data_proof = data(second, directory / "data", oracle)
    if seed_proof != first["verification"] or data_proof != second["verification"]:
        raise ValueError("Original full phase verification changed")
    seed_raw = (directory / "seed/session.btsnoop").read_bytes()
    data_raw = (directory / "data/session.btsnoop").read_bytes()
    seed_wire = parameters.inspect(seed_raw, link=first["transport"]["link"], final=True)
    data_wire = parameters.inspect(data_raw, link=second["transport"]["link"], final=True)
    if seed_wire["disconnects"][0]["timestamp_us"] >= data_wire["connection"]["timestamp_us"]:
        raise ValueError("Data connection must follow actual seed disconnect; no overlapping epochs")
    return {
        "verified": True,
        "connections": 2,
        "actual_default_tested": True,
        "parameter_transactions": 8,
        "activity_pulses": 2,
        "downloads": 2,
        "sd_writes": 0,
        "new_raw_nor_coverage_bytes": 0,
    }
