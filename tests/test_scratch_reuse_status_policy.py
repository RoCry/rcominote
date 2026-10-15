"""Template-role exemptions, never generic unchanged ASCII or oracle selection."""

import pytest
from test_nor_freshness import echo, place
from test_scratch_reuse_parser import NONCE, OTHER, SECTOR, chain

from rcominote.experiments import nor_freshness as old
from rcominote.experiments import scratch_reuse_parser as F


def tail_at(text, index):
    current = place(text, (4095 - index) % 4096)
    previous = bytearray(b"." * 4096)
    previous[4095] = current[4095]
    # Pure parser model; this artificial previous is not an admitted live receipt.
    return current, bytes(previous)


def parse(current, previous, *, policy=F.STATUS_POLICY, nonce=NONCE, offset=0):
    return F._parse_ring(current, previous, nonce=nonce, nor_offset=offset, prefix_policy=policy)


def test_fixed_status_zero_at_physical4095_has_exact_literal_role():
    text = chain()
    status = old.STATUS.search(text)
    position = status.start() + status[0].index(b"buf=0x") + 4
    current, previous = tail_at(text, position)
    for policy in (F.STRICT_POLICY, F.PADDING_POLICY):
        with pytest.raises(ValueError, match="difference-proven"):
            parse(current, previous, policy=policy)
    sector, proof = parse(current, previous)
    assert sector == SECTOR and proof["difference_proven_written_prefix_bytes"] == 4095
    assert proof["status_literal_exemptions"] == [
        {
            "kind": "status-interior-literal",
            "physical_index": 4095,
            "status_relative_index": 30,
            "expected": "30",
            "current": "30",
            "previous": "30",
        }
    ]
    assert "critical_chain_inside_written_prefix" not in proof
    assert "critical_nonpadding_chain_inside_written_prefix" not in proof
    assert proof["critical_variable_and_unexempted_chain_inside_written_prefix"]
    # Public known-control entry still defaults to its historical strict policy.
    with pytest.raises(ValueError, match="difference-proven"):
        F.parse_ring(current, previous, nonce=NONCE, nor_offset=0)


def test_every_status_position_excludes_captured_hex_and_crlf_boundaries():
    text = chain()
    status = old.STATUS.search(text)
    expected = F._status_literals(status)
    for relative in range(len(status[0])):
        current, previous = tail_at(text, status.start() + relative)
        if relative in expected:
            _sector, proof = parse(current, previous)
            assert proof["status_literal_exemptions"][0]["status_relative_index"] == relative
        else:
            with pytest.raises(ValueError, match="difference-proven"):
                parse(current, previous)
    assert all(
        i not in expected
        for n in (1, 2)
        for i in range(status.start(n) - status.start(), status.end(n) - status.start())
    )


def test_all_data_token_characters_and_separators_remain_prefix_proven():
    text = chain()
    rows = old.STATUS.search(text).end() + 6
    for row in range(32):
        for column in range(10, 58):
            current, previous = tail_at(text, rows + row * 60 + column)
            with pytest.raises(ValueError, match="difference-proven"):
                parse(current, previous)


@pytest.mark.parametrize("location", ["address-digit", "colon", "row-newline", "nonce", "producer", "dump"])
def test_other_critical_bytes_are_not_status_literal_exemptions(location):
    text = chain()
    rows = old.STATUS.search(text).end() + 6
    indices = {
        "address-digit": rows + 7,
        "colon": rows + 8,
        "row-newline": rows + 58,
        "nonce": text.index(NONCE.encode()),
        "producer": text.index(b"dbg fread"),
        "dump": text.index(b"dbg dumpbuf"),
    }
    current, previous = tail_at(text, indices[location])
    with pytest.raises(ValueError, match="difference-proven"):
        parse(current, previous)


def test_payload_high_nibble_space_cannot_conceal_a_prefix_short_write():
    # Actual new byte14 would print'14'; old04 prints' 4'. Prefix4095 leaves
    # that old high-nibble space while the low digit4 and newnonce are present.
    sector = bytes([0x14]) + SECTOR[1:]
    text = chain(sector=sector)
    row_start = old.STATUS.search(text).end() + 6
    current = place(text, (4095 - row_start - 10) % 4096)
    previous = bytearray(b"." * 4096)
    previous[4095] = 0x20
    mixed = current[:4095] + b" "
    with pytest.raises(ValueError, match="difference-proven"):
        parse(mixed, bytes(previous))


@pytest.mark.parametrize(
    "fault",
    [
        "status-literal",
        "status-newline",
        "row-address",
        "row-newline",
        "nonce-duplicate",
        "unknown-policy",
        "bool-policy",
    ],
)
def test_noncanonical_grammar_and_policy_still_fail_closed(fault):
    text, policy = chain(), F.STATUS_POLICY
    if fault == "status-literal":
        text = text.replace(b"buf=0x", b"buf=1x")
    elif fault == "status-newline":
        text = text.replace(b"1804fe68\r\n", b"1804fe68\n\r")
    elif fault == "row-address":
        text = text.replace(b"       0:", b"      10:", 1)
    elif fault == "row-newline":
        text = text.replace(b" e  f \r\n", b" e  f \n\r", 1)
    elif fault == "nonce-duplicate":
        text += NONCE.encode()
    else:
        policy = True if fault == "bool-policy" else "accept-any-unchanged-space"
    with pytest.raises(ValueError):
        parse(place(text), b"." * 4096, policy=policy)


def test_status_literal_policy_retains_wrapped_other_filename_prefix300_guard():
    # Artificial parser-level model, not a bypass of a real admitted baseline.
    body = chain(OTHER)
    status = body.index(b"\r\nfread")
    old_tail = body[status:].replace(F.NAME.encode(), b"rcaaaaaaaaaa")
    previous = place(old_tail, 2041)
    actual = place(echo(F.DUMP), 4090, initial=previous)
    actual = place(echo(f"kernel uptime {NONCE}"), 160, initial=actual)
    actual = place(b"\r\nfread 512b: offset=0x0, buf=0x1804fe68\r\nflash read fail\r\n", 2041, initial=actual)
    with pytest.raises(ValueError, match="difference-proven"):
        parse(actual[:300] + previous[300:], previous)


def test_every_partial_prefix_keeps_variable_content_bound_to_current_chain():
    previous = place(chain(OTHER, 0), 100)
    wanted = bytes(reversed(SECTOR))
    full = place(chain(NONCE, 0x4200, wanted), 4095, initial=previous)
    for cut in range(4096):
        mixed = full[:cut] + previous[cut:]
        try:
            sector, proof = parse(mixed, previous, offset=0x4200)
        except ValueError:
            continue
        assert sector == wanted
        assert proof["critical_variable_and_unexempted_chain_inside_written_prefix"]
