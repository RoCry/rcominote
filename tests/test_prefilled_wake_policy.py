"""Closed wake-lock-zero grammar; synthetic rings never promote old failures."""

import json
from unittest.mock import patch

import pytest
from test_nor_freshness import place
from test_paired_nor_audit import replace_download
from test_prefilled_nor_control import RAM
from test_prefilled_nor_pages import fixture
from test_scratch_reuse_parser import NONCE, SECTOR, chain

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_nor_pages as N
from rcominote.experiments import scratch_reuse_parser as F

PLAIN = b"\n" + F.F.LOG_PREFIX
GAPS = [
    PLAIN,
    b"\n" + F.F.COMPOSER_FPS2 + F.F.LOG_PREFIX,
    b"\n\r\n" + F.F.COMPOSER_FPS2 + F.F.LOG_PREFIX[2:],
    F.WAKE_GAP,
]


def parse(data, previous=None):
    return F._parse_ring(
        data,
        b"." * 4096 if previous is None else previous,
        nonce=NONCE,
        nor_offset=0x1ECC00,
        gap_policy=F.PREFILL_WAKE_GAP_POLICY,
    )


def text(gap):
    return gap.join(chain(NONCE, 0x1ECC00).rsplit(PLAIN, 1))


@pytest.mark.parametrize("gap", GAPS)
def test_four_exact_forms_keep_all_gap_bytes_and_prefix_binding(gap):
    data = place(text(gap), 300)
    sector, proof = parse(data)
    assert sector == SECTOR and proof["critical_chain_inside_written_prefix"]
    evidence = proof["producer_dump_gap"]
    assert evidence["inside_written_prefix"] is True and bytes.fromhex(evidence["hex"]) == gap
    assert (data * 2)[slice(*evidence["span"])] == gap
    if gap == F.WAKE_GAP:
        assert evidence["form"] == "wake-lock-zero"
        with pytest.raises(ValueError, match="Unexpected text"):
            F._parse_ring(
                data, b"." * 4096, nonce=NONCE, nor_offset=0x1ECC00, gap_policy=F.PREFILL_GAP_POLICY
            )


def test_every_byte_of_new53byte_notice_is_exact_not_normalized():
    assert len(F.WAKE_GAP) == 53
    for index in range(53):
        changed = bytearray(F.WAKE_GAP)
        changed[index] ^= 1
        with pytest.raises(ValueError):
            parse(place(text(bytes(changed)), 300))


@pytest.mark.parametrize(
    "gap",
    [
        F.WAKE_GAP * 2,
        F.WAKE_GAP.replace(b"lock 0", b"lock 1"),
        F.WAKE_GAP.replace(b"[os]", b"[xx]"),
        F.WAKE_GAP + b" ",
        F.WAKE_GAP.replace(b"lock 0", b"error"),
    ],
)
def test_no_other_os_notice_value_duplicate_or_failure_is_accepted(gap):
    with pytest.raises(ValueError):
        parse(place(text(gap), 300))


def test_each_gap_byte_outside_difference_prefix_rejects_even_with_matching_sector():
    body = text(F.WAKE_GAP)
    at = body.index(F.WAKE_GAP)
    for index in range(53):
        # Only this physical4095 byte is outside the proven copied prefix;
        # all commands/status/payload/dump wrap into lower proven addresses.
        data = place(body, (4095 - at - index) % 4096)
        previous = b"." * 4095 + data[-1:]
        with pytest.raises(ValueError, match="tail outside"):
            parse(data, previous)


def test_prefix300_stale_tail_and_old_nonce_cannot_be_completed_by_new_notice():
    previous = place(chain("rcfedcba9876", 0x1ECC00), 1800)
    current = place(text(F.WAKE_GAP), 160, initial=previous)
    with pytest.raises(ValueError):
        parse(current[:300] + previous[300:], previous)
    with pytest.raises(ValueError, match="future nonce absent"):
        parse(current, place(NONCE.encode(), 0))


def test_known_prefill_public_entry_remains_three_forms_only():
    with pytest.raises(ValueError, match="original three-layout"):
        F.parse_prefilled_ring(
            b"x" * 4096, RAM, b"." * 4096, nonce=NONCE, nor_offset=0, gap_policy=F.PREFILL_WAKE_GAP_POLICY
        )


def test_full_synthetic_unknown_pair_optin_replays_all15transactions_and_both_current_chains(tmp_path):
    actual, plan, _page, baseline = fixture(tmp_path)
    plan["gap_policy"] = actual["gap_policy"] = F.PREFILL_WAKE_GAP_POLICY
    path = tmp_path / plan["pages"][0]["directory"]
    history, previous = baseline, baseline
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
    ):
        page = C.page_plan(plan, 0, plan["expected_before"], plan["parent"]["ended_at"])
        for op in actual["operations"]:
            data = RAM
            if op["kind"] == "nor":
                body = F.WAKE_GAP.join(chain(op["nonce"], page["nor_offset"], SECTOR).rsplit(PLAIN, 1))
                data = place(body, 300 if op["operation_id"] == "first" else 2600, initial=history)
                replace_download(actual, path, op["operation_id"], data)
            op["verification"] = N.content(op, data, previous, RAM, page, history)
            if op["kind"] == "nor":
                history = data
            previous = data
        (tmp_path / "plan.json").write_text(json.dumps(plan))
        actual["plan"] = C.J.reference(tmp_path, tmp_path / "plan.json")
        result = N.validate(actual, path, page, baseline)
        assert result["pair_verified"] and result["gap_policy"] == F.PREFILL_WAKE_GAP_POLICY
        assert result["parameter_transactions"] == 15 and result["independent_oracle"] is False
        # Changing the policy on the original report cannot relabel this as old success.
        actual["gap_policy"] = F.PREFILL_GAP_POLICY
        with pytest.raises(ValueError):
            N.validate(actual, path, page, baseline)


@pytest.mark.parametrize("policy", [True, False, None, "other"])
def test_unknown_explicit_policy_rejects_before_parent_io(policy):
    with patch.object(C, "parent_gate") as parent, pytest.raises(ValueError):
        N.prepare(None, None, [0x1ECC00], gap_policy=policy)
    parent.assert_not_called()
