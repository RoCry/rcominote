# Reproducible helper decompilation on Ubuntu

2026-10-12. Executed host tools against the **public SDK helper**, not CoMi's
firmware. No USB/BLE transport or target-code execution. This removes the local
native-decompiler availability gap for subsequent offline investigations.

## Setup and run

Linux x86_64, Bash, curl, sha256sum, tar and unzip required:

```sh
just re-setup
just helper-analyze \
  "$HOME/w/_tmp/lv_port_actions_technology/action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/adfus.bin" \
  artifacts/helper-ghidra-NEW
```

`tools/setup_re_tools.sh` downloads pinned official releases, verifies SHA-256,
extracts into `~/.cache/rcominote/re-tools` (override `RCOMINOTE_RE_TOOLS`). No
system Java/PATH change. `tools/analyze_helper.sh` rejects a different helper
hash and an existing output directory before analysis. Output includes a saved
Ghidra project, analysis log and selected decompiled functions.

| Tool | Pinned artifact SHA-256 |
|---|---|
| Ghidra12.1.4, `ghidra_12.1.4_PUBLIC_20260921.zip` | `ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db` |
| TemurinJDK21.0.12.1+1, `OpenJDK21U-jdk_x64_linux_hotspot_21.0.12.1_1.tar.gz` | `ce79869e1307ed8ee1e2baa86a412b1eb5b75d10a01006d788a6f968bcfaee94` |

Sources: [Ghidra release][ghidra], [JDK release][jdk], [Ghidra JDK21 requirement][requirements].
Release API asset digests and Ghidra release-body checksum agreed with downloaded
archives. Downloads total approximately778 MB before extraction.

## Import assumptions and observed verification

- Input SHA-256 `470827c527a7111cebeb74e60dd32c007390df34453bce519998963db3ad5953`,
  56,108 B. Fixed SDK commit and provenance in [helper report](helper-static-followup.md).
- Raw Binary loader, `ARM:LE:32:Cortex:default`, configured base `0x2ff70000`.
  `SeedHelper.java` sets Thumb context and seeds instruction-derived function
  entries; neither configuration nor language selection independently identifies
  CoMi's processor.
- Ubuntu actually compiled both Java scripts, imported/analyzed/saved the
  program, and exported all18 selected functions. Analysis reported success
  without timeout. Shell checks require a nonempty export, because headless
  process exit alone is insufficient script-result evidence.
- Wrong board-specific helper was rejected before creating output. Existing
  output was rejected without replacing analysis artifacts.

Original acceptance artifacts reside locally under `artifacts/helper-ghidra/`.
Inferred C types, function boundaries and indirect-call targets need instruction
and data-table corroboration. A successful decompile is not a proof that
initialization is read-only or that this helper is compatible with CoMi.

[ghidra]: https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build
[jdk]: https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.12.1%2B1
[requirements]: https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.1.4_build/GhidraDocs/GettingStarted.md#minimum-requirements
