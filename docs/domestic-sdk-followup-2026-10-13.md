# Domestic SDK acquisition and complete recorder workflow comparison

2026-10-13. New primary-source acquisition, host-only. No device commands,
SDK execution, reset, packaging or Flash writes. Astra independently reviewed
branch/platform classification and recording-backend comparison.

**Acquired a complete SDK repository checkout containing a recording-card application, not a matched
CoMi firmware project.** It supplies a reusable application workflow; actual
CoMi evidence supports common vendor APIs, not a measured small source diff.
Companion [GitHub acquisition](github-sdk-followup-2026-10-13.md) records two
additional complete SDK trees and their architecture checks.

## Renewed domestic pass: source acquired, exact older LARK package identified

User explicitly reopened domestic third-party sharing after Ubuntu handoff.
[Acquisition receipt](evidence/domestic-sdk-renewed-2026-10-13.json) records actual
payloads, hashes, query/tree scope and current access failures. Host-only; no
device commands, contact messages, account login or downloaded-code execution.

| New acquired repository | Fixed revision / payload | Actual value and boundary |
|---|---|---|
| [nopointer/OTA-JX-New](https://gitee.com/nopointer/OTA-JX-New/tree/ca814e72158ac616647deb9bf105e882cefcc8d1) | `ca814e72158ac616647deb9bf105e882cefcc8d1`; 198 tracked files, 84 Java | ActionsIbluz/ActionsLog/ActionsOta/ActionsDial/ActionsSpeed host source; no C/H MCU BSP |
| [nopointer/OTA-JuXin](https://gitee.com/nopointer/OTA-JuXin/tree/51e36cd8af999da16b1a863bca9e915e77962f21) | `51e36cd8af999da16b1a863bca9e915e77962f21`; 65 files, 31 Java | Older Android BLE/OTA implementation; no matched SoC/board source |

Normal public clones are retained at `~/w/_tmp/comi-gitee-ota-jx-new` and
`~/w/_tmp/comi-gitee-ota-juxin`; clean revisions and selected source SHA256s
verified. These are real source acquisitions, not repository-name hits.
Third-party hosting and `com.actions` package names do not independently prove
untouched manufacturer provenance.

The newer repository's `ActionsLog/.../LogManager.java` implements Actions
server1D/command10 text TLVs and F0/F1 parsing; `Global.java` declares the same
e49a3001/3002/3003 log UUID lineage. This gives a source-level host reference.
Its byte-scanning/partial-frame handling is not an integrity oracle; do not copy
it to hide missing fragments. OTA defaults differ from CoMi F5F0. Named older
Android MTU workarounds are not a demonstrated Linux/Mac loss cause. No new
device sender/backpressure contract or reason to rerun failed log trials follows.

**Sharper M4 acquisition target:** the [original developer setup report](https://blog.csdn.net/u010860832/article/details/124030196)
names `SDK-TAG_ZS308A_2700_220112`, build path
`application/bt_watch_call/outdir/lark_dvb_watch/zephyr/ksym.bin`, and firmware
`lark_dvb_watch_ext_nor_220408.fw`. This identifies an older LARK package family,
unlike the previously acquired ZS308B/LEOPARD trees; it supplies no archive URL.
The [separate developer note](https://github.com/peterlintang/normal-data-types/blob/17f59dabf77d3876530130254844e6ef5c531731/bak/3085c%20sdk.txt)
references `ats3085c_dvb_watch_ext_nor_max` and an `ATS308x_zs308A` application
document. Note content and complete2205-entry repository tree were inspected;
no matched package acquired. Two related backup trees also supply no matched
named payload; arbitrary unrelated archives were not treated as SDKs.

The newly found [ZS308A221215 repository](https://github.com/lgpww/SDK-TAG_ZS308A_2700_221215_REL3_N)
is **empty**: metadata size0, normal `git ls-remote` succeeds with zero refs,
release list empty. Keep this rejection so its promising name is not rediscovered
as source. An independently cloned [GitCode SDK guide attachment](https://gitcode.com/open-source-toolkit/d9173/tree/e3701ba9be43135a06630396717d93cea5cec1a9)
contains one PDF: SDK30F v1.1, June2004, Z80/ATJ208X material; it is not LARK/M4
source or a matching programming manual. Third-party PDFs/source stay outside Git.

Current search boundaries:

- Gitee native search returned405/security CAPTCHA. Public v5 search did not
  return even known `rec_jx3`; empty responses do not prove source absence.
  Ordinary public git and uploader repository lists worked. Complete returned
  lists for `szsheep`28 and `yekingsheng`2 were checked; known M33 trees excluded
  from new-source claims.
- AtomGit repository searches for ATS3085/ATS3089/actions_technology/炬芯/炬力/
  ZS308A displayed zero repository matches. Issue/user counts are not source.
  C-x-chen's ATS3085E public git/page remained inaccessible; legacy GitCode.net
  path redirected to login. OpenHarmony's ATS3089 entry is a short overview.
- CSDN's ordinary public search API was located through its search-page bundle.
  Model/tag queries and download-only `t=doc` inspected one page each; fuzzy
  tokenized results were manually distinguished from real matching artifacts.
  `t=download` did not filter downloads and was not used as a download-only oracle.
- Native forum/download and course checks are recorded in the receipt. Search
  misses, unavailable pages and contact-gated descriptions are not package absence
  or successful acquisition.

**Result:** additional Actions host source plus concrete ZS308A package/document
identifiers; still no complete LARK M4 BSP, CoMi original restore bundle or
independent exit proof. Future acquisition can target these exact older package
names and any actual attachment/ref. Do not substitute another M33 build or
repeat empty-repository/known-access-failure checks for a matched payload.

## Acquired material and search boundary

| Public repository / fixed revision | Acquired scope | Finding |
|---|---|---|
| [szsheep/rec_jx3][rec] `6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b` | Complete clean shallow clone on Ubuntu, 22768 tracked files; recursive API tree26164 entries, `truncated:false` | Repository describes a recorder based on Actions3.0 SDK. Contains `application/rec_card`, `bt_recorder_demo`, board files, DSP and schematic. LEOPARD/M33 SoC selection; not an official Actions publication or proof of CoMi provenance |
| [yekingsheng/ats3085e][ats] `37bfcac1fa7a38026460099be747efa3abacf6a9` | Complete recursive API tree14233 entries, `truncated:false`; pinned public git objects acquired on Ubuntu; config/map/ELF hashes verified | Source and checked-in build are LEOPARD/M33; actual ELF declares v8-M.mainline/FPv5/VFP ABI. Map preserves vendor path `D:/Breo/TAG_ZS3085E_2412302/`; not a hidden LARK/M4 build. [Receipt](evidence/recorder-reference-2026-10-13/ats3085e-build.json) / companion report |

Gitee's native **repository**, not code, search was queried through its own
widget/API: `ATS3085L`0, `ATS3085`1, `ATS3089`0, `GL6189`0, `lark_sdk`0,
`SOC_SERIES_LARK`0, `炬芯`4. `Actions Zephyr`122 results: only first20 inspected,
mostly unrelated upstream Zephyr projects. The two acquired leads came from
`ATS3085` and `炬芯`. Counts describe the current repository index, not absence
of code or private SDKs. [Query receipts](evidence/recorder-reference-2026-10-13/acquisition.json).

GitCode's explicit repository query `ATS3085` displayed0; issue/user results
were not counted as source. Indexed `c-x-chen/ATS3085E` / `ATS3089` pages were
unavailable anonymously at this pass, not proven empty. Stop retries without a
new accessible ref. GitHub exact CoMi board-name hits in acquired SDKs point to
old resource paths, not a surviving board directory; see companion report.

The Gitee project page displayed a moderation placeholder while ordinary public
git/API worked. Two Mac clones ended early EOF; API subset retrieval subsequently
hit403 `Rate Limit Exceeded`, so requests stopped. Ubuntu's normal public git
clone with HTTP/1.1 completed. No authentication or private endpoint used.

Five REC_JX3 refs checked by Astra all contain identical M33-selecting SoC
Kconfig blobs and no exact CoMi board or LARK SoC/header; fixed refs in companion
report. Its [16MiB A/B layout][layout] differs from CoMi's actual4MiB table.
Neither that layout's disabled CRC/encryption flags nor generic ADFU settings
describe this CoMi's boot policy or recovery escape.

## Follow the active recording workflow

Source root below: `application/rec_card/`. These are source paths, not measured
runtime success. `prj.conf` enables `CONFIG_RECORDING_APP`, hardware Opus encoding
and `CONFIG_ZERO_STREAM`; `src/CMakeLists.txt` selects the recording module.
[Configuration][prj] / [source selection][cmake].

| Stage | New application's actual source path | CoMi evidence / compatibility boundary |
|---|---|---|
| Activation / requests | `src/app/app_main.c:46` calls `recording_service_init`; `src/ble/ble_cmd_handler.c:1328–1465` queues record start/pause/resume/stop to `rec_service`; physical-key path in `src/app/idle_app.c` | CoMi Boyi dispatcher uses requests06/07/08/09. Shared use of services/messages does not match command frames or state layouts |
| Capture setup | `src/recording/rec_service.c:447–527`: choose microphone switch, check capacity, create output, `media_player_open/play`; OPUS,16kHz/16bit, input1 or2→output1,16kbps, complexity105; physical GPIO58 switch is project-specific | [Actual CoMi producer](recorder-media-config.md): format1,16kHz/16bit,1→1,32kbps; [actual codec table](recorder-codec-dispatch.md): `mp3e`→`aeRECORD.dsp`. No permission to copy GPIO or media struct offsets |
| Encoded output / file | `rec_service.c:401–443`: `zero_stream`, write observer wakes semaphore, optional attached file stream; `rec_file_manager.c:132–166` creates or appends recording file | [Actual CoMi writer](recorder-stream-path.md) first enqueues ring, then synchronously forwards original bytes to file stream; return comes from file branch. Different fan-out implementation |
| Live transfer | `src/ble/ble_sync_thread.c:147–205` opens same session file, seeks byte offset, follows growing length and waits for encoder observer | [Actual CoMi realtime path](realtime-source.md) consumes ring toward e5e3. New tail-file implementation cannot supply CoMi cancel/loss guarantees |
| Pause / resume / stop | `rec_service.c:539–652`: pause/resume media; stop+close media, read file length, detach/close/destroy streams, set idle, wake sync, send result | Lifecycle reference only. Source ignores several close/pause/stop return values; not proof of reliable persistence, power-cut recovery or CoMi stop semantics |

Direct fixed sources: [service][service], [file manager][fm], [sync worker][sync],
[command handler][commands], [application initialization][app].

Other independent differences:

- [GATT profile][profile]: service1910, TX2BB0, RX2BB1; [header][protocol] is
  data-type byte + little-endian16-bit command. Start/pause/resume/stop IDs20–23(decimal).
  CoMi uses E5E0–E5E4 and D22D/version/8-bit command/length/CRC16 framing.
  Wi-Fi/FOTA names in this source do not establish additional CoMi capabilities.
- [File naming][fmh]: `/SD:/REC/REC_<u32 session>_<scene>.opus`, versus actual
  [CoMi fixed recording paths](recording-download-path.md) and14-digit timestamps.
- Bundled `ksdfs/aeRECORD.dsp` and `fs_sdfs/sdfs_k/aeRECORD.dsp` are both73632 B,
  SHA256 `a3b7c7706e191548be36adddcdd8b338810813391a335a574687f5ff93d6bec9`.
  Actual [CoMi DSP](record-dsp-export.md) is110148 B,
  `7ed5482ca4d37c39f6b70e72fc29c129f135bc77eed5d3c0889bfc8bc5fd436e`.
  Same filename is not the same resource or verified DSP ABI.
- [Recording CMake][rec-cmake] explicitly excludes `rec_opus_enc.c` because its
  libopus dependency is not integrated. `rec_capture_stream.c` is compiled but
  has no creation call in this application's sources; current service uses
  `zero_stream`. Do not describe dormant/test sources as the active encoder.
- `bt_recorder_demo` is another source example: `recorder_func.c` actively sets
  `SBC_TYPE`/53kbps despite Opus-related filenames; its ring→deferred-file-write→
  file-reading BLE topology differs from CoMi. The `ap_record` module referenced
  in a comment also exists in the previously acquired LVGL SDK, with synchronous
  callback output, not CoMi's ring worker. Naming alone is a weak match.

## Reuse and next decision

Useful now: whole recording service, request ownership, media lifecycle,
filesystem/stream assembly and transfer architecture. Read the complete
workflow before adding an isolated helper experiment. It depends on platform
mic switching/audio policy, media/BLE archives, DSP loader/resource ABI, FS/SD,
and its own BLE state machine. None is automatically compatible with M4 CoMi.

The user's hypothesis remains plausible: CoMi may be a small OEM change to a
**matching LARK SDK**. These newly available M33 applications are a different
comparison baseline; their differences do not measure CoMi's OEM patch size.
No new firmware backup, Flash writer or independently recoverable entry follows
from this source acquisition.

For the original goal, keep separate acceptance gates: host CLI's actual
protocol coverage; M4 platform/library closure; complete raw storage and unique
configuration backup; independent entry/escape and restoration; then own minimal
boot/display/recording. This pass improves the application reference material,
not the recovery gates. New broad queries, another M33 reference build or
one-callee live reads are not the next default step. Reopen acquisition on an
actual matched package or reference; use the workflow map when implementing
recording on a verified platform.

## Reproduce source acquisition

[Acquisition script](../tools/acquire_recorder_reference.py) pins commit and
scope, checks each Git blob SHA1 and saves SHA256/size manifest; no SDK code is
executed. It resumes only files whose hashes match. First error exits, including
rate limits; no retry storm. [Verified177-file manifest](evidence/recorder-reference-2026-10-13/source-manifest.json)
is committed; third-party source, binaries and schematic stay outside Git.

```sh
uv run tools/acquire_recorder_reference.py artifacts/recorder-reference
# Or supply a previously saved complete, exact-commit Gitee API tree:
uv run tools/acquire_recorder_reference.py artifacts/recorder-reference --tree-file TREE.json
```

If normal git is preferable, clone the fixed ref to `~/w/_tmp` and use its
application tree directly; ordinary Ubuntu clone succeeded this pass. Current
Mac subset additionally includes the full application archive exported with
`git archive <fixed-sha>` from that clean clone. The tool verified177 scoped
blobs locally against the independent API tree without more network requests.
This is source-integrity evidence, not a successful application build.

[rec]: https://gitee.com/szsheep/rec_jx3/tree/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b
[ats]: https://gitee.com/yekingsheng/ats3085e/tree/37bfcac1fa7a38026460099be747efa3abacf6a9
[layout]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/boards/ats3085s_dev_rec_card/firmware.xml
[prj]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/prj.conf
[cmake]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/CMakeLists.txt
[rec-cmake]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/recording/CMakeLists.txt
[service]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/recording/rec_service.c
[fm]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/recording/rec_file_manager.c
[fmh]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/recording/rec_file_manager.h
[sync]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/ble/ble_sync_thread.c
[commands]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/ble/ble_cmd_handler.c
[app]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/app/app_main.c
[profile]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/ble/ble_record_profile.c
[protocol]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/ble/ble_protocol.h
