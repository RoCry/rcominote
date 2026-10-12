# OTA initialization can erase TEMP and store breakpoints before image validation

2026-10-12. Offline audit of verified CoMi FW010004 mapped-system image,
927632 B, SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`.
[Instructions, bytes and literal pools](evidence/ota-prepare-2026-10-12.json).
No new device I/O. Static reachability proves conditional side effects, not that
an erase occurred on this device or on a particular boot.

## Decision

Actual initializer `100669f8` loads/saves OTA breakpoint state and calls partition
preparation **before** image-object initialization (`10066aa4`), hence before a
candidate image's header/manifest validation. This preparation contains real NOR
erase and NVRAM write paths. Package rejection alone cannot establish that an OTA
session's earlier initialization was storage-neutral.

For the observed application's `0d` flag argument, preparation selects recovery
semantics. Its erase candidate, using the verified cached ACPT table, is only
`fw0_temp`, configured NOR range **`0x2f0000..0x3f0000` (1 MiB)**. This does not
prove a currently erased TEMP, nor an erase of the running SYSTEM partition.
Current breakpoint state, partition file states, storage contents and runtime
execution are not measured by this audit.

Initialization and BLE enable must remain distinct. Wrapper
`10001c98..10001d18` calls application initializer `10004ae8` at `10001cf2`
after its own setup succeeds. F5F0 callback branch `100048ba..10004952` instead
loads existing OTA object `1800a8a4` at `100048d8` and calls attach `1006696c`
at `100048dc`. It does not directly call the initializer. Do not infer that
every F5F0 subscription newly executes preparation; this audit does not prove
the complete startup path executes on every boot.

## Initializer ordering and flags

| Actual instructions | Behavior |
|---|---|
| `10004b2e..10004b36` | Caller clears argument word+0c then writes byte `0d`. |
| `10066a18..10066a20` | Clears `0x364` B state at `18019d94`. |
| `10066a24..10066a3a` | Caller bit2 → internal bit2, no version control. |
| `10066a4e..10066a54` | Opens caller storage through `100650b8`; stores pointer at state+18. |
| `10066a68..10066a96` | Caller bit0 → recovery bit0; bit3 → erase-for-upgrade bit3; bit1 → recovery-app bit1, requiring bit0. |
| `10066a98..10066a9a` | `10067b48(state+294)`: load breakpoint, default/store on failed load. |
| `10066a9e..10066aa0` | `100655bc(state)`: prepare partitions. Return is not checked. |
| `10066aa4..10066aa8` | Only now initialize/store image object. |

Observed `0d` sets bits0,2,3, clears bit1. Preparation's actual instructions test
bit0; **bit3 is not its erase gate**. The pinned SDK also has a keep-temp option,
but no corresponding bit copy or keep-temp branch appears in these complete
actual initializer/preparation bodies. Do not transplant that SDK exemption into
this firmware's policy.

## Exact preparation gates

Breakpoint begins state+`294`; overall state is byte+`297`.
Names below are pinned SDK interpretations; numeric comparisons and branches
are independently present in the actual instructions.

| Breakpoint state | Actual behavior with recovery bit0 set |
|---|---|
| `1` CLEAN | Return0 before partition loop or final breakpoint save (`100655e0..100655f6`). |
| `3` UPGRADE_PENDING | Return0 through skip path (`10065604..1006560e`). |
| `4` UPGRADE_WRITING; `0f` UPGRADING_FAIL | Return0 through skip path (`10065610..1006561e`). |
| `2` WRITING_IMG | Iterate candidates; consult per-file state before erase. |
| All other byte values | Iterate candidates; full candidate erase path. Then clear old breakpoint if nonzero, set overall state1, store. |

Loop indexes0..29 (`10065634..1006566e`). Getter `10027650` returns table entries
with stride24 and rejects indexes>29. Null entry returns `-22` immediately.
For nonnull entries, recovery branch accepts only:

- file ID at entry+9 nonzero (`10065644..10065646`);
- type at entry+8 equals5 **or** file ID equals`fe` (`100656aa..100656c0`);
- storage ID = upper nibble of entry+0a, equal storage object's word+10
  (`100656c2..100656e8`, getter `100b1500`).

`100650ee..10065110` initializes matched `spi_flash` storage with type0 and ID0.
[Actual ACPT evidence](partition-readback.md) has 18 nonzero entries, 12 zero
entries, all storage0; sole accepted entry is index16, type5, file ID254,
`fw0_temp` offset`2f0000`, size`100000`. ACPT SHA256
`a071b0cdafad355eb05a71e96fc2cb6a5348ec8b5e11d0ac4dfe54d83671a144`, stored
CRC32`703f5674` verified. These are configured offsets from a runtime cache, not
a new raw Flash read or proof that the live table cannot change.

For state2, `100656f6..10065728` looks up file state:

- `1`, `5`, `6`, `7`: skip erase of that candidate.
- `3`: with recovery set, align `(bp.cur_file.offset + bp.cur_orig_write_offset)`
  down to4 KiB, subtract partition offset, erase suffix; update original offset
  and set file state5 (`10065730..10065792`).
- Other values, including lookup's missing-file return`-1`: full candidate erase,
  set file state1 (`100657a0..100657ac`).

State2 retains overall state2; other non-skipped configured states become1.
Final `100656a2..100656a4` saves breakpoint. State4's per-file handling exists
for the non-recovery branch, but recovery initialization exits earlier for4.

## Actual erase dispatch and error handling

`1006550c` rounds start address down and remaining size up to4 KiB. If buffer and
size are nonzero, it calls `10064e0c` to check for all`ff`; result exactly1 skips
erase. Any other result, including read error, reaches `1006503c`.

For type0 NOR, `1006507e..1006508a` dispatches to `10064fd0`:
load device pointer from storage+0; split request according to storage+0c segment
limit; load driver API table at device+8; call API+8 with `(device, offset, size)`
at `10064ffa`. This is an actual storage-driver erase call, not a symbol-name
inference from a reference SDK. The lower driver/bus commands and success on
physical hardware are outside this bounded audit.

Both preparation erase call sites (`10065784`, `100657a6`) immediately continue
to update file state without checking erase return. Final breakpoint-save return
is also discarded; preparation returns0 except its null-entry error. Its caller
discards even that return. Therefore initialization success does not prove an
erase or breakpoint persistence succeeded.

## Actual breakpoint persistence path

`10067b48` loads `0x4a` B `OTA_BP` via `10067978`. Negative load causes defaults
at `100b1648` (zero74 B; initialize old-version/mirror; state0) and an immediate
save at `10067b86`. Thus failed load can request a store even before prepare.

`1006792c` increments byte0 sequence, then calls `10036a10("OTA_BP", bp, 0x4a)`.
That wrapper locks and passes a concrete NVRAM context to `100364f4`.
The actual implementation checks for identical existing payload and can skip a
write; otherwise emits item metadata/data through `10035e24` at `100366d6` and
`10036704`. `10035e24` checks bounds then calls `10036c38`; its loop calls
device driver API+4 with `(device, address, buffer, length)` at `10036c64`.
This establishes a persistent-store path beyond a RAM-only state assignment.
No NVRAM contents, backend address, store success or physical write was observed.

Default state0 does not meet prepare's clean-state1 exemption. If defaulting
and preparation both execute with the observed flags/table, preparation reaches
the TEMP clean-check/erase path and then requests another save with state1.
Treat this as conditional control flow, not an observed cold-boot outcome.

## Reproduction and scope

```sh
uv run tools/inspect_ota_prepare.py artifacts/mapped-system/mapped-system.bin
```

SHA-bound script decodes complete selected functions up to their literal pools,
rejects incomplete decoding, and emits exact bytes, range hashes and referenced
literals. It does not execute target instructions. ACPT mapping reuses the
independent [committed partition report](evidence/partition-analysis-2026-10-12.json).
Image parsing, transfer, payload write, recovery execution and ROM ADFU are
separate contracts; none is proven safe by these findings.

Pinned SDK comparison:
[prepare and erase](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_upgrade.c#L187),
[initialization](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_upgrade.c#L1735),
[breakpoint save](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_breakpoint.c#L44),
[state values](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/include/ota_breakpoint.h#L21).
