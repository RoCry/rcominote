"""Hand-encoded section chain: independent layout/short-read oracles."""

import pytest

from rcominote.dsp_sections import inspect_image


def image():
    # 540-byte xhqy header, code pointer540, all other fields zero.
    header = b"xhqy" + bytes(16) + b"\x1c\x02\0\0" + bytes(516)
    # size4, DSP address8, payload01 02 03 04; size2/address16/payloadabcd; zero terminator.
    return header + bytes.fromhex("0400000008000000010203040200000010000000abcd00000000")


def test_two_sections_and_four_byte_eof_terminator():
    report = inspect_image(image())
    table = report["tables"][0]
    assert (table["name"], table["offset"], table["terminator_offset"]) == ("code", 540, 562)
    assert [(row["data_offset"], row["bytes"], row["dsp_address"]) for row in table["sections"]] == [
        (548, 4, "0x8"),
        (560, 2, "0x10"),
    ]


@pytest.mark.parametrize(
    ("length", "message"),
    [(549, "payload exceeds"), (556, "incomplete nonempty"), (562, "missing section terminator")],
)
def test_short_header_payload_and_missing_terminator(length, message):
    with pytest.raises(ValueError, match=message):
        inspect_image(image()[:length])
