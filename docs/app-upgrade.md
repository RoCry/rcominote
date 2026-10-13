# App evidence: USB mode, upgrade hooks, firmware acquisition

Research date: 2026-10-12. Host-only inspection; no device commands, app execution,
account login, or flashing. Primary evidence: original bytes inside official APKs.

Coverage correction2026-10-13: [bridge/default configuration audit](wifi-app-paths-2026-10-13.md)
shows1.1.2 defaults to a remote frontend. Conclusions below concern packaged
code and selected decompiled sources, not a complete inventory of live App
features. The configured remote page returned HTTP500 in the new host fetch.

## Conclusions relevant to custom firmware

1. **Boyi has an explicit USB-enable command.** App defines opcode `0x13`, sends
   one boolean byte, and automatically enables USB after connecting over BLE.
   Normal-mode USB non-enumeration therefore does not establish absent data
   wiring or absent recovery mode. Actual USB class, pin wiring, cable capability,
   and the owned unit's response remain unknown.
2. **No Boyi upgrade command identified in the inspected 1.1.2 JS.** Its complete
   command table covers `0x01`–`0x1a`, with `0x0e` absent. Do not probe unassigned
   opcodes as if they were documented upgrade operations.
3. **Mova has OTA declarations, not a demonstrated upgrade implementation.**
   `TRIGGER_OTA=0xe6`, `OTA_FILE_TRANSFER=0xf6`, and characteristic `6e400005…`
   occur only in declarations and command-name logging in this bundle. No
   constructor, transfer writer, image validator, or caller was found using those
   identifiers. This corrects the stronger handoff wording “OTA exists”. Neither
   Mova support in this app nor Nordic-style UUIDs establish CoMi device support.
4. **No usable CoMi firmware image or download endpoint recovered.** Negative
   finding is bounded to the inspected assets and focused decompiled packages.
   The 1.2.4 archive contains two additional opaque `.bin` files; purpose unknown.
   Their filenames alone establish neither recorder firmware nor absence thereof.

## Samples and reproducibility

| Sample | Bytes | APK SHA-256 |
|---|---:|---|
| CoMi 1.1.2 | 53,960,403 | `b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118` |
| CoMi 1.2.4, retained store sample | 85,750,588 | `8aade0a4ca1f9e25b9ebbd51dee97702bf0954e5a66adcf91312b4331414ace7` |

The [official download page](https://www.seeyon.com/CoMiNote/download.html) still
links the [1.1.2 APK](https://www.seeyon.com//Public/Home/CoMi_release_1.1.2_2025-12-26.apk)
in raw HTML checked on the research date. Page link is not evidence of the newest
store version. Download filename's date is not a signing timestamp.

From repository root:

```bash
mkdir -p artifacts
curl -L --fail --output artifacts/comi-1.1.2.apk \
  'https://www.seeyon.com//Public/Home/CoMi_release_1.1.2_2025-12-26.apk'
uv run tools/apk_evidence.py artifacts/comi-1.1.2.apk --out artifacts/apk112
```

The stdlib-only script verifies an exact known APK digest, inventories every ZIP
member with hashes, searches selected literal terms in asset text, and extracts
the main device JS plus short evidence slices into a new caller-selected folder.
It never executes JS, connects to a device, or fetches a recorded URL. Outputs
belong in ignored `artifacts/`; APKs/full extracted assets are not repository
sources. For a locally acquired 1.2.4 APK, pass that path and a different new output
folder: inventory is available, but no matching readable device JS is present.
Unknown sample hashes fail explicitly; research/review a changed sample before
adding a pin.

Offsets below are **zero-based byte offsets in decompressed ZIP member**, end
exclusive, not Unicode character offsets or compressed ZIP offsets. Main member:
`assets/public/assets/index-Btih_BUR.js`, 588,988 bytes, SHA-256
`167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c`.

## Boyi USB call path

| Evidence | Byte range | Observation |
|---|---|---|
| `boyi-constants-frame` | `[217000,219700)` | Boyi company identifier 14172; service `0000e5e0…`; command table `SET_USB_MODE:19`; normal Boyi frame builder |
| `boyi-send-command` | `[232509,233700)` | Writes framed command and resolves `success:true` on matching response; no application result-code check in this generic path |
| `boyi-device-info` | `[235121,236080)` | `GET_DEVICE_INFO` requires at least 44 bytes; payload byte 14 equals 1 → `usbMode:true` |
| `boyi-status-event` | `[220292,220822)` | Status event parser requires at least 20 bytes; byte 2 → USB mode; byte 10 → USB connected |
| `boyi-usb-setter` | `[245602,245936)` | `Uint8Array(1)`, byte 0 = enabled ? 1 : 0, then `sendCommand(…,ue.CMD.SET_USB_MODE,…)` |
| `auto-enable-usb-effect` | `[386500,387100)` | On connected device, call recorder selected by device type with `setUsbMode(deviceConnectId,true)`; suppress repeated calls after reported success |

The control is carried over Boyi BLE, through the existing framed write
characteristic `0000e5e1…`. This does **not** say USB itself carries Boyi frames.
Setter's `success` only means the generic request path received a matching
response. A future controlled experiment needs status readback plus actual host
USB enumeration; app logs reporting “成功” are insufficient.

The observed initial USB behavior in the handoff remains useful, but should be
recorded as “did not enumerate in the tested state”. With the owned device later
available, compare host USB inventory and `usbMode` before/after a deliberate
enable, using a verified data cable. Whether a bootloader appears under a separate
boot condition remains another question. No such change was attempted here.

## Mova declarations and search boundary

`mova-constants` `[253400,255573)` contains the independent service family
`6e400001-b5a3-f393-e0a9-e50e24dcca9e`, OTA write `6e400005…`, company identifier
20068, USB `0xe4`, trigger OTA `0xe6`, file transfer `0xf6`.

Exact occurrences in the **entire main member**:

| Token | Byte offsets | Meaning |
|---|---|---|
| `CHAR_OTA_WRITE` | 253729 | Characteristic declaration only |
| `TRIGGER_OTA` | 254259, 255102, 255116 | Opcode definition; lookup key; lookup string |
| `OTA_FILE_TRANSFER` | 254356, 255290, 255310 | Opcode definition; lookup key; lookup string |
| `firmware` | none | Literal case-insensitive search also found none |

Mova does implement its own USB setter: constructor `CC` at
`[258794,259002)` builds `[0xe4, enabled?1:0]`; setter at `[275210,275510)` checks
a response beginning with success value 1. Recorder method surface inspected at
`[277400,279350)` exposes Wi-Fi controls and reboot, but no upgrade method.
Device manager `[279350,281000)` selects Boyi/Mova independently.

Whole `assets/` `.js/.json/.html` files were also searched for `firmware`, `固件`,
and the OTA identifiers. The only additional relevant hit was a nonclickable
“固件版本” field in `assets/public/assets/index-CPQTL8Yp.js` at byte 2003.
There was no OTA URL or image-consumption path established from those hits.
An obfuscated/numeric implementation, native path, remotely loaded code, or later
app version remains outside this negative conclusion.

Existing JADX output was inspected in `com/seeyon` and `com/webnote`: no matches
for `firmware`, `TRIGGER_OTA`, `OTA_FILE_TRANSFER`, `固件`, `device.?upgrade`,
or `ota.?upgrade`. This is a bounded search of decompiled text, with previous
JADX failures; it does not prove the complete DEX lacks upgrade functionality.
`RecordingCardOpener.open` → `ApNoteSDK.launch` → `ApNoteActivity` connects the
native host to the packaged web app, but these decompiled classes are not needed
to reproduce the byte-level JS findings.

## Bundled image candidates and 1.2.4 limitation

1.1.2 has 1,781 file entries. Filename inventory for `firmware` or extensions
`.bin/.fw/.hex/.img/.dfu/.ufw/.upd` yields `assets/WakeUp.bin` and
`DebugProbesKt.bin`. No recorder image was identified from these names/content
context; no format/signature-based sweep of every opaque payload was performed.

1.2.4 has 2,165 file entries, no `assets/public/` JavaScript, and packages
`assets/ijiami.ajm`, `assets/ijiami.dat`, plus `libijmDataEncryption*` libraries.
This is consistent with the handoff's hardening observation; no encrypted DEX
recovery or dynamic instrumentation was attempted. Additional `.bin` candidates:

| Member | Bytes | SHA-256 | Attribution |
|---|---:|---|---|
| `assets/signed.bin` | 66,032 | `848722d270b849c26d6902d334b6d5564199ec6052e5416a9d7f9c662f546f54` | Opaque bytes; no format or consumer established |
| `assets/af.bin` | 43,760 | `1417960bf7dd0f19e6e9d6e7754994e1b5ba9d2d0d03a32a2087172d56e5a0ca` | Opaque bytes; no format or consumer established |

Other `.bin` members are `assets/WakeUp.bin`, `DebugProbesKt.bin`, and three
store metadata files. Neither unknown file should be used as a flash image.
Next useful app evidence would be the vendor's actual upgrade UI/network flow
or a documented firmware package for the exact recorder hardware revision.

## REA evidence and limits

REA `open_binary` confirmed the 1.1.2 APK identity. Static JS analysis of the
extracted `assets/public/` tree returned parent evidence
`ev_8840348744f87501289f486c9be5db0d7be5b31d862e01f76260bec926fe266c`, summary
`ev_9eb45411dcd591b6d0974f27a63ba72f316f6220c0c160409cff316ffadb16d9`.
Tree digest: `31abe07077bcac91fa51f5e63e75224f5742ac592d98ea4e957aa26803c913ec`.
Graph coverage is partial: main-index semantic worker exhausted its heap, other
expanded relationships reached resource limits. These REA IDs are session
references, not durable acquisition URLs. Conclusions above use direct ZIP
member hashes, byte slices, and source reads, reproducible by the local script;
they do not rely on missing graph edges or claim runtime execution.

## Follow-up REA investigation (2026-10-12)

Reopened exact 1.2.4 APK, matching SHA-256 above. REA inventory completed:
[retained summary](evidence/rea-apk124-inventory-2026-10-12.json), Evidence
`ev_55e78eb27870f81ce25c6e48d39ed76286890a3050a34e94a5134c93f0351988`,
child inventory `ev_5d0ed3747a2aca3c359b276110d4911912e99d7dd9b3cae514a22e353c9c4cd8`.
2166 occurrences include the archive root; 2165 ZIP members. No integrity contradictions;
case-folding name collisions prevent assuming lossless extraction onto a default macOS volume.
Complete 4.9 MB evidence bundle retained locally in `artifacts/rea-apk124-2026-10-12.json`.
Session closed after export.

Focused **ordinary Python ZIP reads**, separate from REA, measured both opaque candidates:
[byte observations](evidence/apk124-candidates-2026-10-12.json). `signed.bin` and `af.bin`
have approximately 7.997/7.993 bits per byte entropy; neither begins with ASCII AOTA or ELF
magic. This does not identify their format or exclude embedded/transformed firmware.
Literal search of 1437 `.so/.dex/.xml/.json/.js` members for `signed.bin`, `af.bin`,
`firmware`, `Firmware`, `AOTA`, `ADFU` found no matches. No claim about encoded strings,
protected content, remote code, or runtime behavior follows from this bounded negative.
The only root DEX is 13,900 bytes, insufficient reason to infer where all app logic resides.

REA `inspect_android_package` could not run: caller-supplied JADX MCP 0.7.1 JAR is not
configured (`REA_JADX_MCP_JAR`). No registration/approval rejection occurred; no configuration
was changed. Archive inspection remained available. Therefore this pass adds no decompilation
or incoming-reference proof for the opaque files. Next useful artifact work requires a usable
Android analysis provider and, for protected code, an authorized app runtime or an unprotected
vendor package. Installing a decompiler alone does not establish access to protected code.

后续修正：1.1.2的Capacitor配置指向远程录音页面；已用本机JADX CLI成功解出1.2.4加载壳，但未恢复其原应用。见 [官方产物继续核查](official-acquisition-followup.md)。打包JS的否定结论不能覆盖当前在线页面。
