# Actual DEFAULT/activity FAST control: two existing-RAM reads pass

2026-10-14 fixed two-connection control **succeeded**. Seed connection settled actual startup FAST and closed normally. Data connection then settled actual startup **DEFAULT24..40/0/500→36**, followed by two fixed PREPARE/START/STOP pulses, separately observed FAST, host normalization6/0/500, complete existing-RAM4096 download, EOF SLOW and actual identity barriers. Both downloads exactly match the fixed original image oracle. **Zero SD writes, new files, producers or new NOR coverage.** `fw1_boot` remains **2560/4096 verified bytes**.

[Frozen receipt](../evidence/startup-ram-default-live-2026-10-14.json) · [preceding startup mismatch](status-remaining-live-2026-10-14.md) · [static DEFAULT/FAST path evidence](ble-default-parameter-path-2026-10-14.md).

Independent offline review imported all experiment dependencies from the **118-file pre-I/O source snapshot** and replayed the original successful control in full. Original state/checkpoint chains, historical/modern2560-byte prefix, existing RAM-bootstrap Actions/state proof, fixed927632-byte image and4096-byte oracle were independently reverified against immutable plan. All phase flags, report/capture hashes, wire partitions, actual parameter transactions, event ledgers, chronological order and read-only states pass. No hardware function ran during review; all historical failures still reject their original replays.

| Actual phase | Evidence | Result |
|---|---|---|
| Seed | Initial connection36/0/500; full GATT; actual before identity; remote FAST6..12/0/500 settles12; actual after identity; normal disconnect |46 ATT packets,107 HCI records,4201 bytes; one complete transaction, zero pending |
| Data startup | Initial connection12/0/500; full GATT, actual identity/file list; remote DEFAULT24..40/0/500 settles36 before first pulse |Actual DEFAULT branch tested; not inferred from previous failure or relabeled FAST |
| First window | Pulse3ACK+F1; actual FAST→host6→oracle4096→EOF SLOW48/4/600→actual identity |Complete independent original wire/state audit passes |
| Second window | Same fixed sequence, second complete oracle4096 download and actual identity; final identity follows |Complete independent original wire/state audit passes |

Data capture:137 ATT packets,251 HCI records,18281 bytes. Exactly **seven complete transactions**, zero pending: DEFAULT, FAST1, host1, SLOW1, FAST2, host2, SLOW2. Every host ATT packet binds exactly to original HCI bytes within direction; all ATT ranges are consumed by fixed GATT, identity, file list, pulse, download or validated status-event handling.

| Data stage | Remote request record | Controller command / status / update records | Applied interval / latency / timeout |
|---|---:|---|---|
| DEFAULT |104|107 /108 /110|36 /0 /500|
| FAST1 |124|127 /128 /130|12 /0 /500|
| Host1 |—|132 /133 /134|6 /0 /500|
| EOF SLOW1 |159|162 /163 /166|48 /4 /600|
| FAST2 |189|192 /193 /195|12 /0 /500|
| Host2 |—|197 /198 /199|6 /0 /500|
| EOF SLOW2 |222|225 /226 /229|48 /4 /600|

Pulse first TX records **111/176** precede respective FAST request records **124/189**. This establishes original wire ordering: requests are not earlier than the pulses. **It does not prove pulses were the unique triggers**; earlier identity traffic may have scheduled hidden deferred FAST work. No hidden queue was inspected or declared empty. Complete actual FAST settlement was required before either host normalization; normalization followed the completed pulse; each exact4096-byte download stayed inside its normalized window; actual SLOW settlement preceded its actual read-only identity barrier.

Each pulse sent only PREPARE/START/STOP, with **three actual ACK frames and one F1**, no console body. **Actual background F0 frames:0; actual `cmd0x0F` status events:0**, in both connections. Complete bounded parsers and ledger audits were enabled, but this trial does not demonstrate those background-event paths. Pulses change temporary Actions/log RAM context and buffers; zero persistent-storage write does not mean zero RAM side effect.

Both separate downloads equal independent image oracle SHA256 `35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b`,4096 bytes each. Original fixed existing RAM file was read twice; no fresh SD export or NOR producer ran. Transfer durations from retained original timestamps:190.749ms and186.614ms. These RAM reads do not add NOR coverage or prove that an unknown-sector producer will succeed.

Seed ran `04:27:18.486824Z`–`04:27:29.359947Z`; data ran `04:27:29.475448Z`–`04:27:48.692863Z`. Aggregate ran `04:27:12.290486Z`–`04:27:48.803411Z`. Seed final ATT record103 precedes captured normal disconnect106; data final ATT247 precedes disconnect250. Both disconnects have `status=0`, `reason=0x16`, observed within the fixed8-second post-close bound. Seed's actual disconnect precedes data's actual connection in original monitor timestamps. Both owned monitors exited0 after SIGINT. Normal disconnect capture does not establish physical firmware-worker exit or clearing of deferred work.

Latest actual identity comes from data's final complete read: owned/unbound, FW010004, NOTE/idle, charging, battery100, free59590MiB. Every seed/data initial, post-download and final identity exactly equals required latest failed-three-job state; permitted read-only capacity decrease is0 and actual decrease is0.

Snapshot manifest SHA256: `c39d570cc2215bc2c60611dd8b10e934e21419fbca8ea63490ac5b84e2f06781`; all118 archived lengths/hashes match. Record created `04:27:05.130868Z`, before plan/job/device I/O, records1605 tests plus159 subtests, successful build and offline source/state preflight. This review verifies archived-source consistency and original chronology, not future equality with current source files.510 checked private input files retained identical hashes across review. Full original HCI/ATT, Actions text, raw identity, file bytes and inventory remain private; only hashes and bounded summaries are published.

Original aggregate report SHA256: `48ec93559b6702abe67c0a00298bcc8abf5d555710a9896fb183c81da76b7da4`. Exact seed/data report, capture, source, oracle and per-download hashes appear in receipt. Earlier failed2800, discovery2a00, startup-mismatch2a00 and their aggregate jobs remain failed. Success establishes this fixed DEFAULT/RAM control only; no full `fw1_boot`, full NOR backup, restoration or flashing guarantee follows.

Offline reproduction from repository root, private originals available; no device I/O:

```sh
PYTHONPATH=artifacts/startup-ram-default-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib
import json
from pathlib import Path
from rcominote.experiments import startup_ram_probe as P
from rcominote.experiments import startup_ram_contract as C

root = Path('artifacts/startup-ram-default-20261014')
image = Path('artifacts/mapped-system-20261012.bin')
assert 'source-snapshot/src' in P.__file__
manifest = root / 'source-snapshot/manifest.json'
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == 'c39d570cc2215bc2c60611dd8b10e934e21419fbca8ea63490ac5b84e2f06781'
sources = json.loads(manifest.read_bytes())['source_files']
assert len(sources) == 118
for entry in sources:
    raw = (manifest.parent / entry['path']).read_bytes()
    assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
proof = P.replay(root, image)
assert proof['actual_default_tested'] and proof['new_raw_nor_coverage_bytes'] == 0
job = json.loads((root / 'report.json').read_bytes())
plan = json.loads(P.J.check_reference(root, job['plan']).read_bytes())
oracle = C.source_gate(plan, image)
data = json.loads((root / 'data/report.json').read_bytes())
assert data['startup_classification']['mode'] == 'default'
assert data['after'] == data['before'] == plan['expected_before']
for op in data['operations']:
    assert (root / 'data' / op['operation_id'] / 'download.bin').read_bytes() == oracle
    assert op['ack_count'] == 3 and op['end_received'] and not op['sd_write_attempted']
    assert sum(frame['command'] == 0xF0 for frame in op['frames']) == 0
    ordering = op['activity_fast_verification']
    assert ordering['pulse_first_record'] <= ordering['remote_request_first_record']
print('actual DEFAULT control passed; two oracle4096 reads; zero SD/new NOR coverage')
PY
```
