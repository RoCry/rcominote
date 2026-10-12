#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer>=0.16,<1"]
# ///
"""Static reconstruction; does not import or execute extracted SDK modules."""

import hashlib
import json
from pathlib import Path

import typer

MASKS = (0x82108421, 0x08411043, 0x10802084, 0x21004108, 0x82008210, 0x04000420, 0x10001020, 0x200021CC)


def gen_seed8(seed: int) -> int:
    return sum(((seed & mask).bit_count() & 1) << bit for bit, mask in enumerate(MASKS))


def gen_seed32(seed: int, plaintext_byte: int) -> int:
    return (
        ((seed << 1) & 0xFFFFFFFC)
        | (((seed ^ (plaintext_byte & 0x3C).bit_count()) & 1) << 1)
        | ((seed & 0x82608EDB).bit_count() & 1)
    )


def keystream(seed: int, plaintext: bytes) -> bytes:
    out = bytearray()
    for byte in plaintext:
        out.append(gen_seed8(seed))
        seed = gen_seed32(seed, byte)
    return bytes(out)


def solve_seed(raw: bytes, plain: bytes) -> tuple[int, int]:
    if len(raw) != len(plain):
        raise ValueError("pair length differs")
    base = int.from_bytes(keystream(0, plain), "little")
    target = int.from_bytes(bytes(x ^ y for x, y in zip(raw, plain)), "little") ^ base
    columns = [int.from_bytes(keystream(1 << i, plain), "little") ^ base for i in range(32)]
    rows = [
        sum(((columns[i] >> j) & 1) << i for i in range(32)) | (((target >> j) & 1) << 32)
        for j in range(8 * len(raw))
    ]
    rank = 0
    pivots = []
    for bit in range(32):
        pivot = next((i for i in range(rank, len(rows)) if (rows[i] >> bit) & 1), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] >> bit) & 1:
                rows[i] ^= rows[rank]
        pivots.append(bit)
        rank += 1
    if any(row == 1 << 32 for row in rows):
        raise ValueError("inconsistent known pair")
    if rank != 32:
        raise ValueError(f"ambiguous seed: rank {rank}")
    return sum(((rows[i] >> 32) & 1) << bit for i, bit in enumerate(pivots)), rank


def transform(data: bytes, seed: int, *, decrypt: bool = False, block_bytes: int = 32) -> bytes:
    if type(block_bytes) is not int or block_bytes <= 0:
        raise ValueError("Block length must be a positive integer")
    out = bytearray()
    for base in range(0, len(data), block_bytes):
        state = seed
        for byte in data[base : base + block_bytes]:
            result = byte ^ gen_seed8(state)
            out.append(result)
            state = gen_seed32(state, result if decrypt else byte)
    return bytes(out)


def main(raw_path: Path, mapped_path: Path):
    raw, plain = raw_path.read_bytes(), mapped_path.read_bytes()
    expected = (
        "28b2e50ba95630f6485bd5e3ccfbd8ebe5f1406ffa36d6c0c4e35c4c71af0678",
        "911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5",
    )
    for data, digest in zip((raw, plain), expected, strict=True):
        if len(data) != 512 or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Input differs from captured raw/mapped system header")
    seed, rank = solve_seed(raw[:32], plain[:32])
    zero_seed, zero_rank = solve_seed(raw[64:96], plain[64:96])
    if seed != zero_seed or transform(plain, seed) != raw or transform(raw, seed, decrypt=True) != plain:
        raise ValueError("Independent block fit or full header verification failed")
    print(
        json.dumps(
            {
                "effective_seed": f"0x{seed:08x}",
                "fit_rank_first_block": rank,
                "fit_rank_zero_block": zero_rank,
                "reset_bytes": 32,
                "verified_bytes": len(raw),
                "held_out_bytes_after_first_block_fit": 480,
                "raw_sha256": expected[0],
                "plain_sha256": expected[1],
                "reencode_matches": True,
                "decode_matches": True,
                "scope": "actual system header only; seed is effective state, not proven efuse key",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    typer.run(main)
