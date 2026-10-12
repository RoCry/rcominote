"""Actions SDFS additive checksum, matching the pinned SDK CheckSum32."""


def checksum32(data: bytes) -> int:
    """Sum complete little-endian uint32 words modulo 2**32.

    The SDK deliberately ignores the final 1–3 bytes when length is not
    divisible by four. File alignment padding is not part of a file checksum;
    callers validating a volume checksum must supply its actual padded bytes.
    See docs/sdfs-checksum.md for the independently captured directory oracle.
    """
    complete_bytes = len(data) - len(data) % 4
    return sum(
        int.from_bytes(data[offset : offset + 4], "little") for offset in range(0, complete_bytes, 4)
    ) & (2**32 - 1)
