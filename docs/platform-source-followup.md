# Matching platform sources: useful LARK assets, incomplete BSP

2026-10-13. Bounded source inventory and primary-site verification. No device I/O,
loader execution, installation, build or contact message. SDK checkout verified
at `26f51e584940d5b141cd1d09d2629d69b595f579`. Online checks used localwebrs.

**New useful lead: the pinned SDK contains unstripped LARK Flash and SD loader
ELFs with debug information.** These are stronger offline references than another
anonymous helper disassembly. A complete ATS3085L/CoMi BSP, chip programming manual,
matched production host package and official CoMi firmware remain unacquired.

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

**Route judgment:** enough named/type evidence exists for one bounded storage
comparison. Start with **Flash `SEGGER_OPEN_Read` plus `addr_translate`** to
resolve host raw-address versus mapped/decrypted-address handling; this directly
affects full NOR backup. Treat initializer compatibility as a separate unresolved
gate. SD's `brom_card_read` is the second comparison for MMC_1. Do not recursively
expand every helper; record remaining gaps after those interface comparisons.

Reproduce against either ELF with `readelf -h -l -SW`, `readelf -sW`,
`readelf --debug-dump=info`, and `readelf --debug-dump=rawline`; check SHA256
first. No persistent analysis tool or per-function report was added.

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

## Availability and stopping decisions

- **Available now:** M4 compiler recipe/source fragments, ROM API declaration,
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
- **Next platform work:** the bounded ELF inventory above is complete; compare
  its named read/address-translation interfaces to actual storage behavior. Record unresolved mappings
  and move on. External acquisition resumes when a real authenticated download,
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
[cubie]: http://www.cubietech.com/product-detail/cubiedvb-ats3085/
[support]: https://cs.actions-semi.com/loginIndex.html
[partner]: https://www.actions-semi.com/index.php?id=7761
