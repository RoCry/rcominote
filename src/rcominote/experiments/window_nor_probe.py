"""One bounded raw0x2400 pair with complete per-download parameter settlement."""

import asyncio
import json
from pathlib import Path

import typer

from rcominote import protocol as Boyi
from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import dual_nor_probe as S
from rcominote.experiments import dual_unknown_pair as U
from rcominote.experiments import hci_interval as H
from rcominote.experiments import param_window as P
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as events
from rcominote.experiments import window_nor_audit as evidence
from rcominote.experiments import window_nor_contract as C
from rcominote.experiments import window_ram_probe as R
from rcominote.experiments.dual_client import Actions, DualConnection
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize
from rcominote.experiments.hci_monitor import Snoop
from rcominote.experiments.sd_bootstrap import verify_state
from rcominote.log_probe import NOTIFY


def attach_status_observer(conn, report):
    """Observe original socket rows before dispatch; changed/unsupported events abort immediately."""
    if not events.enabled(report):
        return
    events.init(report)

    def observe(index, row):
        packet = bytes.fromhex(row["hex"])
        if row["direction"] == "rx" and packet[:3] == b"\x1b\x24\0":
            command, _ = Boyi.parse(packet[3:])
            if command not in (
                Boyi.GET_SERIAL,
                Boyi.GET_BIND_INFO,
                Boyi.GET_DEVICE_INFO,
                Boyi.GET_FILE_LIST,
                Boyi.GET_FILE_DATA,
                Boyi.DEVICE_STATUS_CHANGE,
            ):
                raise ValueError("Unsupported command notification in fixed status-window experiment")
        events.observe(report, index, row)

    conn.client.receive_observer = observe


async def pre_download_fast(monitor, conn, link, *, cursor, required, seconds=8):
    """Consume at most one real FAST; second operation must leave known SLOW first.

    Optional first-stage absence only describes the current wire observation.
    It never proves hidden cache emptiness; final audit still covers all traffic.
    """
    async with asyncio.timeout(seconds):
        while True:
            snapshot = R.observe(monitor, conn, link)
            extra = snapshot["transactions"][cursor:]
            pending = R.logical_pending(snapshot)
            if len(snapshot["transactions"]) < cursor or len(extra) > 1 or (extra and pending):
                raise ValueError("Extra or overlapping pre-download parameter transactions")
            if pending:
                if len(pending) != 1:
                    raise ValueError("Ambiguous pre-download parameter settlement")
                value = pending[0]
                if (
                    value.get("origin") != "remote"
                    or value.get("remote_request") is None
                    or P.parameters(value["remote_request"]) != R.FAST
                ):
                    raise ValueError("Only the bounded pre-download remote FAST is permitted")
            if extra:
                R.expected(extra[0], "remote", R.FAST)
                if not snapshot["pending"]:
                    return extra
            elif not snapshot["pending"] and not required:
                return []
            await asyncio.sleep(0.05)


async def download(conn, report, operation, directory):
    data = bytearray()

    def sink(chunk):
        if len(data) + len(chunk) > 4096:
            raise ValueError("Fixed ring4096 download overflow")
        data.extend(chunk)
        return len(chunk)

    operation["download_start"] = len(report["att_packets"])
    operation["download_started_us"] = H.timestamp_us()
    conn.offline_allowed = True
    try:
        operation["download_bytes"] = await conn.download(operation["name"], sink, offset=0, timeout=8)
        if operation["download_bytes"] != 4096 or len(data) != 4096:
            raise ValueError("Incomplete fixed ring4096 download")
    finally:
        conn.offline_allowed = False
        operation.update(
            received_bytes=len(data),
            download_sha256=A.sha(data),
            download_end=len(report["att_packets"]),
            download_ended_us=H.timestamp_us(),
        )
        with (directory / "download.bin").open("xb") as handle:
            handle.write(data)
    operation["download_verification"] = A.download(report, operation, bytes(data))


def decode(report, operation, directory):
    """Parse only after the actual slow settlement and identity barrier.

    Failure keeps the complete transport evidence and still prevents the next
    producer. Never strip background text or repair the retained ring.
    """
    if operation.get("barrier_complete") is not True:
        raise ValueError("NOR parsing must follow actual slow settlement and identity barrier")
    operation["verification"] = C.payload(report, operation, (directory / "download.bin").read_bytes())
    with (directory / "sector.bin").open("xb") as handle:
        handle.write(bytes.fromhex(operation["verification"]["sector_hex"]))


async def default_fast_proof(monitor, conn, report, operation):
    current, observed, wire = await startup.live_wire(monitor, conn, report)
    if (
        observed["pending"]
        or len(observed["transactions"]) != 2
        or (
            observed["transactions"][0] != report["startup_settlement"]
            or observed["transactions"][1:] != operation["pre_download_fast"]
        )
    ):
        raise ValueError("DEFAULT first Actions requires exactly the original startup and actual FAST")
    return evidence.default_activity_fast(
        current, operation, report["startup_settlement"], operation["pre_download_fast"][0], wire
    )


async def connected(conn, monitor, report, out):
    actions = Actions(conn, report)
    await conn.client.start_notify(NOTIFY, actions.receive)
    report["setup_end"] = len(report["att_packets"])
    report["gatt_proof"] = A.setup(report)
    report["transport"]["link"] = active_link(conn)
    link = report["transport"]["link"]
    failure = None
    try:
        await S.read_identity(conn, report, "before")
        verify_state(report["before"], report["before"], sd_write=False)
        if "expected_before" in report:
            report["predecessor_state_verification"] = verify_state(
                report["expected_before"], report["before"], sd_write=False
            )
        start = len(report["att_packets"])
        try:
            names = {entry.name for entry in await conn.file_list()}
            report["listed_count"] = len(names)
        finally:
            report["file_list_span"] = [start, len(report["att_packets"])]
        if any(op["name"] in names for op in report["operations"]):
            raise FileExistsError("Scratch nonce appears in actual list; no Actions attempted")
        report["visible_audio_list_no_collision"] = True
        if "startup_policy" in report:
            transaction, classification = await startup.wait_startup(
                monitor, conn, link, policy=report["startup_policy"], seconds=12
            )
            report.update(startup_settlement=transaction, startup_classification=classification)
        else:
            report["startup_settlement"] = await R.wait_transaction(
                monitor, conn, link, index=0, origin="remote", parameters=R.FAST, seconds=12
            )
        default_start = report.get("startup_classification", {}).get("mode") == "default"
        state, cursor = report["before"], 1
        for index, operation in enumerate(report["operations"]):
            operation.update(before=state, started_at=S.now())
            snapshot = R.observe(monitor, conn, link)
            if (
                default_start
                and index == 0
                and (len(snapshot["transactions"]) != cursor or snapshot["pending"])
            ):
                raise ValueError("Extra/pending traffic before DEFAULT first Actions; no producer attempted")
            await actions.run(operation)
            operation["actions_verification"] = A.actions(report, operation)
            operation["pre_download_fast"] = await pre_download_fast(
                monitor, conn, link, cursor=cursor, required=bool(index) or default_start
            )
            if default_start and index == 0:
                operation["default_activity_fast_verification"] = await default_fast_proof(
                    monitor, conn, report, operation
                )
            cursor += len(operation["pre_download_fast"])
            await R.normalize(monitor, conn, report, operation, cursor)
            cursor += 1
            await download(conn, report, operation, out / operation["operation_id"])
            operation["slow_settlement"] = await R.wait_transaction(
                monitor, conn, link, index=cursor, origin="remote", parameters=R.SLOW, seconds=8
            )
            cursor += 1
            await S.read_identity(conn, operation, "after")
            operation["state_verification"] = verify_state(state, operation["after"], sd_write=True)
            R.observe(monitor, conn, link)
            operation.update(verified_end=len(report["att_packets"]), barrier_complete=True)
            decode(report, operation, out / operation["operation_id"])
            operation.update(live_complete=True, ended_at=S.now())
            S.save(out / operation["operation_id"] / "checkpoint.json", report)
            state = operation["after"]
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            await S.read_identity(conn, report, "after")
            complete = [op for op in report["operations"] if op.get("live_complete")]
            pending = [
                op for op in report["operations"] if op["sd_write_attempted"] and not op.get("live_complete")
            ]
            if len(pending) > 1:
                raise ValueError("More than one unverified scratch write")
            report["state_verification"] = verify_state(
                complete[-1]["after"] if complete else report["before"],
                report["after"],
                sd_write=bool(pending),
            )
            R.observe(monitor, conn, link)
        except BaseException as error:
            report["after_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


async def capture(report, out, image):
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != H.PEER:
        raise ValueError("Scanned peer differs from owned public address")
    monitor = Monitor(out, snoop=Snoop())
    failure = None
    try:
        await monitor.start()
        async with asyncio.timeout(45):
            conn = DualConnection(device, report)
            attach_status_observer(conn, report)
            async with conn:
                await connected(conn, monitor, report, out)
    except BaseException as error:
        failure = error
        report["capture_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        try:
            report["monitor_stop"] = monitor.stop
            report["monitor_exit"] = await monitor.close()
            raw = monitor.path.read_bytes()
            report["hci_capture"] = {
                "bytes": len(raw),
                "sha256": A.sha(raw),
                "records": monitor.snoop.records,
            }
            if report.get("att_packets") and report["transport"].get("link"):
                report["att_hci_binding"] = dual_hci.bind(report, raw)
            if failure is None:
                report["verification"] = evidence.validate(report, out, image)
                report["final_audit_complete"] = True
                for operation in report["operations"]:
                    operation["ok"] = True
        except BaseException as error:
            report["final_evidence_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


def replay(directory: Path, image: Path) -> dict:
    report = json.loads((directory / "report.json").read_bytes())
    if (
        report.get("ok") is not True
        or report.get("pair_verified") is not True
        or report.get("final_audit_complete") is not True
        or not all(op.get("ok") is True for op in report["operations"])
    ):
        raise ValueError("Original NOR-window pair failed; retain without promotion")
    if evidence.validate(report, directory, image) != report["verification"]:
        raise ValueError("Original full window verification changed")
    result = U.compare_pair(report, directory, validate=C.recipe, parse=C.payload)
    if result != report["pair_verification"]:
        raise ValueError("Original complete fresh pair verification changed")
    return result


def main(
    image: Path, early_parent: Path, window_parent: Path, new_out: Path, sudo_password_stdin: bool = False
):
    report = C.prepare(image, early_parent, window_parent, 0x2400)
    report["final_audit_complete"] = False
    new_out.mkdir(parents=True, exist_ok=False, mode=0o700)
    for operation in report["operations"]:
        (new_out / operation["operation_id"]).mkdir(mode=0o700)
    try:
        authorize(password_stdin=sudo_password_stdin)
        asyncio.run(capture(report, new_out, image))
        report["pair_verification"] = U.compare_pair(report, new_out, validate=C.recipe, parse=C.payload)
        report["pair_verified"] = True
        report["ok"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["ended_at"] = S.now()
        S.save(new_out / "report.json", report)
    print(json.dumps({"ok": True, "pair_verified": True, "new_verified_bytes": 512}))


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)

if __name__ == "__main__":
    app()
