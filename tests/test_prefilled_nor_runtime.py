"""Dry runtime replays synthetic owned wire; never device execution evidence."""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_prefilled_nor_control import RAM, fixture

from rcominote.experiments import prefilled_nor_control as C
from rcominote.experiments import prefilled_nor_runtime as R


@pytest.mark.parametrize(
    "failure,error_type",
    [
        (None, ValueError),
        *[
            (index, error)
            for index in range(5)
            for error in (ValueError, TimeoutError, asyncio.CancelledError)
        ],
    ],
)
@pytest.mark.parametrize("v2", [False, True, "unknown"])
def test_complete_runtime_pass_and_any_download_failure_stop_later_writes(tmp_path, failure, error_type, v2):
    source, out = tmp_path / "source", tmp_path / "out"
    job = None
    if v2 == "unknown":
        from test_prefilled_nor_pages import fixture as unknown_fixture

        original, job, plan, baseline = unknown_fixture(source)
        source = source / job["pages"][0]["directory"]
        out.mkdir()
        (out / "plan.json").write_text(json.dumps(job))
        out = out / job["pages"][0]["directory"]
        oracles = {}
    else:
        original, plan, baseline, oracles = fixture(source)
    if v2 is True:
        from test_prefilled_nor_v2 import upgrade

        with patch.object(C.C.pins, "oracles", return_value=oracles):
            upgrade(source, original, plan, baseline)
    out.mkdir()
    if job is None:
        (out / "plan.json").write_text(json.dumps(plan))
    for label in ("baseline", *(op["operation_id"] for op in plan["operations"])):
        (out / label).mkdir()
    with patch.object(C, "RAM_SHA", C.A.A.sha(RAM)), patch.object(C.C.pins, "oracles", return_value=oracles):
        actual = C.C.report(plan) if job else C.report(plan)
    actual.update(
        {
            k: copy.deepcopy(v)
            for k, v in original.items()
            if k
            not in (
                *C.FIELDS,
                "baseline",
                "operations",
                "plan",
                "before",
                "after",
                "before_span",
                "after_span",
                "predecessor_state_verification",
                "state_verification",
            )
        }
    )
    actual["plan"] = (
        C.C.J.reference(out.parent, out.parent / "plan.json")
        if job
        else C.C.J.reference(out, out / "plan.json")
    )
    actual["att_packets"] = copy.deepcopy(original["att_packets"][: original["setup_end"]])
    raw = (source / "session.btsnoop").read_bytes()
    (out / "session.btsnoop").write_bytes(raw)
    observed = C.A.P.inspect(raw, link=original["transport"]["link"], final=True)
    wire = C.A.common.wire_positions(original, raw)
    owners = {op["operation_id"]: op for op in [original["baseline"], *original["operations"]]}
    cursor, calls, identities = [1], [], []

    def trace(end):
        actual["att_packets"] = copy.deepcopy(original["att_packets"][:end])

    async def identity(_conn, owner, key, state, **_kwargs):
        identities.append(key)
        owner[key] = copy.deepcopy(original[key])
        owner[f"{key}_span"] = original[f"{key}_span"].copy()
        owner["predecessor_state_verification" if key == "before" else "state_verification"] = (
            C.A.verify_state(state, owner[key], sd_write=False)
        )
        trace(owner[f"{key}_span"][1])

    async def files():
        trace(original["file_list_span"][1])
        return []

    async def commands(op, body, *, sd_write_command_index):
        assert body == C.recipe(op)[2:-1]
        assert sd_write_command_index == (0 if op["kind"] == "prefill" else 2)
        expected = owners[op["operation_id"]]
        keys = (
            "notifications",
            "writes",
            "frames",
            "actions_start",
            "actions_end",
            "ack_count",
            "end_received",
            "pending_hex",
            "log_session_complete",
            "sd_write_attempted",
        )
        op.update({k: copy.deepcopy(expected[k]) for k in keys})
        trace(op["actions_end"])

    async def normalize(_m, _c, _report, op, index):
        op.update(
            normalization=observed["transactions"][index],
            normalization_requested_us=owners[op["operation_id"]]["normalization_requested_us"],
        )
        cursor[0] = index + 1

    async def download(_conn, _report, op, target):
        calls.append(op["operation_id"])
        data = (source / op["operation_id"] / "download.bin").read_bytes()
        if len(calls) - 1 == failure:
            (target / "download.bin").write_bytes(b"actual partial")
            raise error_type("bounded download failure")
        for key in (
            "download_start",
            "download_end",
            "download_bytes",
            "received_bytes",
            "download_sha256",
            "download_verification",
        ):
            op[key] = copy.deepcopy(owners[op["operation_id"]][key])
        (target / "download.bin").write_bytes(data)
        trace(op["download_end"])
        return data

    async def finish(_c, _m, _report, op, index, _state, **_kwargs):
        expected = owners[op["operation_id"]]
        op.update(
            {
                k: copy.deepcopy(expected[k])
                for k in ("after", "after_span", "state_verification", "verified_end", "slow_settlement")
            }
        )
        op["barrier_complete"] = True
        cursor[0] = index + 1
        trace(op["verified_end"])

    async def fast(*_args, cursor, required):
        assert required
        tx = observed["transactions"][cursor]
        ledger[0] = cursor + 1
        return [tx]

    ledger = cursor
    clock = [owner[k] for owner in owners.values() for k in ("started_at", "ended_at")]
    actions = SimpleNamespace(run_commands=AsyncMock(side_effect=commands))
    with (
        patch.object(C, "RAM_SHA", C.A.A.sha(RAM)),
        patch.object(C.C.pins, "oracles", return_value=oracles),
        patch.object(C, "ram_source", return_value=(RAM, plan["ram_oracle"])),
        patch.object(C.C.S, "now", side_effect=clock),
        patch.object(R.transfer, "identity", new=AsyncMock(side_effect=identity)),
        patch.object(
            C.C.startup,
            "wait_startup",
            new=AsyncMock(return_value=(original["startup_settlement"], original["startup_classification"])),
        ),
        patch.object(
            C.C.startup,
            "live_wire",
            new=AsyncMock(
                side_effect=lambda *_: (
                    actual,
                    {"transactions": observed["transactions"][: cursor[0]], "pending": []},
                    wire[: len(actual["att_packets"])],
                )
            ),
        ),
        patch.object(
            R.shared.R,
            "observe",
            side_effect=lambda *_: {"transactions": observed["transactions"][: cursor[0]], "pending": []},
        ),
        patch.object(R.shared.R, "normalize", new=AsyncMock(side_effect=normalize)),
        patch.object(R.transfer, "download", new=AsyncMock(side_effect=download)),
        patch.object(R.transfer, "finish_stage", new=AsyncMock(side_effect=finish)),
        patch.object(R.shared.N, "pre_download_fast", new=AsyncMock(side_effect=fast)),
    ):
        if failure is None:
            asyncio.run(
                R.connected(
                    SimpleNamespace(file_list=AsyncMock(side_effect=files)),
                    actions,
                    None,
                    actual,
                    plan,
                    baseline,
                    out,
                )
            )
            actual["ended_at"] = original["ended_at"]
            proof = (
                R.pages.validate(actual, out, plan, baseline)
                if job
                else C.validate(actual, out, plan, baseline, RAM)
            )
            assert proof["parameter_transactions"] == 15 and proof["downloads"] == 5
            assert [op["actions_verification"]["acks"] for op in actual["operations"]] == [4, 6, 4, 6]
        else:
            with pytest.raises(error_type, match="bounded download failure"):
                asyncio.run(
                    R.connected(
                        SimpleNamespace(file_list=AsyncMock(side_effect=files)),
                        actions,
                        None,
                        actual,
                        plan,
                        baseline,
                        out,
                    )
                )
    assert len(calls) == (5 if failure is None else failure + 1)
    assert actions.run_commands.await_count == (4 if failure is None else failure)
    assert identities == (["before", "after"] if failure is None or error_type is ValueError else ["before"])
    assert actual["ok"] is False


@pytest.mark.parametrize("pending", [False, True])
def test_extra_fast_before_prefill_stops_before_any_actions(tmp_path, pending):
    op = {"kind": "prefill", "operation_id": "prefill-first"}
    context = {"cursor": 3, "state": {}, "previous_tx": {}}
    actual = {"transport": {"link": {}}}
    actions = SimpleNamespace(run_commands=AsyncMock())
    snapshot = {"transactions": [{}] * (3 if pending else 4), "pending": [{}] if pending else []}
    with (
        patch.object(R.shared.R, "observe", return_value=snapshot),
        pytest.raises(ValueError, match="before prefill/NOR"),
    ):
        asyncio.run(R.write_stage(None, actions, None, actual, op, context, tmp_path, RAM, {}))
    actions.run_commands.assert_not_called()


def test_wrong_actual_prefill_stops_before_nor_command(tmp_path):
    actions = SimpleNamespace(run_commands=AsyncMock())
    context = {"cursor": 6, "state": {}, "previous_tx": {}, "previous": b"R" * 4096}
    actual = {"transport": {"link": {}}}
    op = {"kind": "nor"}
    with (
        patch.object(R.shared.R, "observe", return_value={"transactions": [{}] * 6, "pending": []}),
        pytest.raises(ValueError, match="before actual full RAM"),
    ):
        asyncio.run(R.write_stage(None, actions, None, actual, op, context, tmp_path, RAM, {}))
    actions.run_commands.assert_not_called()


def test_fixed_one_body_prefill_has_four_acks_and_marks_only_actual_dump_as_write():
    from test_dual_probe import fake_actions

    async def run():
        actions, conn = fake_actions()
        op = {
            "kind": "prefill",
            "operation_id": "prefill-first",
            "name": C.C.F.NAME,
            "dump_command": C.RAM_DUMP,
        }
        expected = C.recipe(op)
        original, states = conn.client.action_write.side_effect, []

        async def send(packet):
            states.append(op["sd_write_attempted"])
            await original(packet)

        conn.client.action_write.side_effect = send
        await actions.run_commands(op, expected[2:-1], sd_write_command_index=0)
        assert [call.args[0] for call in conn.client.action_write.await_args_list] == expected
        assert states == [False, False, True, True]
        assert op["ack_count"] == 4 and op["log_session_complete"] and op["pending_hex"] == ""

    asyncio.run(run())


def test_one_body_cancelled_cleanup_stop_is_two_seconds_and_retains_original_failure():
    from test_dual_probe import fake_actions

    from rcominote.log_capture import START, STOP

    timeout = asyncio.timeout

    async def run():
        actions, conn = fake_actions()
        original = conn.client.action_write.side_effect

        async def send(packet):
            if packet == START:
                raise asyncio.CancelledError("prefill cancelled")
            if packet == STOP:
                await asyncio.sleep(1)
            await original(packet)

        conn.client.action_write.side_effect = send
        op = {}
        with pytest.raises(asyncio.CancelledError, match="prefill cancelled"):
            await actions.run_commands(op, [b"fixedRAMdump"], sd_write_command_index=0)
        assert op["cleanup_error"] == "TimeoutError: " and not op["sd_write_attempted"]
        assert [call.args[0] for call in conn.client.action_write.await_args_list].count(STOP) == 1

    with patch.object(
        asyncio, "timeout", side_effect=lambda seconds: timeout(0.001 if seconds == 2 else seconds)
    ) as bounded:
        asyncio.run(run())
    assert any(call.args == (2,) for call in bounded.call_args_list)
