"""Closed formatter roles; every NOR byte's TWO textual characters stay strict."""

import pytest
from test_nor_freshness import echo, place
from test_scratch_reuse_parser import NONCE, OTHER, SECTOR, chain
from test_scratch_reuse_status_policy import tail_at

from rcominote.experiments import nor_freshness as old
from rcominote.experiments import scratch_reuse_parser as F


def parse(current, previous, *, offset=0, policy=F.FORMAT_POLICY):
    return F._parse_ring(current, previous, nonce=NONCE, nor_offset=offset, prefix_policy=policy)


def test_fixed_row25_separator_at4095_does_not_relax_any_older_policy():
    text = chain()
    rows = old.STATUS.search(text).end() + 6
    current, previous = tail_at(text, rows + 25 * 60 + 42)
    assert current[4095] == previous[4095] == 0x20
    for policy in (F.STRICT_POLICY, F.PADDING_POLICY, F.STATUS_POLICY):
        with pytest.raises(ValueError, match="difference-proven"):
            parse(current, previous, policy=policy)
    sector, proof = parse(current, previous)
    assert sector == SECTOR and proof["difference_proven_written_prefix_bytes"] == 4095
    assert proof["formatter_constant_exemptions"] == [
        {
            "kind": "row-byte-separator",
            "physical_index": 4095,
            "row_index": 25,
            "column": 42,
            "expected": "20",
            "current": "20",
            "previous": "20",
        }
    ]
    assert proof["critical_variable_and_unexempted_chain_inside_written_prefix"]
    assert "critical_chain_inside_written_prefix" not in proof
    assert "critical_nonpadding_chain_inside_written_prefix" not in proof


def test_every_column_of_every_row_has_exact_independent_role():
    text = chain()
    rows = old.STATUS.search(text).end() + 6
    for row in range(32):
        for column in range(60):
            current, previous = tail_at(text, rows + row * 60 + column)
            token_character = 10 <= column <= 57 and (column - 10) % 3 in (0, 1)
            if token_character:
                with pytest.raises(ValueError, match="difference-proven"):
                    parse(current, previous)
            else:
                sector, proof = parse(current, previous)
                assert sector == SECTOR
                exemption = proof["formatter_constant_exemptions"][0]
                assert exemption["row_index"] == row and exemption["column"] == column
                assert exemption["expected"] == exemption["current"] == exemption["previous"]


def test_status_literals_stay_closed_while_both_capture_groups_and_crlf_stay_strict():
    text = chain()
    status = old.STATUS.search(text)
    constants = F._status_literals(status)
    for relative in range(len(status[0])):
        current, previous = tail_at(text, status.start() + relative)
        if relative in constants:
            _sector, proof = parse(current, previous)
            exemption = proof["formatter_constant_exemptions"][0]
            assert exemption["kind"] == "status-interior-literal"
            assert exemption["status_relative_index"] == relative
        else:
            with pytest.raises(ValueError, match="difference-proven"):
                parse(current, previous)


@pytest.mark.parametrize("which", ["high", "low"])
def test_retained_old_token_character_cannot_hide_changed_current_nor_byte(which):
    # Prefix short-write: desired14 text'14'; stale highspace yields04 (' 4'),
    # stale low0 yields10 ('10'). Each mixed row remains canonical but is false.
    text = chain(sector=bytes([0x14]) + SECTOR[1:])
    rows = old.STATUS.search(text).end() + 6
    at = rows + (10 if which == "high" else 11)
    current = place(text, (4095 - at) % 4096)
    old_token = b" " if which == "high" else b"0"
    previous = b"." * 4095 + old_token
    with pytest.raises(ValueError, match="difference-proven"):
        parse(current[:4095] + old_token, previous)


@pytest.mark.parametrize(
    "fault",
    [
        "address",
        "colon",
        "separator",
        "row-crlf",
        "status-literal",
        "status-crlf",
        "nonce-echo",
        "producer-echo",
        "dump-echo",
        "unknown-policy",
        "bool-policy",
    ],
)
def test_wrong_formatter_or_echo_never_becomes_exempt(fault):
    text, policy = chain(), F.FORMAT_POLICY
    if fault == "address":
        text = text.replace(b"       0:", b"      10:", 1)
    elif fault == "colon":
        text = text.replace(b"       0:", b"       0;", 1)
    elif fault == "separator":
        text = text.replace(b" 0  1 ", b" 0, 1 ", 1)
    elif fault == "row-crlf":
        text = text.replace(b" e  f \r\n", b" e  f \n\r", 1)
    elif fault == "status-literal":
        text = text.replace(b"buf=0x", b"buf=1x")
    elif fault == "status-crlf":
        text = text.replace(b"1804fe68\r\n", b"1804fe68\n\r")
    elif fault == "nonce-echo":
        text = text.replace(b"cmd(27)", b"cmd(26)", 1)
    elif fault == "producer-echo":
        text = text.replace(b"dbg fread spi_flash 0", b"dbg fread spi_flash 1")
    elif fault == "dump-echo":
        text = text.replace(b"Call-", b"Note-")
    else:
        policy = True if fault == "bool-policy" else "allow-all-unchanged-ASCII"
    with pytest.raises(ValueError):
        parse(place(text), b"." * 4096, policy=policy)


@pytest.mark.parametrize("which", ["nonce", "producer", "dump"])
def test_complete_command_echoes_remain_prefix_proven(which):
    text = chain()
    at = {
        "nonce": text.index(NONCE.encode()),
        "producer": text.index(b"dbg fread"),
        "dump": text.index(b"dbg dumpbuf"),
    }[which]
    current, previous = tail_at(text, at)
    with pytest.raises(ValueError, match="difference-proven"):
        parse(current, previous)


def test_wrapped_other_filename_prefix300_does_not_adopt_stale_rows():
    # Artificial parser-level model, not a real admitted current-file chain.
    body = chain(OTHER)
    status = body.index(b"\r\nfread")
    previous = place(body[status:].replace(F.NAME.encode(), b"rcaaaaaaaaaa"), 2041)
    actual = place(echo(F.DUMP), 4090, initial=previous)
    actual = place(echo(f"kernel uptime {NONCE}"), 160, initial=actual)
    actual = place(b"\r\nfread 512b: offset=0x0, buf=0x1804fe68\r\nflash read fail\r\n", 2041, initial=actual)
    with pytest.raises(ValueError, match="difference-proven"):
        parse(actual[:300] + previous[300:], previous)


@pytest.mark.parametrize("start", [1500, 4095])
def test_every_physical_prefix_cut_keeps_all_variable_current_bytes(start):
    previous = place(chain(OTHER, 0), 100)
    wanted = bytes(reversed(SECTOR))
    full = place(chain(NONCE, 0x4200, wanted), start, initial=previous)
    for cut in range(4096):
        mixed = full[:cut] + previous[cut:]
        try:
            sector, proof = parse(mixed, previous, offset=0x4200)
        except ValueError:
            continue
        assert sector == wanted and proof["critical_variable_and_unexempted_chain_inside_written_prefix"]


def test_equal_variable_f_at_column41_is_rejected_at_every_row():
    # Mirrors the newly observed reused-file failure: physical4095 is low hex
    # nibble'f' at col41 (11+3*10), not a deterministic trailing separator.
    text = chain(sector=bytes([0x0F]) * 512)
    rows = old.STATUS.search(text).end() + 6
    for row in range(32):
        current, previous = tail_at(text, rows + row * 60 + 41)
        assert current[4095] == previous[4095] == ord("f")
        with pytest.raises(ValueError, match="difference-proven"):
            parse(current, previous)
