# Same-owned-file scratch reuse stops at missing uptime evidence

2026-10-14 unique fixed scratch reuse trial **failed**. Its read-only baseline completed: actual existing4096-byte object exactly matched original owned-file baseline SHA256 `a2f7c04b495717e5b851f911f6dbf24471dfbde567c8124da65eb8c9e43b446d`. First same-path overwrite was **attempted**, then mandatory uptime evidence check failed: `ValueError: Requires one complete actual uptime F0 line after its command`.

[Frozen receipt](../evidence/scratch-reuse-live-2026-10-14.json) · [original static plan](nor-scratch-reuse-plan.md) · [static candidate evidence](../evidence/nor-scratch-reuse-static-2026-10-14.json) · [preceding complete backup-slot dump](final-boot-sector-live-2026-10-14.md).

Independent review imported the125-file pre-I/O source snapshot. Full source gate replayed original known boot0/recovery pair and its complete owned4096-byte file, both independent512-byte oracles,36 pinned static image regions, latest successful final-sector aggregate and its nested3584-byte/checkpoint/DEFAULT-RAM-control chain. Fixed target, owned Call path, two distinct nonces, required59589 state, original plan reference, operation recipes and chronology all match. Current existing object was independently downloaded and matched before first overwrite; original ownership alone was not treated as current content proof.

| Actual stage | Independently verified result |
|---|---|
| Initial GATT/identity/inventory | Complete setup; required owned state; fixed scratch/nonces absent from visible inventory |
| Read-only baseline | Complete4096-byte Boyi download; original hash equality; actual EOF SLOW then identity barrier; original `ok=true/live_complete=true` |
| First boot0 overwrite | Exact PREPARE→START→uptime-with-nonce→boot0 `fread`→same-owned-path4096-byte `dumpbuf`→STOP; six ATT-confirmed commands/six ACK, one F1, zero pending bytes |
| Mandatory uptime evidence | **Zero F0 frames / zero F0 payload bytes / zero complete uptime lines**; exact original error reproduced from original stream |
| First transfer/barrier | No download request, file, post-download identity, retained candidate or freshness/oracle verification |
| Second recovery overwrite | No command, producer, SD write, download or state barrier; directory empty |
| Overall final identity/close | Actual identity unchanged59589; sole normal local disconnect status0/reason0x16 after final ATT |

All original Actions bytes were fully parsed and consumed. No F0 background text was dropped; none was present. Six ACKs/F1 prove exact transport-level sequence and session completion, **not** successful uptime output, producer content, SD update or restoration. First `producer_attempted=true/sd_write_attempted=true` remains an attempt record. Failure occurred immediately after completed Actions, before waiting for a new FAST transaction or sending further normalization/download commands. First and second directories are empty. Missing F0 does not establish that uptime failed to execute; no unique firmware root cause is claimed.

Actual parameter path: exactly three complete transactions, zero pending. Startup remote FAST6..12/0/500 settles12 (request105, accept107, command108, status109, update111); baseline host6/6/0/500 CE1/1 settles6 (113/114/115); actual EOF SLOW32..48/4/600 settles48 (request138, accept141, command142, status143, update145). Original timestamps and HCI record order bind normalization, exclusive baseline transfer191.482ms, EOF settlement and subsequent identity. No post-first-Actions FAST/host/SLOW transaction occurred. DEFAULT was not exercised in this trial.

Capture SHA256 `82daa2ab80229a16326b4e646352e62ec58372b0155b004e0290301ac24a1010`:12003 bytes,192 HCI records,107 ATT packets. Every host ATT packet binds exactly within its direction, GATT proof reconstructs, all transaction spans consume original ATT, host timestamps remain monotonic, status ledger rebuilds to0 events. ATT partition: setup `[0,34)`, initial identity `[34,40)`, inventory `[40,55)`, baseline transfer `[55,76)`, baseline identity `[76,82)`, first Actions `[82,101)`, final identity `[101,107)`. Final ATT ends at HCI188; normal disconnect is HCI191. Passive close observation completes2.159760s after close completion, within8s; original monitor exited0 after SIGINT.

Latest actual identity exactly equals initial and baseline-after identities: owned/unbound, FW010004, NOTE/idle, charging, battery100, **free59589MiB**. Read-only comparison allows and observes zero capacity decrease; remaining raw state fields equal. This does not establish current scratch contents: no post-overwrite object download exists. Original scratch restoration, confirmed replacement, and unchanged content all remain unproven.

Zero new filenames, zero new NOR coverage, no NOR flash write. Ubuntu cohort remains70 download-confirmed + one older device-declared without download + one historical possible, maximum72; no deletion. Previous independently captured4096-byte `fw1_boot` backup-slot dump remains valid historical evidence (`f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6`). It is allFF without an independent content oracle; neither this failure nor earlier dump demonstrates recovery flashing, restoration or post-restore boot.

Original job ran `05:36:33.093186Z`–`05:36:51.118881Z`. Manifest SHA256 `74fb7c169d0133fd266fb1630f0646d251b813dc61cfc11c423baaaa1bc7af46` declares creation `05:36:26.892184Z`, before plan/job/I/O. All125 archived source and98 archived test lengths/hashes pass. Root recorded1766 tests,159 subtests and successful build; those counts are manifest claims from root's pre-I/O execution, not this review independently rerunning the full suite. Archived source consistency and chronology are verified; future/current source equality is not claimed. Static candidate identity does not establish live execution of every uptime region.

384 checked private input files retained identical hashes across this review. Raw ATT/HCI, rings, identity, inventory and nonces remain private; receipt contains hash references and bounded summaries. No new public binary was created. Original top-level/first/second flags remain false; baseline remains true and its checkpoint correctly retains aggregate false. Ordinary full replay still rejects the original failed experiment, and no historical failure is reclassified.

Offline reproduction from repository root, private originals available; no device I/O:

```sh
PYTHONPATH=artifacts/scratch-reuse-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib
import json
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from rcominote.experiments import scratch_reuse_probe as R
from rcominote.experiments import scratch_reuse_contract as C
from rcominote.experiments import scratch_reuse_audit as V
from rcominote.experiments import scratch_reuse_sources as S
from rcominote.experiments import scratch_reuse_parser as F
from rcominote.experiments import dual_audit as A
from rcominote.experiments import dual_hci
from rcominote.experiments import param_window as P
from rcominote.experiments import startup_policy as startup
from rcominote.experiments import status_event as E
from rcominote.experiments import boot_tail_job as J
from rcominote.experiments import window_ram_audit as common
from rcominote.experiments.sd_bootstrap import verify_state

root=Path('artifacts/scratch-reuse-20261014')
image=Path('artifacts/mapped-system-20261012.bin')
sha=lambda b:hashlib.sha256(b).hexdigest()
ref=lambda p:{'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}
report=json.loads((root/'report.json').read_bytes())
plan=json.loads(J.check_reference(root,report['plan']).read_bytes())
manifest_path=root/'source-snapshot/manifest.json'
manifest=json.loads(manifest_path.read_bytes())
assert 'source-snapshot/src' in R.__file__
assert ref(root/'report.json')['sha256']=='58da00f07685e90b564b1f26f6046fdefd724cf25bd0ae616c13bcf49d2be280'
assert ref(manifest_path)['sha256']=='74fb7c169d0133fd266fb1630f0646d251b813dc61cfc11c423baaaa1bc7af46'
assert len(manifest['source_files'])==125 and len(manifest['test_files'])==98
files={root/'report.json',root/'plan.json',root/'session.btsnoop',manifest_path,image}
def refs(value):
 if isinstance(value,dict):
  if {'file','bytes','sha256'}<=value.keys():
   p=Path(value['file']); assert ref(p)['bytes']==value['bytes'] and ref(p)['sha256']==value['sha256']; files.add(p)
  if 'directory' in value and Path(value['directory']).is_dir():
   files.update(p for p in Path(value['directory']).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
  for v in value.values():refs(v)
 elif isinstance(value,list):
  for v in value:refs(v)
refs(plan['sources'])
files.update(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for entry in manifest['source_files']+manifest['test_files']:
 p=manifest_path.parent/entry['path'];b=p.read_bytes();assert len(b)==entry['bytes'] and sha(b)==entry['sha256']; files.add(p)
original_hashes={str(p.resolve()):sha(p.read_bytes()) for p in files}
R.plan_gate(report,plan,root)
baseline=C.source_gate(plan,image)
J.time_order(plan['sources']['state_parent']['ended_at'],manifest['created_at'],plan['planned_at'],report['started_at'],report['baseline']['started_at'],report['baseline']['ended_at'],report['operations'][0]['started_at'],report['operations'][0]['ended_at'],report['ended_at'])
assert report['ok'] is False
warm=report['baseline'];first,second=report['operations']
assert warm['ok'] is True and warm['live_complete'] is True
assert all(o['ok'] is False and o['live_complete'] is False for o in (first,second))
assert report['error']==first['error']==report['capture_error']=='ValueError: Requires one complete actual uptime F0 line after its command'
try:R.replay(root,image)
except ValueError as ex:assert str(ex)=='Original failed scratch experiment cannot be promoted by replay'
else:raise AssertionError('Failed report promoted')
raw=(root/'session.btsnoop').read_bytes();observed=P.inspect(raw,link=report['transport']['link'],final=True)
assert report['hci_capture']=={'bytes':len(raw),'sha256':sha(raw),'records':observed['records']}
assert len(raw)==12003 and observed['records']==192 and not observed['pending']
assert report['att_hci_binding']==dual_hci.bind(report,raw)=={'verified':True,'packets':107,'comparison':'exact within each direction'}
assert report['gatt_proof']==A.setup(report)
assert len(report['att_packets'])==107
assert all(type(x['monotonic_ns']) is int for x in report['att_packets'])
assert all(a['monotonic_ns']<=b['monotonic_ns'] for a,b in pairwise(report['att_packets']))
assert report['monitor_exit']==0 and report['monitor_stop']=={'signal':'SIGINT','requested':True,'delivery':'sent'}
_,events=E.verify(report);assert events['events']==0
wire=common.wire_positions(report,raw)
tx=observed['transactions'];assert len(tx)==3
assert report['startup_settlement']==tx[0]
assert report['startup_classification']==startup.classify(tx[0])
assert report['startup_classification']['mode']=='fast'
assert V.inventory(report,plan)==report['listed_count']
E.bridge(report,report['setup_end'],report['before_span'][0]);A.identity(report,report,'before')
assert report['predecessor_state_verification']==verify_state(plan['expected_before'],report['before'],sd_write=False)
assert warm['before']==report['before']
assert all(k not in warm for k in ('actions_start','producer','sd_write_attempted'))
E.bridge(report,report['file_list_span'][1],warm['download_start'])
assert V.download(report,warm,root)==baseline
assert len(baseline)==4096 and sha(baseline)==S.BASELINE_SHA
F.absent(baseline,[s['nonce'] for s in plan['operations']])
V.baseline_window(report,warm,wire,*tx)
V.barrier(report,warm,report['before'],writing=False)
checkpoint=json.loads((root/'baseline/checkpoint.json').read_bytes())
assert checkpoint['baseline']==warm and checkpoint['ok'] is False
assert checkpoint['att_packets']==report['att_packets'][:warm['verified_end']]
assert all(op['ok'] is False and 'writes' not in op for op in checkpoint['operations'])
for slot,op in zip(plan['operations'],report['operations'],strict=True):assert all(op[k]==v for k,v in slot.items())
assert first['before']==warm['after']
assert first['producer_attempted'] is True and first['sd_write_attempted'] is True
assert all(k not in first for k in ('download_start','download_bytes','after','verification','actions_verification','pre_download_fast'))
E.bridge(report,warm['verified_end'],first['actions_start'])
actionproof=A.action_frames(report,first,expected=C.recipe(first))
assert first['ack_count']==6 and first['end_received'] is True and first['pending_hex']==''
assert not any(f['command']==0xf0 for f in first['frames'])
try:V.actions(report,first)
except ValueError as ex:assert str(ex)=='Requires one complete actual uptime F0 line after its command'
else:raise AssertionError('Missing uptime accepted')
assert all(k not in second for k in ('started_at','writes','actions_start','producer_attempted','sd_write_attempted','download_start','download_bytes','after','verification'))
assert not list((root/'first').iterdir()) and not list((root/'second').iterdir())
E.bridge(report,first['actions_end'],report['after_span'][0]);A.identity(report,report,'after')
E.bridge(report,report['after_span'][1],len(report['att_packets']))
assert report['before']==warm['after']==report['after']
assert report['state_verification']==verify_state(warm['after'],report['after'],sd_write=False)
assert report['after']['device']['free_capacity']==59589
assert report['before_span']==[34,40] and report['file_list_span']==[40,55]
assert warm['download_start']==55 and warm['download_end']==76 and warm['after_span']==[76,82]
assert [first['actions_start'],first['actions_end']]==[82,101] and report['after_span']==[101,107]
for op in (warm,first):assert (datetime.fromisoformat(op['ended_at'])-datetime.fromisoformat(op['started_at'])).total_seconds()<18
assert (datetime.fromisoformat(report['ended_at'])-datetime.fromisoformat(report['started_at'])).total_seconds()<60
(ds,)=observed['disconnects'];assert ds['status']==0 and ds['reason']==0x16 and ds['record']==191 and ds['record']>max(p[1] for p in wire)
assert report['disconnect_observation']=={'observed':True,'event':ds,'max_wait_seconds':8}
a,b,c=[report[k] for k in ('close_requested_us','close_completed_us','disconnect_observed_us')]
assert a<=b<=c<=b+8_000_000 and a<=ds['timestamp_us']<=b+8_000_000
assert {p:sha(Path(p).read_bytes()) for p in original_hashes}==original_hashes
print('failed flags retained; baseline/full-wire/uptime absence/latest-state/source chronology verified')
PY
```
