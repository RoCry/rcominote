# Research route decisions

2026-10-13. Read this before choosing new work. This index supersedes historical
"next step" paragraphs. Goal: own client covering actual capabilities/protocols,
understand shipped functions, complete firmware backup, recoverable flashing,
then own firmware. No single artifact or passing test substitutes for these goals.

## Focus: platform before peripheral detail

User direction: prioritize device, firmware, SoC and SDK understanding; park
blocked details and switch questions. Start with [device/platform map](device-platform-map.md).
Current deliverables, in order:

1. Matching ATS3085L/LARK M4 material: BSP, register/pin documentation,
   production configuration/host, official image. [Source follow-up](platform-source-followup.md)
   identifies previously overlooked unstripped Flash/SD loader ELFs and M4
   ATT source fragments. [Rebuildability inventory](platform-source-followup.md#rebuildability-peripheral-source-survives-platform-closure-does-not)
   also finds substantial LARK peripheral source, missing SoC/build closure and
   v8-M/FPv5 application media/BLE archives; acquire matched M4 dependencies,
   not just a renamed board target. NOR read/address-selection and initialization comparison
   is complete within its static scope: raw host selector is not a live app alias;
   unchanged Init changes hardware/NOR state. Exact bare-metal source-package
   searches acquired no source; resume acquisition on a new entry. SD comparison
   also closed: loader usesSD0, actual CoMi usesSD1; wrapper ignores read errors.
   Preserve both as HAL references, not ready-made backup tools; do not repeat audits.
   [Public history/ref and Vela pass](platform-source-followup.md#public-history-and-vela-provenance-bounded-acquisition-result)
   acquired no complete package: five historical SDK trees and current forks/refs
   add no LARK BSP; Vela guide supplies ATS3085X/vendor-package provenance only.
   Resume these acquisition routes on a new concrete package/ref, not another generic search.
   [Partial chip definitions recovered from DWARF](lark-register-recovery.md)
   now supply12 register layouts/47 IRQ values, cross-ELF and compiler checked;
   they do not restore missing startup/base/bit/board definitions.
   [Renewed GitHub acquisition](github-sdk-followup-2026-10-13.md) and
   [native Gitee/GitCode pass](domestic-sdk-followup-2026-10-13.md) now add two
   complete GitHub SDKs, a complete recording-card SDK and an ATS3085E build
   artifact set. All new inspected platform selections/builds remain M33.
   The recorder source supplies a whole recording workflow; direct comparison
   finds different GATT/framing, Opus/file-tail streaming and DSP resource.
   Keep it as an application reference, not a matched CoMi target or proof of
   the OEM diff size. Acquisition script and177-file hash manifest are reusable.
   Further broad source queries and another M33 build are parked after this
   bounded pass; reopen on a concrete matching package/branch or bring-up need.
   [Official CMSIS Pack index pass](platform-next-route-review.md) supplies no
   matched package metadata; stop that acquisition route until a concrete new link.
   [Production package contract](production-package-contract.md) now traces the
   default outer ACTTEST0 `.fw`, inner maker package, raw and separate AOTA paths.
   Default production includes fw_product, not the legacy fw_maker_ext; no new
   mp_usb helper audit without a matching caller. Retained LARK common XML lacks
   SYS_PARAM/storage_id and differs from actual layout. Acquire the final assembled
   package/configuration, not another isolated family blob.
2. Firmware/recovery overview: [complete actual recovery and RAM handoff](recovery-complete.md) now joins system/boot/DSP/ACPT;
   compare ROM→helper→NOR routes. If justified, acquire one bounded ROM corpus
   for offline analysis instead of one live experiment per callee.
3. A concrete first-run experiment with identified target, entry effects and
   independent escape. Enumeration, helper execution and Flash writes have
   separate evidence gates; complete restoration is not a prerequisite for
   an enumeration-only experiment with an independently established exit.
   [Offline M4 image construction](minimal-firmware-image.md) now closes the
   compiler/linker/ACTH/local-checker path: original and self-built images pass
   actual checker emulation; corruptions reject. This is not target execution,
   a matched BSP, full-chain authorization or a proposed flash experiment.

Client edge cases, backend acquisition, exact timer units and peripheral
details remain recorded below; they do not take priority over matching platform
artifacts. Each task needs a route-changing question and a stopping condition.
Stop when the bounded source search or evidence cannot answer it; record the
gap instead of repeatedly expanding the same investigation.

Current acquisition boundary: [official manual/index follow-up](official-acquisition-next.md#2026-10-13-bounded-manualreset-follow-up)
yielded no device reset procedure or firmware/BSP package. Matching platform
acquisition and ROM enumeration now need new material or an independently
established physical escape; further generic searches/callee reads are parked.
Client failure isolation is closed at the host-session boundary (see [CLI](cli.md));
do not expand it into automatic cancellation/resume while platform work has priority.
Explicit download/sync Ctrl-C now uses the [existing stop contract](download-cancel-contract.md#implemented-host-boundary-2026-10-13):
labeled partial bytes, bounded stop attempt and disconnect. This closes a known
client capability without claiming worker-idle, reliable resume or firmware backup.
[Explicit single-file deletion](file-deletion.md) now covers another documented
client operation: source-backed request, serial/name confirmation, complete list
readback, unknown outcome on interrupted exchange. Host tested only; no device
deletion, secure-erasure proof or platform/recovery advance claimed.

[SD bridge proof](sd-file-bridge.md) changes one acquisition decision: controlled
temporary SD writes are acceptable research side effects, distinct from firmware
NOR writes. Fixed4 KiB RAM transfer and one baseline-qualified boot0 ring export
match independent originals. [Recovery tail acquisition](recovery-complete.md) now adds30 paired missing sectors and a complete63,288-byte image with valid stored checksums. The bounded critical artifact is delivered; keep full-NOR bulk work and failed direct-XIP diagnosis parked.

[Known ROM source transfer](rom-sd-bridge.md) now matches the independent336 B
oracle twice. This establishes that source window only; a larger corpus needs
credible ROM extent/readable-map evidence, not an assumed32 KiB size.
[Normal-mode entry inventory](normal-ram-entry-inventory.md) covers13 roots,
15 static tables/81 subcommands and the direct candidate handlers: code-TLV
controls logging, `devmem load` writes memory; no supported RAM execution contract
was found within that coverage. Park this route until new explicit entry material.

## Capability ledger and evidence gates

| Workstream | Reuse now | Next decisive evidence |
|---|---|---|
| Efficient native transfer | [RAM→SD→Boyi and fixed boot0 ring export](sd-file-bridge.md), compared to independent bytes; SDK/tool sources; [CDC worker negative](usb-cdc-command-inventory.md) | Thirty missing recovery sectors now pass paired reads and complete-image checksum; this bounded workflow is still too slow for full NOR. Choose another critical artifact before more device I/O. Direct-XIP→SD yielded zeros; park its cause. Production host acquisition remains separate |
| Production host/ADFU | [Actual ROM table and entry](actual-rom-adfu-entry.md):19c→1a51, [condition and restore-return](actual-rom-exit-condition.md)1908→1980; [LARK transport selection](lark-transport-selection.md): adfus is UART, adfus_u has USB descriptors; [read handlers](lark-helper-candidate.md), [Host selection](host-selection-followup.md), [actual helper read handlers](helper-static-followup.md), [NOR initialization side effects](helper-nor-initialization.md), [actual boot](actual-boot-flow.md) | Matching production firmware scripts/caller parameters, exact SoC/host selection; device ROM USB identity and exit path before helper execution |
| Full backup | Verified mapped system, boot, DSP, partition table, [complete raw/decoded recovery](recovery-complete.md) | Reliable bulk route; all required physical partitions and unique configuration, repeated reads and integrity checks |
| Flash/recovery | Static boot checks, actual recovery header, [actual OTA no-version-control initialization](ota-version-policy.md), [container/manifest gate](ota-container-contract.md), [conditional initialization effects](ota-initialization-side-effects.md), offline `inspect-ota`, [actual payload writes and commit order](ota-write-commit.md), [NVRAM spare-segment pre-erase](ota-nvram-preerase.md), [complete recovery handoff/checker](recovery-complete.md) | Matching official image/manifest; earlier authorization and runtime handoff; independent recovery entry/exit and restoration proof |
| Own firmware | Reference SDK build, extracted actual code, [live firmware board identity](firmware-board-identity.md) `ats3085l_dvb_watch_ext_nor_max` | [Actual Cortex-M4 r0p1 CPUID](cpu-identity.md), matching manufacturer family but not SDK M33: obtain matching ATS3085L BSP, verify silicon/peripherals, boot/security constraints, reversible minimal boot proof, then display/audio/BLE |
| Client/protocol completeness — deferred detail | [CLI capability ledger](cli-capabilities.md), event-preserving connection, [live byte-offset suffix](download-offset.md), [realtime MP3 equality proof](realtime-live.md), verified BLE controls/download; explicit cancel saves partial bytes and disconnects | [Pause/resume equality verified](realtime-live.md#follow-up-pauseresume-exact-comparison); remaining long-window loss, reliable cancel→resume/device-worker exit, persistent-resume identity and correlated event fields |
| Backend/client integration — deferred acquisition | [Official deployment reference](seeyon-backend-reference.md): Spring Boot package lead, transcription/storage architecture | New externally reachable JAR source; old package hostname resolved to private IP. No documented firmware backup/update route; do not make it a firmware dependency |

BLE remains useful for small, question-driven measurements. Do not convert another
diagnostic primitive into an unattended full dump before comparing native routes.
Android login remains deferred by user. Do not infer reference ATS3089 board equals CoMi.

## Retired or rejected paths

| Path | Status / reason | Reconsider only when |
|---|---|---|
| code-TLV / devmem load as an existing RAM executor | **Unsupported by bounded actual inventory**: code-TLV switches log modes; load installs a fixed byte-writing callback, no uploaded-address call. [Tables and direct paths](normal-ram-entry-inventory.md); no whole-firmware absence claim | New explicit entry/protocol/configuration; do not substitute callback/stack corruption or an unbounded indirect-call scan |
| Bulk NOR through fread→printk ring→mdb | **Retired default route**, not invalid data. ~232 commands/~22 s per512 B plus retries; [measured audit](nor-efficiency.md). Exporter modules moved to `src/rcominote/archive/`; default CLI entries removed | Native SDK/host options compared and bounded experiment demonstrates material throughput/reliability gain |
| ATS3089/M33 reference build as CoMi firmware target | **Not an established target**: live firmware declares ATS3085L; [manufacturer L-family M4F specs and reference differences](ats3085l-primary-sources.md). Keep the successful build only as host/toolchain evidence | Exact BSP or independently verified core/peripheral/configuration compatibility |
| Unchanged LARK init+rs as read-only backup | **Rejected for both UART and USB variants**: [UART initialization](lark-nor-init-side-effects.md) and [independent USB audit](lark-usb-storage-exit.md) send06/01, discard original status1 and may clear status2 bit6 | Matched transport and audited initialization preserving NOR state; simply skipping init is not sufficient |
| Community ATS3085S BLE flasher as CoMi updater | **Rejected unchanged**: [source audit and real watch OTA](ats3085s-community-tool-audit.md); wrong GATT, ignores device range requests, wrong host06 semantics; upstream marks unfinished | Actual CoMi responder and recovery proof; retain offline container evidence only |
| Boot decoded with32 B codec reset | **Disproven** beyond first32 B; fails body checksum. [Bad artifact isolated](archive/rejected-boot-reset32/README.md) | No routine retry: use verified512 B boot decode |
| Normal ABTP rm/rs as bulk read | **Unsupported by inspected implementation**: header constants exist, SDK parser and actual CoMi parser lack those cases; [actual dispatch](audio-fixed-rate-path.md) | Different shipped dispatcher implementing them, with body/side effects understood |
| Enable CDC just to search for backup | **Removed from backup candidates**: complete inspected worker/IRQ/TX/timer provide testing/configuration, no bulk read; [coverage and limits](usb-cdc-command-inventory.md). Unknown commands may write NVRAM | A different actual content-transfer handler found offline; do not fuzz commands |
| ATT/USP FREAD as device backup | **Wrong direction**: device requests host test-file bytes (`tool_att.c`) | A distinct device-to-host storage handler is found |
| F5F0 OTA image-read request as backup | **Wrong direction** in [complete actual receive dispatcher](ota-wire-contract.md): device requests bytes from a host upgrade image; five handlers contain no Flash export | Distinct actual content-export handler; do not subscribe merely to look for one |
| Longer timeout/repeated full retries for missing text | **Not a remedy for captured truncation**; ACK/end can coexist with absent RAM rows | Evidence of delayed intact output, not already terminated truncated output |
| Assume recovery mapped at11000000 now | **Unproven**, [lifetime audit](recovery-mapping-lifetime.md) identifies SDK slot0 replacement at handoff and actual bus-error setup; complete recovery handoff now statically replaces slot0 | Runtime mapping still unobserved; no blind address probe |
| Generic US302A DLL / older ATJ host as CoMi downloader | **Unproven compatibility** despite real read exports | Matching chip-to-host selection, descriptors/framing and initialization |
| More encrypt.bin analysis to find USB readback | **Deprioritized**: inspected modules concern container/encryption; codec result retained | Concrete USB transport caller/reference, not module name |
| Repeated tiny polling turns | **Retired orchestration pattern** | Use bounded experiment or meaningful process milestone; investigate repeated failure before another full run |
| One ROM callee → bespoke live capture → tool → commit, repeated | **Deprioritized research pattern**: resolves local uncertainty while platform/BSP/backup gaps persist | A specific decision requires the bytes, or one justified bounded corpus enables batch offline answers; exact count units alone do not establish safe ROM exit |
| JLink raw bank20000000 as a live app NOR alias | **Unsupported inference**: [actual loader contract](platform-source-followup.md#nor-comparison-host-selector-cache-window-and-initialization) translates host address then copies from its own10000000 cache window | Independent evidence for a live app alias; do not probe that address based on the debugger bank table |
| Unchanged LARK JLink storage loaders as reliable backups | **Rejected unchanged**: [NOR initialization and SD interface comparison](platform-source-followup.md#nor-comparison-host-selector-cache-window-and-initialization); NOR reconfigures mapping/mode and calls unknown ROM init; SD targetsSD0 instead of actualSD1 and returns full length on read errors | Matched implementation with audited initialization, bounds and error propagation; keep typed HAL references |
| LARK `boot_recovery.app` as a complete CoMi rescue image | **Wrong artifact contract**: [6792B writer analysis](flash-recovery-assessment.md#启动授权问题缺的材料与不能替代它的产物); reads appended payload beyond file, erases/writes system and param, requests reset. Not actual recovery; its handoff is now independently available from the complete device image | Matching complete package and outer load/payload contract; it is not a read-only probe or proof of unsigned image boot |

Do not delete verified source evidence because its acquisition method was slow.
Archive rejected output with reason and replacement. Remove obsolete runnable
entry points/examples so a new agent cannot mistake historical progress for a plan.
Reopening a retired route must state the new evidence and specific decision it tests.

## SDK audit anchors

Pinned SDK `lvgl/lv_port_actions_technology@26f51e584940d5b141cd1d09d2629d69b595f579`:

- `application/bt_watch/src/bt_log/log_service.c:645–734`: console code/text dispatch;
  no generic binary memory/storage branch in this dispatch.
- `application/bt_watch/src/tool/spp_test/abtp_inner.h:52–53`: rm/rs constants;
  `abtp_entry.c:126–186`: parser cases, no implementation of those constants.
- `application/bt_watch/src/tool/tool_att.c:26–81`: host test-file pull into device.
- `zephyr/subsys/shell/shell_dbg.c:439–472`: fixed512 B malloc/read/dump/free;
  `:289–307`: printk byte dump, explaining double text transport.
- `zephyr/tools/build_firmware.py:1026–1069`: generated production instructions;
  actual matching host script is a better target than more generic DLL export scans.

Source root: [pinned SDK](https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk).
Source capability remains distinct from enabled/shipped/live CoMi behavior.
