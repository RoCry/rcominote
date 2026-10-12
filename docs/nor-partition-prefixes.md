# Raw NOR partition prefixes and the actual DSP directory

2026-10-12, C261CF0430 / FW010004. Fixed named read targets derived from the CRC-checked [actual ACPT](partition-readback.md). No arbitrary offsets, erase/program, reset, OTA subscription or mode change introduced.

## Fixed targets and source attribution

`diag capture printk-nor-tail --nor-target` accepts only:

| Name | NOR offset | ACPT basis |
|---|---:|---|
| boot (default) | `0` | fw0_boot |
| backup-boot | `2000` | fw1_boot; configured only, not probed this round |
| system | `24000` | fw0_sys |
| dsp | `240000` | sdfs_k / NOR K |

512-byte fread output still labels rows relative to its buffer, not absolute NOR offsets. The original print loop receives shell, buffer and length, not the requested Flash offset. Captures now record target/offset; offline inspection requires exact producer declaration plus observed offset-status line and command echo between completed code guard and context-read frame boundaries. A metadata relabel cannot turn a boot capture into a system capture. Assembly rejects mixed targets before combining bytes.

## System: raw API bytes differ from mapped application bytes

Two independent windows per pass, two passes, cover raw relative `[0,40)` with every row independently repeated and no conflicts. Prefix:

```text
raw NOR 24000: db d5 f9 a3 89 60 bf dc 41 4d bf fb 62 16 1a 36
mapped 10000000: 41 43 54 48 48 54 43 41 19 d8 02 10 62 00 00 00
```

Mapped image is the independently checksum-validated927632 B artifact with SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`. The raw API read at ACPT system offset therefore cannot simply be substituted with the same mapped bytes.

ACPT flag2 corresponds to the SDK encryption bit; differing bytes are consistent with a transformed storage representation. This experiment does not establish the algorithm/key, exact mapping transformation or signature policy. It also does not prove that offset24000 is booted merely because the table names it system. [Earlier mapping uncertainty](mapping-candidate-audit.md) is narrowed by a real byte comparison, not resolved into a writable-image recipe.

## DSP: actual SDFS directory

Raw offset240000 begins `sdfs.bin`, header count7, reported image size `7ee40`. Unlike the system prefix, it is directly interpretable using the actual SDFS lookup layout already recovered from this firmware:32-byte header plus seven32-byte entries. The requested record library lookup is case-insensitive over12 bytes.

[System capture/coverage report](evidence/nor-partition-prefixes-2026-10-12/system/report.json), [DSP capture/coverage report](evidence/nor-partition-prefixes-2026-10-12/dsp/report.json), [parsed directory](evidence/nor-partition-prefixes-2026-10-12/dsp-directory.json). Directory256 B SHA256 `778e2e882fbfc0cd1f4d8ce67005aae3f4c8c3a2b3303f335fbbdaf2a906a755`; all16 directory rows independently double-covered, no conflicts. Twelve DSP sessions also cover the next16 B, which are outside the directory.

| File | Relative offset | Absolute NOR offset | Bytes |
|---|---:|---:|---:|
| tst.bin | `100` | `240100` | 4196 |
| sdfs.txt | `1180` | `241180` | 10 |
| logo.sty | `11c0` | `2411c0` | 196 |
| logo.res | `12c0` | `2412c0` | 416 |
| fcc.bin | `1480` | `241480` | 49008 |
| aerecord.dsp | `d400` | `24d400` | 110148 |
| admusic.dsp | `28280` | `268280` | 355248 |

Reported SDFS image size519744 B fits704 KiB partition; file extents are distinct and bounded. Parser rejects truncated directory rows, duplicate case-insensitive names and out-of-bounds/overlapping extents. Directory checksums are recorded as words, not advertised as verified; file bodies have not been extracted. A valid directory entry is not proof of a complete or loadable DSP file. Independent recovery remains unverified.

## Reproduce

```sh
uv run comi diag capture printk-nor-tail --nor-target system --ring-window 10 \
  --duration 1 --out artifacts/system-prefix.json
uv run comi diag capture printk-nor-tail --nor-target dsp --ring-window 9 \
  --duration 1 --out artifacts/dsp-prefix.json
```

One window does not establish repeated coverage. This round uses system windows9/10 and DSP windows5..10, each in two separate sessions; offline assembly reports missing rows rather than outputting an incomplete512-byte sector. Directory parsing needs only its complete independently repeated256 B, not the remaining sector bytes.

```sh
uv run comi diag inspect-dsp-directory docs/evidence/nor-partition-prefixes-2026-10-12/dsp/nor-dsp-prefix*.json
```
