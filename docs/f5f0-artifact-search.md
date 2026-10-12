# F5F0: bounded app-artifact search

2026-10-12. Host-only byte/text reads; no device commands, app execution,
login, remote requests, decryption, or new decompiler run.

## Result

**No handler or UUID reference for CoMi's observed F5F0/F5F1/F5F2 service
recovered from the inspected app artifacts.** This closes a cheap literal-search
avenue; it does not identify the service or establish absence of implementation.
The [captured GATT](evidence/gatt-2026-10-12.json) remains the direct evidence
that the owned device exposes these UUIDs. Write/notify properties alone do not
establish a protocol, identity request, firmware reader, or OTA behavior.

## Exact CoMi samples

| Input | Identity | Search and result |
|---|---|---|
| CoMi 1.1.2 packaged device JS | `assets/public/assets/index-Btih_BUR.js`; 588,988 B; SHA-256 `167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c` | Existing `artifacts/apk112-final-check/device-index.js` hash reverified; no case-insensitive `f5f0`, `f5f1`, `f5f2`, full UUID, `0xf5f0/1/2`, or decimal `62960/1/2` reference found |
| CoMi 1.2.4 APK | 85,750,588 B; SHA-256 `8aade0a4ca1f9e25b9ebbd51dee97702bf0954e5a66adcf91312b4331414ace7` | All 2,165 ZIP file entries read independently by entry object: 109,610,198 decompressed B; zero complete F5F0/F5F1/F5F2 UUID matches in the encodings below |
| CoMi 1.2.4 existing ordinary JADX output | `artifacts/jadx124/sources`; six `.java` files; 656,014 B | No complete UUID, quoted short UUID, hex integer `0xf5f0/1/2`, or decimal `62960/1/2` match |

Full UUIDs searched:

```text
0000f5f0-0000-1000-8000-00805f9b34fb
0000f5f1-0000-1000-8000-00805f9b34fb
0000f5f2-0000-1000-8000-00805f9b34fb
```

For each UUID, searched full lowercase/uppercase text encoded as ASCII,
UTF-16LE and UTF-16BE; also 16 raw UUID bytes in displayed order and all-byte
reverse order. Offsets would refer to decompressed member bytes. ZIP-member
reads avoid the known case-colliding resource filenames; no directory extraction
was used for this new APK search. The APK's signing block, ZIP comment and bytes
outside ZIP member contents were not searched.

The six Java files expose the protected loading shell, resources and debug
probes, not the original loaded application. See
[official acquisition follow-up](official-acquisition-followup.md). The older
packaged JS declares Boyi E5E0 and Mova 6E400001 families, but literal absence of
F5F0 cannot cover numeric construction, native code, downloaded JS or a newer
runtime. The packaged page's configured remote destination further limits its
coverage of current device behavior.

## Related OEM artifacts

Used retained analyses described and pinned in [OEM protocol lead](oem-protocol-lead.md):

| APK | APK SHA-256 | Existing text searched |
|---|---|---|
| AI DVR Link 3.2.0 | `bba153b4da1db7e1be9f239b3e93eb5b255af9b1d30528198aec5cb9a950e7bd` | `artifacts/oem-ai-dvr-link-blutter`: 3,224 `.dart/.txt/.java/.js` files, 325,339,027 B; excluded `ida_script` |
| Umevo 1.2.5 | `7d9d4a71c274ed8a7420d1aa4440711b592ab935ec5dbba49f0fa310e9c4eb06` | `artifacts/oem-umevo-blutter`: 1,562 files under same selection, 146,192,779 B |

Neither tree contained a complete F5F0/F5F1/F5F2 UUID or exactly quoted short
UUID. Neither `pp.txt` contained a `String:` value including `f5f0/1/2`.
Unrestricted substring searches did produce hexadecimal instruction/object-pool
addresses such as `[pp+0xf5f0]`; inspecting the associated values established
that these are addresses, not service UUID strings. They are not positive
protocol evidence.

These are recovered text searches, not proof that every encoded constant or
native implementation in either APK was analyzed. Existing Blutter analyses
have documented unrelated errors and incomplete coverage. Neither related app
is established as compatible with CoMi; its OTA flow cannot specify F5F0.

## Reproduction and next discriminating evidence

With retained outputs, the quick literal portion is reproducible by:

```bash
rg -ni 'f5f0|f5f1|f5f2|0xf5f[012]\b|6296[012]\b' \
  artifacts/jadx124/sources artifacts/apk112-final-check/device-index.js
rg -ni 'String:.*f5f[012]' \
  artifacts/oem-ai-dvr-link-blutter/pp.txt artifacts/oem-umevo-blutter/pp.txt
```

Both commands returned no matches. The full APK search used stdlib `ZipFile`:
verify exact APK SHA-256, iterate `infolist()`, skip directories, `read(entry)`,
search each of the explicit encoded UUID patterns with `bytes.find`. The
working script/output are ignored local artifacts; the byte selection and
encodings above define this bounded result independently of a decompiler.

Useful next evidence: a matching UUID initializer and incoming handler in
actual CoMi device code, an unprotected compatible app artifact, or relevant
assets from an authorized loaded app session. Current negatives do not justify
writing the public SDK vendor-upload handshake to F5F0. The
[SDK vendor-service audit](vendor-service-followup.md) independently found a
different UUID family and state-changing upload/OTA behavior.
