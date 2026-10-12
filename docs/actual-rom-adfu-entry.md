# Actual ROM table and ADFU entry readback

2026-10-13 (Asia/Singapore). Owned C261CF0430/FW010004, idle. Fixed memory reads
through existing diagnostic shell; no ROM call, download-mode entry, reset,
helper upload, register write or Flash operation.

## New live evidence

[First entry capture](evidence/rom-adfu-first-2026-10-13.json),
[second independent connection](evidence/rom-adfu-second-2026-10-13.json).
Both contain identical48-byte table samples and128-byte entry prefix, complete
addressed rows, matching ACK counts and STOP/end. Two earlier table-only captures
also agreed; retained locally under artifacts/rom-table-{first,second}.json.

| Address actually referenced by verified CoMi boot | Observed Thumb pointer | Interpretation from boot caller |
|---|---|---|
| 0000019c | **00001a51** | ADFU launcher |
| 000001b8 | 000022e9 | CRC used for ACPT/FVER |
| 000001c8 | 000029eb | ACTH checksum |

Table interpretation comes from [complete actual boot](actual-boot-flow.md),
not a generic SDK struct. Captures read three fixed16-byte rows at190/1b0/1c0.
Pointer values establish current address-space contents; no claim about every
ROM API or security policy. CRC/checksum target code was not read in this pass.

[128-byte prefix](evidence/rom-adfu-prefix-2026-10-13.bin), SHA256
`3e089a1137768e844ed0f299e5feda85abe0a53305d7b8898fcd7e8e00066098`.
[Bounded instruction analysis](evidence/rom-adfu-analysis-2026-10-13.json)
decodes only1a50..1a9e, excluding literal pool1aa0/1aa4 and adjacent function.

- Entry1a50 calls1934,4adc,1798,3294,457c in order; saves457c return inr6.
  Their internals/roles remain unknown, rather than assumed SDK equivalents.
- Loads RAM pointers01000908 and01000010 from literal pool.
- Loop1a6c calls1908(r6). Nonzero return restores saved registers then
  tail-branches1980. This is a concrete candidate exit/continuation path,
  not a proved reboot or application handoff.
- Zero result tests byte[01000908+9] againstff. If equal, calls457c,
  stores result at01000010+60, sets bit0 of[01000908+4], calls021c(5,r1,0)
  with r1 carrying the updated value.
- Calls2fc8 and repeats. No command grammar or USB descriptor derived yet.

## Reproduce safely bounded evidence acquisition

```sh
# Table only; 48 bytes from fixed boot-referenced rows.
uv run -m rcominote.experiments.firmware_identity artifacts/NEW-table.json --rom-table
# Also fixed128 B entry prefix, only if live table19c remains00001a51.
uv run -m rcominote.experiments.firmware_identity artifacts/NEW-entry.json --rom-entry
```

Both require a new output, owned idle FW010004 and known getter code guard.
No generic address argument or automatic pointer chasing exists. STOP cleanup
and failure report retention reuse existing experiment. ROM-entry mode rejects
changed table pointer before reading code. Transport completeness is checked
separately from instruction interpretation.

[Post-read ordinary status](evidence/rom-adfu-final-info-2026-10-13.json): same
serial/FW, idle, charging, call mode, noise9. Reads did not test mode switching
or prove recovery from a nonbooting image.

## Next decisive evidence

Inspect actual1908 condition and1980 continuation, then selected entry callees.
These are real-device addresses, unlike public helper transport speculation.
Still missing: ROM upload grammar, accepted RAM helper/security restrictions,
physical USB entry, independent exit/recovery and complete firmware backup.
