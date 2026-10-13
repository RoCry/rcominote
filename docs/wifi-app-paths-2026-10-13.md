# Wi-Fi app paths: shipped 1.1.2 scope and remote frontend boundary

2026-10-13. Host-only follow-up to [capability assessment](wifi-capability-2026-10-13.md).
No login, app execution, device commands, or remote fetch in this pass.
[Retained source evidence](evidence/wifi-app-paths-2026-10-13.json) includes member
hashes, AST ownership, bridge-source hashes and bounded source snippets.

**The shipped local frontend exposes no traced Boyi alternate transfer path.
Mova Wi-Fi methods have no named UI callers across all readable JS assets.
However, the recorder activity's shipped default configuration loads a remote
frontend; local assets cannot establish the current runtime's complete features.**

## Complete readable-asset scope, beyond main-bundle keyword counts

Pinned APK SHA-256:
`b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118`.
All 59 `assets/` members ending `.js/.json/.html` decoded as UTF-8: 6,632,401 bytes.
All 44 JavaScript members parsed with existing `@babel/parser` 8.0.4, zero parse
failures. AST traversal recorded method definitions, member references,
constructors, event strings and their enclosing class/function ownership.
Offsets are zero-based bytes in uncompressed members.

Main member `assets/public/assets/index-Btih_BUR.js` SHA-256:
`167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c`.

| Static route | Member byte offset | Meaning |
|---|---:|---|
| `xC.setWifiEnabled` / `xC.getWifiStatus` | 276340 / 276586 | Mova request implementations |
| `LC.setWifiEnabled` / `LC.getWifiStatus` | 279147 / 279213 | Recorder wrappers calling the request methods |
| Wrapper member references | 279180 / 279243 | Only named callers of those request methods in all 44 JS files |
| `NC.handleCommandNotification` / `getEventTypeForCommand` | 266040 / 266543 | Produce/map `wifi_info`; no matching event consumer found |
| `xw` recording hook calls selected recorder `downloadFile` | 348460 | Existing UI-facing device-file route |
| `eC.downloadFile` | 240849 | Boyi `GET_FILE_DATA`, offset and filename; receives `offline_data` chunks |
| Boyi connection service discovery/subscription | 223361–226463 | Chooses E5E control/write/command/realtime/offline characteristics |
| BLE transport wrapper | 215713 | `writeWithoutResponse`; subscription uses `startNotifications` |

No named call reaches `LC`'s Wi-Fi controls from a UI hook or lazy chunk. No
`wifi_info` consumer or SSID/password/IP-to-socket chain was established. This is
static named-call coverage, not a guarantee against reflection, computed access,
or different remotely delivered code.

The sole `new WebSocket` AST node is in
`assets/h5/vendors/@wangeditor/editor@5.1.23/index.js` at byte 658761, inside
`UppySocket.open`, using `this.opts.target`. Its consumer `XHRUpload.uploadRemote`
constructs a companion socket at byte 684572 with `${host}/api/${token}`. These
are editor upload machinery; no reference connects them to Boyi/Mova recorders.
Do not count a bundled editor's WebSocket implementation as recorder Wi-Fi.

An additional literal search over all 59 text members found no `hotspot`, word
`ssid`, `rfcomm`, word `spp`, `BluetoothSerial`, `BluetoothClassic`, `WifiManager`,
`WifiNetworkSpecifier`, `192.168.`, `ws://`, `wss://`, `createConnection`, or
`net.connect`. Exact regex and inventory are retained. These negatives support
the traced local route only; they do not establish hardware absence.

## Native recorder bridge and alternative transport boundary

`assets/capacitor.plugins.json` lists BluetoothLe, FileTransfer, Filesystem,
Keyboard, Preferences and StatusBar. `ApNoteActivity.onCreate` additionally
registers `ApNoteSDK` before calling its superclass.

- `ApNoteSDKPlugin` exposes `getLaunchParams`, `closeApp`, `syncTodos`, and
  `syncSummary`; source contains no socket or radio transport implementation.
- BluetoothLe `Device.connect` calls Android `connectGatt(...,2,...)` at line 352;
  writes call GATT `writeCharacteristic` at lines 564/573; notifications use
  `setCharacteristicNotification` at line 600. This closes the local JS BLE
  wrapper into an Android GATT implementation.
- FileTransfer `downloadFile` consumes caller `url`/`path` and constructs HTTP GET
  options (lines 223–246); `uploadFile` constructs HTTP POST options (357–390).
  That generic HTTP capability does not supply a recorder endpoint or activation
  command. The shipped recording download route traced above uses BLE; cloud
  upload is a separate [previously established path](seeyon-backend-reference.md).

Focused decompiled packages `com/seeyon`, `com/webnote`, `com/capacitorjs`,
`com/getcapacitor` contain no `BluetoothSocket`, `createRfcomm`, `WifiManager`,
`WifiNetwork`, `new Socket(`, `ServerSocket`, `SocketChannel`, `DatagramSocket`, or
`new WebSocket` hits. Whole JADX source tree also had no classic RFCOMM API hits.
This is bounded source-text evidence, with existing JADX decompilation failures;
it does not exclude opaque native libraries, lost methods, or new app versions.
The outer CoMi application has other generic WebView bridges; they were located,
but no complete audit of every reflected platform plugin was performed here.

## Shipped default path targets remote frontend

Original `assets/capacitor.config.json` explicitly contains:

```json
{"server":{"url":"https://doll.familyrobot.site/noteweb/","androidScheme":"https","cleartext":false}}
```

This is more than an unused URL string. Existing JADX source traces the default
recorder activity path:

1. `ApNoteActivity.onCreate`, lines 19–24: register `ApNoteSDK`, call
   `super.onCreate`; no config/server-path override in this class.
2. `BridgeActivity.load`, lines 38–42: builder receives `this.config`, a field
   with no initializer or recorder-subclass assignment in the inspected code.
3. `Bridge` constructor, lines 153–154: null config invokes
   `CapConfig.loadDefault(activity)`.
4. `CapConfig.loadDefault`, lines 92–101: reads asset configuration; lines
   167–178 name `capacitor.config.json`; line 201 parses `server.url`.
5. `Bridge.initWebView`, lines 428–442: configured URL becomes `localUrl` and
   `appUrl`; `loadWebView`, line 238, loads `appUrl`.

No `setConfig`, `setServerPath`, `setServerBasePath`, `setServerAssetPath`, or
`setServerUrl` recorder override was found under `com/webnote`; unrelated CoMi
configuration methods are not Capacitor overrides. Bridge supports persisted
WebView server-base paths (lines 215–216) and explicit `serverPath` (227–236),
which limit claims about a particular installed instance. Runtime startup,
cached state, authentication redirects and delivered JS were not observed.

Thus the correct negative is “no local shipped caller/path traced”, not “CoMi
runtime cannot support Wi-Fi”. Current remote availability/acquisition belongs
to the parent's separate transport follow-up; no local call graph can replace
that missing frontend evidence. 1.2.4 hardened runtime remains outside this pass.

## Result for next investigation

No justified Boyi Wi-Fi/classic-SPP command or fast file endpoint follows from
the inspected APK. The useful new route is acquiring the configured recorder
frontend or a matching deployed bundle, then inspecting its device selection and
transfer activation. Until then, preserve the actual firmware's
`record_wifi_ota_view.c` lead separately: an OTA view is not evidence that this
App exports recording files through Wi-Fi.

## 1.2.4 entry follow-up and acquisition stop

The retained1.2.4 APK was rehashed to the already pinned
`8aade0a4ca1f9e25b9ebbd51dee97702bf0954e5a66adcf91312b4331414ace7`.
[Candidate asset inventory](evidence/wifi-app124-entry-2026-10-13.json)
records readable text/config member hashes and the exact literal-search scope.
No member name contains `capacitor`; no matching recorder frontend URL or
Wi-Fi entry was recovered. Matches are `serverUrl` in two copies of the
wangEditor bundle. This does not inspect protected application logic and does
not establish that1.2.4 removed recorder functionality or uses the old URL.

Reconciliation with [prior acquisition](official-acquisition-next.md): the old
remote URL's HTTP500 was already known on2026-10-12; the2026-10-13 fetch is a
reconfirmation, not a newly discovered route. Stop re-fetching it or repeating
the same asset searches without a changed endpoint/package.

The unresolved input is a matching deployed frontend/runtime observation or
direct hardware/official-model Wi-Fi evidence. The owner deferred App login;
the last current ADB inventory has no phone attached. Preserve those boundaries
rather than bypassing login, installing unrelated clients, or guessing radio
commands. Existing evidence does not justify a working CoMi Wi-Fi CLI claim.
