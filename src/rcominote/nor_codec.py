"""Observed device NOR decoding; effective state is not a recovered efuse key."""

MASKS = (0x82108421, 0x08411043, 0x10802084, 0x21004108, 0x82008210, 0x04000420, 0x10001020, 0x200021CC)


def decode(raw: bytes, *, block_bytes: int) -> bytes:
    if block_bytes not in (32, 512) or type(block_bytes) is not int:
        raise ValueError("Only observed32/512-byte reset profiles are supported")
    plain = bytearray()
    for start in range(0, len(raw), block_bytes):
        state = 0x0A15A191
        for value in raw[start : start + block_bytes]:
            mask_byte = sum(((state & mask).bit_count() % 2) << bit for bit, mask in enumerate(MASKS))
            byte = value ^ mask_byte
            plain.append(byte)
            state = (
                ((state << 1) & 0xFFFFFFFC)
                | (((state ^ (byte & 0x3C).bit_count()) & 1) << 1)
                | ((state & 0x82608EDB).bit_count() & 1)
            )
    return bytes(plain)
