# Architectural vector-base getter audit

Date: 2026-10-12. Offline primary-source audit; no hardware I/O performed.

**Result:** a single aligned 32-bit read of `0xe000ed08` is an architectural
VTOR getter on Cortex-M4/M33. It has no documented read-to-clear or write
side effect. This makes it a defensible bounded candidate, conditional on
privileged access on the actual core. It does **not** establish the firmware
image base, flash layout, or boot-header address by itself.

## Primary evidence

| Source | Observation | Consequence |
| --- | --- | --- |
| [Arm M33 Generic User Guide][m33], 100235_0100_05, §5.2.1 / §5.2.5 | VTOR at `0xe000ed08`, RW, privileged; bits 31:7 vector-table base; bits 6:0 RES0; banked when Security Extension implemented | Read returns vector base for addressed security bank; no status acknowledgment semantics described |
| Same, §5.2.17 | SCB accesses require aligned words except CFSR/SHPR1–3 | VTOR requires one 32-bit load; bytewise `mdb` unsuitable |
| [Arm M4 Generic User Guide][m4], DUI0553A, §4.3.1 / §4.3.4 / §4.3.15 | Same VTOR address and privileged RW classification; same aligned-word requirement | Getter location/access width common to both candidate core families |
| [Arm exception guide][exceptions] | VTOR locates current vector table; manufacturer controls reset value; application may relocate table to SRAM | Current VTOR need not point to original boot image |
| [Pinned SDK LEOPARD Kconfig][core] | Selects `CPU_CORTEX_M33`, ARMv8-M DSP, FPU | Establishes reference LEOPARD architecture, not owned CoMi identity |
| [Pinned CMSIS M4][cmsis4] / [M33][cmsis33] | `SCB_BASE = 0xe000e000 + 0xd00`; `VTOR` offset `0x008`, volatile `uint32_t`; CMSIS vector getter reads `SCB->VTOR` | Independent source-level address/width corroboration |
| [SDK sleep backup][sleep] | `vector_tbloff_backup = SCB->VTOR` | Actions reference software treats ordinary read as state preservation |
| [SDK startup][startup] | Either sets VTOR to `_vector_start` or copies vectors to `sram_irq_vector` then sets VTOR there | Relocation ambiguity exists in this actual SDK lineage |
| [SDK memory shell][shell] | `mdw` passes width 4; buffer routine dereferences `volatile uint32_t *`; `mdb` uses `volatile uint8_t *` | Candidate command is `dbg mdw e000ed08 1`, not `dbg mdb e000ed08 4` |

## Scope and unresolved access conditions

- Register is RW because firmware can relocate vectors by **writing** it.
  An aligned read has no specified state-changing effect. This is an
  architectural side-effect assessment, not a promise that arbitrary access
  cannot fault on unknown hardware.
- Both guides require privileged access. Existing successful reads of normal
  executable memory do not alone prove shell privilege. SDK shell thread
  creation uses options `0`, but owned firmware's actual execution context
  has not been independently established.
- On M33 with TrustZone, `0xe000ed08` addresses the current security state's
  VTOR. CMSIS exposes non-secure alias `SCB_NS` at `0xe002ed00` only to secure
  builds. Do not add a speculative alias read: security context and extension
  presence remain unknown, and one bank does not identify the other bank.
- Exact CoMi core remains unproven. LEOPARD/ATS3089 reference board selection
  and public tool support strings mentioning ATS3085 do not identify this
  unit. Do not infer core or chip ID from those strings alone.
- Do not issue a larger SCB dump: adjacent `ICSR`, `AIRCR`, fault/status
  registers have different semantics; extending count would add no evidence
  needed for vector-base discovery.

## Bounded proposal

1. Preserve current exact-device / known-code guards. Confirm `mdw` is exposed
   and its output count is measured in words; retain this source audit.
2. If actual context supports a privileged M4/M33 architectural read, allow
   exactly one fixed command `dbg mdw e000ed08 1`. Reject generic addresses,
   byte access, counts greater than one, and automatic alias fallback.
3. Require exactly one addressed 8-hex-digit word, plus normal transport/end
   evidence. Repeat independently; compare register value and uptime/device
   state. A transport ACK alone cannot prove payload completeness.
4. Treat the observed value as a **candidate current vector-table address**.
   Alignment is a consistency check, not authenticity or image-bound proof.
   Audit mapped-memory context before reading any vectors or following a
   reset-handler pointer. SRAM relocation and security banking remain viable.

This avenue can provide an actual pointer rather than a guessed SDK address.
It cannot independently provide a backup method or establish safe flashing.

[m33]: https://documentation-service.arm.com/static/641b2ec1de84571cc27f3ca3
[m4]: https://documentation-service.arm.com/static/5f2ac4ab60a93e65927bbdbf
[exceptions]: https://support.arm.com/documentation/107706/0100/Exceptions-and-interrupts-overview/Vector-table/VTOR-register-and-initialization
[core]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/Kconfig.series
[cmsis4]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/hal/cmsis/CMSIS/Core/Include/core_cm4.h
[cmsis33]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/hal/cmsis/CMSIS/Core/Include/core_cm33.h
[sleep]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_sleep.c#L769
[startup]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/core/aarch32/prep_c.c#L45
[shell]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L60
