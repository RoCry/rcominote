# logsrv runtime context: 2026-10-14

Owned idle CoMi FW010004. Two independent SD snapshots completed: fixed global `1800a9ac/4` → bounded pointer `P=180111fc`; then `P/32` → context fields below. Both original sessions passed strict ATT Actions audit: four confirmed writes, four ACKs, one F1, empty pending; complete Boyi file download; bounded final state comparison. Pointer session free-capacity report fell 59597→59596 integer MiB; all other fields equal. Context session state equal.

| Context offset | Historical value |
|---|---|
| +0, stream pointer | `18011254`; reported, never followed |
| +4, flags byte | `3` |
| +5 / +6, current / requested type | `0 / 0` |
| +7 / +8, rd / wr | `204 / 204`; uint8 cyclic counters, no `<=7` restriction |
| +0A..+19, eight uint16 lengths | `[0,0,0,0,139,0,0,0]` |
| +1C, drop counter | `0` |

The 139-byte value is metadata in the saved context; no slot body was read. Snapshot occurred during its Actions session, before STOP cleared live lengths; SD download occurred afterward. The earlier pointer and later context are non-atomic historical samples. Pointer alignment and `P>=18003ca0`, `P+80<=18045250` establish only the inspected initialized-RAM bound, not current allocator ownership or stable pointer identity between sessions. Sampling commands themselves emit logs. No known-mdb output, partial-slot payload freshness, raw NOR or firmware write is established.

Five fixed code guards matched full mapped image SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`: existing header32/handler160 plus new `1000bf82/32` global load/store, `1000c0c8/16` literal, `1009aa24/48` RAM zero-function/boundary literals. Read-only handler receipt binds its original full Actions write parent. New public bytes total132: guards96 + pointer4 + context32. This round retained five non-audio SD test files; total17 including earlier12; none deleted.

Evidence: [compact receipt](../evidence/logsrv-context-live-2026-10-14.json), [raw samples](../evidence/logsrv-context-live-2026-10-14), [implementation](../../src/rcominote/experiments/logsrv_context_probe.py). Original private reports were audited offline with `validate_guards`, `previous`, `request`, `validate_actions`, `same_identity`, `downloaded`, and `context_fields`. Compact receipt pins report hashes without publishing recording lists, info payloads, frames or full logs/HCI.

Offline replay from a fresh clone, using tracked files only; performs no device operation:

```sh
uv run python -c 'import json; from pathlib import Path; from rcominote.experiments.logsrv_context_probe import replay_public; print(json.dumps(replay_public(Path("docs/evidence/logsrv-context-live-2026-10-14.json")), ensure_ascii=False, indent=2))'
```

Replay checks pinned compact receipt, full gzipped image SHA, five code guards, raw pointer bound, context-parent hash binding, and decoded32 bytes. It records the original private ATT/state audit; it does not rerun that packet audit. Corrupted receipt/raw bytes fail; no missing bytes are repaired or joined.
