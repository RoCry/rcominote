"""Strict full SD prefix and resident-ring history are different predecessors."""

import pytest
from test_nor_freshness import echo, place
from test_scratch_reuse_parser import NONCE, OTHER, SECTOR, chain

from rcominote.experiments import scratch_reuse_parser as F

RAM = b"R" * 4095 + b"H"


def fixture():
    history = place(echo(F.DUMP), 20)
    history = place(echo(F.DUMP), 110, initial=history)
    current = place(chain(NONCE), 300, initial=history)
    return current, history


def test_multiple_resident_old_markers_survive_binary_sd_prefill():
    current, history = fixture()
    # Old coupling incorrectly calls all three markers new against binary RAM.
    with pytest.raises(ValueError, match="exactly one new"):
        F._parse_ring(current, RAM, nonce=NONCE, nor_offset=0)
    sector, proof = F.parse_prefilled_ring(current, RAM, history, nonce=NONCE, nor_offset=0)
    assert sector == SECTOR and proof["difference_proven_written_prefix_bytes"] == 4096
    assert proof["historical_dump_spans"] == [[20, 20 + len(echo(F.DUMP))], [110, 110 + len(echo(F.DUMP))]]
    assert proof["previous_ring_sha256"] != proof["marker_previous_ring_sha256"]
    assert proof["predecessor_roles"] == {
        "difference_prefix": "verified-SD-RAM-prefill",
        "markers_and_nonce": "last-actual-retained-ring",
    }
    assert proof["critical_chain_inside_written_prefix"] and "prefix_policy" not in proof


@pytest.mark.parametrize(
    "fault",
    [
        "swapped-history",
        "old-nonce",
        "same-tail",
        "partial",
        "short-history",
        "wrong-target",
        "marker-reuse",
        "variable-tail",
    ],
)
def test_unproven_or_wrong_predecessor_never_accepted(fault):
    current, history = fixture()
    ram, offset = RAM, 0
    if fault == "swapped-history":
        history = RAM
    elif fault == "old-nonce":
        history = place(NONCE.encode(), initial=history)
    elif fault == "same-tail":
        current = current[:-1] + b"H"
    elif fault == "partial":
        current = current[:4095] + RAM[4095:]
    elif fault == "short-history":
        history = history[:-1]
    elif fault == "wrong-target":
        offset = 0x24400
    elif fault == "marker-reuse":
        history = current
    else:
        # Lastphysicalbyte equals predecessor'f'; changing RAM seed to arbitrary
        # oldring must not turn variable ASCII into a formatter exemption.
        ram = ram[:-1] + b"f"
        current = current[:-1] + b"f"
    with pytest.raises(ValueError):
        F.parse_prefilled_ring(current, ram, history, nonce=NONCE, nor_offset=offset)


def test_old_public_entry_still_restricted_and_does_not_accept_marker_history_option():
    current, history = fixture()
    with pytest.raises(TypeError):
        F.parse_ring(current, RAM, nonce=NONCE, nor_offset=0, marker_previous=history)
    with pytest.raises(ValueError):
        F.parse_ring(current, history, nonce=OTHER, nor_offset=0x24400)
