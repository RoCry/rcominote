# GitHub SDK follow-up: two acquired source trees, same platform gap

2026-10-13. Explicit renewed search for previously unexamined official/third-party
ATS3085L sources. Host-only GitHub API, local clones and GNU readelf; no builds,
loader execution or device I/O. Domestic hosting searched separately.

**Two substantial SDK repositories acquired; neither supplies the missing LARK
M4 SoC layer or a demonstrated M4 application-library set.** They remain useful
vendor-family source references. This result does not invalidate the hypothesis
that CoMi made relatively small changes to a *matching* vendor SDK.

## New acquired packages

| Repository / fixed revision | Complete recursive tree / tracked files | Platform finding |
|---|---:|---|
| [bovinae/SDK-TAG_ZS308B_2700_240516][zs] `8f0ba785447f41398b3b893d150a813e8e0ca892` | 15449 entries / 13339 files; API `truncated:false` | Both OS trees contain only LEOPARD under `soc/arm/actions`; both `Kconfig.series` select `CPU_CORTEX_M33` at line7 |
| [linhui200699/ats3089][ats] `087f9a6845fcc5837000ac6965d7b0780c54cad8` | 16667 entries / 14452 files; API `truncated:false` | Same SoC-selection result; no `soc/arm/actions/lark`, exact `lark.h` or `system_lark.h` in tracked tree |

Local shallow clones: `~/w/_tmp/comi-github-zs308b` and
`~/w/_tmp/comi-github-ats3089`; HEADs checked after checkout. These are independently
published repositories, not evidence of independent vendor implementations or
official endorsement. Both include application, bootloader, framework, thirdparty
and Zephyr trees. Neither has a tracked path containing `rec_card` or
`recorder_ble_ctrl`; that path check is not a claim that all recording functionality
is absent.

Direct platform evidence: [ZS308B Zephyr Kconfig][zs-kconfig],
[ZS308B bootloader Kconfig][zs-boot], [ATS3089 Zephyr Kconfig][ats-kconfig],
[ATS3089 bootloader Kconfig][ats-boot]. ZS308B's
`zephyr/boards/arm/ats3085s_dev_watch_ext_nor/ats3085s_dev_watch_ext_nor_defconfig:10`
selects `CONFIG_SOC_SERIES_LEOPARD=y`. ATS3085 filenames/configuration references
therefore cannot establish ATS3085L/M4 platform compatibility.

Bounded cross-check against the previously pinned LVGL SDK
`26f51e584940d5b141cd1d09d2629d69b595f579`:

- Each new repository has 43 tracked paths containing both `/drivers/` and
  `lark`, including headers. All 43 paths already exist in the LVGL SDK.
  After CRLF→LF normalization, ZS308B has 42/43 identical files, ATS3089 41/43.
  Differences: `zephyr/drivers/display/controller/lcdc_lark.c` in both;
  `bootloader/drivers/spi/spimt_lark.c` additionally in ATS3089. No semantic
  analysis of those differences was needed for this package-level decision.
- Both retained `zephyr/tools/flash_loader/JLink/Devices/Actions/LARK/`
  ELFs are byte-identical to the already audited loaders: Flash SHA256
  `588386943adff3ea2ea8163fa5148b4686d5e3a568acd632028c46628bfb3584`, SD
  `ccfb3ffc17ce11e853c6539ccc1810657709c48cb72f7d1ab775915874b7c4ee`.
  No new loader/DWARF package or reason to repeat initializer analysis.

## Application libraries: new bytes, same declared architecture class

GNU readelf2.42 `-A` on Ubuntu; SHA256 of transferred archives matched local
clones. In **each** repository, all 24 BT-stack member records and all 23 media
member records declare ARMv8-M.mainline, FPv5/FP-D16 for ARMv8, VFP-register
arguments. One media member explicitly names Cortex-M33; others name `8-M.MAIN`.

| Repository | Archive | Bytes | SHA256 |
|---|---|---:|---|
| ZS308B | `framework/bluetooth/bt_stack/libbt_stack.a` | 1674850 | `bc2bf138d8cf4c647c6371665abbfd08310a1eb1994aa7b49202345c14b80af8` |
| ZS308B | `framework/media/libmedia.a` | 1291550 | `ac7c1e709eb7a05720ba22d330bd12e60516e205483d3d851fbfe2cc981ebb18` |
| ATS3089 | `framework/bluetooth/bt_stack/libbt_stack.a` | 1682158 | `d465bfc99a66a0049f4cc58c0de892f114c2bbb79f0ddc8aa5f2488d609d6994` |
| ATS3089 | `framework/media/libmedia.a` | 1275170 | `59a45cf5d7044d257f4ecb1d3554e71acead16df2b5ce269f1dc3e74593a1989` |

These declarations do not prove every object executes an M4-illegal instruction.
They do mean neither newly acquired archive set establishes M4 compatibility.
No attempt to force-link or run these libraries was made.

## Search boundary and rejected new leads

GitHub repository queries: `ATS3085L`, `ATS3085`, `GL6189`, `Actions Zephyr`.
Code queries included `ATS3085L`, `ats3085l_dvb`, `CONFIG_SOC_SERIES_LARK`,
`BAREMETAL_CMSIS`, `GL6189`, `lark_sdk`. Own-repository hits, already audited
LVGL forks/history, empty AiBTS/M1cha repositories and watch-resource packers
were excluded from new-package claims.

`CONFIG_SOC_SERIES_LARK -repo:RoCry/rcominote -repo:lvgl/lv_port_actions_technology`
returned 48 code hits (`incomplete_results:false`), leading to the two acquired
SDKs and these bounded tree checks:

| Additional repository / revision | Observed boundary |
|---|---|
| [kongqj1234/git_kong][kong] `3816894bbdae3ad84909108916eb80e9bc8b628c` | Complete tree7556 entries; only `Kconfig.series` at `arch/csky/soc/actions/andesc/Kconfig.series`; no LARK SoC path or exact LARK/system header. Retained LARK preprocessor branches do not establish a matched ARM BSP; not cloned or expanded |
| [luoyugan/CGM_ATB1119G][cgm] `6a32e2e86d09da86592b1300d3a56ef165cdfe06` | Complete tree2118 entries; no `Kconfig.series`, LARK SoC path or exact LARK/system header. Driver/config references only established at this scope; not cloned or expanded |
| [grandcentrix/actions-zephyr-sdk][gc] `ebfba4933a0a97b8ddaeee886ab1b495bc9a995e` | README and 13-entry tree identify a GitHub Action installing upstream `zephyrproject-rtos/sdk-ng`; “actions” does not mean Actions Semiconductor |

The exact `BAREMETAL_CMSIS` code query excluding this repository returned0.
`lark_sdk` mostly exposed an unrelated Analog Devices Lark DSP SDK; a partial
result page was not used as an exhaustive negative. No claim that GitHub or the
internet contains no matching source. Stop this pass after acquired packages'
SoC/library classification; do not repeat their helpers or old LVGL history.

## What “small OEM SDK changes” would mean

The hypothesis is plausible at the application/framework level, but its size is
unmeasured. Existing [platform source comparison](platform-source-followup.md)
already supports common device APIs, shell/diagnostic lineage and peripheral
source ancestry; [production packaging](production-package-contract.md) and the
[actual image checker](minimal-firmware-image.md) provide additional contracts.
An M4 original product can derive from a matching LARK SDK while these public
trees target a different LEOPARD/M33 branch. That is not evidence of a large OEM
rewrite, nor permission to substitute the available branch unchanged.

Reusable now: source names, algorithms, command/state-machine candidates and
vendor tooling formats, each checked against actual firmware/protocol evidence.
Still needs matching: SoC startup/clocks/memory/IRQ definitions, binary CPU and
calling ABI, controller/DSP resources, board wiring, partition/security behavior.

**Completed follow-up:** the [domestic recording-card comparison](domestic-sdk-followup-2026-10-13.md)
checked build selectors, GATT/framing, filenames and the whole capture/transfer
workflow against CoMi. It established reusable vendor APIs and a complete
application reference, with different protocol, codec configuration and output
topology. It did not establish matching application source or measure CoMi's
OEM patch size. Do not repeat that comparison or infer exact structs/command
support from source names alone.

## Recorder repository branch cross-check

Follow-up to the domestic investigation: bounded public API check of all five
advertised [`szsheep/rec_jx3` branches][rec-branches]. Used the acquired main tree
and retrieved four other recursive trees; all `truncated:false`. No full source
fetch, build or device I/O in this check.

| Branch | Fixed HEAD | Tree entries |
|---|---|---:|
| main | `6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b` | 26164 |
| eink_prj | `7e21f675cc57db18caf9cbfe4943884f3ac83792` | 26559 |
| moan_jx3 | `bbd7074c48e9c2070cb3650dc7513d035ecbc2b8` | 26690 |
| r1_jx3 | `a94f58f54efae53281e41a4729768c983f21d42d` | 26654 |
| spi_renew | `03f091631d49043fdefe29e2cd0662c028491f71` | 26676 |

None contains `soc/arm/actions/lark`, exact `lark.h`/`system_lark.h`, or the
actual `ats3085l_dvb_watch_ext_nor_max` board path. The four non-main heads add
`ats3085s_dev_rec_eink` alongside `ats3085s_dev_rec_card`; neither name establishes
CoMi matching. All five share the same two `Kconfig.series` blobs: Zephyr
`39d5cc2c716c9d3ea1bfffd45936dc1d0258c4f2` selects Cortex-M33 and ARMV8_M_DSP;
bootloader `276def4ccab6a1ec1ff8dfad5d359c46ecca6b0c` selects Cortex-M33. Both
blob bodies read. Stop branch expansion: no stronger M4/actual-board lead.

Two main configuration blobs read for recovery/host relevance:

- [`application/rec_card/boards/ats3085s_dev_rec_card/firmware.xml`][rec-layout],
  blob `b2076926448006bd94d86c9c7d01b842529ba257`: explicitly 16MiB NOR with
  dual system partitions at `0x24000`/`0x1a4000`; recovery at `0x4000`, size
  `0x20000`. Useful recording-project packaging example; not CoMi's measured
  4MiB layout. Its disabled encryption/CRC flags establish configuration intent
  for this project, not CoMi's verification policy.
- Board `bootloader.ini`, blob `38452d2ba82b2537f343bfefcd23ff285b05b666`:
  UART 2000000, ADFU txrx1/gpio0; same blob reused by many watch boards. No matched
  production host, USB wiring or independent exit/reset guarantee follows.

The tree also contains board `recovery.bin` (`c8d437d86467aaa79d929241ed9ac391e1683e66`);
this check did not inspect its bytes or establish its architecture. A filename
is insufficient reason to promote it to a recovery route. The completed
[application comparison](domestic-sdk-followup-2026-10-13.md) records the actual
source selectors, framing and transfer-state differences. Matching UI/function
names alone did not establish an additional CoMi capability.

### Exact board / Boyi source search after UUID mismatch

The domestic application's observed GATT IDs differ from CoMi. A bounded new
GitHub code search found no new matching module:

- Exact `ats3085l_dvb_watch_ext_nor_max` text, excluding this repository: only
  the two already acquired SDKs' `application/bt_watch/resource/360x360/logo.ui`.
  Local lines8/9/13 reference that missing board's `sdfs_k/logo` resources;
  these are retained project paths, not recovered board source. Exact board
  `in:path` search excluding `RoCry`/`rocrp`:0.
- Full `0000e5e0-0000-1000-8000-00805f9b34fb`, excluding those owners:0;
  `boyi path:bluetooth language:JavaScript`, same exclusions:0. Completed query
  responses reported `incomplete_results:false`; coverage remains GitHub's index.
- Bare E5E0/E5E1 and Boyi/recorder combinations produced large unrelated result
  sets. Inspected first pages are not exhaustive negatives. One broader query
  returned503; two narrowed UUID/path queries hit403 rate limits and were not
  retried. A localwebrs full-prefix search found only an unrelated game cheat.

No new source URL justified another clone. The subsequent **whole capture
workflow comparison is complete** in the [domestic report](domestic-sdk-followup-2026-10-13.md):
source start/stop, media configuration, file stream and finalization were compared
with [actual media](recorder-media-config.md), [stream](recorder-stream-path.md)
and [codec](recorder-codec-dispatch.md) evidence. Shared media/stream APIs survive,
but new Opus/file-tail transfer differs from CoMi's MP3/ring-to-BLE implementation.
Retain this as an own-firmware application reference; it is not the Boyi source
module. No per-helper expansion follows from this result.

## ATS3085E checked-in ELF: architecture independently classified

Final bounded lead from the domestic tree: [`yekingsheng/ats3085e`][e-build]
at `37bfcac1fa7a38026460099be747efa3abacf6a9` contains a built application under
`application/bt_watch_no_psram/outdir/ats3085e_dev_watch_ext_nor/zephyr/`.
The public blob API returned403. Standard anonymous Git over HTTP/1.1 on Ubuntu
succeeded; HEAD verified, only the following three files exported for inspection.
Local receipts/payloads: `~/w/_tmp/comi-ats3085e-build/` (`receipt.json`). Each
Git blob SHA1 matched the complete fixed tree; no SDK or ELF execution.

| File | Bytes | Git blob SHA1 | SHA256 |
|---|---:|---|---|
| `.config` | 59525 | `aa8fbf3be6c758b638c668a16a09a1e775e02faa` | `9fa3370b45cdf9d936e45374370ede3c6e27b578f3b7f3df845bcc0e268018aa` |
| `zephyr.map` | 4533898 | `61c5ab626d39468cdced418b3034030f4af87bdc` | `4c384d644fd6bdc48c1990772885d88a463c426158da607a37deb7995de75cee` |
| `zephyr.elf` | 17499860 | `8d7ada49bd9afa7d367d849c420a4852b4866ba1` | `a6ae9bd8296429475dd4df03f3b62c5aff413b9b966b2d00e68337c56ec841c2` |

GNU readelf2.42 `-A` on the actual ELF: CPU name **Cortex-M33**, architecture
ARMv8-M.mainline, FPv5/FP-D16 for ARMv8, VFP-register arguments. ELF SHA256
matched across hosts. `.config:3/20/24/1086` selects board
`ats3085e_dev_watch_ext_nor`, SoC/series `leopard`, `CPU_CORTEX_M33=y`.
Map line550 references
`D:/Breo/TAG_ZS3085E_2412302/zephyr/soc/arm/actions/leopard/libsocatp.a(soc_atp.c.obj)`.
Thus this retained build does not supply an unexpected matched M4 image.
Stop here: no DWARF type/helper expansion or claim that every instruction is
M4-incompatible; no inference about unseen branches or builds.

[e-build]: https://gitee.com/yekingsheng/ats3085e/tree/37bfcac1fa7a38026460099be747efa3abacf6a9/application/bt_watch_no_psram/outdir/ats3085e_dev_watch_ext_nor/zephyr
[rec-branches]: https://gitee.com/api/v5/repos/szsheep/rec_jx3/branches?per_page=100
[rec-layout]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/boards/ats3085s_dev_rec_card/firmware.xml
[zs]: https://github.com/bovinae/SDK-TAG_ZS308B_2700_240516/tree/8f0ba785447f41398b3b893d150a813e8e0ca892
[ats]: https://github.com/linhui200699/ats3089/tree/087f9a6845fcc5837000ac6965d7b0780c54cad8
[zs-kconfig]: https://github.com/bovinae/SDK-TAG_ZS308B_2700_240516/blob/8f0ba785447f41398b3b893d150a813e8e0ca892/zephyr/soc/arm/actions/leopard/Kconfig.series#L7
[zs-boot]: https://github.com/bovinae/SDK-TAG_ZS308B_2700_240516/blob/8f0ba785447f41398b3b893d150a813e8e0ca892/bootloader/soc/arm/actions/leopard/Kconfig.series#L7
[ats-kconfig]: https://github.com/linhui200699/ats3089/blob/087f9a6845fcc5837000ac6965d7b0780c54cad8/zephyr/soc/arm/actions/leopard/Kconfig.series#L7
[ats-boot]: https://github.com/linhui200699/ats3089/blob/087f9a6845fcc5837000ac6965d7b0780c54cad8/bootloader/soc/arm/actions/leopard/Kconfig.series#L7
[kong]: https://github.com/kongqj1234/git_kong/tree/3816894bbdae3ad84909108916eb80e9bc8b628c
[cgm]: https://github.com/luoyugan/CGM_ATB1119G/tree/6a32e2e86d09da86592b1300d3a56ef165cdfe06
[gc]: https://github.com/grandcentrix/actions-zephyr-sdk/blob/ebfba4933a0a97b8ddaeee886ab1b495bc9a995e/README.md
