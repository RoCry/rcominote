"""Canonical address constants only; value-token spaces remain data evidence."""

import pytest
from test_nor_freshness import echo, place
from test_scratch_reuse_parser import NONCE, OTHER, SECTOR, chain

from rcominote.experiments import nor_freshness as old
from rcominote.experiments import scratch_reuse_parser as F


def parse(current, previous, nonce=NONCE):
    return F._parse_ring(current, previous, nonce=nonce, nor_offset=0x24A00, prefix_policy=F.PADDING_POLICY)


def padding_case():
    body = chain(NONCE, 0x24A00)
    at = body.index(b"       0:") + 28 * 60
    current = place(body, (4095 - at) % 4096)
    previous = bytearray(b"." * 4096)
    previous[4095] = 0x20
    return current, bytes(previous)


def test_one_unchanged_address_leading_space_preserves_original_prefix_and_old_rejection():
    current, previous = padding_case()
    sector, proof = parse(current, previous)
    assert sector == SECTOR
    assert proof["difference_proven_written_prefix_bytes"] == 4095
    assert proof["address_padding_exemptions"] == [
        {"physical_index": 4095, "row_index": 28, "column": 0, "current": "20", "previous": "20"}
    ]
    assert "critical_chain_inside_written_prefix" not in proof
    assert proof["critical_nonpadding_chain_inside_written_prefix"]
    with pytest.raises(ValueError, match="difference-proven"):
        F._parse_ring(current, previous, nonce=NONCE, nor_offset=0x24A00)


def test_prior_row_newline_outside_prefix_is_not_address_padding():
    current, previous = padding_case()
    previous = bytearray(previous)
    assert current[4094] == 0x0A
    previous[4094] = current[4094]
    with pytest.raises(ValueError, match="difference-proven"):
        parse(current, bytes(previous))


def test_unchanged_value_high_space_cannot_turn_actual14_into_retained04():
    # Parser-level sequential-short-write countermodel, not an admitted live parent.
    target = bytes([0x14]) + SECTOR[1:]
    body = chain(NONCE, 0x24A00, target)
    high = body.index(b"       0:") + 10
    current = place(body, (4095 - high) % 4096)
    assert current[4095] == ord("1") and current[0] == ord("4")
    previous = bytearray(b"." * 4096)
    previous[4095], previous[0] = ord(" "), ord("4")
    short = current[:4095] + bytes(previous[4095:])
    assert short[4095:] + short[:1] == b" 4"
    with pytest.raises(ValueError, match="difference-proven"):
        parse(short, bytes(previous))


@pytest.mark.parametrize("start", [0, 1500, 3000, 4095])
def test_every_prefix_cut_accepts_only_current_data_or_known_address_padding(start):
    previous = place(chain(OTHER, 0x24A00), 100)
    target = bytes(reversed(SECTOR))
    current = place(chain(NONCE, 0x24A00, target), start, initial=previous)
    for cut in range(4096):
        short = current[:cut] + previous[cut:]
        try:
            sector, proof = parse(short, previous)
        except ValueError:
            continue
        assert sector == target
        allowed = {item["physical_index"] for item in proof["address_padding_exemptions"]}
        for item in proof["address_padding_exemptions"]:
            assert item["column"] < 8 - len(f"{item['row_index'] * 16:x}")
            assert current[item["physical_index"]] == short[item["physical_index"]] == 0x20
        for key in ("nonce_span", "status_span", "rows_span", "producer_span", "dump_span"):
            a, b = proof[key]
            for index in range(a, b):
                at = index % 4096
                assert at < proof["difference_proven_written_prefix_bytes"] or at in allowed
                assert short[at] == current[at]


def test_old_rows_wrapped_other_filename_short_prefix_remains_rejected():
    body = chain(OTHER, 0x24A00)
    tail = body[body.index(b"\r\nfread") :].replace(F.NAME.encode(), b"rcaaaaaaaaaa")
    marker_at = tail.index(echo(F.DUMP.replace(F.NAME, "rcaaaaaaaaaa")))
    previous = place(tail, 4090 - marker_at)
    current = place(echo(F.DUMP), 4090, initial=previous)
    current = place(echo(f"kernel uptime {NONCE}"), 160, initial=current)
    current = place(b"flash read fail", 4090 - marker_at, initial=current)
    with pytest.raises(ValueError, match="difference-proven"):
        parse(current[:300] + previous[300:], previous)


@pytest.mark.parametrize("policy", [None, False, True, "unknown", []])
def test_unknown_or_non_string_policy_rejects(policy):
    with pytest.raises(ValueError, match="Unknown explicit"):
        F._parse_ring(b"", b"", nonce=NONCE, nor_offset=0x24A00, prefix_policy=policy)


def test_default_strict_proof_and_old_public_allowlists_remain_unchanged():
    current, previous = place(chain(), 100), b"." * 4096
    _sector, default = F.parse_ring(current, previous, nonce=NONCE, nor_offset=0)
    assert default["critical_chain_inside_written_prefix"] is True
    assert "prefix_policy" not in default and "address_padding_exemptions" not in default
    assert default["sector_sha256"] == old._sha(SECTOR)
    with pytest.raises(TypeError):
        F.parse_ring(current, previous, nonce=NONCE, nor_offset=0, prefix_policy=F.PADDING_POLICY)
