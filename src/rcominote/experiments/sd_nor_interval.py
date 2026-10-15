"""Fixed4096 ring transport profile and independent private HCI receipt replay."""

from pathlib import Path

from rcominote.experiments import hci_interval as H
from rcominote.experiments import sd_interval_download as session
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.experiments.sd_warm_download import sha

PROFILE = "interval6-ce1"


def replay(transport: dict, directory: Path) -> None:
    """Reconstruct timing/ownership/parameter gates from complete retained capture."""
    exit_code = transport.get("monitor_exit")
    stop = transport.get("monitor_stop", {})
    if exit_code == 130 and stop != {"signal": "SIGINT", "requested": True, "delivery": "sent"}:
        raise ValueError("Exit130 lacks explicit owned-child SIGINT stop receipt")
    if (
        transport.get("profile") != PROFILE
        or transport.get("condition") != "verified-through-download"
        or transport.get("sd_write_attempted") is not False
        or transport.get("update_attempted") is not True
        or transport.get("transfer_complete") is not True
        or exit_code not in (0, 124, 137, 130)
        or any(value for key, value in transport.items() if key.endswith("error"))
    ):
        raise ValueError("Incomplete interval6 transport receipt")
    raw = (directory / "session.btsnoop").read_bytes()
    parser = H.Snoop()
    parser.feed(raw, final=True)
    if transport["hci_capture"] != {"bytes": len(raw), "sha256": sha(raw), "records": parser.records}:
        raise ValueError("Private HCI capture hash/size/record count changed")
    link = transport["link"]
    if link["peer"] != H.PEER or link["controller"] != "hci0":
        raise ValueError("Transport differs from fixed owned peer/controller")
    requested, start, end = (
        transport[key] for key in ("update_requested_us", "download_start_us", "download_end_us")
    )
    if any(type(value) is not int for value in (requested, start, end)) or not requested <= start <= end:
        raise ValueError("Invalid transport chronology")
    if parser.last_stamp < end:
        raise ValueError("Private HCI capture ends before the download interval")
    before = [e for e in parser.events if e["timestamp_us"] < requested]
    baseline = H.current(before, link["handle"], link["local"])
    if baseline != transport["baseline"] or baseline["latency"] != 0 or not 6 < baseline["interval"] <= 3200:
        raise ValueError("Baseline differs from actual HCI state")
    for cutoff in (start, end):
        events = [e for e in parser.events if e["timestamp_us"] <= cutoff]
        applied = H.applied(events, link["handle"], link["local"], baseline, requested)
        if applied is None or applied != transport["applied"]:
            raise ValueError("Private HCI replay does not prove applied condition")
    requests = [
        e
        for e in parser.events
        if e["kind"] == "request" and e["handle"] == link["handle"] and requested <= e["timestamp_us"] <= end
    ]
    if requests != [transport["actual_hci_request"]]:
        raise ValueError("Transport request receipt differs from actual HCI command")
    state = verify_state(transport["before"], transport["after"], sd_write=False)
    if transport.get("state_verification") != state:
        raise ValueError("Transport identity summary differs from full info")


async def download(report: dict, out: Path) -> None:
    # Caller validates phase/source/nonce and complete Actions before reaching here.
    from rcominote.experiments import sd_nor_probe as probe

    if report["phase"] not in ("baseline", "boot", "recovery-block1", "backup-boot-block1") or (
        report["source_address"],
        report["source_bytes"],
    ) != (
        hex(probe.BUFFER),
        4096,
    ):
        raise ValueError("Interval transport permits only fixed4096 ring phases")
    probe.command(report, probe.BUFFER, 4096)
    probe.validate_actions(report, producer=report["phase"] in probe.targets.PRODUCER_PHASES)
    transport = report["transport"] = {
        "profile": PROFILE,
        "policy": "interval6/latency0/current timeout; both hcitool CE hints1; not pure interval-only",
        "sd_write_attempted": False,
        "update_attempted": False,
        "condition": "not-applied",
    }

    async def operation(conn, directory, evidence):
        data = bytearray()

        def sink(chunk):
            if len(data) + len(chunk) > 4096:
                raise ValueError("Ring download exceeds fixed4096 profile")
            data.extend(chunk)
            return len(chunk)

        try:
            report["download_bytes"] = await conn.download(report["name"], sink, offset=0)
            if report["download_bytes"] != 4096 or len(data) != 4096:
                raise ValueError("Incomplete4096 ring download")
            evidence["transfer_complete"] = True
        finally:
            report.update(received_bytes=len(data), download_sha256=sha(data))
            with (directory / "download.bin").open("xb") as handle:
                handle.write(data)

    await session.capture(transport, b"", out, operation=operation)
    replay(transport, out)
