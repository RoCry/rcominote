# Per-download parameter windows, 2026-10-14

**Two complete reads of the existing4096-byte RAM test file succeeded on one owned connection while parameters changed between downloads.** Each received4096 bytes exactly matching independent oracle SHA256`35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b`. HCI-observed interval6/latency0/timeout500 covered each request→Boyi-end window; accepted slow updates completed afterward. This supplies evidence for a per-download model instead of requiring interval6 across the whole session. It adds **zero new raw NOR coverage**.

Only existing test file`rc6ae65544fe` was read twice at offset0. No Actions command, new SD file, file-write command or NOR operation occurred. Initial/final state matched: owned CoMi FW010004 NOTE/idle/charging/battery100/free59591MiB. The complete original report remains `ok=true`; both operations are `ok=true`/`live_complete=true` and independently match the oracle.

## Actual five transactions and two windows

Capture contains205 complete records/16535 bytes. All115 host ATT packets bind exactly within each direction. Five complete parameter transactions were associated by actual remote CID5 request/identifier, host acceptance, matching HCI command, successful Command Status and Connection Update Complete. Host-origin normalizations use min=max6/latency0/timeout500 and CE hints1/1; accepted remote requests use their recorded ranges with CE hints0/0. Initial physical connection remains recorded as interval48/latency4/timeout600.

| Stage | Remote request / accept | HCI request / status / Update Complete | Applied interval / latency / timeout |
|---|---|---|---|
| Startup fast settlement | 104 / 106 | 107 / 108 / 110 | 12 / 0 / 500 |
| First host normalization | — | 112 / 113 / 114 | 6 / 0 / 500 |
| First EOF-associated slow settlement | 137 / 140 | 141 / 142 / 144 | 48 / 4 / 600 |
| Second host normalization | — | 155 / 156 / 157 | 6 / 0 / 500 |
| Second EOF-associated slow settlement | 180 / 183 | 184 / 185 / 187 | 48 / 4 / 600 |

Intervals use1.25ms units, timeouts10ms. Thus6 means7.5ms,12 means15ms,48 means60ms;500/600 mean5s/6s. Requesting slow parameters differs from their later effective Update Complete. Both stages are fully retained; the audit does not hide or discard remote requests to manufacture a quiet session.

| Exact window / barrier | First | Second |
|---|---:|---:|
| Host normalization Update Complete | 114 | 157 |
| GET_FILE request TX | 116 | 159 |
| Remote slow request | 137 | 180 |
| Complete Boyi end RX | 139 | 182 |
| Slow Update Complete | 144 | 187 |
| Subsequent identity barrier | 145→153 | 188→196 |
| Request TX→Boyi end | 190.149ms | 186.606ms |

**Remote requests already appear near the end of each download.** First slow request137 precedes end139 by2µs; second slow request180 and end182 share a timestamp, with original record order180 before182. Slow Update Complete144/187 follows the respective end by88.563/110.706ms. Therefore evidence supports unchanged effective parameters during the data windows, not absence of parameter-request traffic inside them. Original record order and timestamps are preserved without sorting, clamping or repair.

Initial identity and file-list exchange completed before downloads. The experiment waited for startup remote transaction110 to settle, then issued normalization112 and waited for successful update114 before first request116. After first end139, it waited for the associated slow transaction144 to complete before identity145→153. Only after that complete checkpoint and no observed pending negotiation did normalization155 begin; update157 preceded second request159. Second end182 likewise precedes slow completion187 and identity188→196. Final identity197→205 passed. Capture has no unresolved logical transaction or captured disconnect; monitor received owned-process SIGINT and exited0.

These are host-visible protocol/identity barriers. They do not prove physical file-worker exit, emptiness of hidden device parameter caches or absence of later traffic. One connection/two4096-byte transactions do not establish sustained throughput, larger-file reliability, fresh NOR export behavior, full4MiB backup or flashing/restoration.

## Preserved evidence and replay

[Metadata receipt](evidence/download-window-live-2026-10-14.json) records selected parameter fields/window boundaries, original source hashes and private artifact references. Original report SHA256`8ffa203974b1f939ba3365186c771bc4128fa37aeba8efbb5133f9c5ab8aaa6e`; full HCI SHA256`248e57886ca3d61e02ba5694d310fefe6194e7f709c921a0b4baf6ab12da7277`. Eighteen-file source snapshot manifest SHA256`8af620d7f6db3c9b9a1408221f41c46645f83ffa12b8d6ba4b85e4ea788c00dc`. Independent offline replay validates the original RAM-file creation/source parent, complete capture, actual ATT/GATT/Boyi transactions, settlement/window causality, two oracle matches and all identity/state barriers.

Oracle reuses bytes`[0xdd500,0xde500)` from the existing pinned complete system image927632 bytes, SHA256`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`. No new binary or verifier created. Complete private ATT/HCI/downloads/device-info/audio inventory stay private; the published artifact is metadata only.

The original RAM-file bootstrap's unsuccessful download remains failed; only its separately audited file-creation/source evidence is used. Earlier [unknown2200 failures](dual-unknown2200-2026-10-14.md) and [boot-tail failed job](backup-boot-tail-2026-10-14.md) retain original statuses and coverage counts. This is a new explicitly different experiment, not retroactive promotion under a changed contract.

```sh
uv run python - <<'PY'
from pathlib import Path
from rcominote.experiments.window_ram_probe import replay
print(replay(Path("artifacts/window-ram-20261014"), Path("artifacts/mapped-system-20261012.bin")))
PY
```

Replay is offline and requires retained private artifacts plus installed project dependencies. Evidence preparation performed no device operation or original-file modification; it independently checked the complete replay, eighteen source hashes and both original4096-byte oracle matches.
