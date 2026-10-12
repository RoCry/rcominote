# Official acquisition follow-up

2026-10-12. Host-only: official pages, exact retained APK assets, existing ordinary
JADX output. No app execution, account login, API mutation, hardware access, or
guessed download/API paths. No usable recorder firmware acquired in this pass.

## New decisive boundary: recorder web UI can be remote

Exact [1.1.2 official APK](https://www.seeyon.com//Public/Home/CoMi_release_1.1.2_2025-12-26.apk),
SHA-256 `b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118`:

| ZIP member | Bytes | SHA-256 |
|---|---:|---|
| `assets/capacitor.config.json` | 686 | `18aefbea93c9108967e0124e4fb39ee807cc83bd13c9a16d12f1d70cc76c00b9` |
| `assets/public/assets/index-Btih_BUR.js` | 588,988 | `167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c` |

Configuration declares `server.url = https://doll.familyrobot.site/noteweb/`,
`appId = com.webnote.ap`, HTTPS, and mixed content disabled. Existing decompiled
`com.getcapacitor.Bridge` applies configured server URL to `appUrl` and calls
`webView.loadUrl(appUrl)` in its ordinary loading path. Alternative persisted
server paths also exist. `ApNoteActivity` extends `BridgeActivity`, registers the
SDK plugin, and does not establish a different entry URL in its inspected code.

**Inference:** APK-bundled JS is a reproducible protocol artifact, but cannot
establish what recorder UI the current app actually serves. Remote deployment,
cached resources, and native configuration need runtime evidence. No execution
or request from the real app was observed.

One unauthenticated GET to the **exact declared** `/noteweb/` URL returned HTTP
500 (`curl --fail --location --max-time 25`, exit 22). No live HTML/JS was
recovered. This result does not establish permanent outage, the URL actually
used by newer releases, or whether app headers/authentication change behavior.
No sibling assets or speculative upgrade APIs were requested.

## Packaged routes and backend surface

Offsets: zero-based bytes in the decompressed main JS member above. This pass
followed concrete API calls and route construction rather than repeating a
whole-package firmware keyword scan.

| Evidence | Byte positions | Observation |
|---|---|---|
| API facade `st` | 195,464–197,468, starts of 20 literal `at.get/post` calls | Auth; bind/unbind/list devices; record list/delete/rename/transcript/summary/speaker/text/directory operations |
| Upload implementation | same facade, between device list and record delete | `/record/upload` through native file-transfer wrapper |
| Route definitions | 404,066–404,927 | `*`, `/`, auth, files/record detail, recording, device/connect, device/info/:deviceId, time, unbind |

The facade's seven GET and thirteen POST call sites contain no firmware
manifest/download/upgrade operation. Route construction contains no upgrade
page. This is bounded to these explicit implementations; native code, remote
bundles, indirect calls, and newer versions remain outside the conclusion.
The backend URL declared in this JS was **not requested**.

## Official deployment package is server software

New primary source: [CoMi Note deployment manual](https://open.seeyoncloud.com/v5doc/2366/2853/2862.html).
It identifies `comi-note-1.0.zip`, extracted directory
`comi-note-backend-release`, a Spring Boot JAR, Linux x64 JDK 25, database/cache
configuration, and HTTP service ports. Those contents describe the recording
backend, not a device-flash image. Its acquisition heading provides no package
link in fetched HTML; no archive URL was guessed from the filename.

The manual's requirement “CoMi 2.1.0+” concerns its stated backend deployment
context; do not equate that number with recorder firmware 1.0.4 or mobile APK
1.2.4. It supplies no recorder board, bootloader, flash layout, recovery image,
or flashing procedure in the inspected page.

[Official App Store history](https://apps.apple.com/cn/app/comi/id6745251551)
lists added recorder capabilities in mobile release 1.2.0, and authentication /
speech / feedback changes in 1.2.4. These notes do not identify a recorder
firmware upgrade or recovery package. The website download page continues to
link Android 1.1.2; it is not evidence of the newest mobile release.

Raw HTML retained locally, outside Git:

| Page | Bytes | SHA-256 |
|---|---:|---|
| `https://www.seeyon.com/CoMiNote/download.html` | 215,983 | `0edaa7eab2aef7b591c75b4ee9dec1e15757217530a0218c8d27950a256bd2d8` |
| deployment manual above | 77,279 | `b3a590b244e11b5d73e36f7f2318951f3fae2b1ad9198ca41f8acbff57a2c095` |

Bounded discovery queries: `site:seeyon.com "CoMi" "固件"`, `"CoMi Note" "升级"`,
`"CoMi Note" "固件" -site:seeyon.com`, and
`site:open.seeyoncloud.com "录音卡" "固件"`. Results yielded the deployment manual,
marketing/investor material, and unrelated site copies; no recorder image URL
was identified. Search indexing cannot prove absence of an official package.

## Newer Android package: decompiler alone does not expose app logic

Main investigator ran existing ordinary JADX 1.5.6 against the exact pinned
1.2.4 APK; output `artifacts/jadx124`, exit 0. Six generated Java files comprise
the application resources, four `s.h.e.l.l` shell classes, and Kotlin debug
probes. This is separate from REA, whose Android provider remains unconfigured.

Inspected decompiled shell paths: `S.attachBaseContext` calls `N.l` with package
`com.seeyon.comi` then `N.r` with original application class
`com.seeyon.comi.launcher.ComiApplication`; `S.onCreate` calls `N.ra` with that
class. `N` loads `libexec.so`/related native libraries and declares native
classloader entry `al`. These establish a protected native-loading path,
**not** successful recovery of its loaded code or evidence of any firmware UI.
No native library was executed. Merely configuring REA's JADX provider would
not turn this shell output into decrypted application logic.

## Next artifact that would change the answer

1. Actual current recorder page assets and request metadata from an authorized
   app session, including its resolved URL/version; capture only relevant
   firmware/manifest responses if such a UI exists. A site GET failure is not
   a substitute for that evidence.
2. Vendor-supplied device update/recovery package and matched flashing tool,
   explicitly identifying the owned hardware revision; verify package digest,
   partition coverage, signing policy and preservation of unique configuration.
3. If newer protected Android behavior is essential, obtain its loaded runtime
   code or an unprotected vendor build. Static shell classes alone cannot answer
   whether recorder upgrade support was added after the older packaged JS.

No evidence here changes the requirement to establish independent recovery
before flashing a custom image.
