# New fixed three-slot job: startup tuple mismatch, no producer executed

2026-10-14 new fixed job stopped at first slot `0x2a00`, before any Actions. **Zero new verified bytes, zero producer executions, zero SD-write attempts or new scratch files.** `fw1_boot` coverage remains **2560/4096 bytes**, `[0x2000,0x2a00)`. Neither partition nor tail was assembled; original aggregate and pair flags remain false.

[Frozen receipt](../evidence/status-remaining-live-2026-10-14.json) · [preceding successful2800 checkpoint](status-boot-tail-live-2026-10-14.md) · [preceding read-only health trial](status-link-health-2026-10-14.md).

Immutable plan fixed offsets `2a00,2c00,2e00`, six fresh distinct scratch nonces, maximum three connections/six producers/six SD files, and fail-stop without retry/resume. Independent offline review imported this job's archived package sources and verified complete previous checkpoint summary against the plan, all historical/modern prefix sources, actual target/nonce/parent/policy bindings, predecessor state and chronology. Previous2560-byte prefix SHA256 remains `2b6e99ee899e1515e0cc44b220424cd9da6906b39490504bdcca2236755db51c`.

This failure occurred **after successful GATT discovery, initial identity and file list**, at the fixed startup FAST parameter gate. Actual complete remote request was `24..40/latency0/timeout500`; expected request was `6..12/0/500`. Controller successfully applied `36/0/500`; zero parameter transactions remain pending. Calling the archived gate on the actual parsed transaction independently reproduces `ValueError: Observed parameter transaction differs from the next fixed experiment stage`. No observed tuple was silently accepted or replaced.

| Actual stage | Evidence |
|---|---|
| Connection | Successful initial parameters12/0/500, HCI record18 |
| GATT | Complete setup, ATT `[0,34)` |
| Initial identity | Complete actual three-request/reply exchange, ATT `[34,40)`; strict expected-state match |
| File list | Complete actual transaction, ATT `[40,55)`; planned nonces absent |
| Startup request | Remote L2CAP CID5, identifier5; request record104, acceptance106 |
| Controller settlement | Update command107, successful command status108, successful applied36/0/500 update110 |
| Fixed gate | Rejects unexpected request24..40/0/500 before first `Actions.run` |
| Final identity | Cleanup succeeds, ATT `[55,61)`, HCI records111..119, after settlement110 |
| Later slots | `2c00,2e00` host directories contain no files; no execution |

Capture:4995 bytes,119 monitor records,61 ATT packets. Every retained host ATT packet binds exactly to HCI within direction; complete GATT and both identity summaries were independently rebuilt from actual bytes. One complete remote parameter transaction, zero pending, zero host-origin normalization transactions, zero actual status events. Owned monitor received SIGINT and exited0. No disconnect appears in this capture; later close/physical-worker state is not established.

**Latest actual identity is this failed2a00 cleanup's final read**, after the unexpected parameter settlement: owned/unbound, FW010004, NOTE/idle, charging, battery100, free59590MiB. It exactly equals initial identity, immutable expected predecessor, successful new2800 final state and preceding health trial's final state. Read-only state proof allows zero capacity decrease and passes. Thus state evidence advances to this final identity despite zero NOR coverage and failed original pair; no success flag was changed.

Initial connection12/0/500 differs from earlier48/4/600 observations. Device-info identity equality does not imply identical BLE connection parameters. This capture proves the observed sequence and fixed-gate mismatch; it does not establish firmware selector causality or permanent repair of the earlier discovery timeout. Prior health success correctly established communication at its own observation time; this later attempt also completed GATT/identity and then encountered a different gate failure.

Job ran `03:53:45.645208Z`–`03:54:02.232197Z`; first slot ran `03:53:51.841052Z`–`03:54:02.231614Z`. Source snapshot contains113 files, all archived lengths/hashes verified against manifest `737a353e0b97be16b918a43b9119665270692d2bbcc23cc22c52cb300d22364a`. Pre-I/O record created `03:53:37.067832Z`, before plan/job, records1516 tests plus159 subtests, successful build and health preflight. Independent review reran the private health probe's offline `audit`, checked probe source SHA against its recorded SHA, and verified health report/HCI plus final-state equality. No live main/capture function ran during review. No future/current source equality is claimed.

Original job SHA256: `3f98ac2ba0ffa9edad7e0f02a29fec24d7623fac9b20a116454e9be8ad74eedf`. First2a00 report SHA256: `03165ecada9f4d8bf178eec4b8e94352b0f5f34d0b4e8fdc3d34b3711cc08be6`. Capture SHA256: `bc8a88ab18853c551bbe34c9330cd4975370493e449ee6bfcb007721729401fe`.194 checked input files retained identical hashes across review. Full HCI/ATT, device raw identity, audio inventory and scratch names remain private.

Remaining unverified range: `[0x2a00,0x3000)`,1536 bytes. Both original aggregate and first-pair replay reject failure. Prepared nonces are not created files; first/second export directories are empty, later slots unexecuted, and no `tail.bin` or `fw1_boot.bin` exists. No full NOR backup, restoration or flashing guarantee follows.

Offline reproduction from repository root, private originals available; no device I/O:

```sh
PYTHONPATH=artifacts/status-remaining-20261014/source-snapshot/src uv run python - <<'PY'
import json
from pathlib import Path
from rcominote.experiments import status_remaining_job as J
from rcominote.experiments import status_remaining_checkpoint as C
from rcominote.experiments import dual_audit as A
from rcominote.experiments import param_window as P
from rcominote.experiments import window_ram_audit as W
from rcominote.experiments import window_ram_probe as R

root = Path('artifacts/status-remaining-20261014')
image = Path('artifacts/mapped-system-20261012.bin')
assert 'source-snapshot/src' in C.__file__
job = json.loads((root / 'report.json').read_bytes())
plan = json.loads(J.W.J.check_reference(root, job['plan']).read_bytes())
J.validate_plan(plan)
prefix, state, summary = C.verify(Path(plan['checkpoint_directory']), image)
assert summary == plan['checkpoint'] and len(prefix) == 2560
report = json.loads((root / '2a00/report.json').read_bytes())
assert A.setup(report) == report['gatt_proof']
A.identity(report, report, 'before')
A.identity(report, report, 'after')
W.file_list(report)
assert report['before'] == report['after'] == report['expected_before'] == state
raw = (root / '2a00/session.btsnoop').read_bytes()
assert J.W.N.dual_hci.bind(report, raw) == report['att_hci_binding']
observed = P.inspect(raw, link=report['transport']['link'], final=True)
assert len(observed['transactions']) == 1 and not observed['pending']
transaction = observed['transactions'][0]
assert P.parameters(transaction['request']) == (24, 40, 0, 500)
try:
    R.expected(transaction, 'remote', R.FAST)
except ValueError as error:
    assert 'ValueError: ' + str(error) == report['error']
else:
    raise AssertionError('Unexpected startup tuple accepted')
for replay, directory in ((J.replay, root), (J.W.N.replay, root / '2a00')):
    try:
        replay(directory, image)
    except ValueError:
        pass
    else:
        raise AssertionError('Original failed evidence promoted')
print('latest actual free59590; startup mismatch reproduced; coverage unchanged')
PY
```
