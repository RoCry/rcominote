# Public ADFU helper: concrete read handlers

2026-10-12. Static offline analysis only. No USB connection, ADFU switch, helper
upload, target DLL execution or storage initialization performed.
SDK commit `26f51e584940d5b141cd1d09d2629d69b595f579`.

**LEOPARD `adfus.bin` contains real memory/storage read handlers.** This advances
the backup investigation beyond finding a generic host or a `read` string.
It does **not** establish that CoMi accepts this helper, that initialization
preserves storage, or that a complete CoMi backup can currently be made.

## Reproduce

```bash
uv run tools/inspect_helper.py \
  /path/to/lv_port_actions_technology/action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/adfus.bin
```

Script opens bytes only, verifies pinned SHA-256, checks independently recorded
command tokens/pointers, decodes selected Thumb code with Capstone 5.0.6, prints
JSON. A different helper fails immediately. No target execution/device I/O.
Selected observations retained in [evidence](evidence/helper-command-map-2026-10-12.json).
Full local disassembly/extracted Windows files remain under ignored
`artifacts/helper-static/`; blobs are not committed.

## Artifact identity and address basis

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `zephyr/tools/prebuilt/leopard/common/bin/adfus.bin` | 56108 | `470827c527a7111cebeb74e60dd32c007390df34453bce519998963db3ad5953` |
| Same directory `adfus_u.bin` | 57188 | `c17c6f67cd5b6a86ed2e5e96dbebe60384d185aa77e6447ddc47339a467580c5` |
| `boards/arm/ats3089p_dev_watch_sdnand_8b/adfus.bin` | 55784 | `0b5fa8a323349546b74f668ef00aa081cbd20c181b4d2e1150fac89e962536c7` |

Common `fw_product.cfg` defines load `0x2ff70000`, run `0x2ff70001`.
Addresses below use this configured base, **not measured execution**.
Binary begins Thumb instructions rather than ELF metadata. Common helper differs
from the tested reference board helper: choose by established board/storage
identity, not filename alone. `adfus_u.bin` semantics were not analyzed here.

## Dispatcher and handlers

At file `0x467c`, code requests exactly 16 bytes into stack storage, compares
returned count with `0x10`, compares first little-endian halfword against a
16-entry two-byte token array, then calls the corresponding Thumb pointer.

- Tokens at file `0xc2a`: `gf ri rm wm is ic si rc rs ws es cf rr sf rx af`.
- Handler pointer array at file `0xc4c`, 16 little-endian 32-bit entries.
- Dispatcher compares all 16 entries; unmatched token returns 5, short header
  returns 4. This is a helper command layer; ROM USB framing remains separate.

| Token | Thumb pointer | Code file offset | Observed static behavior |
|---|---|---|---|
| `rm` | `0x2ff7481d` | `0x481c` | Reads length from command+4 and memory address from command+8. Below `0x40000000`, passes address/length directly to output routine `0x2ff7bc98`. Higher addresses first copy into local buffer, in chunks ≤`0x4000`, then output. |
| `rs` | `0x2ff74bcd` | `0x4bcc` | Reads length from command+4 and offset from command+8. Calls selected storage object's virtual function at table+4 with `(object, offset, buffer, chunk_size)`; sends buffer through same output routine, chunks ≤`0x4000`. |
| `wm` | `0x2ff747c5` | `0x47c4` | Opposite flow: input routine `0x2ff7bd68`, then memory copy to supplied address. |
| `ws` | `0x2ff74b0d` | `0x4b0c` | Input followed by storage virtual callback at table+8. Confirms distinction from `rs`. |
| `is` | `0x2ff748ad` | `0x48ac` | Selects/initializes storage using command halfword+2; after successful init invokes virtual callback at table+`0x14` with argument 0. This callback resolves to a no-op for all three storage types; actual initializers remain deeper work. |

`rs` being a storage read is inferred from actual data flow and its opposite
`ws` handler, not merely its two-letter name. A USB trace is still needed to
establish the transport framing/handshake used by this helper. The shared output
routine's presence does not establish endpoints or host packet structure.

Important limit: storage callback return value is not checked before `rs`
transmits its buffer. A future host needs independent repeated reads and image
structure checks; a successful transfer alone would not prove valid backup data.
The header's fields+2/+12 are not fully interpreted; do not implement a live host
by filling them with guessed zeros.

### Storage callbacks: post-init no-op, NAND first-read initialization

The constructors resolve concrete seven-entry virtual tables. Offsets below are
file offsets; add configured `0x2ff70000` for code addresses, plus 1 for Thumb
function pointers.

| Type | Constructor | Table | Initializer | Read | Post-init callback (+`0x14`) |
|---|---|---|---|---|---|
| NOR, selector 0 | `0x3eb4` | `0x958` | `0x3c08` | `0x3e48` | `0x3af0` |
| SD, selector 1 | `0x2f6c` | `0x530` | `0x2c28` | `0x2d30` | `0x2574` |
| NAND, selector 2 | `0x3a10` | `0x87c` | `0x37d0` | `0x325c` | `0x3248` |

All three post-init callbacks are exact bytes `00207047`: `movs r0,#0; bx lr`.
Therefore calling this particular callback is not a flush or erase. This narrows
the uncertainty but does not prove initialization side effects absent.

NAND read callback `0x325c` converts offset to `offset >> 9` and size to
`(length + 511) >> 9`, checks sector bounds, and dispatches to `0x4334`.
Before that, first read calls lazy initializer `0x4584` unless a global initialized
flag is already set. Lazy initializer invokes `0x774c`, `0x81b2`, `0x9cf2`,
`0x44d0` and packed-structure indirect callbacks. Its full code range
`0x4584..0x4660` is retained locally. **A read request may therefore initialize
NAND translation state; absence of persistent metadata writes is unproven.**

NOR constructor reads the API pointer at ROM table `0x188+0x1c`, matching upstream
`p_spinor_api` position. NOR read callback handles a capacity boundary/two-chip
path and delegates via wrapper `0x3a28` to that driver's slot+`0x14`.
ROM implementation is absent from this artifact; cannot audit its initialization
or all read side effects from the public helper alone.

Bounded function matching checked GCC/ARMCC `libspinand.a`/`spinand.lib`, including
bootloader variants. Named library `spinand_init` bodies (120/108 bytes) differ
from helper `0x4584` (packed-field accesses, 220 bytes); no exact match established.
Several low-level NAND functions share only 16-byte prefixes. Those prefixes and
names do not justify labeling unresolved helper callees or claiming a no-write
initialization path.

## Original Windows host package actually present

SDK `tools/config_tool.rar` is a 97 MB RAR5 archive, SHA-256
`cec0aa29b8d77ba0a58178bb37d4790f621b2e500c918cd9cdc778094f450bf4`.
It contains English/Chinese `config_tool_1.28.01_20230825` MSI/CAB/setup payloads.
The English MSI File table contains 543 rows. Parsed its CFB streams/string pool
and File table; used mapped CAB IDs to extract selected files with 7zz.
No installer or Windows executable was run.

| File | Bytes | Relevant exports |
|---|---:|---|
| `HardwareEx.dll` | 165888 | `CCommUSB::ADFURead`, `ADFUWrite`, `CallingEntry`, `PollingReady`, `GetStatusInfo`, `GetSysInfo`, `ExtCommand`, `DoRawIO` |
| `Hardware_C.dll` | 13312 | Python bridge `Py_ADFU_Enum`, `Open`, `OpenEP`, `RAWIO`, `Py_SwitchAdfuByType` |
| `ActDbgUsb.dll` | 57344 | Debug stream `open/read/write/send_vendor_cmd` |
| `ATDUsbComm.dll` | 70656 | ATT `Open/Read/Write/DeviceInfo` |

Capstone static disassembly resolves `CCommUSB` constructor's type switch:

| Type | Constructor code RVA | Vtable VA | `ADFURead` implementation RVA |
|---:|---|---|---|
| 0 | `0x1020` | `0x10023b74` | `0x1870` |
| 1 | `0x35b0` | `0x10023cdc` | `0x3fa0` |
| 2 | `0xee90` | `0x10023dc4` | `0xf530` |
| 4 | `0x102a0` | `0x10023e2c` | `0x10a90` |

Type 3/default leaves object's implementation null. Exported `ADFURead` RVA
`0xebb0` dispatches via vtable+`0x1c`; exported `ADFUWrite` RVA `0xebf0` uses +`0x20`.
Concrete read implementations build `USBC` headers and check `USBS` responses,
but implement different command families/header layouts. Some write command byte
`0x05`, `0x09`, `0x08`; others contain `0xca` subcommands. Thus the exported name
alone cannot identify the CoMi protocol or a raw-flash address space.

Package `version.ini`: `SOLUTION=US302A_V1.0`, `CFGVER=0x20002000`.
It is an actual upstream host artifact worth investigating, but neither this
configuration nor exports demonstrate ATS308x/CoMi compatibility.
See [additional host identity research](host-selection-followup.md).

REA artifact inspection verified `HardwareEx.dll` identity as PE/x86 with SHA-256
`986582c243fb0f300c41c483cbc3100f6ff897057b4cace0d30510624a769aa3`:
`ev_60fe0f07a8979a6f8246f8a57b350ac7dbb98febb7764c37a75ad4ca762c214c`.
This evidence is inventory only; semantics above came from local static parsing
and Capstone. REA native providers unavailable: Ghidra unconfigured, Hopper
launcher missing, IDA unconfigured. RAR root unsupported by REA; extracted PE
inspection worked. No provider configuration was changed.

## NAND table and unstripped flash algorithm

Common `nand_id.bin`: 490 bytes, SHA-256
`2577551d322dddfaa179ba165d8ccb3c7b349adce0a4c5bed239011e868f181f`.
Decoded using upstream packed structs: 10-byte header, 8×60-byte records,
magic `0x53648673`; additive 32-bit record checksum `0x6cfeedcd` verified.
Entries: GD5F1GQ5UEYIG, W25N01KVxxIR, MX35LF1GE4AB, DS35Q1GB, F35SQA001G,
F35SQA512M, F50L1G41LB, GD5F1GM7UEYIG. **Supported-chip list; not CoMi chip ID**.

`zephyr/tools/flash_loader/keil/leopard_flash.FLM` is an unstripped ARM ELF.
Symbols include `Init`, `ProgramPage`, `EraseSector`, `EraseChip`, `BlankCheck`,
`storage_init`, `addr_translate`, `partition_get_partition_table`,
`partition_get_partition_download_addr`, and cache mapping functions.
Useful future target for explaining storage/address translation; algorithm load
or `Init` cannot be treated as a read-only SWD attachment.

## Concrete next investigations

1. Trace NAND lazy initializer and driver initializers beyond the now-resolved
   no-op post-init callbacks. Resolve NAND translation metadata writes and ROM
   NOR initialization semantics; exact library matching needs relocation-aware
   whole-function evidence, not names or short prefixes.
2. Identify matching LEOPARD production host, rather than treating US302A config
   tool as compatible. Search matching host's call sites for exact 16-byte command
   construction and transport send/receive; obtain a matching EVK USB trace as
   independent protocol oracle.
3. When transport/init behavior and CoMi hardware are established, implement a
   narrowly scoped read-only host. Require exact USB target, no implicit helper
   launch/erase, explicit bounds and repeated-read verification.

Follow-up [decompilation audit](helper-initialization-decompile.md) now proves
conditional erase/program paths reachable through NAND lazy initialization.
The post-init callback remains a no-op; that does not make the full read path immutable.

Known blocker to live readback: no matching CoMi ROM USB identity/transport,
helper-acceptance or storage initialization side-effect proof. Offline work in
steps 1–2 remains actionable.

## Fixed upstream sources

- [Helper bytes](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/adfus.bin)
- [Load/run configuration](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/fw_product.cfg)
- [Windows package](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/tools/config_tool.rar)
- [NAND packed structs](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/build_nand_id_table/id_tbl.h)
- [NAND checksum/generator](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/build_nand_id_table/id_tbl_generate.c)
- [Unstripped FLM](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/flash_loader/keil/leopard_flash.FLM)
