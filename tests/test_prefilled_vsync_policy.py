"""Exact observed vsync99999 line, not wildcard acceptance of a %u formatter."""

import json
from unittest.mock import patch

import pytest
from test_nor_freshness import place
from test_paired_nor_audit import replace_download
from test_prefilled_nor_control import RAM
from test_prefilled_nor_pages import fixture
from test_prefilled_wake_policy import GAPS, PLAIN
from test_scratch_reuse_parser import NONCE, SECTOR, chain

from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_nor_pages as N
from rcominote.experiments import scratch_reuse_parser as F


def text(gap):
    return gap.join(chain(NONCE, 0x1EDA00).rsplit(PLAIN, 1))


def parse(data, previous=b"." * 4096):
    return F._parse_ring(
        data, previous, nonce=NONCE, nor_offset=0x1EDA00, gap_policy=F.PREFILL_VSYNC_GAP_POLICY
    )


@pytest.mark.parametrize("gap", [*GAPS, F.VSYNC_GAP])
def test_v4_keeps_five_exact_forms_and_each_gap_byte_prefix_proven(gap):
    data = place(text(gap), 300)
    sector, proof = parse(data)
    assert sector == SECTOR and proof["critical_chain_inside_written_prefix"]
    evidence = proof["producer_dump_gap"]
    assert evidence["inside_written_prefix"] and bytes.fromhex(evidence["hex"]) == gap
    assert (data * 2)[slice(*evidence["span"])] == gap
    if gap == F.VSYNC_GAP:
        assert evidence["form"] == "vsync-exact-99999" and len(gap) == 58
        for old in (None, F.PREFILL_GAP_POLICY, F.PREFILL_WAKE_GAP_POLICY):
            with pytest.raises(ValueError, match="Unexpected text"):
                F._parse_ring(data, b"." * 4096, nonce=NONCE, nor_offset=0x1EDA00, gap_policy=old)


def test_all58_literal_bytes_are_fixed_and_never_skipped_outside_written_prefix():
    body = text(F.VSYNC_GAP)
    at = body.index(F.VSYNC_GAP)
    for index in range(58):
        changed = bytearray(F.VSYNC_GAP)
        changed[index] ^= 1
        with pytest.raises(ValueError):
            parse(place(text(bytes(changed)), 300))
        data = place(body, (4095 - at - index) % 4096)
        with pytest.raises(ValueError, match="tail outside"):
            parse(data, b"." * 4095 + data[-1:])


@pytest.mark.parametrize(
    "gap",
    [F.VSYNC_GAP.replace(b"99999", n) for n in (b"99998", b"100000", b"0", b"099999")]
    + [
        F.VSYNC_GAP * 2,
        F.VSYNC_GAP + b" ",
        F.VSYNC_GAP.replace(b"[335]", b"[336]"),
        F.VSYNC_GAP.replace(b"\n\r\n", b"\n", 1),
        F.VSYNC_GAP.replace(b"vsync", b"error"),
    ],
)
def test_dynamic_counter_not_wildcard_and_no_whitespace_normalization_or_other_line(gap):
    with pytest.raises(ValueError):
        parse(place(text(gap), 300))


def test_partial_prefix_stale_scope_and_known_public_entry_never_adopt_v4():
    previous = place(chain("rcfedcba9876", 0x1EDA00), 1800)
    current = place(text(F.VSYNC_GAP), 160, initial=previous)
    with pytest.raises(ValueError):
        parse(current[:300] + previous[300:], previous)
    for offset in (0, 0x4200):
        with pytest.raises(ValueError, match="original three-layout"):
            F.parse_prefilled_ring(
                current, RAM, previous, nonce=NONCE, nor_offset=offset, gap_policy=F.PREFILL_VSYNC_GAP_POLICY
            )


def test_full_synthetic_unknown_pair_v4_has_two_full_chains_and_all15_wire_transactions(tmp_path):
    actual, plan, _page, baseline = fixture(tmp_path)
    plan["gap_policy"] = actual["gap_policy"] = F.PREFILL_VSYNC_GAP_POLICY
    path = tmp_path / plan["pages"][0]["directory"]
    previous, history = baseline, baseline
    with (
        patch.object(P, "RAM_SHA", A.A.sha(RAM)),
        patch.object(P, "ram_source", return_value=(RAM, plan["ram_oracle"])),
    ):
        page = C.page_plan(plan, 0, plan["expected_before"], plan["parent"]["ended_at"])
        for op in actual["operations"]:
            data = RAM
            if op["kind"] == "nor":
                body = F.VSYNC_GAP.join(chain(op["nonce"], page["nor_offset"], SECTOR).rsplit(PLAIN, 1))
                data = place(body, 300 if op["operation_id"] == "first" else 2600, initial=history)
                replace_download(actual, path, op["operation_id"], data)
            op["verification"] = N.content(op, data, previous, RAM, page, history)
            if op["kind"] == "nor":
                history = data
            previous = data
        (tmp_path / "plan.json").write_text(json.dumps(plan))
        actual["plan"] = C.J.reference(tmp_path, tmp_path / "plan.json")
        proof = N.validate(actual, path, page, baseline)
        assert proof["pair_verified"] and proof["gap_policy"] == F.PREFILL_VSYNC_GAP_POLICY
        assert proof["parameter_transactions"] == 15 and proof["independent_oracle"] is False
