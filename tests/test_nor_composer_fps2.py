"""Artificial isolated fixtures; explicit local replay preserves failed receipts."""

import json

import pytest
from test_nor_freshness import NEW_DUMP, ROOT, echo, failure_append, fixture, parse, place, sha

from rcominote.experiments import nor_freshness as F

NOTICE = b"[composer][I][742]: post fps 2\n\r\n"


def sample(notice=NOTICE):
    observation, _, rows, producer, dump = fixture()
    prefix = rows + F.LOG_PREFIX + producer + b"\n"
    return observation, prefix + notice + F.LOG_PREFIX + dump, len(prefix)


def test_exact_notice_is_explicit_and_retained_in_proof():
    observation, body, at = sample()
    ring = place(body)
    with pytest.raises(ValueError, match="Unexpected text"):
        parse(ring, observation)
    sector, proof = parse(ring, observation, allow_composer_fps2=True)
    assert len(NOTICE) == 33 and sha(sector) == observation["sector"]["sha256"]
    assert proof["rule"] == "nearest-producer-exact-status32rows-prefix-dump-composer-fps2-v1"
    assert proof["composer_notice"] == {"hex": NOTICE.hex(), "span": [at, at + 33], "sha256": sha(NOTICE)}
    assert proof["ring_sha256"] == sha(ring)


def test_option_without_notice_preserves_entire_old_proof():
    observation, body, *_ = fixture()
    ring = place(body, 4080)
    assert parse(ring, observation) == parse(ring, observation, allow_composer_fps2=True)


@pytest.mark.parametrize("value", [None, 0, 1, "true", [], {}])
def test_non_bool_option_rejected(value):
    observation, body, *_ = fixture()
    with pytest.raises(ValueError, match="must be bool"):
        parse(place(body), observation, allow_composer_fps2=value)


@pytest.mark.parametrize(
    "notice",
    [
        NOTICE * 2,
        NOTICE.replace(b"fps 2", b"fps 3"),
        NOTICE.replace(b"fps 2", b"fps 02"),
        NOTICE.replace(b"fps 2", b"fps 2 "),
        NOTICE.replace(b"composer", b"otherlog"),
        NOTICE.replace(b"[I]", b"[E]"),
        NOTICE.replace(b"742", b"743"),
        NOTICE.replace(b"2\n", b"2\r\n"),
        NOTICE[:-1],
        NOTICE + b"x",
        NOTICE + b"flash read fail\r\n",
        NOTICE + b"ERROR\n",
        NOTICE + b"\r\nfread 512b: offset=0x4200, buf=0x1804fe68\r\n",
        NOTICE + echo("dbg fread spi_flash 0x4200"),
        NOTICE + b"       0: " + b" 0 " * 16 + b"\r\n",
    ],
)
def test_no_other_text_or_formatter_is_permitted(notice):
    observation, body, _ = sample(notice)
    with pytest.raises(ValueError):
        parse(place(body), observation, allow_composer_fps2=True)


@pytest.mark.parametrize("position", [10, 45, 51, 111, 1971])
def test_notice_cannot_interrupt_status_rows_or_preproducer_prefix(position):
    observation, body, *_ = fixture()
    mutated = body[:position] + NOTICE + body[position:]
    with pytest.raises(ValueError):
        parse(place(mutated), observation, allow_composer_fps2=True)


def test_notice_can_wrap_without_rewriting_ring():
    observation, body, at = sample()
    ring = place(body, (4090 - at) % 4096)
    _, proof = parse(ring, observation, allow_composer_fps2=True)
    assert proof["composer_notice"]["span"] == [4090, 4123]
    assert (ring + ring)[4090:4123] == NOTICE


@pytest.mark.parametrize("has_status", [True, False])
def test_old_rows_new_failure_notice_and_nonce_still_rejected(has_status):
    observation, body, *_ = fixture()
    appended = failure_append(observation["producer"], NEW_DUMP, status=has_status)
    appended = appended.replace(
        b"\n" + F.LOG_PREFIX + echo(NEW_DUMP), b"\n" + NOTICE + F.LOG_PREFIX + echo(NEW_DUMP)
    )
    ring = place(appended, 100 + len(body), initial=place(body, 100))
    for previous in (None, observation["dump_command"]):
        with pytest.raises(ValueError):
            F.parse_ring(
                ring,
                nor_offset=0x4200,
                producer_command=observation["producer"],
                dump_command=NEW_DUMP,
                previous_dump=previous,
                allow_composer_fps2=True,
            )


def test_previous_marker_remains_mandatory_with_notice():
    observation, body, _ = sample()
    with pytest.raises(ValueError, match="one complete"):
        parse(place(body), observation, previous_dump=NEW_DUMP, allow_composer_fps2=True)
    previous = echo(NEW_DUMP)
    _, proof = parse(place(previous + body), observation, previous_dump=NEW_DUMP, allow_composer_fps2=True)
    assert proof["previous_dump_span"] == [0, len(previous)]
    with pytest.raises(ValueError, match="one complete"):
        parse(place(previous * 2 + body), observation, previous_dump=NEW_DUMP, allow_composer_fps2=True)


def replay_private_failed_example():
    """Explicit local-only check; never label reconstructed fixtures as runtime."""
    from rcominote.experiments import window_nor_probe as N

    directory = ROOT / "artifacts/window-nor2400-20261014"
    raw_report = (directory / "report.json").read_bytes()
    assert sha(raw_report) == "682b95fe57703a7ad03f18ad11b9ba0314f0505e53b8e9b583fe372735c64c47"
    report = json.loads(raw_report)
    proofs = []
    hashes = [
        "794e45d39ecaa85c6bad35e8a772dcac4bed4bc3f4091958196e54452244b5e1",
        "4f1ee8b104f8c541b597d8ccf0a1040079d94d1c3459eec978a5b9c2ecb91347",
    ]
    for index, operation in enumerate(report["operations"]):
        ring = (directory / operation["operation_id"] / "download.bin").read_bytes()
        assert sha(ring) == hashes[index]
        kwargs = {
            "nor_offset": 0x2400,
            "producer_command": "dbg fread spi_flash 0x2400",
            "dump_command": operation["dump_command"],
            "previous_dump": report["operations"][0]["dump_command"] if index else None,
        }
        candidate, proof = F.parse_ring(ring, **kwargs, allow_composer_fps2=True)
        assert sha(candidate) == "9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d"
        if index:
            with pytest.raises(ValueError, match="Unexpected text"):
                F.parse_ring(ring, **kwargs)
            assert proof["composer_notice"] == {
                "hex": NOTICE.hex(),
                "span": [3227, 3260],
                "sha256": "5a3ac148d446b5fdc3250152b6e17821a411fde6f6b67fb6088ca6d6c91f2d76",
            }
            assert proof["status_span"] == [1190, 1235]
            assert proof["rows_span"] == [1241, 3161]
            assert proof["producer_span"] == [3181, 3226]
            assert proof["dump_span"] == [3280, 3361]
        else:
            assert (candidate, proof) == F.parse_ring(ring, **kwargs)
        proofs.append(proof)
    with pytest.raises(ValueError, match="Original NOR-window pair failed"):
        N.replay(directory, ROOT / "artifacts/mapped-system-20261012.bin")
    assert sha((directory / "report.json").read_bytes()) == sha(raw_report)
    return {"candidate_proofs": proofs, "original_failed_replay_rejected": True}
