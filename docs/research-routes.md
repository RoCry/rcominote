# Research route decisions

2026-10-12. Read this before choosing new work. This index supersedes historical
"next step" paragraphs. Goal: own client covering actual capabilities/protocols,
understand shipped functions, complete firmware backup, recoverable flashing,
then own firmware. No single artifact or passing test substitutes for these goals.

## Active priorities and evidence gates

| Workstream | Reuse now | Next decisive evidence |
|---|---|---|
| Backend/client integration | [Official CoMi Note deployment reference](seeyon-backend-reference.md): Spring Boot service package lead, public/private transcription and storage architecture | Obtain official JAR; inspect controller/auth/upload/device/version contracts and compare against shipped app. Deployment documentation alone does not establish firmware update or backup support |
| Client/protocol completeness | [CLI capability ledger](cli-capabilities.md), event-preserving connection, [live byte-offset suffix](download-offset.md), [realtime MP3 equality proof](realtime-live.md), verified BLE controls/download | [Pause/resume equality verified](realtime-live.md#follow-up-pauseresume-exact-comparison); next: long-window loss behavior; cancellation completion/race contract and persistent-resume identity; correlated live event fields |
| Efficient native transfer | SDK log/ABTP/USB/tool sources + complete mapped system; [CDC worker negative](usb-cdc-command-inventory.md) | Matching production host/script or actual mapped alias evidence; do not enable CDC in hope of a hidden bulk command |
| Production host/ADFU | [Host selection](host-selection-followup.md), [actual helper read handlers](helper-static-followup.md), [NOR initialization side effects](helper-nor-initialization.md), [actual boot](actual-boot-flow.md) | Matching production firmware scripts/caller parameters, exact SoC/host selection; device ROM USB identity and exit path before helper execution |
| Full backup | Verified mapped system, boot, DSP, partition table, partial raw recovery | Reliable bulk route; all required physical partitions and unique configuration, repeated reads and integrity checks |
| Flash/recovery | Static boot checks, actual recovery header, [actual OTA no-version-control initialization](ota-version-policy.md), [container/manifest gate](ota-container-contract.md), [conditional initialization effects](ota-initialization-side-effects.md), offline `inspect-ota`, [actual payload writes and commit order](ota-write-commit.md), [NVRAM spare-segment pre-erase](ota-nvram-preerase.md), [provisional recovery entry](recovery-entry-candidate.md) | Matching official image/manifest; actual recovery second-stage path, independent recovery entry/exit and restoration proof |
| Own firmware | Reference SDK build, extracted actual code, [live firmware board identity](firmware-board-identity.md) `ats3085l_dvb_watch_ext_nor_max` | [Manufacturer M4F family vs SDK M33 mismatch](ats3085l-primary-sources.md): obtain matching ATS3085L BSP, verify silicon/peripherals, boot/security constraints, reversible minimal boot proof, then display/audio/BLE |

BLE remains useful for small, question-driven measurements. Do not convert another
diagnostic primitive into an unattended full dump before comparing native routes.
Android login remains deferred by user. Do not infer reference ATS3089 board equals CoMi.

## Retired or rejected paths

| Path | Status / reason | Reconsider only when |
|---|---|---|
| Bulk NOR through fread→printk ring→mdb | **Retired default route**, not invalid data. ~232 commands/~22 s per512 B plus retries; [measured audit](nor-efficiency.md). Exporter modules moved to `src/rcominote/archive/`; default CLI entries removed | Native SDK/host options compared and bounded experiment demonstrates material throughput/reliability gain |
| ATS3089/M33 reference build as CoMi firmware target | **Not an established target**: live firmware declares ATS3085L; [manufacturer L-family M4F specs and reference differences](ats3085l-primary-sources.md). Keep the successful build only as host/toolchain evidence | Exact BSP or independently verified core/peripheral/configuration compatibility |
| Boot decoded with32 B codec reset | **Disproven** beyond first32 B; fails body checksum. [Bad artifact isolated](archive/rejected-boot-reset32/README.md) | No routine retry: use verified512 B boot decode |
| Normal ABTP rm/rs as bulk read | **Unsupported by inspected implementation**: header constants exist, SDK parser and actual CoMi parser lack those cases; [actual dispatch](audio-fixed-rate-path.md) | Different shipped dispatcher implementing them, with body/side effects understood |
| Enable CDC just to search for backup | **Removed from backup candidates**: complete inspected worker/IRQ/TX/timer provide testing/configuration, no bulk read; [coverage and limits](usb-cdc-command-inventory.md). Unknown commands may write NVRAM | A different actual content-transfer handler found offline; do not fuzz commands |
| ATT/USP FREAD as device backup | **Wrong direction**: device requests host test-file bytes (`tool_att.c`) | A distinct device-to-host storage handler is found |
| F5F0 OTA image-read request as backup | **Wrong direction** in [complete actual receive dispatcher](ota-wire-contract.md): device requests bytes from a host upgrade image; five handlers contain no Flash export | Distinct actual content-export handler; do not subscribe merely to look for one |
| Longer timeout/repeated full retries for missing text | **Not a remedy for captured truncation**; ACK/end can coexist with absent RAM rows | Evidence of delayed intact output, not already terminated truncated output |
| Assume recovery mapped at11000000 now | **Unproven**, [lifetime audit](recovery-mapping-lifetime.md) identifies SDK slot0 replacement at handoff and actual bus-error setup; partial recovery startup leads to unavailable tail data | Current mapping lifetime established from actual handoff code/state; no blind address probe |
| Generic US302A DLL / older ATJ host as CoMi downloader | **Unproven compatibility** despite real read exports | Matching chip-to-host selection, descriptors/framing and initialization |
| More encrypt.bin analysis to find USB readback | **Deprioritized**: inspected modules concern container/encryption; codec result retained | Concrete USB transport caller/reference, not module name |
| Repeated tiny polling turns | **Retired orchestration pattern** | Use bounded experiment or meaningful process milestone; investigate repeated failure before another full run |

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
