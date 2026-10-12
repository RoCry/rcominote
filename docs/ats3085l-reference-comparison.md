# ATS3085L external-NOR references versus CoMi

2026-10-12. Offline source comparison; no build execution or device I/O.
SDK fixed at `26f51e584940d5b141cd1d09d2629d69b595f579`.

**Useful source family, missing exact production board.** CoMi firmware declares
`ats3085l_dvb_watch_ext_nor_max`; the pinned SDK has no matching board directory.
Closest complete external-NOR board is `ats3085s_dev_watch_ext_nor`.
Its audio-demo packaging says ATS3085L, but memory, storage and display differ.
This supports focused source reuse, not a compatible image/helper selection.

## Board names, chip labels and CPU conflict

- [Audio S packaging][audio-chip] and [audio E packaging][e-chip] both set
  `CHIP_NAME = "ATS3085L"`. Audio, noise-cancel, local-music, BT-music and
  BT-call demos contain these L-labelled configurations.
- [LVGL S packaging][lvgl-chip] instead sets `ATS3085S` under the same S suffix.
  Directory name and `CHIP_NAME` are separate inputs, not silicon identification.
- S has a complete Zephyr board; S4 is another complete external-NOR board.
  E appears in application overlays, but no `zephyr/boards/arm/ats3085e*` board
  exists in this checkout. An E overlay alone is not a buildable board definition.
- S [defconfig][defconfig] selects `SOC_SERIES_LEOPARD`/`SOC_LEOPARD`; the
  [series definition][soc-series] selects ARMv8-M DSP and **Cortex-M33**.
  [Manufacturer ATS3085L datasheets](ats3085l-primary-sources.md) establish the
  public L family as **M4F 128 MHz + DSP 192 MHz, 481 KB SRAM + 4 MB PSRAM**.
  Thus this pinned M33 board is not an exact L CPU configuration. CoMi's physical
  core is still unread. [CubieTech's page][cubie], fetched 2026-10-12, agrees on
  M4F but lists DSP 128 MHz; prose says SPI NAND, feature list says 32 Mbit NOR.
  Prefer manufacturer's family table; neither source proves CoMi's exact part.

## Configuration comparison

Values below come from [S defconfig][defconfig], [audio overlay][audio-overlay]
and [audio project config][audio-project], not a newly resolved `.config`.
An application's final configuration can change defaults.

| Item | Public S external-NOR/audio reference | CoMi evidence / gap |
|---|---|---|
| Board contract | `ats3085s_dev_watch_ext_nor`; audio package ATS3085L | [Actual firmware identity](firmware-board-identity.md): `ats3085l_dvb_watch_ext_nor_max`, version `1.04_2602030950` |
| Clock | HOSC 32 MHz | No measured crystal/core frequency |
| SRAM | 911 KiB, base `2ff60400` | Actual startup uses `1800…` runtime destinations; [startup mapping](startup-memory-readback.md) does not establish total SRAM capacity |
| PSRAM | 8192 KiB, base `38000000`; [S4][s4-defconfig] uses 4096 KiB | Capacity/part/pins unverified; do not choose S4 solely to match CoMi NOR size |
| Flash build settings | `FLASH_SIZE=1920` KiB, base `10000000`; `FLASH_LOAD_SIZE=100000` bytes; ROM start offset `200` | Build/link settings are not physical Flash capacity |
| Packaged NOR | Audio XML `disk_size=2000000` (32 MiB) | [Actual ACPT](partition-readback.md) covers `0..400000` (4 MiB); [cached JEDEC](nor-driver-readback.md) agrees with a 32 Mbit family |
| User storage | S base disables MMC/MMC_ACTS/MMC_SDCARD; audio enables NOR FAT disk `/NOR:` and NOR USB MSC | [Actual SD driver state](card-state-readback.md): MMC_1, SD category, block addressing, 122138624 × 512 B = 62,534,975,488 B; marketed 64 GB |
| Display | [Kconfig][board-kconfig] selects ICNA3310B if DISPLAY; [header][board-header] defaults QSPI, 466×466, round, 60 Hz | [Actual driver](display-board-evidence.md): CH1115 label, 72×40 configuration, I2C_0 command address `3c`; physical part still unverified |
| Audio | ADC input + DAC output; I2SRX/I2STX disabled; external PA option enabled | [Actual audio_in initializer](init-audio-board-evidence.md) binds ADC_0; mic type/count/routing unknown |
| Other peripherals | UART_0 console 115200; I2C/DMA; CST820 touch; STK8321/QMA6100 accelerometer and HX3605 HR options | Watch defaults, not evidence CoMi contains these sensors or touch |

`SD_FS` means the SDK SDFS resource filesystem; it does not override disabled MMC
or prove an SD card. Header `CONFIG_SD=1`/controller names likewise do not prove
an enabled final driver. PSRAM/Flash size units are defined by [PSRAM Kconfig][psram]
and [architecture Kconfig][arch-size].

## Partition geometry: strong common ancestry, unsafe direct substitution

Compare [audio S XML][layout] with actual CRC-verified ACPT. First **14** entries
have equal address/size/file ID, ending at `200000`: boot/param at `0/1000`,
mirrors `2000/3000`, recovery `4000/20000`, system `24000/1a5000`, then user RW,
SDFS, factory/RW/user NVRAM, log/event/coredump. Names may truncate in ACPT.
This is geometry equality, not identical contents, encryption flags or boot ABI.

| Later region | SDK address / size | CoMi address / size |
|---|---|---|
| res_a, ID10 | `200000 / 200000` | `200000 / 40000` |
| font ID12 / res_b ID11 | `400000 / 600000`; `a00000 / 40000` | No such ACPT entries |
| sdfs_k, ID20 | `a40000 / 80000` | `240000 / b0000` |
| TEMP, ID254 | `ac0000 / 100000` | `2f0000 / 100000` |
| runtime log, ID250 | `bc0000 / 10000` | `3f0000 / 10000` |
| NOR udisk, ID40 | `bd0000 / 430000` | No such ACPT entry; recording storage separate |

Both layouts mirror boot/param, not a second complete system. A recovery region
and 1 MiB TEMP do not prove rollback or recovery after arbitrary replacement.
SDK XML disables encryption for boot/param/recovery/system/SDFS; corresponding
CoMi ACPT flags are `2`. Preserve [actual boot/security boundaries](actual-boot-flow.md)
instead of treating source geometry as a production package.

## Build/helper precedence matters

[build.py][build] reads resolved `CONFIG_SOC_SERIES` to select
`tools/prebuilt/<series>/common/bin`, then `<series>/bin`, then `<series>/prebuild`.
It copies `firmware.xml` in board → application → selected application-config
order, later files winning. Board overrides include `adfus*.bin`, `mbrec.bin`,
`bootloader.ini`, `nand_id.bin`, `recovery.bin`, `fw_product.cfg`; app/config
`prebuild` and config `fwimage.cfg`/`bin` are copied later. Board `ota_app.bin`
and optional signed boot image have separate later steps.

S board includes boot/recovery/OTA binaries and [bootloader.ini][boot-config],
but no board-local `adfus.bin` or `fw_product.cfg`: generic LEOPARD files remain
unless a later override supplies replacements. Changing `CHIP_NAME` is not a
helper compatibility check. Its bootloader configuration sets UART0 at 2 Mbaud,
PSRAM MFP3 and ADFU GPIO0; these are reference values, not CoMi entry instructions.
The [public NOR initializer audit](helper-nor-initialization.md) retains unresolved
ROM behavior. No helper download, initialization or test execution was performed.

Priority: obtain exact ATS3085L production BSP/package or documented L/S mapping;
resolve public SDK's M33 versus L's M4F and CoMi PSRAM/clock before any board port.
Reuse this family for targeted code/format comparison; preserve CoMi's measured
layout and peripheral evidence. Full raw backup, compatible flashing helper and
independently demonstrated restoration remain missing.

[audio-chip]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/app_demo/audio_demo/boards/ats3085s_dev_watch_ext_nor/fwimage.cfg
[e-chip]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/app_demo/audio_demo/boards/ats3085e_dev_watch_ext_nor/fwimage.cfg
[lvgl-chip]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/app_demo/lvgl_demo/boards/ats3085s_dev_watch_ext_nor/fwimage.cfg
[defconfig]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3085s_dev_watch_ext_nor/ats3085s_dev_watch_ext_nor_defconfig
[s4-defconfig]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3085s4_dev_watch_ext_nor/ats3085s4_dev_watch_ext_nor_defconfig
[soc-series]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/Kconfig.series#L4-L17
[cubie]: http://www.cubietech.com/product-detail/cubiedvb-ats3085/
[board-kconfig]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3085s_dev_watch_ext_nor/Kconfig.defconfig#L15-L19
[board-header]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3085s_dev_watch_ext_nor/board_cfg.h#L879-L922
[psram]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/Kconfig.defconfig.series#L22-L28
[arch-size]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/Kconfig#L186-L192
[layout]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/app_demo/audio_demo/boards/ats3085s_dev_watch_ext_nor/firmware.xml
[build]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/build.py#L448-L525
[boot-config]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3085s_dev_watch_ext_nor/bootloader.ini
[audio-overlay]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/app_demo/audio_demo/boards/ats3085s_dev_watch_ext_nor.conf
[audio-project]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/app_demo/audio_demo/prj.conf
