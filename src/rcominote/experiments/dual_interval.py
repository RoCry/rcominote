"""Fixed early normalization experiment; historical interval receipts stay frozen."""

import asyncio

from rcominote.experiments import hci_interval as H

EARLY_PROFILE = "dual-unknown-backup2200-early-pair"
BOOT_TAIL_PROFILE = "fixed-fw1-boot-tail-pair"
POLICY = "early-before-identity-interval6-latency0-timeout500-ce1"


def is_early(report):
    return report.get("profile") in (EARLY_PROFILE, BOOT_TAIL_PROFILE)


def baseline(events, link):
    value = H.current(events, link["handle"], link["local"])
    if any(e["kind"] == "request" for e in H.epoch(events, link["handle"], link["local"])):
        raise ValueError("Prior parameter request in early connection epoch; no normalization attempted")
    if not (
        6 < value["interval"] <= 3200 and 0 <= value["latency"] <= 499 and 10 <= value["timeout"] <= 3200
    ):
        raise ValueError("Early normalization requires valid current parameters and interval above6")
    return value


def applied(events, transport):
    observed = transport["baseline"]
    if transport.get("policy") == POLICY:
        # H.applied consumes only timeout from this expected-request argument.
        # Retained physical baseline stays unchanged, including latency/timeout.
        expected = {"timeout": 500}
    elif "policy" not in transport:
        expected = observed
    else:
        raise ValueError("Unknown transport experiment policy")
    link = transport["link"]
    return H.applied(events, link["handle"], link["local"], expected, transport["update_requested_us"])


def gate(monitor, transport):
    return applied(monitor.poll(), transport)


async def watch(monitor, transport):
    while True:
        if gate(monitor, transport) != transport["applied"]:
            raise ValueError("Applied HCI condition disappeared/changed")
        await asyncio.sleep(0.05)
