"""Fixed two-operation session engine; CLI reads only known boot0 then recovery0x4200."""

import asyncio
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.device_commands import read_info
from rcominote.experiments import dual_audit as audit
from rcominote.experiments import dual_hci
from rcominote.experiments import dual_interval as condition
from rcominote.experiments import hci_interval as H
from rcominote.experiments import sd_interval_download as interval
from rcominote.experiments import sd_nor_probe as probe
from rcominote.experiments import sd_nor_targets as targets
from rcominote.experiments.dual_client import Actions, DualConnection
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize, request_once
from rcominote.experiments.hci_monitor import Snoop
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.log_probe import NOTIFY


def now():
    return datetime.now(UTC).isoformat()


def save(path, value):
    with path.open("x") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def operation_directory(operation):
    name = operation.get("operation_id", operation["phase"])
    if name not in ("boot", "recovery-block1", "first", "second"):
        raise ValueError("Unknown fixed operation directory")
    return name


def validate_ring(session, operation, data):
    match session["profile"]:
        case "dual-known-boot0-recovery4200":
            return probe.validate_payload(operation, data)
        case condition.EARLY_PROFILE:
            from rcominote.experiments.dual_unknown_pair import payload

            return payload(session, operation, data)
        case condition.BOOT_TAIL_PROFILE:
            from rcominote.experiments.boot_tail_contract import payload

            return payload(session, operation, data)
        case _:
            raise ValueError("Unknown fixed dual-session profile")


def prepare(image: Path, first: Path, second: Path) -> dict:
    data = image.read_bytes()
    if len(data) != 927632 or audit.sha(data) != probe.IMAGE_SHA:
        raise ValueError("Requires fixed complete FW010004 system image")
    known = targets.verify_pair(first, second, data)
    parents = [
        {"directory": str(p.resolve()), "report_sha256": audit.sha((p / "report.json").read_bytes())}
        for p in (first, second)
    ]
    ops = []
    for phase in (targets.Phase.boot, targets.Phase.recovery):
        name = "rc" + secrets.token_hex(5)
        path = f"/SD:/RECORDER/Call-{name}.mp3"
        op = {
            "phase": phase,
            "name": name,
            "device_path": path,
            "source_address": hex(probe.BUFFER),
            "source_bytes": 4096,
            "dump_command": f"dbg dumpbuf {probe.BUFFER} 4096 {path}",
            "producer": targets.producer(phase),
            "oracle": targets.oracle(phase)[2],
            "transport_profile": "interval6-ce1",
            "sd_write_attempted": False,
            "ok": False,
        }
        probe.command(op, probe.BUFFER, 4096)
        targets.validate_producer(op)
        ops.append(op)
    if ops[0]["name"] == ops[1]["name"]:
        raise ValueError("Scratch nonce collision; no regeneration/retry")
    return {
        "profile": "dual-known-boot0-recovery4200",
        "started_at": now(),
        "serial": OWNED_SERIAL,
        "source_image_sha256": probe.IMAGE_SHA,
        "known_pair": known,
        "parents": parents,
        "policy": "First Actions before update; interval6/CE1 through both downloads, second Actions and barriers",
        "operations": ops,
        "ok": False,
        "transport": {"update_attempted": False},
    }


async def apply_interval(conn, monitor, report):
    t = report["transport"]
    t["link"] = active_link(conn)
    early = condition.is_early(report)
    t["baseline"] = (
        condition.baseline(monitor.poll(), t["link"])
        if early
        else await interval.baseline(monitor, t["link"])
    )
    if active_link(conn) != t["link"]:
        raise ValueError("Active owned link changed before update")
    t["update_requested_us"] = H.timestamp_us()
    t["update_attempted"] = True
    await request_once(t["link"]["handle"], 500 if early else t["baseline"]["timeout"])
    async with asyncio.timeout(8):
        while (result := condition.gate(monitor, t)) is None:
            await asyncio.sleep(0.05)
    t["applied"] = result
    t["actual_hci_request"] = next(
        e
        for e in monitor.poll()
        if e["kind"] == "request"
        and e["handle"] == t["link"]["handle"]
        and e["timestamp_us"] >= t["update_requested_us"]
    )


async def download(conn, op, directory):
    data = bytearray()

    def sink(chunk):
        if len(data) + len(chunk) > 4096:
            raise ValueError("Fixed ring download overflow")
        data.extend(chunk)
        return len(chunk)

    op["download_start_us"] = H.timestamp_us()
    op["download_start"] = len(conn.client.report["att_packets"])
    conn.offline_allowed = True
    try:
        op["download_bytes"] = await conn.download(op["name"], sink, offset=0)
        if op["download_bytes"] != 4096 or len(data) != 4096:
            raise ValueError("Incomplete fixed ring4096 download")
    finally:
        conn.offline_allowed = False
        op.update(
            received_bytes=len(data),
            download_sha256=audit.sha(data),
            download_end_us=H.timestamp_us(),
            download_end=len(conn.client.report["att_packets"]),
        )
        with (directory / "download.bin").open("xb") as handle:
            handle.write(data)
    op["download_verification"] = audit.download(conn.client.report, op, bytes(data))
    op["verification"] = validate_ring(conn.client.report, op, bytes(data))
    with (directory / "sector.bin").open("xb") as handle:
        handle.write(bytes.fromhex(op["verification"]["sector_hex"]))


async def read_identity(conn, owner, key):
    session = conn.client.report
    start = len(session["att_packets"])
    try:
        owner[key] = await read_info(conn, OWNED_SERIAL)
    finally:
        owner[f"{key}_span"] = [start, len(session["att_packets"])]
    owner[f"{key}_verification"] = audit.identity(session, owner, key)
    return owner[key]


async def finish_operation(conn, monitor, report, op, out):
    await download(conn, op, out / operation_directory(op))
    await read_identity(conn, op, "after")
    op["state_verification"] = verify_state(op["before"], op["after"], sd_write=True)
    conn._check_failure()
    op["verified_end_us"] = H.timestamp_us()
    op["verified_end"] = len(report["att_packets"])
    if condition.gate(monitor, report["transport"]) != report["transport"]["applied"]:
        raise ValueError("Applied condition changed before operation barrier")
    op["live_complete"] = True
    op["ended_at"] = now()
    # Durable actual-session prefix, never a manufactured per-op discovery.
    save(out / operation_directory(op) / "checkpoint.json", report)


async def remainder(conn, monitor, report, actions, out):
    first, second = report["operations"]
    await finish_operation(conn, monitor, report, first, out)
    second["before"] = first["after"]
    second["started_at"] = now()
    second["condition_start_us"] = H.timestamp_us()
    await actions.run(second)
    second["actions_verification"] = audit.actions(report, second)
    await finish_operation(conn, monitor, report, second, out)


async def guarded_remainder(conn, monitor, report, actions, out):
    work = asyncio.create_task(remainder(conn, monitor, report, actions, out))
    watcher = asyncio.create_task(condition.watch(monitor, report["transport"]))
    try:
        done, _ = await asyncio.wait((work, watcher), return_when=asyncio.FIRST_COMPLETED)
        if watcher in done:
            await watcher
        await work
    finally:
        for task in (work, watcher):
            if not task.done():
                task.cancel()
        await asyncio.gather(work, watcher, return_exceptions=True)


async def connected(conn, monitor, report, out):
    actions = Actions(conn, report)
    await conn.client.start_notify(NOTIFY, actions.receive)
    report["setup_end"] = len(report["att_packets"])
    report["gatt_proof"] = audit.setup(report)
    failure = None
    try:
        early = condition.is_early(report)
        if early:
            await apply_interval(conn, monitor, report)
        await read_identity(conn, report, "before")
        verify_state(report["before"], report["before"], sd_write=False)
        if "expected_before" in report:
            report["predecessor_state_verification"] = verify_state(
                report["expected_before"], report["before"], sd_write=False
            )
        names = {entry.name for entry in await conn.file_list()}
        if any(op["name"] in names for op in report["operations"]):
            raise FileExistsError("Scratch path exists; no Actions attempted")
        report["visible_audio_list_no_collision"] = True  # Do not copy private recording inventory.
        first = report["operations"][0]
        first.update(before=report["before"], started_at=now())
        if early:
            if condition.gate(monitor, report["transport"]) != report["transport"]["applied"]:
                raise ValueError("Early condition changed before first producer; no SD write attempted")
            first["condition_start_us"] = H.timestamp_us()
        await actions.run(first)
        first["actions_verification"] = audit.actions(report, first)
        if not early:
            await apply_interval(conn, monitor, report)
            first["condition_start_us"] = H.timestamp_us()
        await guarded_remainder(conn, monitor, report, actions, out)
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            await read_identity(conn, report, "after")
            complete = [op for op in report["operations"] if op.get("live_complete")]
            state_base = complete[-1]["after"] if complete else report["before"]
            pending = [
                op for op in report["operations"] if op["sd_write_attempted"] and not op.get("live_complete")
            ]
            if len(pending) > 1:
                raise ValueError("More than one unverified scratch write")
            report["final_state_base"] = "last-completed-operation" if complete else "session-before"
            report["state_verification"] = verify_state(state_base, report["after"], sd_write=bool(pending))
            report["verified_end_us"] = H.timestamp_us()
        except BaseException as error:
            report["after_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


def barrier_span(report, operation=None):
    if operation is not None:
        expected = [operation["download_end"], operation["verified_end"]]
        if operation["after_span"] != expected:
            raise ValueError("Operation identity is not its actual post-download barrier")
    elif report["after_span"] != [report["operations"][-1]["verified_end"], len(report["att_packets"])]:
        raise ValueError("Final identity is not the actual complete session tail")


def finalize(report, out, monitor):
    report["final_audit_complete"] = False
    raw = monitor.path.read_bytes()
    report["hci_capture"] = {"bytes": len(raw), "sha256": audit.sha(raw), "records": monitor.snoop.records}
    report["att_hci_binding"] = dual_hci.bind(report, raw)
    if report["before_span"][0] != report["setup_end"]:
        raise ValueError("Initial identity does not immediately follow session setup")
    audit.identity(report, report, "before")
    state_base = report["before"]
    boundary = report["before_span"][1]
    for op in report["operations"]:
        if op.get("live_complete"):
            if op["before"] != state_base or op["actions_start"] < boundary:
                raise ValueError("Operation before/barrier chain or chronological span changed")
            if op["state_verification"] != verify_state(op["before"], op["after"], sd_write=True):
                raise ValueError("Operation state summary changed")
            audit.actions(report, op)
            barrier_span(report, op)
            audit.identity(report, op, "after")
            data = probe.downloaded(op, out / operation_directory(op), 4096)
            if audit.download(report, op, data) != op["download_verification"]:
                raise ValueError("Saved Boyi notification verification changed")
            if validate_ring(report, op, data) != op["verification"]:
                raise ValueError("Saved payload verification changed")
            op["hci_verification"] = audit.hci(report, op, raw)
            op["ok"] = True
            state_base, boundary = op["after"], op["verified_end"]
    if all(op["ok"] for op in report["operations"]):
        barrier_span(report)
        audit.identity(report, report, "after")
        if report["state_verification"] != verify_state(state_base, report["after"], sd_write=False):
            raise ValueError("Final state differs from last completed barrier")
        audit.hci(report, report["operations"][-1] | {"verified_end": report["after_span"][1]}, raw)
        report["final_audit_complete"] = True


def replay(directory: Path, image: Path) -> dict:
    """Independent private receipt replay, including all original guard parents."""
    report = json.loads((directory / "report.json").read_text())
    parents = report["parents"]
    if len(parents) != 2:
        raise ValueError("Requires exactly two known-pair parents")
    expected = prepare(image, *(Path(p["directory"]) for p in parents))
    for key in ("profile", "serial", "source_image_sha256", "known_pair", "parents"):
        if report[key] != expected[key]:
            raise ValueError("Fixed recipe/parent evidence changed")
    ops = report["operations"]
    if len(ops) != 2 or [op["phase"] for op in ops] != ["boot", "recovery-block1"]:
        raise ValueError("Only boot0 then recovery0x4200 permitted")
    if ops[0]["name"] == ops[1]["name"]:
        raise ValueError("Independent per-target scratch nonces required")
    for op in ops:
        probe.command(op, probe.BUFFER, 4096)
        targets.validate_producer(op)
        if (op["source_address"], op["source_bytes"], op["transport_profile"], op["oracle"]) != (
            hex(probe.BUFFER),
            4096,
            "interval6-ce1",
            targets.oracle(op["phase"])[2],
        ):
            raise ValueError("Operation source/target oracle differs from fixed recipe")
    raw = (directory / "session.btsnoop").read_bytes()
    parser = Snoop()
    parser.feed(raw, final=True)
    if report["hci_capture"] != {"bytes": len(raw), "sha256": audit.sha(raw), "records": parser.records}:
        raise ValueError("Final private capture changed")
    from types import SimpleNamespace

    finalize(report, directory, SimpleNamespace(path=directory / "session.btsnoop", snoop=parser))
    if (
        report.get("ok") is not True
        or report.get("error")
        or report.get("final_evidence_error")
        or report.get("after_error")
    ):
        raise ValueError("Session was not fully successful; retain individual checkpoints")
    if not all(op.get("live_complete") and op.get("ok") for op in ops):
        raise ValueError("Requires both independently complete known targets")
    return {
        "verified": True,
        "connections": 1,
        "targets": [0, 0x4200],
        "sector_sha256": [op["verification"]["sector_sha256"] for op in ops],
    }


async def capture(report, out):
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != H.PEER:
        raise ValueError("Scanned peer differs from owned public address")
    monitor = Monitor(out, snoop=Snoop())
    failure = None
    try:
        await monitor.start()
        async with asyncio.timeout(45):
            async with DualConnection(device, report) as conn:
                await connected(conn, monitor, report, out)
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            report["monitor_stop"] = monitor.stop
            report["monitor_exit"] = await monitor.close()
            finalize(report, out, monitor)
        except BaseException as error:
            report["final_evidence_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


def main(
    image: Path, known_first: Path, known_second: Path, new_out: Path, sudo_password_stdin: bool = False
):
    report = prepare(image, known_first, known_second)
    new_out.mkdir(parents=True, exist_ok=False, mode=0o700)
    for op in report["operations"]:
        (new_out / op["phase"]).mkdir(mode=0o700)
    try:
        authorize(password_stdin=sudo_password_stdin)
        asyncio.run(capture(report, new_out))
        if not all(op["ok"] for op in report["operations"]):
            raise ValueError("Both known targets must fully pass")
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = now()
        save(new_out / "report.json", report)
    print(json.dumps({"ok": True, "known_sectors": 2, "connections": 1}))


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
