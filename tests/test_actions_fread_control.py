"""Synthetic direct printk visibility; no fixture is an actual NOR observation."""

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from test_actions_fast_control import echo, f0
from test_actions_fast_control import fixture as ram_fixture

from rcominote.experiments import actions_fast_control as C
from rcominote.experiments import actions_fast_runtime as R
from rcominote.experiments import actions_fread_control as F
from rcominote.log_capture import STOP
from rcominote.log_probe import ACK
from rcominote.log_stream import Stream

ORACLE = bytes(range(256)) * 2


def plan_fixture(root):
    _actual, plan = ram_fixture(root / "ram")
    del plan["mdb_command"], plan["ram_oracle"]
    plan.update(
        profile=F.PROFILE,
        producer_command=F.PRODUCER,
        nor_offset=0,
        budget=F.BUDGET.copy(),
        oracle_bytes=512,
        oracle_slice=[0, 512],
        oracle_sha256=C.A.A.sha(ORACLE),
        nor_oracle={"nor_offset": 0, "bytes": 512, "sha256": C.A.A.sha(ORACLE)},
    )
    return plan


def body(plan, data=ORACLE):
    rows = b"".join(
        (f"{i * 16:8x}: " + "".join(f"{b:2x} " for b in data[i * 16 : (i + 1) * 16]) + "\r\n").encode()
        for i in range(32)
    )
    return (
        echo(plan["marker_command"])
        + b"\r\nfread 512b: offset=0x0, buf=0x1804fe68\r\n"
        + b"\r\n" * 3
        + rows
        + F.F.LOG_PREFIX
        + echo(F.PRODUCER)
    )


def frames(text):
    stream = Stream()
    for at in range(0, len(text), 504):
        stream.feed(f0(text[at : at + 504]))
    return stream.frames


@pytest.mark.parametrize("mode,fillers", [("fast", 0), ("default", 0), ("fast", 8)])
def test_full_synthetic_wire_boot0_visibility_requires_current512_and_applied6(tmp_path, mode, fillers):
    plan = plan_fixture(tmp_path)
    actual, plan = ram_fixture(
        tmp_path / "nor", mode=mode, fillers=fillers, plan_override=plan, oracle=ORACLE, output=body(plan)
    )
    proof = C.validate(actual, tmp_path / "nor", plan, ORACLE)
    assert proof["bytes"] == 512 and proof["acks"] == 5 + fillers
    assert proof["new_raw_nor_coverage_bytes"] == proof["sd_writes"] == 0
    assert proof["content"]["rows"] == 32 and "target_span" in proof["text_origin"]
    assert not proof["content"]["oracle_used_to_select_chain"]
    assert F.producer_packet()[8:] == F.PRODUCER.encode()


@pytest.mark.parametrize("early", [True, "partial"])
def test_even_partial_status_or_rows_before_fread_tx_cannot_certify_current_read(tmp_path, early):
    plan = plan_fixture(tmp_path)
    actual, plan = ram_fixture(
        tmp_path / "nor", plan_override=plan, oracle=ORACLE, output=body(plan), early_data=early
    )
    with pytest.raises(ValueError, match="precede their actual command"):
        C.validate(actual, tmp_path / "nor", plan, ORACLE)


@pytest.mark.parametrize(
    "fault",
    [
        "no-body",
        "partial",
        "order",
        "address",
        "high-space",
        "delimiter",
        "wrong-offset",
        "echo-length",
        "newline-echo",
        "failure",
        "late-failure",
        "other-producer",
        "duplicate",
        "oracle",
        "old-marker",
    ],
)
def test_ack_status_and_matching_partial_data_cannot_replace_one_full_chain(tmp_path, fault):
    plan = plan_fixture(tmp_path)
    text = body(plan)
    first = text.index(b"       0: ")
    if fault == "no-body":
        text = text[:first] + text[first + 32 * 60 :]
    elif fault == "partial":
        text = text[: first + 31 * 60] + text[first + 32 * 60 :]
    elif fault == "order":
        text = text[:first] + text[first + 60 : first + 120] + text[first : first + 60] + text[first + 120 :]
    elif fault == "address":
        text = text[:first] + b"     100" + text[first + 8 :]
    elif fault == "high-space":
        text = text[: first + 10] + b"0" + text[first + 11 :]
    elif fault == "delimiter":
        text = text[: first + 12] + b"\t" + text[first + 13 :]
    elif fault == "wrong-offset":
        text = text.replace(b"offset=0x0", b"offset=0x200")
    elif fault == "echo-length":
        text = text.replace(
            echo(F.PRODUCER),
            echo(F.PRODUCER).replace(f"cmd({len(F.PRODUCER)})".encode(), b"cmd(99)"),
        )
    elif fault == "newline-echo":
        text = text.replace(echo(F.PRODUCER), echo(F.PRODUCER).replace(b"\r\n\n", b"\n\r\n"))
    elif fault == "failure":
        text = text[:first] + b"fread failed\r\n" + text[first:]
    elif fault == "late-failure":
        text += b"\r\nfread failed\r\n"
    elif fault == "other-producer":
        text += echo("dbg fread spi_flash 0x200")
    elif fault == "duplicate":
        text += text
    elif fault == "old-marker":
        text = text.replace(plan["marker"].encode(), b"afcffffffffffffffff")
    else:
        with pytest.raises(ValueError, match="oracle"):
            C.parse(frames(text), plan, ORACLE[::-1])
        return
    with pytest.raises(ValueError):
        C.parse(frames(text), plan, ORACLE)


@pytest.mark.parametrize("bad", ["offset", "command", "ram-profile", "write-budget"])
def test_plan_and_packet_allowlists_cannot_be_used_as_general_nor_console(tmp_path, bad):
    plan = plan_fixture(tmp_path)
    if bad == "offset":
        plan["nor_offset"] = 512
    elif bad == "command":
        plan["producer_command"] = "dbg fread spi_flash 0x200"
    elif bad == "ram-profile":
        plan["profile"] = C.PROFILE
    else:
        plan["budget"]["sd_writes"] = True
    with pytest.raises((ValueError, KeyError)):
        C.validate_plan(plan)
    with pytest.raises(ValueError):
        C.packet(F.PRODUCER)  # Historical RAM encoder's public allowlist stays fixed.


def test_host_source_checks_original_raw_oracle_and_historical_identity_only(tmp_path):
    expected = plan_fixture(tmp_path)
    source = expected["state_reference"] | {
        "references": {"report": expected["state_reference"]["historical_report"]},
        "baseline_sha256": "historical-not-current",
    }
    with (
        patch.object(C.C, "parent_gate", return_value=(b"not current", expected["expected_before"], source)),
        patch.object(F, "oracle_source", return_value=(ORACLE, expected["nor_oracle"])),
    ):
        plan, data = F.prepare(tmp_path / "image", tmp_path)
        assert F.source_gate(plan, tmp_path / "image") == data == ORACLE
        assert "baseline_sha256" not in plan["state_reference"]
        changed = copy.deepcopy(plan)
        changed["nor_oracle"]["proof"] = {"filled_from_mapped": True}
        with pytest.raises(ValueError, match="independent raw"):
            C.source_gate(changed, tmp_path / "image")


@pytest.mark.parametrize(
    "mode,fault", [("fast", None), ("default", None), ("fast", "missing-body"), ("default", "missing-fast")]
)
def test_fixed_runtime_one_producer_or_preburst_stop_and_retains_original_stream(tmp_path, mode, fault):
    plan = plan_fixture(tmp_path)
    actual, _ = ram_fixture(tmp_path / "nor", mode=mode, plan_override=plan, oracle=ORACLE, output=body(plan))
    session = C.report(plan) | {
        "transport": actual["transport"],
        "startup_classification": actual["startup_classification"],
        "att_packets": [],
    }
    conn = SimpleNamespace(
        queue=asyncio.Queue(), _transaction=asyncio.Lock(), offline_allowed=False, _check_failure=lambda: None
    )
    conn._fail = lambda error: setattr(conn, "failure", error)
    conn.client = SimpleNamespace(_link=SimpleNamespace(notifications=[]))
    actions = R.FixedActions(conn, session)
    ledger = [1]
    normalized = [False]

    async def send(packet):
        if packet == F.producer_packet():
            assert normalized[0]
        actions.receive(None, ACK)
        if packet == F.producer_packet() and fault is None:
            for row in frames(body(plan)):
                actions.receive(None, bytes.fromhex(row["hex"]))
        if packet == STOP:
            actions.receive(None, b"\x1d\xf1\x81\0\0")

    async def settle(*_args, **_kwargs):
        if fault == "missing-fast":
            raise TimeoutError("expected FAST not applied")
        ledger[0] = 2
        return actual["operation"]["activity_fast"][0]

    async def normalize(*_args):
        normalized[0] = True
        ledger[0] += 1

    conn.client.action_write = AsyncMock(side_effect=send)
    with (
        patch.object(R.R, "normalize", new=AsyncMock(side_effect=normalize)),
        patch.object(R.R, "wait_transaction", new=AsyncMock(side_effect=settle)),
        patch.object(
            R.R, "observe", side_effect=lambda *_: {"transactions": [{}] * ledger[0], "pending": []}
        ),
    ):
        if fault:
            with pytest.raises((ValueError, TimeoutError)):
                asyncio.run(actions.run_control(session["operation"], plan, None, ORACLE))
        else:
            asyncio.run(actions.run_control(session["operation"], plan, None, ORACLE))
    writes = [call.args[0] for call in conn.client.action_write.await_args_list]
    assert writes.count(F.producer_packet()) == (0 if fault == "missing-fast" else 1)
    assert writes.count(STOP) == 1 and len(writes) <= 13
    assert session["operation"]["sd_write_attempted"] is False
    assert bool(session["operation"].get("live_complete")) == (fault is None)
