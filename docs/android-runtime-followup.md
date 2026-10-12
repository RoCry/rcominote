# Android runtime follow-up — 2026-10-12

Scope: existing installed `com.seeyon.comi` on the connected, owned Android phone.
Read-only package/process/task/socket/log inspection; one temporary local ADB
forward, removed afterward. No app install/update, launch, login, device binding,
recording, deletion, firmware update, root, or permission change.

## Observed

| Question | Runtime evidence | Boundary |
|---|---|---|
| Installed app version | `1.2.4`, version code `10`, min SDK 21, target SDK 34; installer `com.heytap.market` | Package manager declaration; APK byte identity not acquired in this pass |
| Debuggable application | Package flags `[ HAS_CODE ALLOW_CLEAR_USER_DATA LARGE_HEAP ]`; `DEBUGGABLE` absent | Release flag does not determine WebView debugging by itself |
| Existing process | `pidof com.seeyon.comi` → `14564` | Already running; this investigation did not launch it |
| Existing app task | Task 237 has only `com.seeyon.comi/.launcher.ui.login.AccountLoginActivity`; sleeping, not visible, idle | Activity-manager state, not a screenshot or proof of all persisted authentication state |
| WebView inspection surface | `/proc/net/unix` exposes `@webview_devtools_remote_14564` | Socket presence alone does not prove a responsive debug endpoint |
| CDP discovery | Forwarded that exact socket to ephemeral localhost port 61907; `GET /json/list` received zero bytes and timed out after 5 seconds | No target, current page URL, script, or network request recovered |
| Scoped retained logs | REA `read_adb_logcat`, PID 14564, requested newest 500 lines → 0 lines / 0 bytes | Empty retained window; no conclusion about earlier requests or disabled logging |

REA package inspection Evidence:
`ev_c3f2afa24c8f3481c33ae386fb4192acb5281fe2c36f813c163f829c3ccd55a2`.
Scoped log Evidence:
`ev_caec44ce290337221bc46ee382dd0e98eae41958ed1fb8a8273eed662b5eeda7`.

REA `inspect_adb_window` returned no focus declarations; Evidence
`ev_fee3a9ff30281525a7975bf1d116b105cdfed41b41fa0b461b09feadbe471fca`.
This does not identify a foreground app. Direct task inspection supplies the
narrow CoMi activity observation above. REA browser discovery did not return
within the observation period and was cancelled; no successful REA browser
Evidence is claimed. The independent bounded HTTP request establishes the
endpoint timeout.

Ignored local records: `artifacts/android-runtime/{package.txt,activity.txt,unix-before.txt}`.
They contain host/device metadata and are intentionally not committed. Empty
`cdp-targets.json` is a failed request artifact, not a valid target listing.

## Blocker and next useful action

Owner response in this session: **暂时不登录**. Authenticated runtime research is
explicitly deferred; no further phone actions are part of this pass.

The observed CoMi task is at the account-login activity. An authenticated recorder
page and its upgrade workflow have not been observed. Login-dependent navigation
stopped here; no credentials were requested or submitted, and no alternative
activity/deep link was used to bypass the login flow.

To resume this route: owner opens CoMi normally, completes any required login,
and leaves its recorder page open. Then re-observe its current PID, exact WebView
socket, page target and page sources. A now-responsive endpoint can provide the
actual loaded URL/assets; observing a normal update-status page may reveal a
firmware metadata route without initiating an update. If the WebView socket
remains unresponsive, retain that as a separate transport blocker rather than
inferring absence of a firmware-update feature.

This pass proves neither a current recorder page URL nor firmware acquisition,
backup, update or recovery capability. The old bundled `noteweb` URL remains
static historical evidence; it has not been corroborated in app runtime.
