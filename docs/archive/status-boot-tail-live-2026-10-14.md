# Fixed four-slot fw1_boot job: verified2800, then discovery timeout

2026-10-14 actual job adds **512 unique verified bytes**, raw `[0x2800,0x2a00)`. Cumulative `fw1_boot` coverage: **2560/4096 bytes**, `[0x2000,0x2a00)`. Original aggregate job failed at `0x2a00`; no partition was assembled. Previous failed2800 evidence remains failed and contributes zero coverage. This increment comes from the **new independently successful2800 pair**.

[Frozen evidence receipt](../evidence/status-boot-tail-live-2026-10-14.json) · [actual verified sector2800](../evidence/status-boot-tail-live-2026-10-14/sector2800.bin) · [preceding failed five-slot job](window-boot-tail-live-2026-10-14.md).

Immutable plan fixed offsets `2800,2a00,2c00,2e00`, eight distinct scratch nonces, maximum four connections/eight producer executions/eight SD files, and fail-stop without retry/resume. Fresh offline replay verified complete retained checkpoint summary against `plan.checkpoint`, all historical/modern parent sources, planned nonces, targets, parents, policy, prestate and chronological acquisition order. New2800 initial state equals the independently verified final identity from previous failed2800; this uses that old capture only as a state anchor.

| Actual slot | Evidence | Original result | Coverage increment |
|---|---|---|---|
| `0x2800` | Two fresh fixed-sector producer executions, separate nonces, complete4096-byte downloads,32 rows each, second requires first dump; both actual identity barriers complete | Full Actions/ATT/HCI/parameter/state audit and independent pair replay pass |512 bytes |
| `0x2a00` | Connection established, MTU exchanged,19 ATT packets during partial GATT discovery; no actual initial identity or Actions | `TimeoutError: [Errno 110] Connection timed out`; original flags false |0 |
| `0x2c00,0x2e00` | Precreated host directories contain no files | Unexecuted after failure |0 |

Successful2800 began `03:31:13.874641Z`, ended `03:31:28.697141Z`. Capture:255 monitor records,148 ATT packets,18648 bytes; every host ATT packet binds exactly to captured wire bytes within direction. Six complete parameter transactions, zero pending: startup FAST, first host normalization/SLOW, second FAST, second host normalization/SLOW. Both download windows independently verify interval6/latency0/timeout500 and SLOW settlement before actual identity barriers. Monitor received owned SIGINT and exited0. Original aggregate failure does not invalidate this independently completed pair.

Status-aware policy `unchanged-status20-usb-connected-max8` was enabled. **Actual new2800 ledger and complete ATT replay contain zero status events.** This connection therefore does not demonstrate live insertion of `cmd0x0F` between Actions and download, or inside another transaction. It validates a zero-event capture under the new policy. The previous failed2800 capture still contains its separately described event; no policy flag or success flag was added to that original report.

Failed2a00 began `03:31:28.718769Z`, ended `03:31:38.733957Z`. HCI explicitly records successful connection (`status=0`) followed by disconnect reason `0x08`, connection/supervision timeout. Last original ATT row is outgoing Find Information request `0428002800`; no corresponding reply appears. Failure occurred during **GATT discovery after connection**, before setup completed. Capture:55 records,19 ATT packets,2136 bytes; retained ATT bytes independently bind to HCI using the captured connection handle. Monitor exited0 after owned SIGINT. No initial/final identity, Actions span, producer execution, SD-write attempt or downloaded file exists for this slot. Its prepared nonces are not counted as new SD files. Host evidence identifies the failed stage; it does not establish the RF/device-side cause of timeout.

The last actual identity comes from successful2800: owned/unbound, FW010004, NOTE/idle, charging, battery100, free59590MiB. Initial state, both per-write identity barriers and final read-only identity preserve the same integer free-capacity report. Later2a00 capture has no identity; device state after that timeout is unknown. Two new scratch files were download-confirmed and retained;2a00 added zero attempted files.

Earlier2048 verified bytes were independently reconstructed before adding the new sector:

- `0x2000..0x2200`: pinned historical archive,22 distinct non-atomic windows,32 confirmed rows with at least two sources per row; complete analyzer report equals pinned report and512-byte prefix.
- `0x2200..0x2400`: actual successful early2200 pair, full original replay.
- `0x2400..0x2600`: actual successful composer-window pair, full original replay.
- `0x2600..0x2800`: actual successful pair from previous failed five-slot job, full original replay.

Combined earlier2048-byte SHA256: `d0ff1b294b5288d1ae1421eadf5b2d38a8752b76d472ff30bed9028e25b1c5b8`. New2560-byte verified prefix SHA256: `2b6e99ee899e1515e0cc44b220424cd9da6906b39490504bdcca2236755db51c`. These hashes describe independently targeted source bytes; equal allFF sectors do not substitute for address/producer provenance.

Public sector2800 was copied byte-for-byte from **this job's actual2800/first/sector.bin**, only after full pair replay,512-byte length, equality with its second actual sector and allFF checks. Its SHA256 is `9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d`. Two reads contribute one512-byte increment. No independent content oracle exists.

Frozen source snapshot contains110 files. Every archived length/hash matches manifest `e5e805f7138133390f6413411c26f5f5cf9c672a05117ce2865588170f26205a`; pre-capture record was created `03:30:50.345775Z`, before plan and job start. Its recorded checks report1452 tests plus159 subtests and successful package build. This review imported archived package sources for offline replay and verified snapshot internal consistency and record chronology. It makes no claim that later/current source files equal that snapshot. Across review,325 private original input files retained identical hashes.

Remaining unverified range: `[0x2a00,0x3000)`,1536 bytes. New aggregate replay, failed2a00 replay, old aggregate replay and old failed2800 replay all reject their original failures. Neither `tail.bin` nor `fw1_boot.bin` exists. No full-partition/full-NOR backup, restoration or flashing guarantee, worker-exit proof or cache-clear proof follows. Full HCI/ATT/rings/raw identities/device info/file inventory remain private.

Offline reproduction from repository root, with private originals available; no device I/O:

```sh
PYTHONPATH=artifacts/status-boot-tail-20261014/source-snapshot/src uv run python - <<'PY'
import json
from pathlib import Path
from rcominote.experiments import status_window_job as Q
from rcominote.experiments import status_event as E
from rcominote.experiments import window_nor_job as W
from rcominote.experiments import window_nor_probe as N
from rcominote.experiments import window_state_checkpoint as K

root = Path('artifacts/status-boot-tail-20261014')
old = Path('artifacts/window-boot-tail-20261014')
image = Path('artifacts/mapped-system-20261012.bin')
assert 'source-snapshot/src' in K.__file__
job = json.loads((root / 'report.json').read_bytes())
plan = json.loads(Q.J.check_reference(root, job['plan']).read_bytes())
Q.validate_plan(plan)
prefix, state, summary = K.verify(old, image)
assert summary == plan['checkpoint'] and len(prefix) == 2048
report = json.loads(Q.J.check_reference(root, job['completed'][0]['report']).read_bytes())
assert report['expected_before'] == state
assert N.replay(root / '2800', image) == job['completed'][0]['verification']
assert E.verify(report)[1]['events'] == 0
sector = (root / '2800/first/sector.bin').read_bytes()
assert len(sector) == 512 and sector == bytes([255]) * 512
assert sector == Path('docs/evidence/status-boot-tail-live-2026-10-14/sector2800.bin').read_bytes()
assert K.A.sha(prefix + sector) == '2b6e99ee899e1515e0cc44b220424cd9da6906b39490504bdcca2236755db51c'
for replay, directory in ((Q.replay, root), (N.replay, root / '2a00'),
                          (W.replay, old), (N.replay, old / '2800')):
    try:
        replay(directory, image)
    except ValueError as error:
        assert 'Original' in str(error)
        print('expected original failure:', error)
    else:
        raise AssertionError('failed original evidence promoted')
print('verified prefix:2560/4096 bytes; actual new status events:0')
PY
```
