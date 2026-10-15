"""Isolated fixed Actions lifecycle; production Actions.run_commands is unchanged."""

import asyncio
import json
from pathlib import Path

import typer

from rcominote.ble_target import OWNED_SERIAL, find_device
from rcominote.experiments import actions_fast_control as C
from rcominote.experiments import paired_nor_runtime as capture_helpers
from rcominote.experiments import scratch_reuse_probe as identity
from rcominote.experiments import startup_ram_probe as closing
from rcominote.experiments import window_nor_probe as observer
from rcominote.experiments import window_ram_probe as R
from rcominote.experiments.dual_client import Actions, DualConnection
from rcominote.experiments.hci_interval_io import Monitor, active_link, authorize
from rcominote.experiments.hci_monitor import Snoop
from rcominote.log_capture import START, STOP
from rcominote.log_probe import NOTIFY, PREPARE
from rcominote.log_stream import Stream


class FixedActions(Actions):
    def receive(self, characteristic, data):
        super().receive(characteristic, data)
        if (
            self.failure is None
            and self.stream.ended
            and (
                self.stream.pending
                or self.stream.frames[-1]["command"] != 0xF1
                or sum(frame["command"] == 0xF1 for frame in self.stream.frames) != 1
            )
        ):
            self.failure = ValueError("F1 must terminate the exact original Actions stream")
            self.changed.set()

    async def run_control(self, op, plan, monitor, oracle):
        C.validate_plan(plan)
        if self.operation is not None or not self.conn.queue.empty() or self.conn.client._link.notifications:
            raise ValueError("Fixed Actions control overlaps queued traffic")
        self.operation, self.stream, self.failure, self.expected = op, Stream(), None, 0
        self.total_expected = 13
        op.update(
            notifications=[],
            writes=[],
            frames=self.stream.frames,
            sd_write_attempted=False,
            log_session_complete=False,
            actions_start=len(self.session["att_packets"]),
            started_at=C.C.S.now(),
            phase="start",
        )
        attempted, failure = False, None
        link = self.session["transport"]["link"]
        base = C.recipe(plan, 0)

        async def send(packet, *, cleanup=False):
            if self.expected >= 13:
                raise ValueError("Fixed Actions command budget exceeded")
            self.expected += 1
            row = {"hex": packet.hex(), "att_write_confirmed": False}
            op["writes"].append(row)
            if cleanup:
                async with asyncio.timeout(2):
                    await self.conn.client.action_write(packet)
            else:
                await self.conn.client.action_write(packet)
            row["att_write_confirmed"] = True
            if not cleanup:
                await self.wait(lambda: self.stream.acks >= self.expected)

        def window():
            value = R.observe(monitor, self.conn, link)
            if len(value["transactions"]) != index + 1 or R.logical_pending(value):
                raise ValueError("Applied6 target window changed or has pending negotiation")

        async with self.conn._transaction:
            try:
                await send(PREPARE)
                attempted = True
                await send(START)
                op["phase"] = "condition"
                mode = self.session["startup_classification"]["mode"]
                index = 1
                if mode == "default":
                    op["activity_fast"] = [
                        await R.wait_transaction(
                            monitor, self.conn, link, index=1, origin="remote", parameters=R.FAST, seconds=8
                        )
                    ]
                    index = 2
                else:
                    op["activity_fast"] = []
                await R.normalize(monitor, self.conn, self.session, op, index)
                window()
                op.update(
                    condition_applied=True, phase="target", burst_start=len(self.session["att_packets"])
                )
                await send(base[2])
                window()
                await send(base[3])
                for count in range(9):
                    window()
                    if C.parse(self.stream.frames, plan, oracle, incomplete=True) is not None:
                        break
                    if count == 8:
                        break  # STOP may flush the final text; acceptance follows F1.
                    op["fillers"] = count + 1
                    await send(C.packet(C.VERSION))
                window()
            except BaseException as error:
                failure = error
                raise
            finally:
                try:
                    if attempted:
                        self.total_expected = self.expected + 1
                        await send(STOP, cleanup=failure is not None)
                        if failure is None:
                            await self.wait(lambda: self.stream.ended)
                            if self.stream.pending or self.stream.acks != self.total_expected:
                                raise ValueError("Incomplete fixed Actions stream")
                            window()
                            op["content_verification"] = C.parse(self.stream.frames, plan, oracle)
                            op.update(log_session_complete=True, live_complete=True, phase="complete")
                except BaseException as error:
                    op["cleanup_error"] = f"{type(error).__name__}: {error}"
                    if failure is None:
                        raise
                finally:
                    op.update(
                        actions_end=len(self.session["att_packets"]),
                        ack_count=self.stream.acks,
                        end_received=self.stream.ended,
                        pending_hex=self.stream.pending.hex(),
                        ended_at=C.C.S.now(),
                    )
                    self.operation = None
                    if failure is not None or op.get("cleanup_error"):
                        self.conn._fail(RuntimeError("Fixed Actions control failed; session retired"))


async def initial(monitor, conn, actual, plan):
    # DEFAULT's subsequent activity FAST may already have settled before START.
    async with asyncio.timeout(12):
        while True:
            snapshot = R.observe(monitor, conn, actual["transport"]["link"])
            transactions = snapshot["transactions"]
            if len(transactions) > 2:
                raise ValueError("Extra startup parameter transactions before fixed control")
            if transactions:
                first = transactions[0]
                classification = C.C.startup.classify(first, policy=plan["startup_policy"])
                if len(transactions) == 2:
                    C.A.common.transaction(transactions[1], origin="remote", parameters=R.FAST)
                    if classification["mode"] != "default" or R.logical_pending(snapshot):
                        raise ValueError("Only DEFAULT followed by one actual settled FAST permitted")
                elif R.logical_pending(snapshot) and classification["mode"] == "fast":
                    raise ValueError("Pending parameter activity after startup FAST")
                if not snapshot["pending"]:
                    return first, classification
            await asyncio.sleep(0.05)


async def connected(conn, actions, monitor, actual, plan, oracle):
    failure = None
    try:
        await identity.identity(conn, actual, "before", plan["expected_before"])
        startup, classification = await initial(monitor, conn, actual, plan)
        actual.update(startup_settlement=startup, startup_classification=classification)
        await actions.run_control(actual["operation"], plan, monitor, oracle)
    except BaseException as error:
        failure = error
        raise
    finally:
        if isinstance(failure, (TimeoutError, asyncio.CancelledError)):
            actual["after_error"] = "Final identity omitted after timeout/cancellation; no new read command"
        else:
            try:
                await identity.identity(conn, actual, "after", actual["before"])
                R.observe(monitor, conn, actual["transport"]["link"])
            except BaseException as error:
                actual["after_error"] = f"{type(error).__name__}: {error}"
                if failure is None:
                    raise


async def capture(actual, plan, oracle, out):
    C.plan_gate(actual, plan, out)
    device = await find_device(serial=OWNED_SERIAL, seconds=12)
    if device.address.upper() != C.A.P.H.PEER:
        raise ValueError("Scan differs from fixed owned public peer")
    monitor = Monitor(out, snoop=Snoop(), seconds=70)
    failure = None
    try:
        async with asyncio.timeout(60):
            await monitor.start()
            conn = DualConnection(device, actual)
            observer.attach_status_observer(conn, actual)
            actions = FixedActions(conn, actual)
            connection_failure = None
            try:
                async with conn:
                    try:
                        await conn.client.start_notify(NOTIFY, actions.receive)
                        actual["setup_end"] = len(actual["att_packets"])
                        actual["gatt_proof"] = C.A.A.setup(actual)
                        actual["transport"]["link"] = active_link(conn)
                        await connected(conn, actions, monitor, actual, plan, oracle)
                    finally:
                        actual["close_requested_us"] = C.A.P.H.timestamp_us()
            except BaseException as error:
                connection_failure = error
                raise
            finally:
                actual["close_completed_us"] = C.A.P.H.timestamp_us()
                if actual["transport"].get("link"):
                    try:
                        await closing.observe_disconnect(monitor, actual)
                    except BaseException as error:
                        actual["disconnect_error"] = f"{type(error).__name__}: {error}"
                        if connection_failure is None:
                            raise
    except BaseException as error:
        failure = error
        actual["capture_error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        try:
            actual["monitor_stop"] = monitor.stop
            actual["monitor_exit"] = await monitor.close()
            raw = monitor.path.read_bytes()
            actual["hci_capture"] = {
                "bytes": len(raw),
                "sha256": C.A.A.sha(raw),
                "records": monitor.snoop.records,
            }
            if actual.get("att_packets") and actual["transport"].get("link"):
                actual["att_hci_binding"] = C.A.dual_hci.bind(actual, raw)
        except BaseException as error:
            actual["final_evidence_error"] = f"{type(error).__name__}: {error}"
            if failure is None:
                raise


def main(image: Path, planpath: Path, newout: Path, sudo_password_stdin: bool = False):
    capture_helpers.private_output(newout)
    raw = planpath.read_bytes()
    plan = json.loads(raw)
    oracle = C.source_gate(plan, image)
    newout.mkdir(parents=True, exist_ok=False, mode=0o700)
    (newout / "plan.json").write_bytes(raw)
    actual = C.report(plan) | {"plan": C.C.J.reference(newout, newout / "plan.json")}
    try:
        C.plan_gate(actual, plan, newout)
        if C.source_gate(plan, image) != oracle:
            raise ValueError("Historical state/oracle reference changed before authorization")
        authorize(password_stdin=sudo_password_stdin)
        C.plan_gate(actual, plan, newout)
        if C.source_gate(plan, image) != oracle:
            raise ValueError("Historical state/oracle reference changed before connection")
        asyncio.run(capture(actual, plan, oracle, newout))
        actual["ended_at"] = C.C.S.now()
        actual["verification"] = C.validate(actual, newout, plan, oracle)
        actual["ok"] = True
    except BaseException as error:
        actual["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        actual["ended_at"] = C.C.S.now()
        C.C.S.save(newout / "report.json", actual)


app = typer.Typer(pretty_exceptions_show_locals=False)
app.command()(main)
if __name__ == "__main__":
    app()
