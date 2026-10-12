# ATS3085L primary sources: do not substitute LEOPARD/M33 defaults

2026-10-12. Primary vendor pages and complete PDF pages inspected; no device I/O.
[Acquisition metadata and SHA256](evidence/ats3085l-primary-sources-2026-10-12.json).

## Manufacturer evidence

Actions' own **Smart Watch Bluetooth Audio SoC** brochures:

- [Download2510](https://www.actions-semi.com/index.php?c=download&id=2510), one page,
  PDF metadata2022: ATS3085L column identifies M4F128 MHz, DSP192 MHz,
  481 KB SRAM+4 MB OPI RAM, no integrated NOR, QFN68 7x7 mm.
- [Download2972](https://www.actions-semi.com/index.php?c=download&id=2972), two pages,
  PDF metadata2024: page1 independently lists ATS3085L as M4F128 MHz,
  DSP192 MHz,481 KB SRAM+4 MB QSPI DDR PSRAM, external DTR NOR, QFN68.
  Adjacent E/S variants are labeled MStar rather than M4F. Page2 lists ATS3089P
  separately, with1168 KB+32 MB HPI PSRAM and8 MB NOR. Do not assign L the
  capabilities of another column or interpret MStar as an identified ARM core.

Metadata years are file metadata, not independently established publication dates.
Both brochures were rendered and visually checked; text extraction alone did not
recover their tables reliably. Original PDFs remain local under `artifacts/`;
repository retains source links, hashes and factual findings, not full copies.

**Consequence:** the [actual firmware board name](firmware-board-identity.md)
`ats3085l_dvb_watch_ext_nor_max` now points toward a manufacturer-documented
M4F family. The tested reference SDK's `LEOPARD -> CPU_CORTEX_M33` build is a
real architecture mismatch to that family, despite shared APIs/formats and some
`CHIP_NAME="ATS3085L"` packaging files. Do not call the built ATS3089 firmware a
CoMi starting binary or assume Cortex-M33 instructions/MPU setup are usable.

Follow-up: [two live CPUID reads](cpu-identity.md) independently establish
Cortex-M4 r0p1 (`410fc241`). Physical SoC marking, FPU configuration and board
wiring remain unmeasured. Family register/ROM/helper assumptions still require
their own checks.

## Development-board lead and its limits

[CubieTech CubieDVB-ATS3085](http://www.cubietech.com/product-detail/cubiedvb-ats3085/)
names ATS3085L, Zephyr/Xiaomi Vela and LVGL; it describes software/hardware design
as open but production material as closed. USB data/flashing support is a
**development-board** feature, not proof that CoMi routes its USB pins identically.

The vendor page conflicts internally: prose says SPI NAND; feature list says
32 Mbit SPI NOR. It also gives DSP128 MHz versus Actions' DSP192 MHz. Treat the
manufacturer's explicit model columns as stronger product-family evidence,
without assuming the devkit's actual clock/configuration. Published PCB photos
show a large watch development board, not CoMi's recorder PCB.

Rendered page and raw HTML development section have no SDK/schematic download
link; the Chinese-material field is blank. No SDK/archive was acquired from this
lead, and no contact message was sent. Exact CoMi board-name search returned no
result; that is a bounded search outcome, not proof of no private matching BSP.

## Next evidence gate

Use [reference comparison](ats3085l-reference-comparison.md) to select source
components, not a flashable board. Prioritize an ATS3085L/M4F BSP or matched
production package; require actual peripheral/pin/clock/storage agreement before
any custom boot. The common LEOPARD helper remains unverified for this family;
[initialization side effects](helper-nor-initialization.md) cannot be waived by
its real read handlers. No full backup, restore or own-firmware boot follows from
product-family documentation.
