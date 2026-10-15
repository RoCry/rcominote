"""Pure classification of one actual startup transaction; DEFAULT is not FAST.

FW010004 delayed peripheral worker can request DEFAULT when FAST application
returned -120 and cleared pending bit9. A DEFAULT startup still requires a
separate actual FAST settlement before host normalization or data download.
This module sends no commands and does not change existing probe policy.
"""

import asyncio

from rcominote.experiments import param_window as parameters

POLICY = "startup-remote-fast-or-default-once"
LEGACY_POLICY = "startup-remote-fast-only"
FAST = (6, 12, 0, 500)
DEFAULT = (24, 40, 0, 500)


def classify(transaction: dict, *, policy: str | None = None) -> dict:
    selected = LEGACY_POLICY if policy is None else policy
    if selected not in (LEGACY_POLICY, POLICY):
        raise ValueError("Unknown explicit startup policy")
    try:
        request, status, update = (transaction[key] for key in ("request", "status", "update"))
        remote, accept = (transaction[key] for key in ("remote_request", "remote_accept"))
        requested = parameters.parameters(request)
        mode = "fast" if requested == FAST else "default" if requested == DEFAULT else None
        if mode is None or (mode == "default" and selected != POLICY):
            raise ValueError("Startup tuple is outside its explicit FAST/DEFAULT policy")
        if (
            transaction["origin"] != "remote"
            or parameters.parameters(remote) != requested
            or any(type(value) is not int for value in requested)
            or remote["kind"] != "remote-request"
            or remote["direction"] != "rx"
            or accept["kind"] != "remote-accept"
            or accept["direction"] != "tx"
            or type(remote["identifier"]) is not int
            or not 1 <= remote["identifier"] <= 255
            or remote["identifier"] != accept["identifier"]
            or accept["result"] != 0
            or request["kind"] != "request"
            or status["kind"] != "status"
            or update["kind"] != "update"
            or status["status"] != 0
            or update["status"] != 0
            or request["handle"] != update["handle"]
            or (request["min_length"], request["max_length"]) != (0, 0)
            or not requested[0] <= update["interval"] <= requested[1]
            or (update["latency"], update["timeout"]) != requested[2:]
        ):
            raise ValueError("Startup lacks complete exact accepted remote request/status/update")
        for item in (remote, accept, request, status, update):
            if (
                type(item["record"]) is not int
                or item["record"] < 1
                or type(item["timestamp_us"]) is not int
                or item["timestamp_us"] < 0
            ):
                raise ValueError("Startup requires original record indices and timestamps")
        remote_records, accept_records = remote["records"], accept["records"]
        for item, records in ((remote, remote_records), (accept, accept_records)):
            if (
                not records
                or any(type(record) is not int for record in records)
                or records != sorted(set(records))
                or records[-1] != item["record"]
                or len(records) != len(item["timestamps_us"])
                or item["timestamps_us"][-1] != item["timestamp_us"]
            ):
                raise ValueError("Startup signaling original record bounds changed")
        if not (
            remote_records[-1]
            < accept_records[0]
            <= accept_records[-1]
            < request["record"]
            < status["record"]
            < update["record"]
        ):
            raise ValueError("Startup request/accept/command/status/update causal record order changed")
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Incomplete original startup transaction") from error
    return {
        "policy": selected,
        "mode": mode,
        "parameters": list(requested),
        "requires_fast_before_normalization": mode == "default",
    }


async def wait_startup(
    monitor, conn, link, *, policy: str | None = None, seconds: float = 12
) -> tuple[dict, dict]:
    """Wait for exactly transaction0; preserve its original dictionary and indices."""
    from rcominote.experiments import window_ram_probe as R

    if policy not in (None, LEGACY_POLICY, POLICY):
        raise ValueError("Unknown explicit startup policy")
    async with asyncio.timeout(seconds):
        while True:
            snapshot = R.observe(monitor, conn, link)
            transactions = snapshot["transactions"]
            if len(transactions) > 1 or (transactions and R.logical_pending(snapshot)):
                raise ValueError("Startup requires exactly one complete transaction without extras/pending")
            if transactions and not snapshot["pending"]:
                original = transactions[0]
                return original, classify(original, policy=policy)
            await asyncio.sleep(0.05)


async def live_wire(monitor, conn, report, *, seconds: float = 1) -> tuple[dict, dict, list]:
    """Bounded original capture-tail/host-prefix readiness; no commands or repair."""
    from rcominote.experiments import dual_audit as A
    from rcominote.experiments import dual_hci
    from rcominote.experiments import window_ram_audit as common
    from rcominote.experiments import window_ram_probe as R

    link = report["transport"]["link"]
    async with asyncio.timeout(seconds):
        while True:
            R.observe(monitor, conn, link)
            raw = monitor.path.read_bytes()
            observed = parameters.inspect(raw, link=link)
            if R.logical_pending(observed):
                raise ValueError("New parameter negotiation before FAST ordering proof")
            if not observed["pending"]:
                wire_rows = dual_hci.att_packets(raw, link["handle"])
                host_rows = list(report["att_packets"])
                complete = True
                for direction in ("tx", "rx"):
                    actual = [row["hex"] for row in wire_rows if row["direction"] == direction]
                    expected = [row["hex"] for row in host_rows if row["direction"] == direction]
                    if len(actual) > len(expected) or actual != expected[: len(actual)]:
                        raise ValueError("Changed/extra actual ATT bytes before FAST ordering proof")
                    complete &= len(actual) == len(expected)
                if complete:
                    current = report | {
                        "att_packets": host_rows,
                        "hci_capture": {
                            "bytes": len(raw),
                            "sha256": A.sha(raw),
                            "records": observed["records"],
                        },
                    }
                    wire = common.wire_positions(current, raw)
                    return current, observed, wire
            await asyncio.sleep(0.05)
