# Remaining Boyi client contracts

2026-10-13. Host-only, fixed official CoMi1.1.2 source; no bind, unbind, format,
factory reset or phone-type command executed. These are client-coverage gaps,
not new platform, backup or recovery evidence.

**All five remaining actions have sufficient request evidence for explicit host
interfaces. Their effects remain unverified.** Implement them together with
honest completion reports; do not leave known wire operations unavailable merely
because hardware validation is intentionally deferred. No generic command
escape hatch, account login or automatic device mutation follows from this scope.

## Fixed source

APK SHA-256:
`b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118`.
Member `assets/public/assets/index-Btih_BUR.js`:588988 bytes, SHA-256
`167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c`;
rehash matched before this audit. [Source acquisition](cli-capabilities.md#source-identity-and-reproduction),
[extractor](../tools/apk_evidence.py). Ranges are zero-based bytes, end exclusive.

| Range | Source | SHA-256 |
|---|---|---|
| `[233642,234663)` | bind and unbind | `ff1dfdd6c7fe5ca3cc5e914cbdbaa1ce0197b3e15b67b662393ea69c72a3c055` |
| `[243257,244253)` | serial and bind-info getters | `e4622b852a47d8ca96b090036db074f0944333e9c16953baf7b384f94946b958` |
| `[244532,244817)` | format | `8fffcd5ce0d0ae66dfd49e9d8607e6e1e04a68312b7ab61f4cdc6e38825ed129` |
| `[245156,245599)` | factory reset | `9b74b3be63d4b9b8712d641ec79964c747cb893a3d389ed3e607e8b58ff2bd45` |
| `[247787,248131)` | phone type | `18bc152bd027cb58ac4038908b995ec769b090b436ce6f0211fefea429c9d829` |

Common `sendCommand` `[232509,233642)` SHA-256
`3c4308c099f839bd1328f00438c3edd13a689ea13f11739212d6862f62fee177`:
register matching-opcode callback, then write; default5000ms timeout; resolve
generic success on first matching response without interpreting result bytes.
Write error or timeout is an app error. This is the same
[response/effect distinction used for deletion](file-deletion.md).

## Remaining operations

| Action | Exact official encoding | App completion | What is not established |
|---|---|---|---|
| Bind |03;17 bytes: first16 user-ID character codes, NUL-pad short IDs, truncate long IDs; final byte00 | `sendCommand`,5000ms; no payload-status validation | Accepted ID domain, server/account association, authenticated ownership, persistence |
| Unbind |03;16 zero bytes + final00 keep files /01 delete files; default keep | Direct write, no response wait; comment expects device disconnect | Unbind or deletion completion; disconnect is not an ACK or reset proof |
| Format |10;empty | `sendCommand`,explicit10000ms; no payload-status validation | Exact formatted objects, successful formatter completion, secure erasure, effect on configuration |
| Factory reset |12;empty | Direct write, no response wait; comment expects disconnect | Reset completion, precise settings/data scope, independent hardware escape |
| Phone type |18;one byte assigned from argument; log labels0 Android, every other value iOS | `sendCommand`,5000ms; no payload-status validation | Accepted nonzero domain, physical effect, persistence, readback field |

Factory reset is explicitly named“恢复出厂设置” by the official method. Never
present it as ordinary reboot, or reuse it to justify ROM-entry escape.

`getBindInfo` requests02 with no payload; app removes NULs from reply text and
tests whether any byte is nonzero. It imposes no fixed user-ID reply length or
identity-comparison contract. Raw before/after reply and the nonzero predicate
may be reported; they do not prove binding to a particular cloud account. A
readback failure after a bind request leaves effect unknown; do not resend03.

The phone-type source has no range validation. A search of this complete fixed
member's `setPhoneType(` references found the method and forwarding wrappers,
not a concrete UI caller establishing a narrower enum. A CLI restricted to
`android=0` / `ios=1` is a conservative host domain, with1 chosen from the
source's nonzero branch; it is not evidence that firmware rejects2..255. Never
derive this setting automatically from the host OS or send it during connection.

## Independent golden requests

Generated in Bun from only official pure `Bt` `[216249,217090)` and constants /
`ry` / `ho` `[217643,219336)`, as in [deletion oracle](file-deletion.md#primary-source-and-independent-request-oracle).
No project frame/CRC code used. These establish encoding, not device acceptance.

| Input | Complete request hex |
|---|---|
| Bind ASCII `0123456789abcdef`, keep files | `d22d0103113031323334353637383961626364656600d2df` |
| Unbind, keep files | `d22d0103110000000000000000000000000000000000a95b` |
| Unbind, delete files | `d22d0103110000000000000000000000000000000001689b` |
| Format | `d22d011000ed7e` |
| Factory reset | `d22d011200ec1e` |
| Phone Android0 | `d22d011801003e1f` |
| Phone iOS candidate1 | `d22d01180101ffdf` |

## Whole request surface

Official `ue.CMD` defines25 opcode entries: **23 request opcodes**, plus device
event0f and voice event19. The request class has24 operation methods because
bind and unbind both use03; `sendCommand` is infrastructure, not another device
capability. This counts the fixed app's Boyi surface, not all hidden firmware
commands or the unrelated Mova protocol.

| Request opcode | Official operation | Existing CLI coverage at start of this pass |
|---|---|---|
|01|serial|info / identity reads|
|02|bind info|info / bound state|
|03|bind, unbind|missing; two explicit actions|
|04|sync time|set-time|
|05|device status|info / settings show|
|06|start recording|record start; realtime owned capture|
|07|stop recording|record stop; realtime cleanup|
|08|pause recording|record pause|
|09|resume recording|record resume|
|0a|file list|files / download / sync|
|0b|file data|download / sync, explicit byte offset|
|0c|stop file transfer|download/sync explicit cancellation after accepted bytes; bounded stop then disconnect|
|0d|delete file|delete with identity/name confirmation and complete-list readback|
|10|format|missing|
|11|indicator|settings set indicator|
|12|factory reset|missing|
|13|USB support|settings set usb|
|14|voice control|settings set voice|
|15|recording info|recording-info|
|16|segment duration|settings set segment|
|17|noise reduction|settings set noise|
|18|phone type|missing|
|1a|screen always-on|settings set backlight|

Thus19 request opcodes already have a host path; completing03/10/12/18 adds
**four** opcodes and **five** actions.0c is intentionally tied to the owned
download-cancellation lifecycle, rather than exposed as an unsolicited stop
that could affect a worker of unknown provenance. Events0f/19 and realtimee5e3
are covered separately by watch/realtime; they do not increase the request count.

## One bounded implementation slice

- Explicit management operations; required serial checked against connected
  device before mutation, operation-specific confirmation, observed idle state.
  These are host safeguards, not atomic ownership or authentication.
- Bind: nonempty printable ASCII ID up to16 bytes; reject excess/Unicode/NUL
  rather than mimic destructive truncation. Reserve all-zero03 for unbind.
- Unbind defaults to keep files. The delete flag requires separate explicit
  deletion confirmation; never derive it from a generic force/yes option.
- Return factual stages: write attempted/completed, matching response received
  and raw bytes where applicable, optional readbacks, `effect_verified=false`.
  `ok` or process success, if used, must explicitly scope to request delivery,
  never ownership change, format or reset completion.
- Unbind/reset use a dedicated serialized write-only path, then close the
  session. Do not fake an ACK wait, reinterpret disconnect as success, auto
  reconnect or retry. A write exception/disconnect may occur after device
  acceptance: record unknown outcome, not“nothing happened.”
- Format and phone-type wait only for their matching responses under the app's
  deadlines. Empty post-format list or changed free capacity may be observations,
  never proof that formatting completed or all content was erased.
- Preserve cancellation before mutation; after a write attempt, report unknown
  outcome and disconnect. Buffered replies require explicit cancellation
  checkpoints; the deletion regression supplies an existing failure oracle.

Host tests can verify independent golden frames, required confirmation before
BLE, device identity mismatch, one-send behavior, timeouts/late replies and
write-only disconnect/cancellation. No hardware acceptance is claimed by these
tests. Keep live effect verification, cloud identity proof, reliable resume,
full firmware backup, safe flashing and independent physical reset unresolved.

### Selected CLI and result contract

`comi maintenance {bind USER_ID, unbind, format, factory-reset, phone-type android|ios}`.
All actions require explicit serial. Bind/unbind/format/factory-reset additionally
require `--confirm ACTION`. Unbind keeps recordings by default; deleting them
requires both `--delete-recordings` and `--confirm-delete-all SERIAL` matching
the selected serial. Phone type is explicit, never a connection side effect.

Bind input:1..16 ASCII bytes in20..7e, padded on the right to16 with00, followed
by byte00. Control characters, NUL, Unicode and oversized IDs reject before BLE.
This preserves the source's short-ID encoding without silent truncation; valid
vendor/cloud IDs remain unknown.

| Outcome | Report | Exit |
|---|---|---:|
| Matching response received for bind/format/phone, or write completed for unbind/reset | `status=submitted_unverified`, `ok=false`, `device_effect_verified=false`; raw reply only where applicable |3|
| Request/response failure, timeout or indeterminate disconnect | `status=unknown`, effect unverified; no automatic retry |1|
| Cancellation after mutation attempt | `status=unknown`, effect unverified; disconnect, no retry |130|

These commands have no effect-success exit0. Validation/identity/state failure
before mutation must state that nothing was submitted. The write-only path
serializes one write and permanently invalidates that session; CLI closes it
without reconnecting. A finite write-only timeout, if added, is host policy:
the official source supplies no explicit deadline for these direct writes.

### Host implementation verification

[Management group](../src/rcominote/maintenance.py) now implements all five
actions, using [Connection.send_only](../src/rcominote/connection.py) for the two
write-only operations. Write-only5s deadline is explicit host policy. The
coverage table above records the pre-implementation baseline; all23 fixed-app
request opcodes now have a host path, with0c constrained to owned cancellation.

[Real-Connection tests](../tests/test_maintenance.py):9 tests plus25 subtests
passed. Seven request goldens match; arbitrary matching reply payload `ff7e`
does not promote effects to verified. Tests also cover pre-BLE validation,
identity/idle rejection, write/ACK failure with late responses, permanent
write-only session retirement, bounded stuck writes, real SIGINT with buffered
ACK and disconnect failure preserving already observed reply bytes. Reply
fixtures `d22d010302ff7ea9e4`, `d22d011002ff7ead60` and
`d22d011802ff7eaf00` came from the same independent official JS framing oracle;
they are synthetic failure-boundary inputs, not live management replies.

No management action was run on the device. Host request coverage is complete
for this pinned Boyi table; device effects and the original firmware goals remain
separate, unresolved acceptance boundaries.
