# Official CoMi Note 1.1 backend reference

2026-10-12. Read-only comparison: official deployment manual + pinned official
APK JS. No account login, authenticated API request, server execution or device I/O.
Package inspection remains pending. Parent retained page Markdown locally at
`artifacts/seeyon-backend-deployment-2930.md`.

## New useful lead

[Official CoMi Note（录音卡1.1）部署手册](https://open.seeyoncloud.com/v5doc/2366/2853/2930.html)
explicitly identifies the recorder backend used inside CoMi mobile and requires
CoMi 2.1.1+. Unlike the previously inspected
[older manual](https://open.seeyoncloud.com/v5doc/2366/2853/2862.html), this page
provides an [official installation-package directory](https://seeyon-install-packages.seeyoncloud.com/ProductInstall/comi-install/ai-V2.1.1-release_20260530/ComiNote/).
It names `CoMi-Note-Server-linux-arm64.zip` and
`CoMi-Note-Server-linux-x86_64.zip`, containing a Spring Boot executable JAR,
external YAML and launch scripts. Its illustrated directory includes bundled
JDK 25 Linux x64. ARM64 package contents require independent inspection; the
illustration alone does not establish its included runtime architecture.
[Source: deployment/package sections](https://open.seeyoncloud.com/v5doc/2366/2853/2930.html).

This makes exact controller routes, request/response DTOs, authentication checks,
storage keys, transcription jobs and callback handling accessible research
targets. These are prospective JAR-inspection targets, not findings from an
already inspected package.

Bounded acquisition attempt: HTTPS package-directory request failed on both
Mac curl/LibreSSL (`SSL_ERROR_SYSCALL`) and Ubuntu curl/OpenSSL; HTTP returned an
empty reply; localwebrs directory navigation timed out. No archive was acquired.
These transport failures establish neither authentication requirements nor
package absence, and do not justify guessing archive URLs beyond documented links.

## What the manual establishes

| Area | Explicit documentation | Client relevance |
|---|---|---|
| Routing | OA Nginx `/seeyon/comi-note/(.*)` rewritten to `/$1`; public HTTP 8905 (`COMI_PUBLIC_PORT`), internal 8907 (`COMI_INTERNAL_PORT`) | Deployment prefix and public/internal boundary; not an API route inventory |
| Auth | External authentication address among required base configuration; CoMi Note application authorization and intelligent-application binding in OA | Login depends on surrounding CoMi/OA integration; exact token contract not documented here |
| Public deployment | MySQL + Redis; TOS object storage; `COMI_TRANSCRIPTION_PROVIDER=tingwu`, `COMI_TINGWU_ENABLED=true`; Tingwu audio/video-file transcription | Independent client may reuse upload/transcription/summary workflow once server API is known |
| Completion | Tingwu project configured without callback; backend actively polls transcription results | Polling workflow exists in this deployment; poll endpoint/timing not given |
| Private deployment | Internal ASR service; `COMI_INTERNAL_IP_WHITELIST`, externally reachable storage base URL; recording LLM request URL | Different processing provider, not necessarily a different mobile API |
| Private ASR | Official image digest `89772399bd9ed074d6d96cb9fce3359a3fb353be60066a833eb2fdec534b64a0`; host 33112→container 22012 described as external transcription, 33115→22015 internal model service | Concrete component/version lead; no HTTP method/path/schema supplied |

All rows derive from the
[official deployment/configuration/ASR sections](https://open.seeyoncloud.com/v5doc/2366/2853/2930.html).
“Public deployment” describes the documented Tingwu/TOS arrangement. It does
not prove that the old APK's publicly reachable hostname serves this release.

## Comparison with pinned APK 1.1.2

Evidence: official [APK acquisition URL](https://www.seeyon.com//Public/Home/CoMi_release_1.1.2_2025-12-26.apk),
APK SHA-256 `b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118`;
ZIP member `assets/public/assets/index-Btih_BUR.js`, SHA-256
`167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c`.
Local extracted source `artifacts/apk112-final-check/device-index.js` rehashed
in this pass. Offsets below are zero-based bytes in that member.

| Evidence | Observed contract |
|---|---|
| Base URL at 156104 and 193627 | `https://doll.familyrobot.site/gpu03recordings/api/v1` |
| Axios interceptor after 193627 | Authenticated calls set `Authorization: Bearer TOKEN` and `X-UID: UID`; non-GET JSON content type unless opted out |
| `/zhiyuan/auth` at 195464; caller after facade | POST with `skipAuth:true`; caller supplies `uid`, `token`, `phone`; returned `uid`/`token` persisted |
| Response adapter before facade | JSON envelope `code`, `message`, `data`; success `code===0`; HTTP or envelope 401 clears auth and redirects |
| Native upload wrapper after 156104 | `/record/upload`; native `uploadFile`, `chunkedMode:false`, auth headers plus `deviceId` and `recordName` passed as headers. `formData` variable name does not establish multipart form fields |

Facade starts of all 20 literal Axios calls: 195464–197468. Upload is an additional
native-wrapper path. Exact declared routes:

- POST `/zhiyuan/auth`, `/device/bind`, `/device/unbind`;
  GET `/device/list`.
- Upload `/record/upload`; POST `/record/delete`, `/record/change-name`;
  GET `/record/list`, `/record/transcript/detail`.
- GET `/record/summary/status`, `/record/get-todos-and-summary`,
  `/record/summary/template/list`; POST `/record/summary`.
- POST `/record/change-speaker`, `/record/change-text`,
  `/record/change-all-text`, `/record/change-dir`.
- GET `/record/dir/list`; POST `/record/dir/create`, `/record/dir/delete`,
  `/record/dir/rename`.

These bytes are a reproducible older-client contract, not live server acceptance.
The manual exposes no concrete matching `/api/v1` routes, so compatibility with
the advertised 1.1 backend remains unverified. The old bundle can load remotely;
its relationship to the current mobile runtime remains bounded as described in
[official-acquisition-followup.md](official-acquisition-followup.md).

## Priorities and limits

1. Inspect exact advertised archive/JAR first: route mappings + DTOs + auth
   filter + upload implementation + async processing state machine. Compare the
   named routes above before creating a cloud CLI.
2. Determine whether package includes web assets/OpenAPI and whether backend
   configuration selects a compatible recorder page. Prefer those artifacts to
   protected Android runtime extraction for server-side questions.
3. Keep version namespaces distinct: manual's CoMi 2.1.1+, recorder-backend 1.1,
   mobile APK 1.1.2/1.2.4 and device firmware 1.0.4 are not interchangeable.
4. The inspected page supplies no board identity, firmware image, backup API,
   bootloader protocol or flashing/recovery procedure. Backend usefulness for
   independent clients is established; contribution to device firmware recovery
   still needs an actual artifact or implementation path.

No speculative API probes or deployment are needed to answer the first two
priorities. Older “no installation link” notes describe 2862 at its capture time;
they must not be generalized to the newly supplied 2930 page.
