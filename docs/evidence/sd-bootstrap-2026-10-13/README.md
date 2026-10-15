# Fixed RAM / mapped XIP → SD → Boyi receipts

Public summary: [`../sd-bootstrap-2026-10-13.json`](../sd-bootstrap-2026-10-13.json). Source report hashes pinned; private recording-file lists removed. Only generated non-audio test names/paths remain. No full reports, btsnoop, or monitor dumps published.

| Experiment | Result |
|---|---|
| RAM4096 creation | Actions4 confirmed writes/4 ACK/F1, empty pending; subsequent Boyi download failed3852/4096. Partial bytes not retained. |
| RAM suffix | Independent read-only offset3968/128B from same test file matched oracle; parent receipt bound. |
| XIP header attempt A | Preflight LE ATT connect errno38; no Actions/SD write or before/after observation. |
| XIP header B/C | Two independent32B test files downloaded completely and matched mapped image header. |
| XIP handler creation | Actions4 confirmed writes/4 ACK/F1, empty pending; subsequent download connection errno38. |
| Handler read attempt A | Parent-bound download-only preflight errno38; no new Actions/SD write or before/after observation. |
| Handler read B | Parent-bound read-only160B download completed and matched mapped image handler. |

All six experiments with before/after observations have identical complete device-info JSON, including52-byte raw info and idle recording state. Preflight failures have no such observation; do not infer an identity check from missing fields. Four file-creation Actions sessions each contain only PREPARE, START, the fixed `dbg dumpbuf` command, STOP; five ATT Write Responses include CCCD enable. Read-only suffix/handler downloads do not execute Actions.

## Retained successful raw downloads

| File | Bytes | Source / independent oracle | SHA256 |
|---|---:|---|---|
| `header-b32.bin` | 32 | mapped0x10000000, system image offset0 | `2337540c74a6aa8984eb481c2fea27a80d12cfd4c24c5300db820f86a733f486` |
| `header-c32.bin` | 32 | independent file, same mapped header | `2337540c74a6aa8984eb481c2fea27a80d12cfd4c24c5300db820f86a733f486` |
| `handler160.bin` | 160 | mapped0x10024a20, image offset0x24a20 | `3f76f18c95ed6dfd6711681465491669ee48448b229eacfefb85aa9033ce68ab` |
| `ram-tail128.bin` | 128 | RAM0x18000000 bootstrap file offset3968; initialization oracle image offset0xdd500+3968 | `4df945cc5444f4b5bf12834aa20aac25d070113c55d36ec4e244fadc02c4272f` |

Complete mapped system image SHA256: `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`. Fixed RAM4096 initialization oracle SHA256: `35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b`.

**RAM full-file transfer remains failed.** No3852-byte partial exists for independent inspection; do not append/splice tail128 or claim4096-byte success. XIP32/160 are mapped system bytes, not raw NOR sectors, full NOR backup, writable firmware proof, or independent restoration. Test SD files remain on card under the documented residue policy; the verifier never deletes or modifies device files.

## Fresh-clone offline verification

From repository root:

```sh
uv run tools/verify_sd_bootstrap.py published docs/evidence/sd-bootstrap-2026-10-13.json
```

This verifies pinned public receipt, fixed ranges, parent bindings, summarized Actions cleanup, and all four retained raw-file hashes. It does not re-observe hardware or re-read the complete private reports/image.

Original complete-report/image comparison, when ignored originals are available:

```sh
uv run tools/verify_sd_bootstrap.py original artifacts/mapped-system-20261012.bin \
  artifacts/live-sd-bootstrap-20261013 \
  artifacts/live-sd-tail128-20261013 \
  artifacts/live-sd-xip32-a-20261013 \
  artifacts/live-sd-xip32-b-20261013 \
  artifacts/live-sd-xip32-c-20261013 \
  artifacts/live-sd-handler160-20261013 \
  artifacts/live-sd-handler160-read-20261013 \
  artifacts/live-sd-handler160-read-b-20261013
```

Both modes are standalone, dependency-free PEP723 scripts and entirely offline. Actions proof comes from retained socket ATT trace; no independent HCI or over-the-air observation is claimed.
