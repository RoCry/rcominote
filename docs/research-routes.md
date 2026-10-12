# Research route decisions

2026-10-12. Read this before choosing new work. This index supersedes historical
"next step" paragraphs. Goal: own client covering actual capabilities/protocols,
understand shipped functions, complete firmware backup, recoverable flashing,
then own firmware. No single artifact or passing test substitutes for these goals.

## Active priorities and evidence gates

| Workstream | Reuse now | Next decisive evidence |
|---|---|---|
| Client/protocol completeness | [CLI capability ledger](cli-capabilities.md), actual Android code, verified BLE controls/download | Map missing operations/events/error behavior to actual handlers; bounded real-device verification for each claimed capability |
| Efficient native transfer | SDK log/ABTP/USB/tool sources + complete mapped system; [CDC direct-command negative](usb-cdc-command-map.md) | Resolve remaining CDC worker/callee boundaries without repeating known table; current mapping proof before any new mapped-address read |
| Production host/ADFU | [Host selection](host-selection-followup.md), [actual helper read handlers](helper-static-followup.md), [actual boot](actual-boot-flow.md) | Matching production firmware scripts/caller parameters, exact SoC/host selection; device ROM USB identity and exit path before helper execution |
| Full backup | Verified mapped system, boot, DSP, partition table, partial raw recovery | Reliable bulk route; all required physical partitions and unique configuration, repeated reads and integrity checks |
| Flash/recovery | Static boot checks, actual recovery header | Known transport/init side effects, matching official image, independent recovery entry/exit and restoration proof |
| Own firmware | Reference SDK build and extracted actual code | Board/SoC/peripheral agreement, boot/security constraints, reversible minimal boot proof, then display/audio/BLE |

BLE remains useful for small, question-driven measurements. Do not convert another
diagnostic primitive into an unattended full dump before comparing native routes.
Android login remains deferred by user. Do not infer reference ATS3089 board equals CoMi.

## Retired or rejected paths

| Path | Status / reason | Reconsider only when |
|---|---|---|
| Bulk NOR through fread→printk ring→mdb | **Retired default route**, not invalid data. ~232 commands/~22 s per512 B plus retries; [measured audit](nor-efficiency.md). Exporter modules moved to `src/rcominote/archive/`; default CLI entries removed | Native SDK/host options compared and bounded experiment demonstrates material throughput/reliability gain |
| Boot decoded with32 B codec reset | **Disproven** beyond first32 B; fails body checksum. [Bad artifact isolated](archive/rejected-boot-reset32/README.md) | No routine retry: use verified512 B boot decode |
| Normal ABTP rm/rs as bulk read | **Unsupported by inspected implementation**: header constants exist, SDK parser and actual CoMi parser lack those cases; [actual dispatch](audio-fixed-rate-path.md) | Different shipped dispatcher implementing them, with body/side effects understood |
| Enable CDC just to search for backup | **Deprioritized**: actual direct command table is production testing/configuration, no bulk read; unknown commands may write NVRAM | Actual content-transfer handler found offline; do not fuzz commands |
| ATT/USP FREAD as device backup | **Wrong direction**: device requests host test-file bytes (`tool_att.c`) | A distinct device-to-host storage handler is found |
| Longer timeout/repeated full retries for missing text | **Not a remedy for captured truncation**; ACK/end can coexist with absent RAM rows | Evidence of delayed intact output, not already terminated truncated output |
| Assume recovery mapped at11000000 now | **Unproven**, boot-time mapping does not prove application-time alias | Current mapping lifetime established from actual code/state |
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
