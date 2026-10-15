# NOR0x2400 window trial, 2026-10-14

**Both new4096-byte files downloaded completely, but the original pair failed strict second-ring freshness parsing; new verified coverage0 bytes.** Second producer→dump gap contains one exact composer statistics line. The original parser rejected that extra text before waiting for second slow settlement/identity checkpoint. Capture ends with five completed parameter transactions plus one pending slow transaction; final identity succeeds, but the full window audit did not pass. No candidate/full-partition binary published.

Fixed target is NOR`[0x2400,0x2600)`, two producer executions/new SD files on one owned connection, gated by independently successful early2200 and known-RAM window parent chains. Both parent chains were independently replayed. Raw backup-boot verified coverage remains1024/4096 bytes; no full NOR, sustained scaling or flashing/restoration claim follows.

## Actual operation boundaries

Both Actions sessions passed five confirmed writes/five ACKs/F1/empty pending. Each exact new-nonce Boyi transaction declared4096, delivered4096 and ended completely. All141 actual ATT packets bind to complete245-record/18244-byte private HCI capture; monitor SIGINT sent, exit0. Independent offline checks reproduced both Actions/download proofs, first strict freshness and barrier, final identity/state and parameter stages.

| Operation | Original outcome |
|---|---|
| First | Full4096 SHA256`794e45d39ecaa85c6bad35e8a772dcac4bed4bc3f4091958196e54452244b5e1`; strict32-row512 candidate SHA256`9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d`; unique current marker and own identity barrier passed; `live_complete=true` |
| Second | Full4096 SHA256`4f1ee8b104f8c541b597d8ccf0a1040079d94d1c3459eec978a5b9c2ecb91347`; original strict parser raises `Unexpected text/status/failure between current producer and dump`; no second sector file, slow settlement or own completion barrier |

Both original operation `ok` flags remain false: this implementation only sets them after the full capture audit. Top-level `ok=false`, `pair_verified=false`, `final_audit_complete=false`. First complete single-read candidate does not substitute for the missing second verified acquisition or increase pair-verified coverage.

## Exact extra line, without repairing the ring

Second physical ring gap`[3226,3280)` is54 bytes, SHA256`6e90c546f667fcc46f73275f5036d5c4460e146b26051b07c00179ff7a7d5dfe`:

```text
\n[composer][I][742]: post fps 2\n\r\n\r\n[logsrv][I][679]:\x20
```

Escapes above denote original newline/CR bytes and final ASCII space. Extra line`[3227,3260)` is33 bytes, SHA256`5a3ac148d446b5fdc3250152b6e17821a411fde6f6b67fb6088ca6d6c91f2d76`. Original rule allowed only the fixed newline/logsrv prefix between producer and current dump; it therefore rejected this exact original ring. No line was deleted, bytes repaired, second sector manufactured or failed pair reclassified.

Astra's static comparison with pinned actual FW010004 bytes identifies composer display post-count statistics logging: actual formatter`post fps %u\n`, encoded line742, composer module pointer. Four original code/literal/format/module-region hashes were independently checked and bound in metadata. Thus this line itself is not a fread failure message. That inference does not demonstrate caller-thread/CPU-branch execution or display correctness, nor authorize accepting arbitrary intervening text.

## Five settled transactions, second slow still pending

Initial physical parameters are interval48/latency4/timeout600. Host normalizations explicitly request6/6/0/500 with CE hints1/1; accepted remote ranges retain CE hints0/0.

| Stage | Remote request / accept | HCI request / status / Update Complete |
|---|---|---|
| Startup FAST6..12/0/500 | 105 / 107 | 108 / 109 / 111, effective12/0/500 |
| First host normalization | — | 134 / 135 / 136, effective6/0/500 |
| First SLOW32..48/4/600 | 159 / 162 | 163 / 164 / 166, effective48/4/600 |
| Required second pre-download FAST | 197 / 199 | 200 / 201 / 203, effective12/0/500 |
| Second host normalization | — | 205 / 206 / 207, effective6/0/500 |
| Second SLOW pending | 230 / 232 | 233 / 234 / **no Update Complete** |

First Actions112→132 preceded normalization; first download138→161 took176.774ms. Its slow request159 and end161 share a timestamp, with159 preceding161 by record order; effective slow update166 follows end by57.227ms, before identity167→175. Optional first FAST list is empty. Second Actions176→196 was followed by the real mandatory FAST197→203, then normalization205→207 and download209→235,185.307ms.

Second slow request230 precedes end235 by2.027ms; matching host command233/status234 is retained. No later slow Update Complete appears before capture termination. Original code raises freshness failure immediately after complete download, before its planned slow wait/checkpoint. Final identity236→245 nonetheless passes, with reported FW010004 NOTE/idle/charging/battery100/free59591MiB; it cannot replace the missing second-stage barrier, prove slow2 effective or make the full window audit successful. No captured disconnect was inferred or fabricated.

## Frozen original version and replay

[Metadata receipt](evidence/window-nor2400-live-2026-10-14.json) binds original report SHA256`682b95fe57703a7ad03f18ad11b9ba0314f0505e53b8e9b583fe372735c64c47`, full private HCI SHA256`4d87c3fb4615b8e8b08c568de76d19ba48c079efb00ed002b34bf1fe8696971b`, first checkpoint and34-file source snapshot manifest SHA256`834ec103f639c924473c26b2cee26b483790c232c47fbdf87a7bac311acc185f`. Snapshot describes the original observed strict grammar/decode-before-settlement implementation. Subsequent parser or sequencing changes do not rewrite this original or supply missing settlement/barrier events; any new controlled trial requires separate artifacts.

Ubuntu scratch accounting:56 download-confirmed files + one old device-declared4096/unverified-content file + one historical possible file, maximum58. This trial adds two complete downloaded scratch files; none deleted. Complete rings/ATT/HCI/device-info/audio inventory remain private; only parameter/count/hash metadata and the selected nonprivate composer gap are published. No new binary or verifier created.

```sh
uv run python - <<'PY'
from pathlib import Path
from rcominote.experiments.window_nor_probe import replay
try:
    replay(Path("artifacts/window-nor2400-20261014"), Path("artifacts/mapped-system-20261012.bin"))
except ValueError as error:
    print(f"Expected original-failure rejection: {error}")
else:
    raise AssertionError("Original failed NOR-window pair promoted")
PY
```

Offline replay rejects the original before success revalidation. Evidence preparation performed no device operation, grammar/source edit, original-file modification or additional hardware retry.
