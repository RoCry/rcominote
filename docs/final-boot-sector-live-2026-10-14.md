# Final2e00 pair succeeds: complete4096-byte backup fw1_boot dump

2026-10-14 new fixed single-sector job **succeeded**. Actual `0x2e00` pair adds512 unique bytes; complete backup `fw1_boot` range `[0x2000,0x3000)` is now **4096/4096 verified bytes**. Original assembled `fw1_boot.bin` independently replays against all eight address-specific source sectors and has SHA256 **`f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6`**.

[Frozen receipt](evidence/final-boot-sector-live-2026-10-14.json) · [actual complete fw1_boot.bin](evidence/final-boot-sector-live-2026-10-14/fw1_boot.bin) · [actual final sector2e00.bin](evidence/final-boot-sector-live-2026-10-14/sector2e00.bin) · [preceding partial controlled job](startup-boot-tail-live-2026-10-14.md).

All4096 captured bytes areFF: this backup-slot dump contains no boot-program content. There is **no independent content oracle**, and this result does not demonstrate boot0/recovery flashing or restoration. No NOR flash write, restore or post-restore boot was attempted; full NOR backup and recoverability remain unestablished.

Independent offline review imported the120-file pre-I/O source snapshot and reran complete original aggregate/pair replay. Admission independently reconstructs previous3584 bytes, preserves original failed2e00 as a zero-coverage/no-identity failure, verifies latest actual2c00 state and exact original DEFAULT/RAM control through its original state parent, then binds new final target, parents, policy, two fresh planned nonces, initial state and chronology. Original plan excludes all37 prior planned/ancestral names. One new connection, two independent producer executions and two SD files were fixed before authorization; no retry/resume occurred.

| NOR range | Actual source evidence |
|---|---|
| `0x2000..0x2200` | Pinned historical archive:22 distinct non-atomic windows,32 confirmed rows, minimum two sources per row; exact analyzer report/prefix equality |
| `0x2200..0x2400` | Original successful early2200 fresh pair |
| `0x2400..0x2600` | Original successful composer-window2400 fresh pair |
| `0x2600..0x2800` | Successful2600 checkpoint in original failed five-slot job |
| `0x2800..0x2a00` | New successful2800 pair in original failed four-slot job |
| `0x2a00..0x2e00` | Two independently completed targeted pairs in original failed controlled-three job |
| `0x2e00..0x3000` | This new successful final fixed pair |

Historical2000 evidence remains explicitly non-atomic; it was not rewritten as a modern pair. Every modern sector retains its own full original fresh-pair/source-chain replay. Equal FF hashes never substitute producer address, original capture, nonce or freshness proof. Prior3584-byte SHA256 is `92feb2e31d43ffb2ce5935a4a58559c35aa422cf7e6f829ddaa5aef1a69190c9`; new final512-byte SHA256 is `9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d`.

The new pair has two separate exact `0x2e00` producers/nonces, two complete4096-byte ring downloads,32 fresh rows per sector, strict previous-dump requirement for second read, and actual post-download identity barriers. Full Actions, GATT, ATT/HCI, parameter-window, device-state, ring freshness and pair comparison pass. Both original operation flags and final pair/aggregate flags are true; individual per-read `pair_verified=false` remains unchanged because pairing is established at the enclosing pair level. Saved checkpoint still has aggregate `ok=false`, correctly recording completed pair before final assembly; final original aggregate is true.

Actual startup classification was **FAST**: initial connection48/latency4/timeout600, accepted remote FAST6..12/0/500 settles12. Exactly six complete transactions, zero pending: startup FAST, first host normalization/SLOW, mandatory second FAST, second host normalization/SLOW. Both transfers independently stayed inside interval6/0/500 windows, and actual EOF SLOW settlement preceded each actual identity barrier. Transfer durations185.924ms and175.933ms. This NOR connection did not exercise DEFAULT startup; preceding successful RAM control remains the separate actual DEFAULT observation.

Capture:18648 bytes,255 HCI records,148 ATT packets; every actual host packet binds exactly within direction, and original transaction spans are fully consumed. Actual status events:0. Owned monitor exited0 after SIGINT. No disconnect event appears in this capture; normal disconnect, physical firmware-worker exit and hidden deferred-queue clearing are not inferred.

Latest actual final identity: owned/unbound, FW010004, NOTE/idle, charging, battery100, **free59589MiB**. Initial identity matched required59590. First small SD export kept59590; second changed integer report to59589, within the independently verified maximum1MiB reporting step per write. Final read-only identity remained59589, with zero allowed/actual decrease from second operation's state. Other device-info fields and raw bytes outside free-capacity encoding remain equal. The integer reporting step does not establish exact file-allocation bytes.

Two new scratch files were independently downloaded and retained: Ubuntu cohort70 download-confirmed, one older device-declared without download, one historical possible, maximum72. No files were deleted.

Original aggregate ran `05:08:19.937351Z`–`05:08:41.755729Z`; actual pair `05:08:24.922417Z`–`05:08:41.353502Z`. Source manifest SHA256 `7512c71c527beb8c30e703894d3a086581f7654347ab19838e50e7c860f22006` fixes120 distinct archived files and declares creation at `05:08:14.514017Z`, before plan/job/I/O. Every archived length/hash was independently verified. Manifest records root's1641 tests plus159 subtests and successful build; these counts come from root's execution record, not an independent full-suite rerun by this review. No separate pre-I/O `record.json` was invented. Archived-source consistency and original timestamps are verified; future/current source equality is not claimed.

Public binaries are direct byte-for-byte copies of **actual assembled output** `artifacts/final-boot-sector-20261014/fw1_boot.bin` and **actual first-sector output** `2e00/first/sector.bin`. Before copying, review checked full4096 length/hash/allFF, exact independently reconstructed3584+512 source equality, final-sector equality with its second read and actual `tail.bin`. No bytes were synthesized or filled; no earlier FF sector replaced the final target.886 checked private input files retained identical hashes across review. Exact job/report/capture/checkpoint/output/source hashes appear in receipt; raw HCI/ATT/rings/identity/inventory/nonces remain private.

Every historical failed job/pair remains failed, including previous features-failed2e00. The successful final pair is a new independent job. Completion applies to this raw4096-byte backup partition only.

Offline reproduction from repository root, private originals available; no device I/O:

```sh
PYTHONPATH=artifacts/final-boot-sector-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib
import json
from pathlib import Path
from rcominote.experiments import status_remaining_job as J

root = Path('artifacts/final-boot-sector-20261014')
image = Path('artifacts/mapped-system-20261012.bin')
assert 'source-snapshot/src' in J.__file__
manifest = root / 'source-snapshot/manifest.json'
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == '7512c71c527beb8c30e703894d3a086581f7654347ab19838e50e7c860f22006'
entries = json.loads(manifest.read_bytes())['source_files']
assert len(entries) == 120
for entry in entries:
    raw = (manifest.parent / entry['path']).read_bytes()
    assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
proof = J.replay(root, image)
assert proof['partition_bytes'] == 4096 and proof['independent_oracle'] is False
job = json.loads((root / 'report.json').read_bytes())
plan = json.loads(J.W.J.check_reference(root, job['plan']).read_bytes())
prefix, state, source = J.admission(plan, image)
assert len(prefix) == 3584 and source == plan['checkpoint']
pair = json.loads((root / '2e00/report.json').read_bytes())
assert J.W.N.replay(root / '2e00', image) == job['completed'][0]['verification']
assert pair['expected_before'] == state and pair['before']['device']['free_capacity'] == 59590
assert pair['after']['device']['free_capacity'] == 59589
sector = (root / '2e00/first/sector.bin').read_bytes()
full = J.W.J.check_reference(root, job['outputs']['fw1_boot.bin']).read_bytes()
assert sector == (root / '2e00/second/sector.bin').read_bytes() == (root / 'tail.bin').read_bytes()
assert len(sector) == 512 and len(full) == 4096 and full == prefix + sector
assert all(byte == 255 for byte in full)
assert hashlib.sha256(full).hexdigest() == 'f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6'
public = Path('docs/evidence/final-boot-sector-live-2026-10-14')
assert (public / 'fw1_boot.bin').read_bytes() == full
assert (public / 'sector2e00.bin').read_bytes() == sector
print('original final pair/aggregate verified; raw backup partition4096/4096; restore untested')
PY
```
