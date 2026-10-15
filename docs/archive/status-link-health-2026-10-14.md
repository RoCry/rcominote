# One-shot GATT/identity health: current communication verified

2026-10-14 read-only health trial **passed**, from `03:42:54.408578Z` to `03:43:12.860150Z`. Full GATT setup and two complete actual identity reads succeeded after the earlier2a00 discovery timeout. This verifies communication during this trial; it does **not identify or establish repair of the earlier timeout's root cause**.

[Frozen receipt](../evidence/status-link-health-2026-10-14.json) · [preceding failed job and successful2800 checkpoint](status-boot-tail-live-2026-10-14.md).

Independent offline review loaded the private probe with `runpy.run_path` and called only its `audit` function. Exact result equals original saved verification. Probe SHA256 `6bab70df911d71bea7ced9b204eefb061a2ce4ec4e72012eb5718d98b61d13e4` matches original report's recorded source hash. Dependencies were imported from the preceding frozen110-file source snapshot; all archived lengths/hashes were rechecked. No live capture/main function ran during review. No later/current-source equality claim is made.

| Check | Actual evidence |
|---|---|
| Original result | `ok=true`; no retained error; independent audit passes |
| Capture |4201 bytes,107 monitor records,46 ATT packets; complete exact binding within direction |
| GATT/identity | Full setup ATT `[0,34)`; complete three-request/reply identities `[34,40)` and `[40,46)` |
| State | `before == after == expected_before == successful new2800.after`; free59590MiB, zero allowed decrease |
| Parameters | One complete remote-requested startup FAST transaction; requested6..12/latency0/timeout500, applied12/0/500; zero pending, zero host-origin normalization transactions |
| Status events | Policy enabled; zero actual events |
| Commands/storage | Zero Actions commands, producers, SD-write attempts, downloads or new NOR coverage |
| Monitor | Owned SIGINT sent, monitor exit0; stderr empty |

Startup settlement completes at HCI record94 before final identity. Final original ATT packet occupies record103. After explicit connection-context close, probe passively observed for at most8 seconds; captured Disconnection Complete has `status=0`, `reason=0x16`, record106. It occurs **2.023812 seconds after final ATT**, on the same owned connection handle. Both complete identities precede disconnect; no premature link drop appears. Captured close does not prove physical firmware-worker exit or hidden-cache clearing.

Last observed identity: owned/unbound, FW010004, NOTE/idle, charging, battery100, free59590MiB. One remote startup negotiation includes the host controller's corresponding update command; zero **host-origin normalizations** does not mean zero HCI commands. Notification configuration and GATT discovery are part of this health trial; no Actions data commands or SD exports were sent.

Original report SHA256: `20133998df7c702e36bd6f01eba06caeabd79a0251466a4380b144e031bdbaa8`. Capture SHA256: `db073382d26242da08a7567418ed4676f25588f5f133ed9f8cf7c3816f5d3552`. Four original health input files retained identical hashes across offline review. Full probe, HCI/ATT, raw identity and peer identifiers remain private.

`fw1_boot` verified coverage remains **2560/4096 bytes**. Original failed2a00, its aggregate job, and previous failed2800/aggregate retain their failures. This health success does not demonstrate stable future connections, exercise live status-event insertion, complete backup, or establish restoration/flashing guarantees.

Offline reproduction from repository root with private originals; no device I/O:

```sh
PYTHONPATH=artifacts/status-boot-tail-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib
import json
import runpy
from pathlib import Path

root = Path('artifacts/status-link-health-20261014')
report = json.loads((root / 'report.json').read_bytes())
assert hashlib.sha256((root / 'probe.py').read_bytes()).hexdigest() == report['source_sha256']
probe = runpy.run_path(str(root / 'probe.py'))
assert 'source-snapshot/src' in probe['W'].__file__
assert report['ok'] is True and probe['audit'](../report) == report['verification']
assert report['before'] == report['after'] == report['expected_before']
raw = (root / 'session.btsnoop').read_bytes()
observed = probe['P'].inspect(raw, link=report['transport']['link'], final=True)
wire = probe['W'].wire_positions(report, raw)
assert len(observed['disconnects']) == 1
event = observed['disconnects'][0]
assert event == report['disconnect_observation']['event']
assert event['record'] > max(row[1] for row in wire)
assert (event['status'], event['reason']) == (0, 0x16)
print('health verified; final ATT103 precedes disconnect106; coverage unchanged')
PY
```
