# Matching platform sources: useful LARK assets, incomplete BSP

2026-10-13. Bounded source inventory and primary-site verification. No device I/O,
loader execution, installation, build or contact message. SDK checkout verified
at `26f51e584940d5b141cd1d09d2629d69b595f579`. Online checks used localwebrs.

**The pinned SDK retains substantial LARK peripheral source, plus unstripped
Flash/SD loader ELFs; its application libraries are not a matched M4 set.**
The source/build/dependency inventory below replaces the narrower ATT/loader-only
view. A complete ATS3085L/CoMi BSP, chip programming manual,
matched production host package and official CoMi firmware remain unacquired.

Follow-up: [12 register layouts/47 IRQ values recovered from existing DWARF](lark-register-recovery.md), with self-contained partial header and compiler checks; [official CMSIS Pack index check](platform-next-route-review.md) acquired no matching package. Neither closes the BSP gap.

## Rebuildability: peripheral source survives, platform closure does not

Read the fixed tracked tree and its CMake/Kconfig selectors, not filenames alone.
No new build, device I/O or source modification. Paths below are relative to
`action_technology_sdk/zephyr/`; this is a source inventory, not a claim that
these drivers match CoMi's firmware revision or physical wiring.

| Layer | Retained material / build hook | Missing boundary / practical decision |
|---|---|---|
| CPU, startup, memory | M4 ATT recipes and typed debugger loaders described below | `soc/arm/actions/lark` absent in both OS trees; current SoC Kconfig discovers only retained series and CMake selects `${SOC_SERIES}`. Startup, IRQ, clocks, memory map and CoMi board configuration do not form a buildable target |
| Audio capture/output | [`drivers/audio/phy_lark`][audio-lark]: ADC/DAC/I2S RX/TX/SPDIF sources, selected by `CONFIG_SOC_SERIES_LARK`; ADC selected by `CONFIG_AUDIO_IN_ADC_SUPPORT` | Real register/algorithm reference, beyond ATT. ADC includes `soc.h`/`board_cfg.h`, uses `AUDIO_ADC_REG_BASE`, clock/reset IDs and DMA config; missing LARK platform and actual microphone/VMIC wiring still matter |
| PMU ADC / battery | [`adc_acts_lark.c`][adc-lark], `CONFIG_ADC_ACTS_LARK`; internal/external battery directories selected by their LARK Kconfig options | PMU ADC is distinct from audio ADC. Charging code depends on SoC/ATP and board configuration. External tree contains CW6305/CW2015-specific files; this does not identify CoMi's charger or prove a completed external-charger implementation |
| I2C/SPI transfer engines | `i2cmt_lark.c` / `spimt_lark.c`; `CONFIG_I2CMT_LARK` / `CONFIG_SPIMT_LARK` | These are named transfer-engine implementations, not proof of an entire matched storage or display stack. Do not replace ordinary I2C/SPI drivers merely because these filenames say LARK |
| Bluetooth controller interface | [`drivers/ipmsg/lark/ipmsg_btc.c`][ipmsg-lark], its own CMake file and ATT controller sources | Parent `drivers/ipmsg/CMakeLists.txt` adds only LEOPARD: retained file is not currently wired into a LARK build. Requires `soc_memctrl.h`, `soc_atp.h`, calibration and controller image; not a complete BLE stack |
| USB | Shared `usb_otg_aotg.c` plus [`usb_aotg_lark.h`][usb-lark]; shared header selects it when `CONFIG_USB_AOTG_OTG_VERSION == 0x551A22CF` | Substantial USB controller definitions survive. Driver requires SoC clock/reset/PMU APIs; neither this selector nor the USB helper proves CoMi's D+/D− wiring or normal-mode enumeration |
| NOR / SD | Named/type-rich LARK Flash/SD ELFs, audited below | Useful implementation references; unmatched initialization/controller/error behavior blocks unchanged use as backup tools |
| Media / application BLE | Public interfaces and shipped static archives | Present archives declare v8-M/FPv5, not a demonstrated M4 dependency set; see measured attributes below |

The retained ADC source is also **not an exact source reconstruction**: its
`phy_adc_init` calls reset, clears the full driver-data structure and initializes
the ADC LDO ([source][adc-init]); [actual CoMi init](init-audio-board-evidence.md)
is54B and clears one byte before its observed register update. Shared device/API
ancestry helps comparison, but does not establish identical structs or revision.

### Binary dependencies: measured architecture, not directory inference

GNU readelf2.42 `-A` on existing Ubuntu checkout; archive SHA256 independently
matches Mac and pinned SDK files. [Compact evidence][library-evidence] records
hashes, object counts and attribute distributions. All inspected member records:

| Archive; relative to SDK root | Objects with attributes | CPU / FPU / call ABI declarations |
|---|---:|---|
| `framework/bluetooth/bt_stack/libbt_stack.a` |24| ARMv8-M.mainline, FPv5/FP-D16 for ARMv8, VFP registers |
| `framework/media/libmedia.a` |23| ARMv8-M.mainline, FPv5/FP-D16 for ARMv8, VFP registers; one object explicitly names Cortex-M33 |
| `application/bt_watch/src/att/att_patterns/lib/lark/socatp/libatpatt.a` |1| ARMv7E-M, VFPv4-D16, VFP registers |

These are ELF declarations, not a proof that every object executes an unsupported
instruction. Nevertheless, neither v8-M archive is established as a compatible
CoMi M4 library; a successful M33 link cannot prove that. The M4 ATP test library
is not a replacement for application media/BLE libraries, and hard-float calling
convention alone does not make the architectures interchangeable. CoMi FPU
configuration and application ABI remain independently unmeasured.

Reproduce with `readelf -A ARCHIVE` and `sha256sum ARCHIVE` at the fixed SDK
commit; inspect each member rather than taking the first CPU tag. This bounded
audit does not classify every shipped library or reconstruct closed code.

**Route decision:** public LARK code is a useful peripheral-source base, not
merely a collection of tools. Changing M33 to M4 and inventing a board directory
does not close missing SoC startup/headers or binary dependencies. Prefer a
matched LARK platform package including M4 media/BLE libraries and controller/
DSP resources. If unavailable, a future minimal M4 RAM diagnostic can omit media
and BLE; even that still requires a known load/entry/exit contract. A full recorder
port is a separate stage. Park individual register/callee questions until that
stage needs them; do not expand this inventory into another unbounded audit.

## New findings in already acquired source

### LARK debugger loaders exist below the README's advertised path

The SDK's [internal JLink device table][jlink] explicitly declares:

| Property | LARK declaration | Practical value / boundary |
|---|---|---|
| CPU | `JLINK_CORE_CORTEX_M4` | Matches measured core class; does not identify exact CoMi silicon revision |
| Loader work RAM | `01010000`, size `c000` | Same address lineage as actual boot and LARK ADFU; not proof this whole region is free in running CoMi |
| Flash banks | system `10000000`, bootloader `11000000`, raw `20000000` | Debugger/loader address contract; **not proof of an ordinary CPU-readable raw NOR alias** |
| Bank maximums | mapped banks `1000000`, raw `2000000` | Loader limits, not measured Flash capacity |

The [README][readme] directs installation from top-level
`tools/JLinkDevices/Actions`, whose [table][top-jlink] exposes only LEOPARD/M33.
The deeper SDK directory actually retains these tracked artifacts:

| Artifact | File inspection | SHA256 |
|---|---|---|
| [LARK Flash ELF][flash-elf] | ARM EABI5 ELF, debug_info, not stripped | `588386943adff3ea2ea8163fa5148b4686d5e3a568acd632028c46628bfb3584` |
| [LARK SD ELF][sd-elf] | ARM EABI5 ELF, debug_info, not stripped | `ccfb3ffc17ce11e853c6539ccc1810657709c48cb72f7d1ab775915874b7c4ee` |
| [LARK Keil FLM][flm] | ARM EABI5 ELF, not stripped | `1ca3b308dc45ee860d197670e25072d2598ffcd2d43df9cb73a7a465929ede82` |

Confirmed with tracked-file inventory, `file` and SHA256; subsequent bounded
symbol/type inventory appears below. Debug information supplies function names,
types and source-location clues, not embedded original source or proof of a
safe read-only initializer. These are programming
algorithms: do not execute them as a passive probe. The existing unchanged
[LARK ADFU initializer rejection](lark-nor-init-side-effects.md) still stands.

**Use:** compare named storage interfaces against actual CoMi drivers; stop at
concrete register/ABI differences. This can advance backup-tool design and
own-firmware storage support without USB access.

### M4 source fragments survive outside the missing SoC directory

Under `application/bt_watch/src/att/att_patterns`, [scripts/lark.mk][lark-mk]
contains genuine GCC and ArmClang M4 build options: `CONFIG_SOC_LARK`,
`-mcpu=cortex-m4`, Thumb, hard-float and `fpv4-sp-d16`. The [LARK library build][lib]
collects common utility/ring-buffer/compensation sources plus LARK-specific
clock and Bluetooth-controller code. This is more than the already known Keil
project template; it is reusable compiler/ABI and peripheral-reference material.

However, the shared [configuration][att-config] defaults to LEOPARD, and the
[loader linker script][linker] consumes a shared [address file][addresses]
setting `ATT_LOADER_ADDR=30044000`, size `a00`, subsequent pattern size `4000`.
That address has not been matched to CoMi. Merely entering a directory called
`lark` does not make the present defaults a valid M4/CoMi build. No build was
attempted, and this is not an independent bootable application BSP.

The shared ATT [ROM API header][brom] starts at `188`; its field order places
ADFU at `19c`, CRC32 at `1b8`, image checksum at `1c8`, agreeing with the
[actual boot-referenced table](actual-rom-adfu-entry.md). This is useful source
ancestry evidence. Other fields, signatures and revision compatibility remain
unverified; do not extend those three matches into a claim that every ROM API works.

LARK-specific [pin-control][pinctrl] and [device configuration][dev] headers also
survive. They offer pin-function bitfields and DMA/audio/PMU names for comparison.
The listed I2C0 pin pairs do not include the actual firmware's GPIO14/15 candidate;
therefore these headers are not a substitute for CoMi wiring evidence. Both
`zephyr/soc/arm/actions/lark` and `bootloader/soc/arm/actions/lark` remain absent
from the fixed Git tree. Complete BSP acquisition is still a real gap.

## Follow-up: two ELF symbol/type inventories

Same date and hashes above; read-only `readelf` on the existing Ubuntu checkout.
Inspected headers, segments, symbol tables, DWARF info and source line tables.
No loader execution or function disassembly. REA's available layout inspector
supports ELF64/x86-64, so these ARM ELF32 files used existing GNU readelf directly;
no tool installation. Symbol values below retain the Thumb bit; DWARF code
addresses are even. These addresses belong to the loaders, not running CoMi.

### Build ancestry and memory constraints

Both producers identify GCC **10.2.1 20201103**, Cortex-M4, Thumb,
`fpv4-sp-d16`, hard-float, `-O3` and `-fshort-enums`. Source paths identify
**`BAREMETAL_CMSIS/lark_sdk`**, not a complete Zephyr BSP:

- Flash: `Projects/Flashloader/SES/Src/{FlashPrg,FlashDev,partition}.c`;
  `Drivers/LarkHal/lark_hal_{spicache,storage,uart,wdg,conf}.c`.
- SD: `Projects/Flashloader/SES/SD_Src/{SdPrg,SdDev}.c`;
  `Drivers/LarkHal/lark_hal_card.c` plus UART/watchdog/configuration units.
- DWARF source tables name `Drivers/CMSIS/Device/Include/{lark,system_lark}.h`
  and `lark_hal_card.h`. The SD build's outer path contains `Source_GL6189`;
  this is a build-directory label, not proof CoMi's chip is GL6189.
- Exact `lark_hal_storage.c`, `lark_hal_card.c`, `lark_hal_spicache.c`, `lark.h`
  and `system_lark.h` were absent from the pinned tracked-file inventory.
  **Those filenames now make vendor/source acquisition specific.**

| ELF | Code range, end exclusive | NOBITS data | Descriptor | Total linked extent |
|---|---|---|---|---|
| Flash | `01010000..01010f1c` | `370` bytes | `0101128c`, size `10a0` | `01010000..0101232c` |
| SD | `01010000..01011120` | `200c` bytes | `0101312c`, size `10a0` | `01010000..010141cc` |

Both declare RAM budget `01010000..0101c000`, stack `100`, heap `100` bytes.
SD has an **8192-byte `rbuf` at `01011124`**, then `g_card_rca` at `01013124`
and `g_card_type` at `01013128`. NOBITS bytes require initialization; copying
only file-backed sections would not reproduce the complete runtime contract.
Both ELF entry values point at **ProgramPage**, not SystemInit or a reset
vector. These are debugger-invoked algorithms, not standalone bootable firmware.

### Named interfaces worth retaining

| Artifact / symbol | ELF value | ELF kind / size | DWARF contract or significance |
|---|---|---|---|
| Flash `SEGGER_OPEN_Read` | `01010681` | GLOBAL FUNC /160 B | `int(unsigned long Addr, unsigned long NumBytes, unsigned char *pDestBuff)` |
| Flash `addr_translate` | `010108ed` | GLOBAL FUNC /212 B | `int(unsigned int logical_addr, flash_info *info)` |
| Flash `partition_init` | `01010871` | GLOBAL FUNC /124 B | `int(void)` |
| Flash `storage_init` | `01010ad1` | GLOBAL FUNC /444 B | `void(void)`; initialization effects uninspected |
| Flash `spicache_init` / `spicache_enable` | `010109f9` / `01010a55` | GLOBAL FUNC /92 B,72 B | Named mapping/cache entry points; compatibility uninspected |
| Flash `g_param_part` | `01010f24` | LOCAL OBJECT /872 B | `system_param_part` |
| SD `SEGGER_OPEN_Read` | `01010399` | GLOBAL FUNC /116 B | Same host read signature as Flash variant |
| SD `brom_card_read` | `01010d9d` | GLOBAL FUNC /440 B | `unsigned int(unsigned int addr, unsigned int sector_len, unsigned char *buf)` |
| SD `brom_card_write` | `01010f55` | GLOBAL FUNC /460 B | Same parameter types/names as read; proves write API is also present |
| SD `card_access_init` | `0101087d` | GLOBAL FUNC /376 B | `unsigned int(unsigned int *p_card_type, unsigned int *p_card_rca)` |
| SD `sdcard_init` | `01010ccd` | GLOBAL FUNC /116 B | `unsigned int(void)` |
| SD `card_mfp_select` | `010107f5` | GLOBAL FUNC /136 B | `void(int mfp)`; pin selection requires comparison |

Names and argument labels are recorded metadata, not execution evidence or
verified units/error semantics. In particular, `brom_card_read` has code inside
this ELF; its name does not mean it is an actual CoMi ROM-table function.

### Recovered types: useful comparison boundaries

All sizes/offsets below are decimal unless prefixed `0x`; DIE offsets identify
entries in `readelf --debug-dump=info` for the hash-bound files above.

| ELF / type | DIE / size | Selected fields and offsets |
|---|---|---|
| Flash `spi_info` | `0xb7e` /32 B | base0, flag4, cs_gpio8, bus_width10, delay_chain11, freq_khz12, dma_base16; set_cs20, set_clk24, prepare_hook28 |
| Flash `spinor_info` | `0xc51` /40 B | spi0, chipid32, flag36 |
| Flash `spinor_operation_api` | `0xc86` /32 B | init0, set_clk4, read_chipid8, read_status12, write_status16, read20, write24, erase28 |
| Flash `flash_info` | `0xdde` /12 B | flash_offset0, storage_id4, max_size8 |
| Flash `partition_table` | `0x2712` /744 B | entries start16; CRC740. Entry size24; name0, type8, file_id9, mirror_id10, flag11, offset12, size16, entry_offs20 |
| Flash `system_param_part` | `0x2851` /872 B | partition table0, firmware version744 |
| Flash `MEM_Type` | `0x73e` /784 B | mapping/address pairs at `0x300/304` and `0x308/30c`; agrees with actual boot's slot0 offsets, not proof of every register definition |
| Flash `SPI0_Type` | `0x3460` /24 B | CTL0, STA4, TXDAT8, RXDAT12, BC16, SEED20 |
| SD `brom_sdc_reg_t` | `0x2b89` /56 B | EN0, CTL4, STATE8, CMD12, ARG16, five response words20..36, DAT40, BLK_SIZE44, BLK_NUM48, SEED52 |
| SD `brom_dma_reg_t` | `0x2abe` /32 B | ctl0, start4, saddr8, saddr1=12, daddr16, daddr1=20, framelen24, remain_framelen28 |

The 744-byte table/24-byte entries provide a stronger format comparison with
[actual ACPT](partition-readback.md). The typed NOR API separates read from
status/write/erase operations, helping a future side-effect audit. Neither
establishes which implementation or ROM revision the loader selects.

**MMC_1 remains a comparison target, not a match:** actual firmware binds
`MMC_1` to `40058000` and has its own wrapper/state ABI
([evidence](card-state-readback.md)). This inventory recovers the loader's SDC
register offsets but does not establish its selected controller base, pinmux,
address units or equivalence to that actual driver. Do not transplant the API.

**Route judgment:** the bounded NOR/SD comparisons below resolve debugger address
selection, initialization boundaries and the SD controller mismatch. Do not
recursively expand every helper.

Reproduce against either ELF with `readelf -h -l -SW`, `readelf -sW`,
`readelf --debug-dump=info`, and `readelf --debug-dump=rawline`; check SHA256
first. No persistent analysis tool or per-function report was added.

## NOR comparison: host selector, cache window and initialization

Same ELF/hash, static analysis only. Root examined read/translation and fixed
literal pools; Astra independently examined initialization. [1774B of selected
instructions and literal bytes](evidence/lark-storage-contract-2026-10-13.json)
retain eleven named regions; code fully decodes with Capstone5.0.6, literal pools
excluded. REA opened/identified the ARM ELF, but native analysis reported no
configured Ghidra/Hopper/IDA provider; existing LLVM objdump and Capstone supplied
the instruction evidence. No target execution, live memory probe or new CLI tool.

### `20000000` is a debugger selector, not a proven live raw alias

`addr_translate` at010108ec tests these unsigned address intervals:

| Host address; end exclusive | Output / condition |
|---|---|
| `10000000..10400000` | Require valid cached partition table; first type2/system entry offset + address−10000000; storage0, return0 |
| `11000000..11400000` | Require table; first type3/recovery offset + address−11000000; storage0, return0 |
| `20000000..30000000` | address−20000000; storage0, return0; **no partition-table prerequisite** |
| `30000000..40000000` | Set storage3, return−1 |
| `60000000..a0000000` | Set storage2, return−1 |
| `a0000000..e0000000` | Set storage1, return−1 |
| Other addresses, invalid table or no matching type | Return−1 |

Table scan uses30 slots of24B, not just declared `part_cnt`; type, physical
offset and validity gate control the selection. It does not inspect mirror,
encryption flags or partition size, and does not populate `flash_info.max_size`.
Fixed4 MiB logical windows and256 MiB raw-selector window are software ranges,
**not capacity evidence**.

`SEGGER_OPEN_Read` at01010680 calls translation; failure returns0. For successful
storage0 it passes destination, **10000000 + translated physical offset**, and
requested byte count to `soc_memcpy`, then returns that count. It does not check
count against partition/device bounds or propagate the ROM memcpy return value.
`soc_memcpy` tail-branches through ROM table1ac. This is a cache-backed read,
not an SPI-read command issued by the read handler itself.

Concrete comparisons using [CoMi's actual table](partition-readback.md), conditional
on that table being accepted by this loader; **not observed loader execution**:

| Host request | Physical offset selected | Loader CPU copy source |
|---|---|---|
| `10000200` | `00024200` (system +512B) | `10024200` |
| `11000000` | `00004000` (recovery start) | `10004000` |
| `20000000` | `00000000` (raw NOR start) | `10000000` |
| `203fffff` | `003fffff` (last byte of configured4 MiB) | `103fffff` |
| `20400000` | `00400000`, still accepted by translator | `10400000`, beyond that configured capacity |

The loader establishes its own mapping before these reads. Its `spicache_init`
writes `40010300=1000000f`, `40010304=0`, `40010308=1800000f`, `4001030c=0`:
two CPU windows backed by physical offset0, without offset bit31 set. Actual
[CoMi boot mapping](actual-boot-flow.md) writes the same slot0 register pair,
but selects recovery offset4000, CPU11000000 and a conditional offset bit31;
running system mapping is another lifetime. Shared register layout supports
ancestry, not interchangeable mapping state. **Do not issue `mdb 20000000` in
the running app on the strength of this debugger table.**

### Read/Verify selection does not skip initialization

`Init` disables interrupts and resets clocks/pinmux/system state; before testing
its mode argument it unconditionally calls mfp_init, uart_init, storage_init,
spicache_init, spicache_disable, ROM chip-ID, spicache_enable and partition_init.
Read/Verify mode is therefore not a state-preserving shortcut. Init returns0
without propagating partition_init failure; inspected code does not restore the
incoming interrupt/mapping state.

`storage_init` uses SPI base40028000. TXDAT(+8), with separate controller/CS
transitions, receives **AB;06;C5 00;E9;FF;FF FF**. Instruction sites10b0e,
10b48,10b7e/80,10bb4,10be8,10c22/24 are retained in the evidence JSON.
Pinned SDK [spinor.c][spinor] namesC5 as extended-address-register write andE9
as exit4-byte-address mode. Device-specific effects/persistence remain unproved;
do not mislabel these as array erase/page program. It then calls slot0 of the
table atROM1a4 withr0=0: an uninspected ROM initializer. Busy polling has no
visible timeout. Four inspected init interfaces contain no direct array erase
or page-program call; unknown ROM behavior prevents a full no-write conclusion.

`partition_init` first checks parameter offset1000, including ACPT/FVER CRCs,
then tries3000 if the first copy fails (`010108d8..010108e2`). Either valid copy
caches872B and sets the validity flag; both failing blocks logical100/110
selectors. Raw200 selector does not depend on that flag.

**Decision:** retain this loader as a named/typed implementation reference for
raw-versus-logical reads. Unchanged `Init→Read` is not approved as a preserving
backup procedure; simply skipping Init is also unsupported because read depends
on the cache map. Next source target is the identified bare-metal LarkHal/
Flashloader package. Initialization ROM internals and per-register roles stay
recorded gaps; no recursive callee audit is required to reach this decision.

### Source-package acquisition boundary

After identifying the package, exact public searches for `BAREMETAL_CMSIS` +
`lark`, `lark_sdk` + Actions, and ATS3085L SDK GitHub returned no results;
filename search produced unrelated pages. An authenticated GitHub code query
`filename:lark_hal_storage.c` returned `total_count:0`. No matching source was
acquired. These are dated indexed-search outcomes, not proof of absence/private
availability. Stop this search pass; resume on a new package/repository/vendor
entry, keeping the exact LarkHal/Flashloader filenames as acquisition targets.

## SD comparison: different controller, read-error propagation defect

Same SD ELF/hash; Astra examined five named interfaces, root independently
checked the host read wrapper. Their complete symbol-bounded bytes and ARM
`$t/$d` code/literal separation are retained under `sd_reference` in the same
[instruction evidence](evidence/lark-storage-contract-2026-10-13.json). No device
I/O or target execution. Stop at the demonstrated mismatch; no callee expansion.

| Question | Inspected instructions / comparison |
|---|---|
| Controller | `card_access_init` literal010109dc, `brom_card_read` literal01010f38 and `card_mfp_select` literal01010874 all select **40054000 / SD0**. CoMi's [actual MMC_1 configuration](card-state-readback.md) selects **40058000 / SD1** |
| DMA | `01010df8..01010e16` uses channel registers4001c100, CTL85, source40054028 (SD0 DAT), destination=buffer, frame length=`sector_len<<9`; start bit0 |
| Length | `01010ddc..01010de2` sets BLK_SIZE512, BLK_NUM=`sector_len`; DMA agrees. Bottom-level length is a count of512B sectors |
| Address | `01010dd4..01010df6` tests `g_card_type` bit7; clear→`addr<<9`, set→addr unchanged in ARG. Input is sector address, converted for byte/block card mode |
| Transfer/error | CMD18/read-multiple-block, then CMD12/stop; inspected STATE mask8017. Normal path returns0, visible error/timeout paths1 |
| Poll budgets | Counts000f4241 for transfer/DMA and000186a1 for stop, callingudelay(1); no wall-clock-duration or all-callee boundedness claim |

Controller names follow pinned [soc_regs.h][soc-regs]. Those shared register
constants do not establish exact silicon identity or usable board pins.

`SEGGER_OPEN_Read` at01010398 exposes a byte-addressed host selector:

- `010103c6..010103d2`: requireAddr≥a0000000 and uint32(Addr+NumBytes)<e0000000;
  no separate overflow check.
- `010103d4..010103e0`: sector address=`(Addr−a0000000)>>9`, sector count=
  `uint32(NumBytes+511)>>9`. No alignment rejection or first/last-sector trimming;
  a non512-multiple request can make the lower layer write beyond requested length.
- `010103e2`: callbrom_card_read; result is printed. **01010402 returns the original
  requested NumBytes even on a bottom-level failure.** Range rejection returns−1,
  unlike the NOR wrapper's0. Host full-length success is not a valid backup oracle.

`sdcard_init` tries pinmux0 then1. Both configure the same SD0: first writes
control addresses4006802c/30/34 with300a/180a/180a; second uses40068008/04/0c.
Failed selections reset their pin modes to1000. These are reference register
addresses, not measured CoMi wiring or controller switching.
Subsequent send_init_cmd and card_reset internals remain unread.

`card_access_init` has CMD8→CMD55/CMD41 and CMD1 fallback paths, setting type
codes1/0x82 or3/0x83. Do not transplant those enums into CoMi's distinct
type0/CCS1 driver state ABI. Only bit7's addressing role is directly established
by these loader instructions.

**Decision:** retain SD command/DMA/addressing as HAL implementation reference.
Unchanged loader is neither a matched MMC_1 driver nor a reliable SD exporter;
do not adapt pins alone or trust its wrapper length. This comparison is complete
within the declared scope. Return to matching platform artifacts and overall
hardware understanding, not the unread SD initialization callees.

## Official access routes: live result and actual value

| Source checked | Result | Value for own firmware / backup |
|---|---|---|
| [CubieDVB-ATS3085 product page][cubie] | Still names ATS3085L, M4F, Zephyr/Vela, open software/hardware design and closed production material. Development-material field remains blank; explicit support and sales contacts exist | Concrete party from which to obtain an M4 BSP, schematic or evaluation kit. Public page itself provides none of those files. No contact sent |
| [Actions technical-support portal][support] | Live login page; no authenticated session used | Official access boundary for chip/BSP/production documentation. Cannot claim the desired ATS3085L package exists behind login without seeing it |
| [Actions/CyweeMotion announcement][partner] | Explicitly distinguishes ATS3085C/L/S/3089 SDKs and describes API headers, libraries, examples and documentation supplied for each family | Confirms family-specific SDK material exists in the vendor ecosystem. No SDK archive or programming manual linked in the inspected article |
| [Pinned LVGL/Actions README][readme] | Explicitly targets ATS3089P EVB/M33; points to Windows configuration tool and Actions board acquisition | Existing host/toolchain reference. Its EVB wiring, flashing steps and erase setting do not transfer to CoMi |

Cubie page still conflicts internally on NAND versus 32-Mbit NOR and its DSP
clock differs from the [manufacturer brochures](ats3085l-primary-sources.md).
Those brochures establish family specifications, not a register/programming
manual. No fresh full chip manual was acquired in this pass.

Two focused searches only: `site:cubietech.com ATS3085 SDK download` and
`site:actions-semi.com ATS3085L 开发 SDK`; followed the primary pages above.
No repeated empty-repository search, generic DLL scan or retry of the known
private-address Seeyon installation host.

## Public history and Vela provenance: bounded acquisition result

Same date; [compact primary-source inventory][acquisition-evidence]. The local
LVGL checkout was shallow, so its single commit could not answer historical
availability. GitHub exposes28 master commits. Five **non-truncated** recursive
trees cover the first SDK import, duplicate SDK roots, cleanup, RC and latest SDK
updates: `ef24e7fe`, `2d6ad9d3`, `9942d4ca`, `cd96ad01`, `9c9ef49f`.
None contains a `soc/arm/actions/lark` directory or LARK/ATS3085L board path;
the only retained Actions `Kconfig.series` files identify LEOPARD. Both historical
blob variants explicitly select `CPU_CORTEX_M33`; the oldest is not a hidden M4
target under that name. This covers
those snapshots, not every object ever uploaded to GitHub.

Astra also checked current6 upstream branches,1 tag,0 releases and7 direct
forks. Five fork master heads equal pinned26f51e5; two are upstream ancestors.
Inspected extra branch changes supply no new SDK package; all7 forks have no
release attachments. The SDK PR's source fork, `junminacts/lv_port_actions_technolgy`,
also has the same master and no tags/releases. Stop this ref/history acquisition
pass; resume on a genuinely new SDK commit, fork payload or vendor archive.

The Cubie board's Vela claim led to a separate primary source: openvela's fixed
[chip-porting guide][vela-porting] includes `CONFIG_ATS3085X_BOOTLOADER` and an
ARMv7-M toolchain example. Its nearby linker example uses these origins:

| Example region | Origin; **not measured CoMi configuration** |
|---|---|
| Flash / SRAM / PSRAM | `10000000` / `01000400` / `18000000` |
| DSP inner RAM / shared RAM | `01054000` / `0106a600` |

The guide does not identify the exact ATS3085 variant, board or example provenance.
Neither region lengths nor its entry symbol are a CoMi linker recipe. CoMi's
observed OS remains Zephyr; Vela material is an alternative chip-layer source lead.
The official [vendor-layout guide][vela-vendor] places chip implementations under
`vendor/<vendor>/chips` and boards/libraries in separate vendor directories.
Thus absence from main NuttX's ARM tree does not prove no vendor implementation.
Inspected public open-vela/NuttX and Apache NuttX ARM directories plus bounded
open-vela code searches acquired no Actions/LARK vendor source package.

**Acquisition targets now have three distinct forms:** complete LARK Zephyr
SoC/BSP plus matching M4 application libraries; `BAREMETAL_CMSIS/lark_sdk`
LarkHal/Flashloader source; or an Actions Vela vendor package with chip/startup/
clock/register definitions. Each can contribute different layers. No matched
source package, official firmware or new device transfer route was acquired here;
do not repeat public absence checks or treat a generic OS port as a CoMi BSP.

## Availability and stopping decisions

- **Available now:** LARK audio/ADC/power/USB/IPMSG source with the build-hook and
  dependency gaps above; M4 compiler recipe/source fragments, ROM API declaration,
  LARK pin/device definitions, unstripped Flash/SD algorithms, existing public
  ADFU binaries. Useful for comparative offline platform work; none proves a
  complete matching BSP or an executable CoMi backup procedure.
- **Not available from inspected public pages/tree:** exact
  `ats3085l_dvb_watch_ext_nor_max` BSP, full chip programming manual, confirmed
  CoMi production host configuration and official full firmware image. This is
  a bounded acquisition result, not a claim that these artifacts do not exist.
- **Official CoMi firmware:** no new acquisition entry found here. The earlier
  [Seeyon deployment lead](seeyon-backend-reference.md) concerns a backend JAR;
  do not rename it a device firmware package or repeat its inaccessible host.
- **Next platform work:** NOR/SD interface comparisons above are complete within
  their stated static boundaries. Acquire the now-identified bare-metal source
  package or other matching platform material. External acquisition resumes when a real authenticated download,
  vendor-provided BSP, board schematic or matched package becomes available.

[readme]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/README.md
[top-jlink]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/tools/JLinkDevices/Actions/LEOPARD/Devices.xml
[jlink]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/flash_loader/JLink/JLinkDevices.xml#L6-L10
[flash-elf]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/flash_loader/JLink/Devices/Actions/LARK/lark_flash.elf
[sd-elf]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/flash_loader/JLink/Devices/Actions/LARK/lark_sd.elf
[flm]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/flash_loader/keil/lark_flash.FLM
[lark-mk]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/att/att_patterns/scripts/lark.mk
[lib]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/att/att_patterns/lib/lark/Makefile
[att-config]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/att/att_patterns/scripts/config.mk
[linker]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/att/att_patterns/loader/lark/link.ld.S
[addresses]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/att/att_patterns/include/att_linker_addr.h
[brom]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/att/att_patterns/include/soc-include/brom_interface.h
[pinctrl]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/cfg_drv/pinctrl_lark.h
[dev]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/cfg_drv/dev_lark.h
[spinor]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spinor/spinor.c#L61-L75
[soc-regs]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_regs.h#L61-L62
[cubie]: http://www.cubietech.com/product-detail/cubiedvb-ats3085/
[support]: https://cs.actions-semi.com/loginIndex.html
[partner]: https://www.actions-semi.com/index.php?id=7761
[audio-lark]: https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/audio/phy_lark
[adc-lark]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/adc/adc_acts_lark.c
[ipmsg-lark]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/ipmsg/lark/ipmsg_btc.c
[usb-lark]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/usb/otg/usb_aotg_lark.h
[adc-init]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/audio/phy_lark/phy_audio_adc.c#L3595-L3650
[library-evidence]: evidence/lark-library-attributes-2026-10-13.json
[acquisition-evidence]: evidence/lark-source-acquisition-2026-10-13.json
[vela-porting]: https://github.com/open-vela/docs/blob/ef76237d468708be054b4c066d00fabf64ae4220/en/chip_porting/porting_guide.md#L579-L670
[vela-vendor]: https://github.com/open-vela/docs/blob/ef76237d468708be054b4c066d00fabf64ae4220/en/chip_porting/Vendor.md
