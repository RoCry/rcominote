# NAND read initialization can reach erase/program transactions

2026-10-12 · static SDK-helper analysis; no CoMi execution or device I/O.

**Finding:** public LEOPARD helper's first logical NAND `rs` read can initialize a
translation layer whose conditional branches issue NAND block erase and page program
transactions. Treating `rs` plus its storage initialization as a guaranteed read-only
backup procedure is unsupported. This does **not** show that every initialization
writes, that these branches execute on healthy media, or that CoMi uses this helper,
selector, driver, or NAND geometry.

## Artifact and method

- SDK commit: [`26f51e584940d5b141cd1d09d2629d69b595f579`](https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579).
- File: `action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/adfus.bin`.
- Length: 56,108 bytes (`0xdb2c`). SHA-256:
  `470827c527a7111cebeb74e60dd32c007390df34453bce519998963db3ad5953`.
- Address basis: matching `fw_product.cfg` download address `0x2ff70000`;
  entry `0x2ff70001`. Every offset below is a **file offset**;
  runtime VA = `0x2ff70000 + offset`. Thumb pointers include bit 0.
- Actual Ghidra 12.1.4 headless analysis on Ubuntu, ARM little-endian Cortex/Thumb
  language; JDK `21.0.12.1+1`. Additional functions exported from the analyzed
  project with `-process adfus.bin -readOnly -noanalysis`.
- Decompiled C used to follow arguments and conditions; direct calls and command
  constants independently checked against helper bytes with Capstone 5.0.6.
  Ghidra calls/types are inferred, not source names or observed execution.
- Local ignored evidence: `artifacts/helper-static/ghidra-decompiled-initial.c`,
  `ghidra-initialization.c`, `ghidra-flash-primitives.c`, and
  `init-callsite-instructions.txt` in the same directory. No target code executed.

## Reachability from a read

Storage command dispatch and tables are recorded in
[helper-static-followup.md](helper-static-followup.md) and
[evidence JSON](evidence/helper-command-map-2026-10-12.json).

| File offset | Static role / relevant behavior |
|---|---|
| `0x4bcc` | `rs`: calls selected storage object's read callback, then sends buffer to host. |
| `0x87c` | NAND vtable; read slot holds Thumb pointer `0x2ff7325d`. |
| `0x325c` | NAND read: if initialized flag is zero, calls `0x4584`; sets flag only on success. Bounds check and requested read occur **after** initialization. |
| `0x4584` | Translation initialization: calls `0x41fc`; on success calls thunk `0x774c` → `0x5a4c`. Requires return value 1, then calls thunk `0x81b2` → `0x8100`, `0x9cf2`, and `0x44d0`. |
| `0x5a4c` | Large initialization/recovery routine. Several conditional branches call erase wrapper `0x5390`; later branches call program wrapper `0x53b0` with constructed metadata buffers. |

Minimal faithful pseudocode for NAND read, omitting logging:

```c
sectors = (length + 511) >> 9;
first_sector = offset >> 9;
if (!initialized) {
    if (initialize_translation(driver) != 0) return -1;
    initialized = 1;
}
if (first_sector + sectors > capacity) return -1;
return logical_read(driver, first_sector, buffer, sectors);
```

Even a zero-length or out-of-range NAND read reaches initialization before the
later checks. This is a static call-order observation, not a recommended probe.
`rs` also discards the storage callback's return value; successfully receiving bytes
alone does not prove that a valid backup was read.

## Conditional array modification paths

The first proven path is entirely within `0x5a4c`, reached during lazy initialization:

```text
rs → NAND read 0x325c → initializer 0x4584 → thunk 0x774c → 0x5a4c
  conditional erase:
    0x5390 → thunk 0xb888 → 0xb7e8 → 0xc820 → SPI transmit 0xd6b0
  conditional program:
    0x53b0 → 0xb40c → 0xcba8 OR 0xccdc → SPI transmit 0xd6b0
```

`0x5390` builds a packed block command via `0x4e44`; `0xb7e8` maps its block
with `0xb0d8`, multiplies by pages per block, calls `0xc820`, then polls readiness
with `0xc750`. `0xc820` assembles opcode **`0xd8` + 3 row-address bytes** and sends
four bytes through the SPI path. This is a block erase transaction.
Opcode interpretation is corroborated by Linux v6.12's primary
[SPI-NAND definitions](https://github.com/torvalds/linux/blob/v6.12/include/linux/mtd/spinand.h):
`SPINAND_BLK_ERASE_OP` is `0xd8` with three address bytes;
`SPINAND_PROG_EXEC_OP` is `0x10` with three address bytes. This corroborates
command meaning, without identifying CoMi's flash chip.

`0x53b0` builds a packed page command and calls `0xb40c`. That routine validates
configuration and page state, then selects ordinary/quad program paths:

- `0xcba8`: load page data; optional spare/OOB load with opcode `0x84`;
  then **`0x10` + 3 row-address bytes** through SPI.
- `0xccdc`: quad load path; optional spare/OOB load with opcode `0x34`;
  then the same **`0x10` + row** transaction.

The final `0x10` transaction is page program execute. `0xb40c` also has a separate
conditional `0xc820` erase path when its page-state checks fail; this is additional
potential modification, not necessary to establish the main chain.

Ghidra's `0x5a4c` output contains type-propagation and stack/dead-code warnings.
Consequently, branch variables have no asserted domain names here. Concrete
observations: erase calls exist at `0x6452`, `0x64da`, `0x65e2`, `0x68f4`,
`0x6a00`, `0x6b54`, `0x7156`; program calls at `0x72f4`, `0x7452`.
Around the latter branches, code fills a buffer with `0x42`, copies 0x7fe bytes
of internal table data, computes a check value, and programs two pages. These
operations support a translation-metadata interpretation; the exact on-flash
format and trigger conditions remain unproven.

Selected raw bytes, independently decoded as Thumb:

| File offset | Bytes | Instruction |
|---|---|---|
| `0x6452` | `fe f7 9d ff` | `bl 0x2ff75390` |
| `0x72f4` | `fe f7 5c f8` | `bl 0x2ff753b0` |
| `0x53a8` | `06 f0 6e fa` | `bl 0x2ff7b888` |
| `0x541a` | `05 f0 f7 ff` | `bl 0x2ff7b40c` |
| `0xb868` | `00 f0 da ff` | `bl 0x2ff7c820` |
| `0xc822` | `d8 23` | `movs r3, #0xd8` |
| `0xc84a` | `00 f0 31 ff` | `bl 0x2ff7d6b0` |
| `0xcc8c` | `10 23` | `movs r3, #0x10` |
| `0xccae` | `00 f0 ff fc` | `bl 0x2ff7d6b0` |
| `0xcdd2` | `10 23` | `movs r3, #0x10` |
| `0xcdf4` | `00 f0 5c fc` | `bl 0x2ff7d6b0` |

A second initialization path reaches `0x9cf2` → conditionally `0x91cc`;
that function calls erase thunk `0xb888` at `0x9378` and program wrapper `0xb40c`
at `0x93d6` (and another later call). `0x44d0(obj, 0)` also invokes routines
`0x7d20` and `0x8028` that process pending state. These reinforce the finding;
full write-set/condition analysis of all these branches is unfinished.

## Other initialization effects and limits

- `is` invokes selected storage init, then vtable slot `+0x14`. All three recorded
  post-init callbacks are exactly `movs r0, #0; bx lr`; that slot is not the concern.
- NAND initial storage setup `0x37d0` can call `0xb0c4` → `0xc720` to issue
  opcode `0x1f` (Set Feature), including feature addresses `0xb0` and `0xa0`
  under chip/configuration conditions. Feature-register effects/persistence depend
  on the actual NAND; they are separate from the proven array erase/program paths.
- Repeating `is` on an existing object first invokes vtable slot `+0x18`.
  That close/cleanup path has not been fully audited; skipping the lazy initializer
  alone would not establish an entirely non-mutating session.
- NOR uses ROM API callbacks whose implementation is absent from this blob.
  SD and NOR behavior cannot inherit the NAND conclusion or a read-only guarantee.
- Library symbol names and short byte matches were insufficient to identify an
  exact matching unstripped initializer; no symbol-based identity claimed.

## Reproduction and next decision

For the complete demonstrated path, export these additional functions from the
pinned analyzed helper project (in addition to dispatcher/storage/read/init entries):

```text
0x5a4c 0x5390 0x53b0 0xb888 0xb7e8 0xc820 0xb40c 0xcba8 0xccdc
```

Useful supporting exports: `0xc750`, `0xd664`, `0xd6b0`, `0x91cc`, `0xb0c4`,
`0xc720`; thunks `0x774c` and `0x81b2` resolve to `0x5a4c` and `0x8100`.
All fit within the artifact; `0x91cc` is the file offset for VA `0x2ff791cc`.

Before a backup implementation uses this helper on CoMi: identify actual storage
and helper compatibility, then establish an initialization/physical-read route
whose complete call path cannot erase or program. A raw physical NAND read would
also need geometry, ECC and OOB handling; logical `rs` is not a raw immutable
snapshot contract. Current evidence closes the narrower question: this helper's
NAND logical read path cannot be treated as intrinsically read-only.
