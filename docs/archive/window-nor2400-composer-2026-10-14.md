# Verified NOR0x2400 pair with exact composer notice, 2026-10-14

**A new independent trial verified512 raw bytes at NOR`[0x2400,0x2600)` through two fresh producer executions/new files, complete download-window audits and equal sectors.** Both512-byte sectors are allFF, SHA256`9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d`. This adds512 verified bytes, taking backup-boot coverage to1536/4096 bytes. No independent byte oracle is claimed; unknown addresses are not presumedFF.

Actual `fw1_boot` partition is NOR`[0x2000,0x3000)`. Verified prefix now`[0x2000,0x2600)` combines original2000 prefix, separately paired2200 and this new paired2400 sector. Remaining`[0x2600,0x3000)` contains five unknown512-byte sectors. No full partition/NOR backup, restoration, flashing, sustained scaling or physical worker-exit claim follows.

## Actual successful acquisition

Private `artifacts/window-nor2400-composer-20261014/` is a separate original trial. Both operations passed five confirmed Actions writes/five ACKs/F1/empty pending; two distinct producer/nonces/files; complete4096-byte Boyi downloads; strict32-row target/marker association; actual slow settlement and own identity/state barrier; then decoding and final complete audit. Both operation `ok`, `barrier_complete`, `live_complete` flags are true while their single-operation pair flags stay false; the completed top-level comparison sets `pair_verified=true`/`final_audit_complete=true`.

| Original operation | Retained4096-byte ring SHA256 | Freshness rule |
|---|---|---|
| First | `aab4a2b76fec7da862f0266fe26d1c39de90d408c0941329813748bb177ec826` | Original strict rule, no extra notice |
| Second | `a5ec81cfd3de98d683cf930062bf24362ce325e8cc8aec039b3a2701a567958a` | Explicit exact composer-fps2 rule, mandatory previous-dump anchor |

Second proof actually exercises the new window-only option: exact33-byte `[composer][I][742]: post fps 2\n\r\n` at physical ring`[2180,2213)`, SHA256`5a3ac148d446b5fdc3250152b6e17821a411fde6f6b67fb6088ca6d6c91f2d76`. Its current status/rows/producer/dump stay separately bounded, with the first dump`[2596,2677)` required to precede current status within the same circular snapshot. Actual rule is `nearest-producer-exact-status32rows-prefix-dump-composer-fps2-v1`.

Default parser remains strict. The explicit option admits only that known exact line in the audited producer→dump formatter gap, retaining32 canonical rows, unique target-matching current producer/status, previous nonce anchor and failure/extra-transaction rejection. It does not delete bytes, skip arbitrary logs, accept other FPS/source lines or use oldFF content as an oracle. Actual source context for that composer statistics line is documented in the [preserved earlier failure](window-nor2400-live-2026-10-14.md).

## Six complete parameter transactions and barriers

Initial captured parameters remain interval48/latency4/timeout600. Before each download, prior observed negotiations settle, then host normalization explicitly requests min=max6/latency0/timeout500 with CE hints1/1. Remote requests retain their own exact ranges and CE hints0/0.

| Stage | Remote request / accept | HCI request / status / Update Complete |
|---|---|---|
| Startup FAST6..12/0/500 | 104 / 106 | 107 / 108 / 110, effective12/0/500 |
| First host normalization | — | 133 / 134 / 135, effective6/0/500 |
| First SLOW32..48/4/600 | 159 / 162 | 163 / 164 / 166, effective48/4/600 |
| Mandatory second pre-download FAST | 197 / 199 | 200 / 201 / 203, effective12/0/500 |
| Second host normalization | — | 205 / 206 / 207, effective6/0/500 |
| Second SLOW settlement | 231 / 233 | 234 / 235 / 238, effective48/4/600 |

First Actions111→131 precedes host normalization; download137→161 takes187.173ms, then slow completion166 precedes identity167→175. First optional FAST is absent. Second Actions176→196 is followed by the real mandatory FAST197→203, normalization205→207, download209→236 taking197.205ms, slow completion238 and identity239→247. Final identity also passes. Slow Update Complete follows each Boyi end by95.416/100.510ms; remote slow signaling near the end does not itself mean slow parameters already took effect.

**Decoding occurs after each complete slow settlement and identity/state barrier**, before its operation becomes live-complete or the next Actions session can start. Consequently second composer parsing succeeded after its required second settlement/barrier existed. Complete capture contains256 records/18683 bytes; all149 host ATT packets bind exactly within each direction. Six logical parameter transactions completed, none pending, no captured disconnect. Monitor SIGINT sent, exit0. All initial/per-operation/final reported state matches: owned FW010004 NOTE/idle/charging/battery100/free59591MiB. These are protocol/state observations, not proof hidden caches are empty or device worker threads exited.

## New original bytes, preserved old failure

[Public sector512](../evidence/window-nor2400-composer-2026-10-14/sector.bin) was copied byte-for-byte from **this new trial's `first/sector.bin`**, after checking both new sector files agree and every byte isFF. Identical hashes at old addresses do not replace this acquisition: no old prefix, old candidate or assumedFF oracle was reused. [Metadata receipt](../evidence/window-nor2400-composer-2026-10-14.json) binds exact source path/report/hash, target range, both originals, parameter windows and source snapshot.

Original report SHA256`7b0b2e8366df265499be45eae8061db7fe98609447089d49073eba129f47e852`; full private HCI SHA256`8b97473dc252637a5d63715791e0ab20a91dd2fba24361740c2b22c785fdb214`; new34-file source snapshot manifest SHA256`bf750ad730ae6aaec8a57159f8b7aa8797ea6826f610e2fa80b783eb7e6a3c43`. Independent `window_nor_probe.replay` passes both full parent chains, complete Actions/Boyi/HCI/window/identity/freshness checks and final pair equality.

The [earlier failed window trial](window-nor2400-live-2026-10-14.md), original report, doc and metadata remain unchanged. Its replay still refuses the original failed flags; this new success does not supply its missing slow settlement/barrier or retroactively change its strict-parser outcome. Complete rings/ATT/HCI/device-info/audio inventory remain private. No new verifier or assembled partition created.

This trial adds two downloaded scratch files. Ubuntu cohort:58 download-confirmed files + one old device-declared4096/unverified-content file + one historical possible file, maximum60; none deleted.

```sh
uv run python - <<'PY'
from pathlib import Path
from rcominote.experiments.window_nor_probe import replay
print(replay(Path("artifacts/window-nor2400-composer-20261014"), Path("artifacts/mapped-system-20261012.bin")))
PY
```

Replay is offline and requires retained private originals plus installed project dependencies. Evidence preparation performed no device operation, original-file modification or additional hardware retry.
