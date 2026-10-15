# Controlled fw1_boot job: verified2a00/2c00, then pre-ATT features failure

2026-10-14 fixed three-slot job independently verified raw `0x2a00` and `0x2c00`, adding **1024 unique bytes**. Cumulative `fw1_boot` coverage: **3584/4096 bytes**, `[0x2000,0x2e00)`. Only `[0x2e00,0x3000)`,512 bytes, remains unverified. Original aggregate job failed at `2e00`; that slot contributed zero bytes/files. **No `tail.bin` or `fw1_boot.bin` was assembled.**

[Frozen receipt](evidence/startup-boot-tail-live-2026-10-14.json) · actual [sector2a00](evidence/startup-boot-tail-live-2026-10-14/sector2a00.bin) / [sector2c00](evidence/startup-boot-tail-live-2026-10-14/sector2c00.bin) · [preceding DEFAULT/RAM control](startup-ram-default-live-2026-10-14.md) · [Linux features-error mapping](linux-le-features-error-2026-10-14.md).

Independent offline review imported the119-file archived source snapshot, replayed the complete old2560-byte source/state chain and exact successful RAM-control parent, and checked immutable plan, checkpoints, targets, six planned fresh nonces, parents, policy, predecessor states and chronology. Both completed NOR pairs pass their **full original** Actions/ATT/HCI/parameter/state/freshness/pair replay. Terminal failure remains failed; successful checkpoints add coverage individually.

| Actual slot | Original evidence | Original result | Unique coverage increment |
|---|---|---|---|
| `0x2a00` | Two separate fixed-sector producers/nonces; two complete4096-byte ring downloads;32 fresh rows per read; second requires previous dump; actual identity barriers | All original success flags true; full pair replay passes |512 bytes |
| `0x2c00` | Same independent complete fixed-target evidence, own actual captures and nonces | All original success flags true; full pair replay passes |512 bytes |
| `0x2e00` | HCI connection event followed by failed remote-features completion; zero ACL/ATT, GATT, identity, Actions, producer or SD-write activity | Original pair/aggregate failed; empty export directories |0 |

Successful2a00 capture:18648 bytes,255 HCI records,148 ATT packets. Successful2c00 capture:18676 bytes,256 HCI records,148 ATT packets. Complete host/wire binding passes for both. Each has six complete parameter transactions, zero pending: startup FAST, first host normalization/SLOW, mandatory second FAST, second host normalization/SLOW. Each first Actions has zero additional pre-download FAST transactions; second has exactly one. Both downloads independently verify interval6/latency0/timeout500 and actual SLOW settlement before actual identity barriers. Both monitor exits0 follow owned SIGINT; both actual status ledgers contain zero events.

**Both new NOR connections actually observed startup FAST, not DEFAULT.** Explicit FAST-or-DEFAULT admission was enabled and its exact successful control parent replayed, but DEFAULT behavior was observed in the preceding RAM control only. These two successful NOR captures therefore do not establish a live DEFAULT-startup NOR execution. No failed receipt was relabeled or silently widened.

Public sectors were copied independently from this job's **actual2a00/first/sector.bin** and **actual2c00/first/sector.bin**. Each is512 bytes, allFF, and equals its own second independently produced sector. Both SHA256 values are `9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d`; equal hashes do not substitute address/producer provenance or permit copying one target in place of the other. There is no independent content oracle. Two reads count as one512-byte increment per address.

Original verified2560-byte prefix SHA256 remains `2b6e99ee899e1515e0cc44b220424cd9da6906b39490504bdcca2236755db51c`, grounded in historical2000 double coverage and original successful2200/2400/2600/2800 pairs. Adding only these two actual sectors in address order gives3584-byte SHA256 `92feb2e31d43ffb2ce5935a4a58559c35aa422cf7e6f829ddaa5aef1a69190c9`. This was verified in memory; no partial image was published as an assembled partition.

Failed2e00 capture:950 bytes,23 HCI records, **zero ACL/ATT**. Actual stages:

| HCI record | Observation |
|---|---|
|18|LE Enhanced Connection Complete, status0; alone does not establish a usable ATT socket/GATT session |
|21|LE Read Remote Features command, opcode `0x2016` |
|22|Command Status0; command accepted |
|23|LE Meta event code `0x3e`, subevent `0x04`, **payload failure status `0x3e`** |

Host report preserves `OSError: [Errno 38] LE ATT connect failed`. There was **no peripheral ATT Error Response or unsupported ATT command**: ATT never began. [Separate installed-module/static-source evidence](linux-le-features-error-2026-10-14.md) closes the Linux mapping from HCI status `0x3e` to default ENOSYS38. This explains the host error number; it does not establish why radio/controller/peer features exchange failed. Outer LE event code and inner failure status happen to share the value `0x3e` and have different meanings. No disconnect appears in this failed capture; none is invented.

Latest actual identity remains successful **2c00's final read**: owned/unbound, FW010004, NOTE/idle, charging, battery100, free59590MiB. Every actual2a00/2c00 initial, per-write and final identity equals its required predecessor; all four small SD exports show zero integer capacity decrease within their per-write allowance. Failed2e00 retains a prepared `expected_before`, but has no actual before/after identity. Device state after that failure is unknown.

Four new scratch files were independently downloaded and retained. Ubuntu cohort:68 download-confirmed, one earlier device-declared without download, one historical possible, maximum70. Planned2e00 nonces added zero attempted/confirmed files. No files were deleted.

Aggregate ran `04:46:04.582063Z`–`04:46:48.442899Z`;2a00 `04:46:10.522009Z`–`04:46:26.987071Z`;2c00 `04:46:27.232507Z`–`04:46:45.487122Z`;failed2e00 `04:46:45.728621Z`–`04:46:48.442735Z`. Both saved checkpoints exactly match immutable original job progress at their respective completion boundaries.

Source snapshot:119 distinct files; every archived length/hash matches manifest `f6289e63f29600a7b17497f88d9f82c446c23c4989d698c2b376018d49e99d11`. Record created `04:45:53.951704Z`, before plan/job/I/O, records1627 tests plus159 subtests, successful build and offline source/control/state preflight. This review verifies archived-source consistency and original acquisition chronology, not future equality with current source files.655 checked private input files retained identical hashes. Exact original job/pair/capture/checkpoint/source hashes are in receipt; full HCI/ATT/rings/raw identity/inventory/scratch nonces remain private.

Original aggregate and2e00 pair replay reject failure. Earlier failed jobs/pairs retain their failures; preceding RAM control adds no NOR coverage. No complete `fw1_boot`, full NOR backup, restoration/flashing guarantee, physical firmware-worker exit or hidden-queue clearing proof follows from these partial successes.

Offline reproduction from repository root, private originals available; no device I/O:

```sh
PYTHONPATH=artifacts/startup-boot-tail-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib
import json
from pathlib import Path
from rcominote.experiments import status_remaining_job as J
from rcominote.experiments.sd_bootstrap import verify_state

root = Path('artifacts/startup-boot-tail-20261014')
image = Path('artifacts/mapped-system-20261012.bin')
assert 'source-snapshot/src' in J.__file__
job = json.loads((root / 'report.json').read_bytes())
plan = json.loads(J.W.J.check_reference(root, job['plan']).read_bytes())
J.validate_plan(plan)
prefix, state, source = J.checkpoint.verify(Path(plan['checkpoint_directory']), image)
assert source == plan['checkpoint'] and len(prefix) == 2560
assert J.control_source.verify(Path(plan['control_parent']['directory']), image, source) == plan['control_parent']
assert job['ok'] is False and len(job['completed']) == 2
for completed, slot in zip(job['completed'], plan['slots'][:2], strict=True):
    label = slot['directory']
    report = json.loads(J.W.J.check_reference(root, completed['report']).read_bytes())
    assert report['expected_before'] == state
    assert report['predecessor_state_verification'] == verify_state(state, report['before'], sd_write=False)
    assert report['nor_offset'] == slot['nor_offset']
    assert [op['name'] for op in report['operations']] == slot['names']
    assert J.W.N.replay(root / label, image) == completed['verification']
    block = (root / label / 'first/sector.bin').read_bytes()
    assert len(block) == 512 and block == bytes([255]) * 512
    assert block == (root / label / 'second/sector.bin').read_bytes()
    assert block == Path(f'docs/evidence/startup-boot-tail-live-2026-10-14/sector{label}.bin').read_bytes()
    prefix += block
    state = report['after']
assert len(prefix) == 3584 and state['device']['free_capacity'] == 59590
assert hashlib.sha256(prefix).hexdigest() == '92feb2e31d43ffb2ce5935a4a58559c35aa422cf7e6f829ddaa5aef1a69190c9'
for replay, directory in ((J.replay, root), (J.W.N.replay, root / '2e00')):
    try:
        replay(directory, image)
    except ValueError:
        pass
    else:
        raise AssertionError('Original failed evidence promoted')
assert not (root / 'tail.bin').exists() and not (root / 'fw1_boot.bin').exists()
print('3584/4096 verified bytes; only2e00 remains; original aggregate still failed')
PY
```
