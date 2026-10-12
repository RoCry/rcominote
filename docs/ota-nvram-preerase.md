# OTA preerases the next user NVRAM segment

2026-10-12. Offline audit of verified FW010004 mapped application,
SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`.
[Actual bytes/instructions/initializer](evidence/ota-nvram-preerase-2026-10-12.json).
No device I/O, current RAM snapshot or observed erase.

## Decision

The [payload writer](ota-write-commit.md) has an additional conditional NOR erase
path outside the payload partition: it requests clearing **the next user NVRAM
segment**, leaving the current segment selected by the NVRAM state intact when
that state is valid. This is spare-space preparation, not `clear_all`, a factory
reset or evidence that all current settings are deleted. The older segment can
contain stale records; it is not necessarily already blank.

For the cached partition table and normal initialized two-segment state, only one
4 KiB block is selected: either `0x1ee000..0x1ef000` or
`0x1ef000..0x1f0000`, whichever is opposite the current segment. The actual live
segment offset has not been read, so this audit does not choose one address or
claim that either erase happened. Erase/read failure can be hidden from OTA.

## Actual call and fixed region identity

`10065c3a..10065c40` passes`1000` (4096 B) to thunk `100a52d2`, which jumps
directly to `10035fc4`. This occurs after the file start/size checks and image
offset lookup, before receive-worker startup and the first payload write.
It can recur for each file entering this writer path; file states6/7 skip it.

`10035fc4` loads fixed context `18001bac`. Its startup initializer at
`100df0ac` contains name `User Config` and segment size`1000`; initial base,
total size and segment offset are0. The established
[startup copy](startup-memory-readback.md#三段复制调用) copies this initialized
data into RAM. Those initial zeros are **not** current runtime values.

Actual NVRAM initialization `10036b10` requests partition file ID8 at
`10036b24..10036b26`, then stores that entry's offset+`0c` and size+`10` into
context+`18` and+`1c` (`10036b2c..10036b34`). The verified cached
[ACPT](partition-readback.md) identifies ID8 as `nvram_us`, storage0,
base`1ee000`, total`2000`. Initializer `10036bc0` obtains `spi_flash` via
`10036d1c`, installs its pointer in the context, then scans this region at
`10036c08`. Scan loads header records, validates magic/state/header CRC and
selects a segment by sequence (`10036800..1003685e`), assigning context+`24`.
No header or current sequence was sampled here.

## Exact address selection

In `10035fc4..10036026`, let `S=context.seg_size`, `T=total_size`,
`C=current seg_offset`, `L=requested length`:

- Round `L` up to`S` using `(L + S - 1) & -S`.
- Cap at `T - S`; the current segment's capacity is excluded.
- Start at `C + S`. If start+length exceeds`T`, erase the trailing region,
  wrap to offset0 and erase the remainder.
- Call region erase `10035ec4`; discard its return, return0.

With initializer `S=1000`, cached `T=2000`, request`1000`, and valid current
offset0 or`1000`, this selects exactly the other segment. At current offset
`1000`, the wrap first issues a zero-length trailing erase, then offset0/`1000`.
Region-relative offsets are translated by adding context base+`18` before the
driver call. This is conditional on successful initialization and valid state;
the function does not independently revalidate current segment metadata.

## Blank check and failure propagation

`10035ec4` requires a nonnull storage pointer, bounded range and start/length
aligned to4 KiB; invalid parameters return`-22`. For each requested sector it
calls blank check `10035dd0` with length`1000`; return1 skips erase. Otherwise:

1. Load storage device and compute `base + sector_offset` (`10035f18..20`).
2. Call `100a52d6` with `(device, address, 1000)` at `10035f22`.
3. Thunk loads API table at device+8 and invokes **erase slot+8**.

The erase result is ignored; loop continues and normal region erase returns0.
The outer clear also ignores validation failures and always returns0. Its OTA
caller does not check that result. The complete actual clear has no final flush
call, unlike the pinned SDK public wrapper.

Blank check reads128 B chunks through `10036ca8` and tests words for`ffffffff`.
That read implementation detects a negative lower-driver return and returns`-5`,
but blank check discards it (`10035dfa..10035dfe`). On a failed read it can inspect
stale buffer contents. Therefore neither a skipped erase nor OTA continuation
proves that the selected sector was blank, read successfully or erased.

## Reproduce

```sh
uv run tools/inspect_ota_nvram_preerase.py artifacts/mapped-system/mapped-system.bin \
  > /tmp/comi-ota-nvram-preerase.json
cmp /tmp/comi-ota-nvram-preerase.json docs/evidence/ota-nvram-preerase-2026-10-12.json
```

Tool SHA-checks input; selected complete clear/erase/blank-check/read functions
and bounded initialization/caller intervals exclude literal pools. It preserves
the 56 B startup initializer separately. SDK comparison only:
[region clear/erase](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/nvram/nvram_config.c#L300),
[public wrapper](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/nvram/nvram_config.c#L1361).
No concurrency, power-cut recovery or durability guarantee follows from this
bounded erase audit.
