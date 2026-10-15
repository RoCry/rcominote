"""Strict text association; isolated fixtures are synthetic, never runtime rings.

Public positive fixtures combine unchanged published status/rows/echo spans with
observed fixed formatter bytes and artificial padding. replay_private_examples()
is an explicit local-only check of four original full rings, including malicious
append mutations; it raises if any required private artifact is missing.
"""

import hashlib
import json
from pathlib import Path

import pytest

from rcominote.experiments import nor_freshness as F
from rcominote.experiments.sd_bridge import sector_from_ring

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "docs/evidence"
RECEIPT = PUBLIC / "sd-nor-offset4200-live-2026-10-14.json"
NEW_DUMP = "dbg dumpbuf 402910729 4096 /SD:/RECORDER/Call-rc1234567890.mp3"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def echo(command):
    return f"logsrv: cmd({len(command) + 1}) {command}\n\r\n".encode()


def place(body, start=0, *, initial=None):
    """Artificial ring placement/append; never an actual device acquisition."""
    assert len(body) <= 4096
    data = bytearray(b"." * 4096 if initial is None else initial)
    for i, byte in enumerate(body):
        data[(start + i) % 4096] = byte
    return bytes(data)


def fixture(index=0):
    observation = json.loads(RECEIPT.read_bytes())["observations"][index]
    pieces = []
    for key in ("status_and_rows", "producer_marker", "dump_marker"):
        ref = observation[key]
        data = (PUBLIC / ref["file"]).read_bytes()
        assert len(data) == ref["bytes"] and sha(data) == ref["sha256"]
        pieces.append(data)
    status_rows, producer, dump = pieces
    # These literal prefixes were independently observed between the public
    # spans in all four private examples. Padding/placement remain synthetic.
    body = status_rows + F.LOG_PREFIX + producer + b"\n" + F.LOG_PREFIX + dump
    return observation, body, status_rows, producer, dump


def parse(data, observation, **kwargs):
    return F.parse_ring(
        data,
        nor_offset=0x4200,
        producer_command=observation["producer"],
        dump_command=observation["dump_command"],
        **kwargs,
    )


@pytest.mark.parametrize("index", [0, 1])
def test_unchanged_public_spans_in_explicit_artificial_ring(index):
    observation, body, *_ = fixture(index)
    start = observation["status_and_rows"]["ring_span"][0]
    sector, proof = parse(place(body, start), observation)
    assert len(sector) == 512 and sha(sector) == observation["sector"]["sha256"]
    assert proof["status_span"][0] == start
    assert proof["rows_span"][1] == observation["status_and_rows"]["ring_span"][1]
    assert proof["producer_span"] == observation["producer_marker"]["ring_span"]
    assert proof["dump_span"] == observation["dump_marker"]["ring_span"]
    assert proof["bounded_chain_bytes"] == len(body)
    assert not proof["previous_dump_required"]


@pytest.mark.parametrize("start", [0, 1, 4095, 4096 - 45, 4096 - 1971, 4096 - 2138])
def test_whole_chain_and_individual_markers_can_wrap(start):
    observation, body, *_ = fixture()
    sector, proof = parse(place(body, start), observation)
    assert sha(sector) == observation["sector"]["sha256"]
    assert proof["status_span"] == [start, start + 45]
    assert proof["rows_span"][0] == (start + 51) % 4096
    assert proof["dump_span"][0] == (start + len(body) - 81) % 4096


def failure_append(producer, dump, *, status=True):
    header = b"\r\nfread 512b: offset=0x4200, buf=0x1804fe68\r\n" if status else b""
    failure = b"flash read fail\r\n\r\n" if status else b"malloc fail\r\n\r\n"
    return header + failure + F.LOG_PREFIX + echo(producer) + b"\n" + F.LOG_PREFIX + echo(dump)


@pytest.mark.parametrize("has_status", [True, False])
def test_old_complete_rows_new_read_failure_new_nonce_never_becomes_second_read(has_status):
    observation, body, *_ = fixture()
    old = place(body, 100)
    modified = place(
        failure_append(observation["producer"], NEW_DUMP, status=has_status), 100 + len(body), initial=old
    )
    # Demonstrate this is the old validator's real attribution weakness, not
    # simply an incomplete row fixture: it still returns the previous sector.
    previous = sector_from_ring(
        modified, nor_offset=0x4200, producer_command=observation["producer"], dump_command=NEW_DUMP
    )
    assert sha(previous) == observation["sector"]["sha256"]
    for previous_dump in (None, observation["dump_command"]):
        with pytest.raises(ValueError):
            F.parse_ring(
                modified,
                nor_offset=0x4200,
                producer_command=observation["producer"],
                dump_command=NEW_DUMP,
                previous_dump=previous_dump,
            )


@pytest.mark.parametrize(
    "fault",
    [
        "row",
        "row_format",
        "row_offset",
        "status",
        "status_offset",
        "prefix",
        "extra_status",
        "extra_producer",
        "other_producer",
        "fail_before_echo",
        "fail_after_echo",
        "producer_length",
        "dump_length",
    ],
)
def test_mutations_cannot_be_skipped_to_recover_an_older_candidate(fault):
    observation, body, status_rows, producer, dump = fixture()
    if fault == "row":
        body = body[:51] + body[111:]
    elif fault == "row_format":
        body = body.replace(b" 1 ", b"01 ", 1)
    elif fault == "row_offset":
        body = body.replace(b"       0: ", b"      10: ", 1)
    elif fault == "status":
        body = body[45:]
    elif fault == "status_offset":
        body = body.replace(b"offset=0x4200", b"offset=0x4400", 1)
    elif fault == "prefix":
        body = body.replace(b"[679]", b"[680]", 1)
    elif fault == "extra_status":
        body = status_rows + status_rows[:45] + body[len(status_rows) :]
    elif fault == "extra_producer":
        body = body.replace(producer, producer + producer, 1)
    elif fault == "other_producer":
        body = body.replace(producer, producer + echo("dbg fread spi_flash 0x4400"), 1)
    elif fault == "fail_before_echo":
        body = body.replace(producer, b"flash read fail\n\n" + producer, 1)
    elif fault == "fail_after_echo":
        body = body.replace(dump, b"flash read fail\n\n" + dump, 1)
    elif fault == "producer_length":
        body = body.replace(b"cmd(27)", b"cmd(26)", 1)
    else:
        body = body.replace(b"cmd(63)", b"cmd(62)", 1)
    with pytest.raises(ValueError):
        parse(place(body), observation)


def test_duplicate_complete_current_dump_is_ambiguous():
    observation, body, _, _, dump = fixture()
    with pytest.raises(ValueError, match="one complete"):
        parse(place(body + dump), observation)


@pytest.mark.parametrize("cut", [1, 2, 30, 60, 244])
def test_no_padding_or_salvage_of_truncated_input(cut):
    observation, body, *_ = fixture()
    with pytest.raises(ValueError, match="complete4096"):
        parse(place(body)[:-cut], observation)
    # Also reject a full-size ring with a truncated current command echo.
    with pytest.raises(ValueError):
        parse(place(body[:-cut]), observation)


def test_previous_anchor_is_required_unique_and_must_precede_current_status():
    observation, body, *_ = fixture()
    prior = echo(NEW_DUMP)
    sector, proof = parse(place(prior + body, 4000), observation, previous_dump=NEW_DUMP)
    assert len(sector) == 512 and proof["previous_dump_required"]
    assert proof["previous_dump_span"] == [4000, 4000 + len(prior)]
    for modified in (body, prior + prior + body, body[:51] + prior + body[51:]):
        with pytest.raises(ValueError):
            parse(place(modified), observation, previous_dump=NEW_DUMP)
    # Physical array order is not time order: this is a valid previous marker
    # on the preceding circular turn, exactly as in the actual dual example.
    assert parse(place(body + prior), observation, previous_dump=NEW_DUMP)[1]["previous_dump_required"]
    with pytest.raises(ValueError, match="nonces must differ"):
        parse(place(body), observation, previous_dump=observation["dump_command"])


@pytest.mark.parametrize(
    "interrupt",
    [
        b"malloc fail\r\n",
        b"flash read fail\r\n",
        b"ERROR\r\n",
        b"\r\nfread 512b: offset=0x4400, buf=0x1804fe68\r\n",
        echo("dbg fread spi_flash 0x4400"),
    ],
)
def test_prior_marker_anchor_forbids_hidden_intermediate_producer_or_failure(interrupt):
    observation, body, *_ = fixture()
    # The local nearest chain alone is intact; the declared previous-op anchor
    # adds a stronger transaction interval and must not silently be ignored.
    data = place(echo(NEW_DUMP) + interrupt + body)
    assert len(parse(data, observation)[0]) == 512
    with pytest.raises(ValueError):
        parse(data, observation, previous_dump=NEW_DUMP)


@pytest.mark.parametrize("offset", [True, -512, 1, 0x400000])
def test_invalid_offset_contract(offset):
    observation, body, *_ = fixture()
    with pytest.raises(ValueError, match="aligned512"):
        F.parse_ring(
            place(body),
            nor_offset=offset,
            producer_command=observation["producer"],
            dump_command=observation["dump_command"],
        )


def test_wrong_producer_and_arbitrary_dump_are_rejected():
    observation, body, *_ = fixture()
    with pytest.raises(ValueError, match="Producer"):
        F.parse_ring(
            place(body),
            nor_offset=0x2200,
            producer_command=observation["producer"],
            dump_command=observation["dump_command"],
        )
    with pytest.raises(ValueError, match="scratch nonce"):
        F.parse_ring(
            place(body),
            nor_offset=0x4200,
            producer_command=observation["producer"],
            dump_command="dbg dumpbuf 0 4096 /SD:/x",
        )


def replay_private_examples():
    """Explicit local check: exact four real rings, hashes and malicious appends."""
    receipt = json.loads(RECEIPT.read_bytes())
    cases = []
    for observation in receipt["observations"]:
        path = ROOT / observation["download"]["file"]
        cases.append((path, observation, observation["download"]["sha256"], 0x4200, None))
    parent = ROOT / "artifacts/dual-known-nor-20261014"
    report = json.loads((parent / "report.json").read_bytes())
    for index, op in enumerate(report["operations"]):
        cases.append(
            (
                parent / op["phase"] / "download.bin",
                op,
                op["download_sha256"],
                (0, 0x4200)[index],
                report["operations"][0]["dump_command"] if index else None,
            )
        )
    results = []
    for path, observation, expected_sha, offset, previous in cases:
        data = path.read_bytes()
        assert sha(data) == expected_sha
        raw, proof = F.parse_ring(
            data,
            nor_offset=offset,
            producer_command=observation["producer"],
            dump_command=observation["dump_command"],
            previous_dump=previous,
        )
        from rcominote.experiments.sd_nor_targets import oracle

        phase = "boot" if offset == 0 else "recovery-block1"
        assert raw == oracle(phase)[1]
        if offset == 0x4200:
            mutated = place(
                failure_append(observation["producer"], NEW_DUMP), proof["dump_span"][1], initial=data
            )
            assert (
                sector_from_ring(
                    mutated,
                    nor_offset=offset,
                    producer_command=observation["producer"],
                    dump_command=NEW_DUMP,
                )
                == raw
            )
            with pytest.raises(ValueError):
                F.parse_ring(
                    mutated,
                    nor_offset=offset,
                    producer_command=observation["producer"],
                    dump_command=NEW_DUMP,
                    previous_dump=observation["dump_command"],
                )
        results.append(
            {
                "source": str(path.relative_to(ROOT)),
                "proof": proof,
                "real_ring_failure_append_rejected": True if offset == 0x4200 else None,
            }
        )
    return results


def test_two_same_offset_chains_use_distinct_markers_and_the_latest_complete_rows():
    observation, body, *_ = fixture()
    first_body = body.replace(b"0x4200", b"0x2200")
    first = place(first_body, 1700)
    producer = "dbg fread spi_flash 0x2200"
    first_bytes, first_proof = F.parse_ring(
        first, nor_offset=0x2200, producer_command=producer, dump_command=observation["dump_command"]
    )
    second_body = first_body.replace(observation["dump_command"].encode(), NEW_DUMP.encode())
    # Explicit synthetic counterexample to accidental old-row selection: one
    # current byte differs. Parsing returns it without imposing an oracle/pair.
    second_body = second_body.replace(b"       0: da ", b"       0: db ", 1)
    second = place(second_body, first_proof["dump_span"][1], initial=first)
    second_bytes, proof = F.parse_ring(
        second,
        nor_offset=0x2200,
        producer_command=producer,
        dump_command=NEW_DUMP,
        previous_dump=observation["dump_command"],
    )
    assert first_bytes[0] == 0xDA and second_bytes[0] == 0xDB
    assert first_bytes[1:] == second_bytes[1:]
    assert proof["previous_dump_required"] and proof["previous_dump_span"] == first_proof["dump_span"]
