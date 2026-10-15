# CLI capability and settings specification

2026-10-12. Static evidence from official CoMi 1.1.2 APK; existing owned-device
observations cited separately. Boyi only. App source establishes request bytes
and app interpretation, not whether this firmware accepts every operation.

## Source identity and reproduction

APK SHA-256: `b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118`.
Decompressed ZIP member `assets/public/assets/index-Btih_BUR.js`: 588,988 bytes,
SHA-256 `167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c`.
All ranges below: zero-based **bytes**, end exclusive, in this member. Extract
with [apk_evidence.py](../tools/apk_evidence.py); verify member digest before
interpreting slices. Source acquisition and prior REA coverage:
[app-upgrade.md](app-upgrade.md). No fresh APK execution or device I/O performed
for this specification.

| Source region | Range | Purpose |
|---|---|---|
| `ue.CMD`, `ry`, `ho` | `[217643,219336)` | Complete Boyi command constants, CRC, frame builder |
| `V8` | `[219336,219782)` | Response header/version/length/CRC checks |
| `Y8`, `Z8` | `[220352,220992)` | Device/voice-control event payloads |
| `il` | `[221179,223211)` | Recording/file response status and layouts |
| `eC.sendCommand` | `[232509,233642)` | Request completion semantics |
| `eC.syncTime` | `[234663,235121)` | Six-byte local calendar clock |
| `eC.getDeviceStatus` | `[235121,236151)` | Settings getters inside device-info reply |
| `eC.getRecordingInfo` | `[246291,246953)` | Recording-info request and parsed result |

## Settings: explicit setters plus readback

Get all current settings using `GET_DEVICE_INFO=0x05`, empty request payload;
reply must contain at least 44 bytes. There are no separate settings-getter
opcodes in this Boyi table. All six setters below send **exactly one byte**.

| CLI setting | Opcode | Accepted CLI values / payload byte | GET_DEVICE_INFO byte | Setter range |
|---|---:|---|---:|---|
| `usb` | `0x13` | off `00`, on `01` | 14 | `[245599,245939)` |
| `indicator` | `0x11` | off `00`, on `01` | 16 | `[244817,245156)` |
| `voice-control` | `0x14` | off `00`, on `01` | 40 | `[245939,246291)` |
| `segment` | `0x16` | 30min `00`, 1h `01`, 2h `02`, 3h `03` | 41 | `[246953,247358)` |
| `noise-reduction` | `0x17` | integer 0 through 16 inclusive | 39 | `[247358,247787)` |
| `backlight` | `0x1a` | off `00`, on `01` | 42 | `[248131,248489)` |

Boolean getters: indicator/voice-control/backlight return null for `ff`, true for
`01`, false otherwise. USB is true only for `01`; source has no null handling.
Noise and segment getter bytes remain raw integers. Preserve raw replies for
investigation; a null/unknown readback cannot prove successful mutation.

Noise setter explicitly rejects numbers outside 0..16. Require integers in CLI;
JavaScript's Uint8Array conversion is not a specification for fractional inputs.
No meanings for individual noise levels were established. Segment setter labels
0 as 30 minutes, 1 as 1 hour, 2 as 2 hours, **all other values** as 3 hours; it does
not validate a 0..3 range. A CLI restricted to 0..3 is a conservative inference
from those four labels, not proof that firmware rejects other bytes. Search of
every `assets/public/assets/*.js` member in the pinned APK found no settings UI
caller establishing a narrower domain; the main member contains setters and
wrappers. Backlight source label is “屏幕常亮”: always-on toggle, not brightness.
USB toggle means “USB support”; USB class/enumeration must be observed separately.

[Owned-device USB roundtrip2026-10-13](usb-next-steps-2026-10-13.md) now verifies
on→off→on field readback and restoration; passive Mac USB inventories remain
identical, complete8-file lists unchanged. This is not MSC activation or proof
that the original magnetic cable carries data. NOTE/CALL is readable but has
no confirmed setter among these23 fixed-App requests.

Setter slice SHA-256 values:

| Setting | SHA-256 |
|---|---|
| USB | `d9fddecd10e8e0890780f749491c37b6634e4547b1bac7d23b7a1ea99af30fd3` |
| Indicator | `c51b51f6ade9bc1031d4a848d99211fa0478c2b4f258fd2dc0fb2622240edc78` |
| Voice-control | `ce7fb210aa2c971ff8db7685a64f5e3e5bcc9afd9063cd19d655254be5defe59` |
| Segment | `1d710ae7cb1d03b1b47cab2fd357d6ea26555f6334d6ccaab47f521d5ba95c7f` |
| Noise-reduction | `51453ef5f8932ac4a0e90ac212065eebb1e51f427197a13f22def959035ae929` |
| Backlight | `f18daa20d0f5f3936750d8ee1c92d7f935efbd86880bdba9b16752a3f5de18db` |

`SET_PHONE_TYPE=0x18` also sends one byte; source labels 0 Android, otherwise iOS
(`[247787,248131)`). No matching readback field or evidence of effect found.
Implemented as explicit `maintenance phone-type android|ios`, outside the
readback-verified settings command. Never assign host OS automatically; iOS1
is a conservative host choice from the source's nonzero branch.

### ACK and error contract

`sendCommand` resolves `{success:true,data:replyPayload}` when a frame passes `V8`
and the opcode matches. **It does not inspect setter result bytes.** All six
setters propagate this generic success without further validation. Consequently,
neither empty reply nor first byte `00` has established application-level ACK
meaning for these setters. Do not invent one from recording/file status codes.

CLI should report the raw matching response, then issue device-info again and
require requested field equality. Distinguish `response_received` from
`verified_by_readback`. Timeout, disconnect, CRC/length error, unsupported/null
readback, or mismatch must fail clearly. If before equals requested value,
readback verifies retained state but cannot prove an actual change occurred.
Readback alone does not prove persistence across reboot or physical effect.

## Recording controls and status

All requests below have empty payload. ASCII names occupy 14 bytes; numeric
file sizes are u32 big-endian. Kind 0 means call, any other value note. Record
state and recording mode are different fields. Actual mode is NOTE01/CALL02 in
GET_DEVICE_INFO byte15 and event0f byte3; unknown mode values fail parsing. This
corrects the pinned App labels using actual firmware and physical-screen readback.
START/STOP/file kind remains Note01/Call00; do not reuse the mode enum.
[Static paths and two-mode live samples](note-call-audio-2026-10-13.md).

| Opcode | Request | Valid reply payload |
|---:|---|---|
| `0x06` | start | At least 16 bytes: status `00`, name `[1,15)`, kind byte 15 |
| `0x07` | stop | At least 21: status `00`, name `[1,15)`, size `[15,19)`, kind byte 19 (`01` note, `00` call; pinned App STOP label corrected), need-sync byte 20 (`01` true) |
| `0x08` | pause | At least 16: status `00`, name `[1,15)`, kind byte 15 |
| `0x09` | resume | Same layout as pause |
| `0x15` | recording-info | Exact `01`: idle. Otherwise at least 20: status `00` recording / `02` paused, name `[1,15)`, size `[15,19)`, kind byte 19 |

For start/stop/pause/resume, exact payload `01` is explicit failure. Other
unknown statuses, truncated payloads, or malformed framing must fail. App's
START parser checks `<15` although subsequently accessing byte 15; CLI should
require 16, avoiding the source off-by-one. Do not treat status `02` as success
for a recording-control reply merely because it means paused in recording-info.

Device-info byte 10 maps 0 idle / 1 recording / all others paused in app source.
The recording-info request provides stricter status evidence and current file.
Control methods: `[236151,238428)`; parser: `[221179,223211)`.

## Discovery, files, events and diagnostics

| Capability | Source / wire contract | Evidence boundary |
|---|---|---|
| Scan / serial / bind-state / device-info | Company 14172; e5e0/e5e1/e5e2; `01`,`02`,`05` | Existing owned-device read-only verification in [protocol.md](protocol.md) |
| Serial | Empty `01` request; app requires >=16 reply bytes, strips NUL | `getSerial` `[243257,243735)` |
| Bind-state | Empty `02`; app treats any nonzero reply byte as bound | `[243735,244253)`; not identity authentication |
| Files | Empty `0a`; status0 + name14 + size4 + kind1; status1 fail; status2 end | `[238428,240494)`; require explicit end |
| Download / byte offset | `0b` payload name14 NUL-padded + offset u32 BE; status0 + full-size4, status1 fail, status2 end; bytes on e5e4 | `[240849,243257)`; [live offset17 suffix matches full file](download-offset.md); automatic persistent resume and per-block checksum remain absent |
| Stop transfer | Empty `0c`; immediate reply and possible worker-exit reply both00; first ACK is not a completion barrier | `[244253,244532)`; [actual CLI SIGINT trial](download-cancel-contract.md#actual-cli-sigint-validation-2026-10-13): exit130, exact4,416 B prefix; fresh full/offset exports equal independent baseline. No automatic resume, same-session reuse or worker-exit proof; sync batch cancellation remains host-tested |
| Delete one recording | `0d` + raw ASCII name, no padding; app accepts generic matching reply | `[240494,240849)`; [scratch-file real acceptance](file-deletion.md#owned-scratch-recording-real-cli-acceptance): new10256B recording downloaded twice identically, deleted, fresh list restored original7 entries. Listed absence only; no secure-erasure or reboot-persistence proof, no retry |
| Set time | `04`: local year-2000,month,day,hour,minute,second, each one byte | `[234663,235121)`; generic response, no readback established |
| Device events | `0f`: >=20 payload; charging0,battery1,USB-mode2,mode3,power-off4,noise5,voice6,indicator7,segment8,backlight9,USB-connected10 | `Y8` `[220352,220806)`; [client watch implemented](client-events.md), replay verified; earlier passive sample had zero events; later manual CALL switch captured mode3=`02` |
| Voice events | `19`: >=5; enabled byte0==1,size u32BE bytes1..4 | `Z8` `[220806,220992)`; app emits no public event; our client preserves it, live field semantics unverified |
| Realtime audio | Raw notifications on e5e3, forwarded as bytes | [Historical byte equality including pause/resume](realtime-live.md); historical CLI-only CALL labels are unreliable. [Physically confirmed NOTE/CALL short samples](note-call-audio-2026-10-13.md) both MP3/16kHz/mono/32kbps with realtime/full-download equality; app handler supplies no packet/codec decoder |
| Logs / fixed diagnostics / bounded code sample | Separate Actions e49a3001 service | [device-diagnostics.md](device-diagnostics.md), [mapped-code-readback.md](mapped-code-readback.md); does not establish whole-flash backup |

### Excluded from capability verification

Source declares `BIND=03` (17 bytes: user-id16 + delete-files byte),
`FORMAT_DEVICE=10` (empty), `RESET=12` (empty; **factory reset**, not reboot). Unbind reuses
`03` with zero user-id and optional delete flag. Factory reset/unbind deliberately do not
wait for response because device disconnects. These alter ownership/storage or
reset state; existence is documented, not justification to run them while
verifying read-only/ordinary control capabilities. No Boyi `0e` defined. No Boyi
upgrade opcode, firmware signer, complete backup, or restore CLI established.
Mova OTA declarations and UUIDs cannot be applied to Boyi.

`maintenance` now implements these explicit request encodings plus phone type.
All effects remain unverified; submitted requests exit3 with `ok=false`, not
effect-success0. Unbind/reset use one serialized write, invalidate and close the
session without ACK wait or reconnect. [Complete23-opcode coverage and goldens](remaining-client-contracts.md).

`DELETE_FILE=0d` is implemented with explicit confirmation and list readback.
[Owned-device acceptance](file-deletion.md) removed one newly created scratch
recording after two identical retained exports; a fresh complete list restored
the original7 entries. Matching ACK alone never qualifies as verified deletion.
List absence does not prove physical/secure erasure or restart persistence.

## Verification ledger

- **Verified on owned device, previous work:** discovery/status, file listing and
  recording export; previous recording controls/time evidence retained in repo.
  See [protocol.md](protocol.md) and [evidence index](evidence/README.md).
- **Settings with actual field roundtrips:** noise9→8→9, backlight00→01→00,
  segment03→01→03, USB on→off→on. Evidence below and
  [USB trial](usb-next-steps-2026-10-13.md). These prove selected reported values,
  not all values, physical effects or reboot persistence. Indicator/voice-control
  setters remain source-derived with no live mutation acceptance.
- **Mode and short-audio acceptance:** physical NOTE→info01, CALL→info02 plus
  event0f mode02; each mode has a6s MP3/16kHz/mono/32kbps sample whose realtime
  bytes equal its complete download. This does not establish microphone wiring,
  acoustic selectivity or long-recording reliability. Historical mode labels
  based only on the old CLI are not physical-mode evidence.
- **Firmware investigation verified separately:** Zephyr version shell output,
  NVRAM configuration read, two matching 16-byte code samples. Each has its own
  bounded evidence; none is a restorable official firmware image.
- **Unresolved:** complete physical Flash contents and physical-device confirmation,
  complete firmware readback,
  independent recovery path, official image acquisition, signing restrictions,
  exact board/SoC identity. A comprehensive device CLI helps collect evidence for
  these questions but does not itself settle them.

## Unified CLI live validation

The package implements the source-derived explicit setters with readback and rejects unavailable values. The2026-10-12 pass observed recording start/pause/resume/stop, recording-info, complete download/sync, and noise9→8→9 with matching state readback. Later backlight/segment/USB roundtrips are accounted for above. Clock synchronization has no known readback getter and was not live-tested. See [validation](evidence/cli-validation-2026-10-12.json) and [usage](cli.md).

### 2026-10-13: two more setters accepted on owned hardware

[Existing CLI roundtrip evidence](evidence/settings-roundtrip-2026-10-13.json),
FW010004: backlight00→01→00, segment03→01→03. Each of four setters changed
the reported field; each subsequent independent connection returned the expected
raw device-info byte42/41. All five info snapshots idle; final full info/settings
restored exactly, complete before/after recording lists identical at7 files.

Matching response payload00 is retained without assigning ACK semantics.
Acceptance is reported-field state, not physical screen effect, automatic timed
segmentation, persistence across reset or all possible values. Setters may trigger
internal configuration writes. No USB toggle, null indicator/voice setter,
recording, file deletion, reset or firmware-write request performed in this pass.
Raw local outputs remain ignored; public evidence omits the recording list.

## Later firmware research status

Complete owned-device mapped-system export now succeeds: 927632 B, validated header and body checksum; reproducible Ubuntu offline analysis. Actual ACPT contains18 NOR entries over4 MiB logical range. These replace the earlier partial-read status, not the raw-backup/recovery limitations. `diag capture printk-state` and `diag inspect-printk` verify console snapshots; two observations select the UART_0 DMA path. See [current roadmap](archive/firmware-roadmap.md) and [mapping boundary](mapping-candidate-audit.md).
