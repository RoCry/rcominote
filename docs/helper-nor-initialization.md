# Public LEOPARD helper NOR initialization changes controller/address state

2026-10-12. Offline analysis; no execution, helper upload or device I/O.
Pinned SDK common `adfus.bin`, 56108 B, SHA256
`470827c527a7111cebeb74e60dd32c007390df34453bce519998963db3ad5953`.
This is a public helper, **not recovered CoMi code or demonstrated compatibility**.
Offsets below are file offsets; configured execution base is`2ff70000`.
[Exact instructions/literals/data](evidence/helper-nor-initialization-2026-10-12.json).

## Decision

Selecting NOR (`is` selector0) reaches a real ROM initializer and conditionally
changes Flash address mode before any `rs` data read. The visible helper storage
path does not call the NOR program/erase/write-status slots. However, the ROM
initializer implementation is absent, so absence of array or status modification
cannot be established. This closes the helper-side call inventory; ROM bytes or
an independently validated implementation remain the specific missing evidence.
No live backup procedure follows from this audit.

## Selection and initializer

`is` at`48ac` reads selector halfword+2. Exactly0 calls`2424`, which returns NOR
constructor`3eb4`. Constructor loads API pointer from **ROM address`1a4`**
(`188 + 1c`) into global`2ff7e084`, assigns storage vtable`2ff70958`, and assigns
primary info object`2ff7daec`. The object starts with controller base`40028000`.
`is` calls vtable initializer`3c08` with selector byte0. Only a negative final
initializer result causes failure; success post-init`3af0` is a no-op.

Complete initializer`3c08..3d30`, excluding literal pool:

| File instructions | Concrete behavior |
|---|---|
| `3c1c..3c30` | Configure GPIO64 through`2fe8`, drive high through`3004`, then callback`3baa` drives it high again and delays. These helper callees contain MMIO writes/delay, no storage API call. |
| `3c38..3c44` | Selector0 writes`1800` to controller/pin registers`40068018` and`4006801c`. Selector3 has a different register setup outside selected selector0 path. |
| `3c4a..3c5e` | Call ROM API slot0 with info pointer; retain result in r7. Then call slot8 to obtain chip ID and save it in helper RAM. No early exit after failed slot0. |
| `3c76..3c94` | If primary chip capacity byte (ID byte2) >`18`, call ROM slot`28` with argument4; set controller`40028000` bit16. SDK names this four-byte address mode. |
| `3c96..3cb4` | When info controller base is`40028000` (as primary initializer), compute primary capacity`1 << ID.byte2`, configure secondary-chip flags/callback via`3bc4`. |
| `3cb8..3d02` | Call ROM slot8 again for secondary ID; manufacturer byte0/`ff` means no secondary capacity. Otherwise compute its capacity, conditionally call slot`28` with4 for capacity >16 MiB. Restore primary info flags/callback via`3be8`. |
| `3d04..3d08` | Return the original slot0 result, after all intervening probing/configuration. |

The helper's log text `snor int ret=%d` at`3c42` occurs **before** ROM init and
passes zero on selector0. That message alone cannot prove ROM initialization
succeeded. The final return and host result still do not establish unchanged
Flash contents.

Nonlogging direct helper callees on this path are now resolved: `2fe8` writes a
GPIO control register; `3004` changes its output bit; `3baa` uses those GPIO and
delay routines; `3f50` polls timer`4000c108`; `3bc4`/`3be8` update RAM info fields.
The ROM calls are the remaining storage implementation boundary.

## Read and prior NOR close

NOR read`3e48..3eb0` splits a read across the primary capacity boundary. A
secondary read calls`3bc4`, reads through wrapper`3a28`, then calls`3be8` to
restore primary RAM fields. `3bc4` installs GPIO64 callback`3baa` in info+`14`
and sets/clears info+`24` bit1 according to secondary capacity; `3be8` restores
that bit according to primary capacity and clears the callback. These are RAM
configuration changes. They do not themselves prove restoration of Flash's
physical address mode.

Wrapper`3a28` delegates to ROM API slot`14`, passing info, offset, buffer and
length; it clears offset bit31 when supplied. It contains no program/erase call.
ROM read internals and their use of callback/flags remain unavailable.

`is` first closes any previous storage object. If that previous object is this
NOR implementation, vtable exit`3b9c` calls ioctl`23` with parameter0. Its exact
jump-table target`3b22` repeatedly calls ROM slot`0c` with command5 until status
bit0 clears. It does **not** use the neighboring ioctl`22` address-mode branch.
There is no visible explicit three-byte-mode reset in this NOR close path.
Other previous storage types are outside this NOR-only audit.

## ROM boundary and claim limits

Pinned SDK [ROM table declaration](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/brom_interface.h#L24)
and [NOR API layout](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spi_flash.h#L63)
support these slot names; actual helper independently proves the offsets/calls:

| ROM API slot | Visible callers | SDK interpretation / remaining unknown |
|---|---|---|
| `00` | `3c54` | `init`; internal commands, status/protection writes and failures unknown. |
| `08` | `3c5e`, `3cc0` | `read_chipid`; transaction implementation unknown. |
| `28` | `3c8a`, `3cfc` | `set_addr_mode(info,4)`; opcode and persistence chip/ROM-dependent. |
| `14` | Tailcall at`3a3e` | `read`; implementation not present. |
| `0c` | Prior NOR close loop`3b2c` | `read_status(info,5)`; implementation not present. |

No explicit calls to slots`10` write-status,`18` program, or`1c` erase appear in
the selected init/read/close storage paths. This bounded negative evidence does
not cover nested ROM behavior. Reference application driver source contains
other status/configuration paths and is not an exact substitute for ROM init.
The helper's two-chip support and geometry calculations also do not identify
CoMi storage or prove correct bounds on its hardware.

## Reproduce

```sh
uv run tools/inspect_helper_nor.py /path/to/common/bin/adfus.bin \
  > /tmp/comi-helper-nor.json
cmp /tmp/comi-helper-nor.json docs/evidence/helper-nor-initialization-2026-10-12.json
```

SHA-bound tool emits selected complete function intervals, exact bytes/hashes,
literal values, NOR table, primary info initializer and separate ioctl jump table.
It does not obtain ROM implementations or execute target instructions.
