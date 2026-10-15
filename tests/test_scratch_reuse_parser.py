"""Artificial canonical rings and physical-prefix short writes, never live proof."""

import pytest
from test_nor_freshness import echo, place

from rcominote.experiments import nor_freshness as old
from rcominote.experiments import scratch_reuse_parser as F

NONCE = "rc0123456789"
OTHER = "rc9876543210"
SECTOR = bytes(range(256)) * 2


def chain(nonce=NONCE, offset=0, sector=SECTOR):
    rows = b"".join(
        (f"{i:8x}: " + "".join(f"{b:2x} " for b in sector[i : i + 16]) + "\r\n").encode()
        for i in range(0, 512, 16)
    )
    producer = f"dbg fread spi_flash {'0' if offset == 0 else hex(offset)}"
    return (
        echo(f"kernel uptime {nonce}")
        + b"\r\nfread 512b: offset=0x"
        + f"{offset:x}".encode()
        + b", buf=0x1804fe68\r\n"
        + b"\r\n" * 3
        + rows
        + old.LOG_PREFIX
        + echo(producer)
        + b"\n"
        + old.LOG_PREFIX
        + echo(F.DUMP)
    )


def parse(raw, previous=bytes(b"." * 4096), *, nonce=NONCE, offset=0):
    return F.parse_ring(raw, previous, nonce=nonce, nor_offset=offset)


@pytest.mark.parametrize("start", [0, 1, 2000, 4095, 4000, 4096 - 50])
def test_exact_current_chain_can_wrap_at_any_boundary(start):
    sector, proof = parse(place(chain(), start))
    assert sector == SECTOR and proof["nonce_span"][0] == start
    assert proof["new_physical_dump_required"] and not proof["oracle_used_to_select_chain"]


def test_old_same_dump_before_nonce_allowed_and_unchanged_current_position_rejected():
    previous = place(echo(F.DUMP), 20)
    current = place(chain(), 200, initial=previous)
    sector, proof = parse(current, previous)
    assert sector == SECTOR and proof["historical_dump_spans"] == [[20, 20 + len(echo(F.DUMP))]]
    previous = place(chain(OTHER), 200)
    current = place(echo(f"kernel uptime {NONCE}"), 200, initial=previous)
    with pytest.raises(ValueError, match="new physical"):
        parse(current, previous)


@pytest.mark.parametrize(
    "fault",
    [
        "absent",
        "duplicate",
        "badlength",
        "secondstatus",
        "secondproducer",
        "fail",
        "anotherdump",
        "duplicatecurrent",
        "row",
        "prefix",
        "sameafter",
    ],
)
def test_ambiguity_failures_and_noncanonical_bytes_are_never_salvaged(fault):
    raw = chain()
    if fault == "absent":
        raw = raw[len(echo(f"kernel uptime {NONCE}")) :]
    elif fault == "duplicate":
        raw = echo(f"kernel uptime {NONCE}") + raw
    elif fault == "badlength":
        raw = raw.replace(b"cmd(27)", b"cmd(26)", 1)
    elif fault == "secondstatus":
        raw = raw.replace(b"\r\nfread", b"\r\nfread 512b: offset=0x0, buf=0x1804fe68\r\n\r\nfread", 1)
    elif fault == "secondproducer":
        raw = raw.replace(b"\r\nfread", echo("dbg fread spi_flash 0x4200") + b"\r\nfread", 1)
    elif fault == "fail":
        raw = raw.replace(b"\r\nfread", b"flash read fail\r\nfread", 1)
    elif fault == "anotherdump":
        raw = raw.replace(b"\r\nfread", echo(F.DUMP.replace(F.NAME, OTHER)) + b"\r\nfread", 1)
    elif fault == "duplicatecurrent":
        raw += echo(F.DUMP)
    elif fault == "row":
        raw = raw.replace(b"       0:", b"      10:", 1)
    elif fault == "prefix":
        raw = raw.replace(b"[679]", b"[680]", 1)
    else:
        raw = raw.replace(b"\r\nfread", echo(F.DUMP) + b"\r\nfread", 1)
    with pytest.raises(ValueError):
        parse(place(raw))


def test_old_rows_fresh_nonce_then_current_fread_failure_rejected():
    previous = place(chain(OTHER, 0x4200), 100)
    appended = (
        echo(f"kernel uptime {NONCE}")
        + b"malloc fail\r\n"
        + echo("dbg fread spi_flash 0x4200")
        + b"\n"
        + old.LOG_PREFIX
        + echo(F.DUMP)
    )
    current = place(appended, 100 + len(chain(OTHER, 0x4200)), initial=previous)
    with pytest.raises(ValueError):
        parse(current, previous, offset=0x4200)


@pytest.mark.parametrize("start", [0, 1500, 3000, 4095])
def test_every_partial_physical_prefix_overwrite_cannot_promote_old_target(start):
    previous = place(chain(OTHER, 0), 100)
    full = place(chain(NONCE, 0x4200, bytes(reversed(SECTOR))), start, initial=previous)
    # Model f_write short return: only contiguous file prefix, never rotate or fill.
    for cut in range(4096):
        mixed = full[:cut] + previous[cut:]
        try:
            sector, proof = parse(mixed, previous, offset=0x4200)
        except ValueError:
            continue
        # Acceptance proves the coherent retained current chain, not file atomicity.
        assert sector == bytes(reversed(SECTOR))
        for key in ("nonce_span", "status_span", "rows_span", "producer_span", "dump_span"):
            a, b = proof[key]
            indices = [(a + i) % 4096 for i in range(b - a)]
            assert all(mixed[i] == full[i] for i in indices)


@pytest.mark.parametrize("cut", [1, 30, 60, 1000])
def test_truncation_never_padded(cut):
    with pytest.raises(ValueError):
        parse(place(chain())[:-cut])
    with pytest.raises(ValueError):
        parse(place(chain()[:-cut]))


def test_previous_nonce_absence_is_mandatory_and_wrong_known_offset_rejected():
    with pytest.raises(ValueError, match="nonce absent"):
        parse(place(chain()), place(NONCE.encode()))
    with pytest.raises(ValueError):
        parse(place(chain()), offset=0x4200)


def test_wrapped_new_filename_suffix_cannot_promote_unchanged_high_tail_rows():
    # Parser-level artificial defensive model: previous is NOT the pinned live
    # baseline receipt. A prefix short write changes a wrapped filename suffix
    # and low-address nonce, while retaining an old valid high-address chain.
    body = chain(OTHER)
    status = body.index(b"\r\nfread")
    old_tail = body[status:].replace(F.NAME.encode(), b"rcaaaaaaaaaa")
    previous = place(old_tail, 2041)
    # Keep exact canonical status2041/rows2089/producer4029/dump4090 spans.
    assert old_tail.index(echo(F.DUMP.replace(F.NAME, "rcaaaaaaaaaa"))) + 2041 == 4090
    actual = place(echo(F.DUMP), 4090, initial=previous)
    actual = place(echo(f"kernel uptime {NONCE}"), 160, initial=actual)
    actual = place(b"\r\nfread 512b: offset=0x0, buf=0x1804fe68\r\nflash read fail\r\n", 2041, initial=actual)
    short = actual[:300] + previous[300:]
    with pytest.raises(ValueError, match="difference-proven written prefix"):
        parse(short, previous)
