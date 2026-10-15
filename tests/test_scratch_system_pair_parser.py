"""Fixed24200 parser and artificial prefix-short-write defenses, never live data."""

import pytest
from test_nor_freshness import echo, place
from test_scratch_reuse_parser import NONCE, OTHER, SECTOR, chain

from rcominote.experiments import nor_freshness as old
from rcominote.experiments import scratch_reuse_parser as F


@pytest.mark.parametrize("start", [0, 100, 2000, 3000, 4095])
def test_fixed_unknown_page_can_wrap_without_expanding_known_entry(start):
    current = place(chain(NONCE, 0x24200), start)
    sector, proof = F.parse_system_ring(current, b"." * 4096, nonce=NONCE)
    assert sector == SECTOR and proof["nor_offset"] == 0x24200
    assert proof["target_profile"] == "fixed-unknown-system24200"
    with pytest.raises(ValueError, match="Only independent known"):
        F.parse_ring(current, b"." * 4096, nonce=NONCE, nor_offset=0x24200)


def test_second_actual_ring_has_its_own_nonce_and_first_actual_predecessor():
    first = place(chain(NONCE, 0x24200), 100)
    second = place(chain(OTHER, 0x24200), 2400, initial=first)
    raw, proof = F.parse_system_ring(second, first, nonce=OTHER)
    assert raw == SECTOR and proof["previous_ring_sha256"] == old._sha(first)
    with pytest.raises(ValueError):
        F.parse_system_ring(first, first, nonce=OTHER)
    with pytest.raises(TypeError):
        F.parse_system_ring(second, first, nonce=OTHER, nor_offset=0x24400)


def test_second_fresh_nonce_with_old_complete_rows_and_current_failure_rejected():
    first_body = chain(NONCE, 0x24200)
    first = place(first_body, 100)
    failure = (
        echo(f"kernel uptime {OTHER}")
        + b"\r\nfread 512b: offset=0x24200, buf=0x1804fe68\r\n"
        + b"flash read fail\r\n"
        + old.LOG_PREFIX
        + echo("dbg fread spi_flash 0x24200")
        + b"\n"
        + old.LOG_PREFIX
        + echo(F.DUMP)
    )
    second = place(failure, 100 + len(first_body), initial=first)
    with pytest.raises(ValueError):
        F.parse_system_ring(second, first, nonce=OTHER)


def test_wrapped_other_filename_suffix_cannot_promote_old_system_rows_from_tail():
    # Artificial parser-level model, not a claim about the pinned live parent.
    body = chain(OTHER, 0x24200)
    tail = body[body.index(b"\r\nfread") :].replace(F.NAME.encode(), b"rcaaaaaaaaaa")
    marker_at = tail.index(echo(F.DUMP.replace(F.NAME, "rcaaaaaaaaaa")))
    previous = place(tail, 4090 - marker_at)
    current = place(echo(F.DUMP), 4090, initial=previous)
    current = place(echo(f"kernel uptime {NONCE}"), 160, initial=current)
    current = place(b"flash read fail", 4090 - marker_at, initial=current)
    short = current[:300] + previous[300:]
    with pytest.raises(ValueError, match="difference-proven written prefix"):
        F.parse_system_ring(short, previous, nonce=NONCE)


@pytest.mark.parametrize("start", [0, 1500, 3000, 4095])
def test_every_prefix_short_write_may_accept_only_complete_current_chain(start):
    previous = place(chain(NONCE, 0x24200), 100)
    target = bytes(reversed(SECTOR))
    current = place(chain(OTHER, 0x24200, target), start, initial=previous)
    for cut in range(4096):
        mixed = current[:cut] + previous[cut:]
        try:
            sector, proof = F.parse_system_ring(mixed, previous, nonce=OTHER)
        except ValueError:
            continue
        assert sector == target
        for key in ("nonce_span", "status_span", "rows_span", "producer_span", "dump_span"):
            a, b = proof[key]
            assert all(mixed[(a + i) % 4096] == current[(a + i) % 4096] for i in range(b - a))


@pytest.mark.parametrize("fault", ["nonce-prior", "duplicate", "wrong-offset", "short", "old-marker"])
def test_fixed_system_freshness_failures_cannot_be_salvaged(fault):
    previous = b"." * 4096
    current = place(chain(NONCE, 0x24200), 100)
    if fault == "nonce-prior":
        previous = place(NONCE.encode())
    elif fault == "duplicate":
        current = place(echo(f"kernel uptime {NONCE}"), 3000, initial=current)
    elif fault == "wrong-offset":
        current = place(chain(NONCE, 0x24400), 100)
    elif fault == "short":
        current = current[:-1]
    else:
        previous = place(chain(OTHER, 0x24200), 100)
        current = place(echo(f"kernel uptime {NONCE}"), 100, initial=previous)
    with pytest.raises(ValueError):
        F.parse_system_ring(current, previous, nonce=NONCE)
