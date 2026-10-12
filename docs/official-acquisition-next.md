# Official acquisition: live recheck

2026-10-12, 03:40–03:42 UTC. Host-only GETs and retained source reads. No app
execution, account login, hardware access, or state-changing API request.

## Current public paths

| Exact source | Current observation | Consequence |
|---|---|---|
| [APK-declared recorder page](https://doll.familyrobot.site/noteweb/) | HTTP 500, 186-byte nginx error page; direct curl and localwebrs agree | No HTML application or linked live JS recovered |
| [Official download page](https://www.seeyon.com/CoMiNote/download.html) | HTTP 200, 215,983 bytes; SHA-256 unchanged from prior capture | Still links the exact Android 1.1.2 APK and same App Store id |
| [Download-page JS](https://www.seeyon.com/Public/Home/zhuanqu/yhdh2025/js/bundle.js?v=2) | HTTP 200, 18,975 bytes | Download-page asset acquired; literal search for `CoMi`, `apk`, `firmware`, `noteweb`, `https`, `升级` found no matches |
| [App Store](https://apps.apple.com/cn/app/comi/id6745251551) | Version 1.2.4, September 7; recorder capabilities mentioned in 1.2.0 history | Release history supplies no identified recorder update/recovery package |
| [Official recorder deployment manual](https://open.seeyoncloud.com/v5doc/2366/2853/2862.html) | Still describes Spring Boot backend and JDK 25; package acquisition heading has no link | `comi-note-1.0.zip` remains server software, not an acquired device image |

Official download-page anchors, lines 4781–4782 of retained raw HTML:

- `https://apps.apple.com/cn/app/comi/id6745251551`
- `https://www.seeyon.com//Public/Home/CoMi_release_1.1.2_2025-12-26.apk`

No newer Android URL, recorder firmware URL, recovery utility, or matching board
information established by these linked sources. Search queries `"CoMi"
"录音卡" "固件"` and `"CoMi Note" "升级" "固件"` yielded no independent
artifact lead; the latter returned this research repository. Search indexing is
not proof of absence.

## Retained evidence and reproducibility

Ignored local artifacts; only methods and digests committed:

| Artifact | SHA-256 |
|---|---|
| `artifacts/noteweb-next.html` | `d3af065b1a979140769859a3464a3dc0f167dee16085068f13a63e12b1e6ab0d` |
| `artifacts/comi-download-next.html` | `0edaa7eab2aef7b591c75b4ee9dec1e15757217530a0218c8d27950a256bd2d8` |
| `artifacts/comi-download-bundle-next.js` | `7a5cebcb1cd6a08cf1213d44ccb437c42a517084cd7bd590e06d520781c970cd` |

`artifacts/noteweb-next.headers` records `Date: Mon, 12 Oct 2026 03:40:36 GMT`,
HTTP 500, nginx/1.18.0 (Ubuntu), Content-Length 186. Public HTML capture headers
are in `artifacts/comi-download-next.headers`.

```sh
localwebrs visit 'https://doll.familyrobot.site/noteweb/'
curl --location --max-time 25 --silent --show-error \
  --dump-header /tmp/comi-noteweb.headers --output /tmp/comi-noteweb.html \
  --write-out '%{http_code} %{size_download} %{url_effective}\n' \
  'https://doll.familyrobot.site/noteweb/'
```

The retained 1.1.2 APK was rehashed and matches
`b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118`.
A bounded literal search of its already-generated `com.seeyon.comi`,
`com.webnote`, and `com.capacitorjs` Java source trees for `firmware`, whole-word
`ota`, `adfu`, `25f8`, and `固件` found no matches. This source search cannot
exclude indirect, encoded, remote, or newer protected implementations.

## What would unlock this route

1. An authorized current app session exposing the actual recorder page URL,
   resolved assets, and any firmware-check response. Anonymous HTTP 500 does
   not show the URL/header/authentication state of a real newer app session.
2. A vendor-supplied recovery/update package matched to the owned recorder,
   including loader/tool and board revision. No public package was found here.

This recheck closes the currently visible anonymous web route; it does not
establish permanent outage or absence of vendor firmware. Earlier static
package scope and protected 1.2.4 limitation remain in
[official-acquisition-followup.md](official-acquisition-followup.md).
