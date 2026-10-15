"""Unknown-only explicit DEFAULT pulse; actual FAST precedes every baseline.

Legacy FAST has no pulse and retains its exact archived proof/transaction count.
"""

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_link_checkpoint as times
from rcominote.experiments import startup_ram_audit as pulse_audit
from rcominote.experiments import window_ram_probe as R

POLICY = C.startup.POLICY


def enabled(plan):
    return plan["profile"] in (C.PREFILLED_PROFILE, C.PREFILLED_PAGE) and plan.get("startup_policy") == POLICY


def budget(base, policy):
    if policy == C.startup.LEGACY_POLICY:
        return base.copy()
    if policy != POLICY:
        raise ValueError("Unknown explicit prefilled startup policy")
    return {k: v for k, v in base.items() if k != "parameter_transactions"} | {
        "max_parameter_transactions": 16,
        "max_startup_pulses": 1,
        "max_startup_commands": 3,
    }


def pulse(report, op):
    proof = pulse_audit.pulse(report, op)
    if (
        op.get("operation_id") != "startup-default-pulse"
        or op.get("ack_count") != 3
        or op.get("end_received") is not True
        or op.get("pending_hex") != ""
        or op.get("log_session_complete") is not True
        or any(frame["command"] not in (0x10, 0xF1) for frame in op["frames"])
        or len(op["frames"]) != 4
        or op["frames"][-1]["command"] != 0xF1
    ):
        raise ValueError("Startup pulse requires exactly3ACK/terminalF1, zero console body/F0")
    return proof


async def settle(conn, actions, monitor, report, plan, startup, classification):
    boundary = report["file_list_span"][1]
    if classification["mode"] == "fast":
        return startup, 1, boundary
    if not enabled(plan):
        raise ValueError("DEFAULT pulse requires explicit unknown-prefill startup policy")
    link = report["transport"]["link"]
    observed = R.observe(monitor, conn, link)
    if len(observed["transactions"]) != 1 or observed["pending"]:
        raise ValueError("Extra/pending negotiation before zero-body startup pulse")
    op = report["startup_pulse"] = {"operation_id": "startup-default-pulse", "started_at": C.S.now()}
    try:
        await actions.run_commands(op, [], sd_write_command_index=None)
        op["actions_verification"] = pulse(report, op)
        op["activity_fast"] = await R.wait_transaction(
            monitor, conn, link, index=1, origin="remote", parameters=R.FAST, seconds=8
        )
        current, observed, wire = await C.startup.live_wire(monitor, conn, report)
        if (
            len(observed["transactions"]) != 2
            or observed["pending"]
            or op["activity_fast"] != observed["transactions"][1]
        ):
            raise ValueError("DEFAULT requires exactly one full activity FAST before baseline")
        op["activity_fast_verification"] = pulse_audit.activity_fast(
            current, op, startup, op["activity_fast"], wire
        )
        first, _last = A.E.edge(current, op["actions_start"], op["actions_end"])
        if (
            not startup["update"]["timestamp_us"]
            < wire[first][2]
            <= op["activity_fast"]["remote_request"]["timestamp_us"]
        ):
            raise ValueError("DEFAULT/pulse/FAST original timestamps out of order before baseline")
        op["live_complete"] = True
    finally:
        op["ended_at"] = C.S.now()
    return op["activity_fast"], 2, op["actions_end"]


def extra(actual, plan):
    return int(enabled(plan) and actual["startup_classification"]["mode"] == "default")


def audit(actual, plan, observed, wire):
    startup = observed["transactions"][0]
    classification = C.startup.classify(startup, policy=plan["startup_policy"])
    if actual["startup_settlement"] != startup or actual["startup_classification"] != classification:
        raise ValueError("Stored startup differs from explicit complete FAST/DEFAULT classification")
    boundary = actual["file_list_span"][1]
    proof = {"mode": classification["mode"], "pulse_performed": False}
    if classification["mode"] == "fast":
        if "startup_pulse" in actual:
            raise ValueError("FAST startup cannot invent a DEFAULT pulse")
        return startup, boundary, proof
    if not enabled(plan):
        raise ValueError("Legacy startup cannot adopt DEFAULT")
    op = actual["startup_pulse"]
    C.J.time_order(actual["started_at"], op["started_at"], op["ended_at"], actual["baseline"]["started_at"])
    A.E.bridge(actual, boundary, op["actions_start"])
    if op.get("live_complete") is not True or op["actions_verification"] != pulse(actual, op):
        raise ValueError("Original zero-body startup pulse incomplete or changed")
    fast = observed["transactions"][1]
    activity = pulse_audit.activity_fast(actual, op, startup, fast, wire)
    first, last = A.E.edge(actual, op["actions_start"], op["actions_end"])
    normal = observed["transactions"][2]
    C.J.time_order(
        op["started_at"],
        times.iso(wire[first][2]),
        times.iso(max(wire[last][2], fast["update"]["timestamp_us"])),
        op["ended_at"],
    )
    if (
        op["activity_fast"] != fast
        or op["activity_fast_verification"] != activity
        or not startup["update"]["timestamp_us"] < wire[first][2] <= fast["remote_request"]["timestamp_us"]
        or not max(wire[last][1], fast["update"]["record"]) < normal["request"]["record"]
        or not max(wire[last][2], fast["update"]["timestamp_us"])
        <= actual["baseline"]["normalization_requested_us"]
        <= normal["request"]["timestamp_us"]
    ):
        raise ValueError("DEFAULT/pulse/actualFAST must fully settle before baseline normalization")
    return (
        fast,
        op["actions_end"],
        proof | {"pulse_performed": True, "pulse": op["actions_verification"], "activity_fast": activity},
    )
