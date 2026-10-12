# SDFS checksum semantics and actual directory validation

2026-10-12. Offline SDK source / shipped packer analysis; no device commands.

**Confirmed:** SDFS uses an additive little-endian 32-bit checksum. Existing,
independently repeated CoMi directory bytes validate against the separately
stored directory checksum `0xef0b5e3d`. Recording DSP file checksum must equal
`0x96d685bb` once all **110148 bytes** have been acquired. Directory validation
does not establish acquisition or validity of any file body.

## Primary sources

Pinned SDK commit `26f51e584940d5b141cd1d09d2629d69b595f579`:

- [SDFS CheckSum32 and XIP verifier, lines 418–458](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/sdfs/sdfs.c#L418-L458): checksum loop, directory checksum field, per-file checksum scope.
- [File-system verifier, lines 683–728](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/sdfs/sdfs.c#L683-L728): same checks via bounded file reads. Its public `sdfs_verify` uses a 2560-byte cache, with 2048 bytes available for each data chunk; intermediate chunks remain word-aligned.
- [Build wrapper, lines 44–59](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_sdfs.py#L44-L59): delegates to platform `make_sdfs`; Python wrapper does not implement checksum.
- [Shipped Linux x86-64 packer](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/utils/linux-x86_64/make_sdfs): ELF64 executable, stripped, statically linked; SHA-256 `fbac80f06f70a13392f0d6de7ee02282a87ca6c4928ccbd7ed4e196eca3303eb`.

The last source was inspected with `objdump`; addresses below are virtual ELF
addresses, not offsets in CoMi firmware. Source-level algorithm corroborated
by packer instructions, rather than inferred from similarly named ATF / OTA
format checksums.

## Exact algorithm and padding

For byte string `b`, `CheckSum32(b, len(b))` is:

```text
sum(LE32(b[4*i : 4*i+4]) for i in range(floor(len(b)/4))) mod 2^32
```

Unsigned overflow wraps. No carry folding, complement, CRC, seed, byte swap,
or inclusion of a checksum word unless that word belongs to the explicitly
selected byte range. **Trailing 1–3 bytes are ignored**, not zero-padded.

| Stored field | Exact packer input | Padding / exclusion |
|---|---|---|
| Each file record `+0x1c` | File's original `size` bytes | File's final partial word ignored; following alignment padding excluded |
| Volume header `+0x18` (`reserved[1]`) | `N * 32` bytes beginning at volume `+0x20` | All file directory records, including their checksum words; volume header and directory alignment gap excluded |
| Volume header `+0x1c` (`checksum`) | Bytes from `(N+1)*32` through `volume_size` | Entire data area plus file alignment padding and any directory alignment gap; volume header / complete directory excluded |

Packer evidence:

- `0x40128b..0x4012e8`: checksum function; adds 32-bit loads; loop count `len >> 2`.
- `0x4012f6..0x401319`: directory length `(N+1)*32`, data start rounded up to 64 bytes.
- `0x40174c..0x401763`: each file allocation extent rounded up to 64 bytes.
- `0x40142a..0x401447`: file checksum invoked with original file size; stored in directory record `+0x1c`.
- `0x4018dc..0x401938`: per-file allocation padding explicitly filled with zero.
- `0x4014e9..0x40150d`: volume checksum over `volume_size - (N+1)*32`, starting at exact unaligned directory end; stored in header `+0x1c`.
- `0x401510..0x40152f`: directory checksum over `N*32` at `volume+32`, stored in header `+0x18`.

General caveat: packer allocates the output with `malloc` and explicitly zeros
header / directory records and per-file padding. The optional gap between
unaligned directory end and aligned data start has no explicit initialization
in this function; its actual bytes must be included when validating a volume,
rather than assumed zero. CoMi has `N=7`, so directory ends at `0x100`, already
64-byte aligned; this ambiguity does not affect its directory/data boundary.

Reproduce packer inspection from the pinned checkout:

```sh
objdump -d --start-address=0x40128b --stop-address=0x40157a \
  action_technology_sdk/zephyr/tools/utils/linux-x86_64/make_sdfs
objdump -d --start-address=0x40174c --stop-address=0x40193d \
  action_technology_sdk/zephyr/tools/utils/linux-x86_64/make_sdfs
```

## Actual CoMi checks now possible

Retained [directory report](evidence/nor-partition-prefixes-2026-10-12/dsp-directory.json)
and [raw double-read captures](evidence/nor-partition-prefixes-2026-10-12/dsp/):

| Quantity | Actual value / result |
|---|---|
| Complete header + directory | 256 bytes, NOR `0x240000..0x240100` |
| Directory SHA-256 | `778e2e882fbfc0cd1f4d8ce67005aae3f4c8c3a2b3303f335fbbdaf2a906a755` |
| File directory input | 224 bytes, NOR `0x240020..0x240100` |
| Computed directory checksum | `0xef0b5e3d` |
| Independently captured header `+0x18` | `0xef0b5e3d` — **matches** |
| Header `+0x1c` volume data checksum | `0xff2a3fa3` — **not yet validated** |
| File checksum words summed modulo `2^32` | `0xff2a0f6a` |
| Difference: volume data sum minus file sum | `0x3039` |

The difference is consistent with ignored final two bytes of the only
non-word-aligned file (`sdfs.txt`, size 10) contributing to a zero-padded word
in the volume checksum. Bytes `39 30` (`90`) would contribute exactly `0x3039`.
This is a consistency inference; no file-body bytes are established by it.

Reproduce actual directory validation from this repo:

```sh
uv run python - <<'PY'
from pathlib import Path
from rcominote.nor_windows import analyze
from rcominote.sdfs_checksum import checksum32

evidence = Path("docs/evidence/nor-partition-prefixes-2026-10-12/dsp")
report = analyze(sorted(evidence.glob("nor-dsp-prefix*-*.json")))
rows = {int(r["offset"], 16): r["variants"][0] for r in report["rows"]}
assert all(rows[offset]["sources"] >= 2 for offset in range(0, 256, 16))
raw = b"".join(bytes.fromhex(rows[offset]["hex"]) for offset in range(0, 256, 16))
expected = int.from_bytes(raw[24:28], "little")
actual = checksum32(raw[32:256])
print(f"directory: computed={actual:#010x}, stored={expected:#010x}")
assert actual == expected == 0xef0b5e3d
PY
```

Recording DSP file extent: `0x24d400..0x268244`, length `0x1ae44` =
110148, divisible by four. Validate only those original bytes against
directory checksum **`0x96d685bb`**; exclude 60 bytes before next file starts
at `0x268280`. Matching this additive checksum supplies an independent
format check but not a cryptographic authenticity guarantee or recovery proof.

Unknown: all file-body and complete-volume checksum results await complete
acquisition; the pinned SDK packer is not evidence that this exact binary
built CoMi's volume, though its directory checksum contract matches measured
bytes. No on-device checksum verifier was invoked.
