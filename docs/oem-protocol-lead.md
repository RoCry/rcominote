# OEM / official-app lead — 2026-10-12

Status: useful independent firmware-acquisition lead; **no CoMi firmware image, OEM identity, or compatible updater established**. Host-only static work; no device command or firmware API request.

## Device comparison

Third-party [LA518 capture notes](https://github.com/wojt-janowski/mobile-la518-recorder/blob/8cc0b24ca598241bc0d557534526f902121fb4db/PROTOCOL.md), inspected at that commit. These observations belong to another owner's UMEVO Note Plus / LA518; do not transfer commands to CoMi.

| Property | Owned CoMi, repo protocol / captures | LA518, third-party report |
|---|---|---|
| Application service | E5E0; E5E1–E5E4 | F0F0; F0F1–F0F4 |
| Envelope | `D2 2D 01` | `80 08 02` |
| CRC | CRC16/A001, initial 0, little endian | TX zero trailer; RX algorithm unresolved |
| Manufacturer ID | `0x375c` | `0x189a` |
| Serial | 10 ASCII characters | 15 ASCII characters |
| Bind | Not required for observed CoMi path | `131186` exchange reported required |
| `0x09` | Resume recording | OTA association is speculative in capture notes |
| File row | 20 bytes: name14, size4 big endian, two flags | 20 bytes: flag, name14, separator, size3 big endian, flag |
| Actions log service | `e49a3001…`; shell/read response observed | Same family reported, no responses in that capture |

Concrete shared clues: unusual literal `xink_test`; recording/file operations `06/07/0a/0b`; timestamp filenames; MP3 16 kHz / 32 kbps; Actions-family UUIDs. They justify inspecting related official apps, not identifying CoMi's manufacturer, SoC, or update format. LA518 notes' "ADTS" wording does not establish MP3 framing.

## First-party acquisition

- [UMEVO Note Plus app guide](https://www.umevo.ai/pages/help-center-app-guide-detail?id=APP-01): explicitly pairs Note Plus with **AI DVR Link**.
- [UMEVO manual](https://www.umevo.ai/pages/help-center-manual-detail): Note Plus, MP3 / 32 kbps / 64 GB, computer USB file transfer. No firmware/recovery package found on this page.
- [Kinghal app download](https://app.kinghal.com/): exact Android link `./file/AI_DVR_Link-3.2.0.apk`, Google Play `com.ai.dvrlink`, App Store `6680163395`.
- [Apple's AI DVR Link listing](https://apps.apple.com/us/app/ai-dvr-link/id6680163395): developer Dongguan Kinghal Electronic Technology Co., LTD; seller CG E-commerce LLC. This identifies the app publisher, not CoMi's OEM.
- [Current UMEVO download page](https://www.umevo.ai/pages/help-center-app-download): separate current app `com.umevo.recorder`; exact APK below. Distinguish this from the Note Plus guide's AI DVR Link pairing.

Exact downloads, HTTP 200; Android manifest parsed from each APK:

| URL | Manifest | Bytes | SHA-256 |
|---|---|---:|---|
| `https://app.kinghal.com/file/AI_DVR_Link-3.2.0.apk` | `com.ai.dvrlink` 3.2.0 / code320; minSDK24, targetSDK35 | 355395559 | `bba153b4da1db7e1be9f239b3e93eb5b255af9b1d30528198aec5cb9a950e7bd` |
| `https://static.umevo.ai/app-downloads/android/package.apk` | `com.umevo.recorder` 1.2.5 / code42; minSDK24, targetSDK36 | 113780425 | `7d9d4a71c274ed8a7420d1aa4440711b592ab935ec5dbba49f0fa310e9c4eb06` |

Local ignored carriers: `artifacts/oem-ai-dvr-link-3.2.0.apk`, `artifacts/oem-umevo-current.apk`. SHA permits verifying future acquisitions; mutable URLs do not pin future bytes.

## Static evidence / limits

AI DVR Link REA archive Evidence `ev_5c92c31149c6446c2cedb7e8ca4fcb32734d5056eaf718f2a1a998475e90319d`, retained `artifacts/oem-ai-dvr-link-rea.json`. Archive inventory complete within substeps; case-fold collisions and APK signing-block inventory limitations remain. JADX1.5.6 processed Java wrappers with 51 AI DVR / 37 UMEVO errors; Dart AOT carries the important application logic. Static parsing never executed either APK.

All 2508 AI DVR / 963 UMEVO ZIP file names checked for firmware/OTA/upgrade/update or bin/fw/img/hex/dfu/uf2/fwp/rom/pack/pak/zip suffixes. AI DVR candidates: upgrade PNGs, Flutter AssetManifest.bin, Kotlin DebugProbesKt.bin (`CAFEBABE` Java class); UMEVO only the two latter. **No named update image found by this filter**; opaque or embedded payloads remain outside this negative result. Full member metadata/candidate hashes retained in `artifacts/oem-*.members.json`; reproducible method: `uv run tools/inspect_apk_members.py APK --out NEW_JSON`.

AI DVR **arm64 libapp.so** SHA `f5530f73cf43d4874c9bd7e95da06f787974806495c1269b36c915ce8a72217a`. Selected ASCII literals, hexadecimal **file offsets** (not code addresses or call relationships):

| Offset | Literal / implication limited to presence |
|---:|---|
| `0x12968b` | `LA518A` |
| `0x14ec66` | `e49a25f8-f69a-11e8-8eb2-f2801f1b9fd1` — OTA service, role confirmed below |
| `0x249b76` | `e49a25e0-f69a-11e8-8eb2-f2801f1b9fd1` |
| `0x2da1ab` | `e49a28e1-f69a-11e8-8eb2-f2801f1b9fd1` |
| `0x236384` | `/device/firmware_version` |
| `0x25f320` | `https://resource.aidvrlink.com:8099/api/player/firmware_upgrade` |
| `0x99295e` | `package:dvrlink/dvrlink_module/version/firmware_version_mgr.dart` |
| `0x26d0b8` | `package:dvrlink/dvrlink_bluetooth/dfu_manager.dart` |
| `0x9c2df` | `package:dvrlink/dvrlink_bluetooth/xlx_link/dfu/xlx_ota_manager.dart` |
| `0x2d48d3` | `package:dvrlink/dvrlink_bluetooth/xlx_link/protocol/command/firmwareUpgrade/firmware_upgrade_command.dart` |
| `0x141005` | `package:dvrlink/dvrlink_wifi/xlx_ota/ota_controller.dart` |

UMEVO arm64 libapp.so SHA `013601d5085451d8ae34494b3dedd82c63be83538de33dd8d9b89d14893f2b60`: `LA518` at `0x7ea3b`, `0000F0F0` at `0xb9a48`, `https://api.umevo.ai/api` at `0xc77d7`, `firmwareVersion` at `0xceace`, outdated-firmware UI text at `0x14d5ac`. These first-party artifacts corroborate LA518/F0F0 app support; they do not identify the CoMi transport.

## Recovered Dart call paths

Offline Blutter analysis establishes these additional facts; addresses below are ELF code addresses, distinct from the string file offsets above.

- `/device/firmware_version` is **a Flutter navigation route**, not a firmware HTTP endpoint: `FirmwareVersionMgr::checkFirmwareUpgrade` closure calls `ModularRouterDelegate::pushNamed` at `0x1831a44`.
- Actual HTTP: `FirmwareDao::firmwareUpgrade` (`0x181c7a0`, size `0x40c`) JSON-encodes a map at `0x181c9e8`; creates Dio Options `method="post"` at `0x181c9f8`; calls `HttpManager::netFetch` with the exact `resource.aidvrlink.com:8099` URL at `0x181ca20`. Its caller `checkFirmwareUpgrade` awaits the result at `0x181ded4`, then calls `showUpdateDialog` at `0x181df7c`. Thus **metadata-check semantics are inferred from client control flow**, not demonstrated server-side behavior.

Request map recovered from `0x181c8a4–0x181c988`:

| Field | App-supplied value |
|---|---|
| `deviceType` | integer `0` |
| `platform` | string `"4"` |
| `model` | string `"1"` |
| `version` | current `DVRLinkDeviceInfo::versionStr()` for BLE, `wifiVersionStr()` otherwise |
| `sn` | app hard-coded literal `"100001250300001"`; **not owned CoMi serial** |
| `playerId` | local-storage `dvrlink_user-id` integer |
| `updateType` | enum index: BLE `0`, Wi-Fi `1`, all `2` (object-pool evidence) |
| `token` | local-storage `dvrlink_wear_token` string; key name only, no user's credential extracted |

`netFetch` passes JSON body + empty caller headers to Dio (`0x139c794`); full merged Dio/interceptor configuration has not been audited. FirmwareDao accepts successful wrapper plus JSON `code == 200` (`0x181caa8`, tagged Dart integer `0x190`), then parses `data` through `_$FirmwareFromJson` (`0x181cafc`). Model keys: `clientCode`, `filePath`, `fwId`, `hardwareVersion`, `newVersion`, `productCode`, `status`, `targetVersion`, `fileMd5`, `zhDesc`, `enDesc`, `fileSize`. No actual response or concrete `filePath` obtained.

## OTA image / transport checks

- `DVRLinkDFUManager::download` (`0x19432a8`) downloads the request URL via `HttpManager::download` (`0x194334c`); after HTTP200 computes local-file MD5 (`0x1943378`) and compares with the request MD5 (`0x19433ec`). Mismatch reports `DOWNLOAD_FAIL` (`DFUStatus@1edadf1`); equality reaches `_startOta` (`0x1943458`). This is an integrity check, not a digital-signature proof.
- `DVRLinkManager::startOTA` (`0x1943658`) constructs a DFU request and directly calls `DVRLinkXlXOTAManger::startOTA` at `0x19436ac`. The APK contains `cmd_3085s`, generic and `cmd_slink` protocol branches. These names do not prove LA518/CoMi chip identity; no Boyi/E5E0 match found in the recovered `dvrlink_bluetooth` tree.
- `DVRLinkBleProfiles` methods explicitly select OTA service `e49a25f8…` (`isOTAService`, `0x194548c`), TX `e49a25e0…` (`isOTATXUuid`, `0x1945150`), RX `e49a28e1…` (`isOTARXUuid`, `0x194522c`); alternate E0E0/E0E1/E0E2 short UUIDs also appear. Common long suffix `f69a-11e8-8eb2-f2801f1b9fd1`. **These differ from CoMi's working log service `e49a3001…`.**
- XLX `startOTA` reads an image header via `_readOTAHeader` (`0x19438d4`). Header reader (`0x194415c`, size `0x1fc`) UTF8-decodes the leading four bytes and compares with literal `AOTA` (`0x19441d0`); the AOTA branch then decodes a later header region, alternate format follows a different branch. Thus actual support for an Actions-style AOTA carrier is established in this app; compatible CoMi image/board configuration is not.
- XLX `_writeBinData` constructs a Crc32 instance (`0x16beac8`), feeds outgoing block bytes to `ParametricCrcSink::iterateBytes` (`0x16beb38`) and serializes the result into the outgoing data. Header selection / MD5 download / block CRC paths inspected; **no cryptographic signature validation established or excluded**. Device boot-chain checks remain unknown; see [SDK signature caveat](actions-sdk.md).

The current UMEVO APK also recovered through Blutter (Dart3.12.0). Its `umevo/services/bluetooth_protocol.dart` and `bluetooth_connection.dart` are available for follow-up. Bounded recovered-assembly search found no `AOTA`, `firmware_upgrade` or `/firmware` endpoint in this newer app; no claim about obfuscated or server-selected update logic.

No firmware API request issued: valid appropriate AI DVR Link account/device context is unavailable; no guessed `playerId`, token, device version or update type used. No firmware image downloaded, no cross-device flashing compatibility or official recovery path established.

## Reproduce / retained evidence

Blutter [source pinned at `4a60ac6`](https://github.com/worawit/blutter/tree/4a60ac648bf448c5a7596437243bcd0b9376fdf0), reviewed before use; macOS Darwin25 / AppleClang21, Homebrew CMake/Ninja, capstone and icu4c@78. Repository wrapper `tools/run_blutter.py` declares dependencies through uv, verifies exact Blutter commit and clean tracked source, and refuses existing output. Static analyzer compiles matching Dart VM libraries; never launches APK or generated Frida script.

```sh
git clone https://github.com/worawit/blutter.git "$HOME/w/_tmp/blutter"
git -C "$HOME/w/_tmp/blutter" checkout 4a60ac648bf448c5a7596437243bcd0b9376fdf0
PKG_CONFIG_PATH=/opt/homebrew/opt/icu4c@78/lib/pkgconfig \
  uv run tools/run_blutter.py artifacts/oem-ai-dvr-link-3.2.0.apk \
  artifacts/oem-ai-dvr-link-blutter --blutter-dir "$HOME/w/_tmp/blutter" \
  > artifacts/oem-ai-dvr-link-blutter.log 2>&1
# Same invocation with oem-umevo-current.apk and oem-umevo-blutter.
```

AI DVR Dart3.10.8 / snapshot `1ce86630892e2dca9a8543fdb8ed8e22`; Dart checkout `f934176b0195e655c73e92d431079457ceba488f`. UMEVO Dart3.12.0 / snapshot `41be3daaabd524b8aa7423bc24584957`; checkout `98116461144f4429ab873f8497023a5ec3b08127`. Both analyzer processes exit0; AI DVR log records three instruction-analysis errors outside the paths cited above, so recovery is not exhaustive.

Generated trees `artifacts/oem-{ai-dvr-link,umevo}-blutter/{asm,objs.txt,pp.txt}` remain ignored. Decisive AI DVR assembly files under `asm/dvrlink/`: `dvrlink_common/dao/firmware_dao.dart`, `dvrlink_model/device/Firmware.dart`, `dvrlink_module/version/firmware_version_mgr.dart`, `dvrlink_bluetooth/{dfu_manager.dart,dfu_constants.dart,dvrlink_mgr.dart}`, `dvrlink_bluetooth/xlx_link/{bluetooth_profiles.dart,dfu/xlx_ota_manager.dart}`. Offsets + APK SHA + pinned analyzer permit rebuilding; static assembly annotations remain analyst interpretations, not runtime traces.

The committed wrapper was rerun against the pinned AI DVR APK: same Dart snapshot,
firmware URL/call-site and AOTA/CRC anchors recovered. Full text is not byte-stable:
for example, analyzer-host `IMM` pointer annotations at `0x181ca60/0x181cacc`
changed between runs. Do not treat those host pointer values as target firmware
addresses or require a whole-annotation-file hash match. Three unrelated analysis
errors remained; process exit0 alone is not exhaustive recovery proof.
