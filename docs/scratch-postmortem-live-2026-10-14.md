# Read-only postmortem confirms retained same-file boot0 update

2026-10-14 unique fixed **read-only postmortem succeeded**. Complete4096-byte download of the original owned scratch object has SHA256 `3621a69cc9215acf435ecab311088f53e8eb65d28f3d3a80cce6aca892560360`, different from the immediately pre-overwrite baseline `a2f7c04b495717e5b851f911f6dbf24471dfbde567c8124da65eb8c9e43b446d`. Its uniquely bound first-attempt nonce/current dump chain yields512 boot0 bytes matching independent oracle SHA256 `72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec`.

[Frozen receipt](evidence/scratch-postmortem-live-2026-10-14.json) · [original failed scratch trial](scratch-reuse-live-2026-10-14.md) · [original fixed plan/static candidate](nor-scratch-reuse-plan.md) · [previous complete backup-slot dump](final-boot-sector-live-2026-10-14.md).

This later independent read confirms that the earlier first same-path overwrite attempt updated retained object content. **Original trial remains failed**: six ACK/F1 but zero F0 never satisfied its mandatory actual uptime-line gate; its first download/barrier did not occur, and second recovery target was never attempted. Later content evidence does not rewrite original flags or complete the planned two-target reuse control. No retry or additional producer/write was performed.

Independent review imported128-file pre-I/O source snapshot and reran full original postmortem replay. Exact failed-parent report/plan/HCI pins, original complete baseline, first six-ACK/zero-F0 partial wire, latest actual59589 identity and normal disconnect replay independently. Its original source gate also replays known boot0/recovery ownership and both independent oracles,36 static image regions, successful final4096-byte backup aggregate and nested3584-byte/control/state chain. Original plan binds failed parent, fixed owned path, first nonce/target, policy, initial state and chronology before new I/O.

| Layer | Actual result |
|---|---|
| New runtime activity | One connection, one complete4096-byte download; zero Actions, producers, SD writes or new filenames |
| Startup/transfer | Strict actual FAST→host interval6→actual EOF SLOW; zero pending negotiations |
| Raw retained content | Different from old complete baseline; one new physical exact dump marker; first nonce absent from baseline and unique in current circle |
| Known candidate | Exact boot0 status/producer/current dump chain,32 canonical rows,512 bytes; independent oracle compared only after parsing |
| Original failure | Top/first/second remain false, baseline remains true; original uptime F0 contract still fails |
| State/close | Initial/immediate/final identities exactly equal owned59589; sole normal local disconnect after all ATT |

Physical ring proof: nonce echo `[2846,2891)`, status `[2925,2967)`,32-row text `[2973,4893)` crossing4096-byte wrap, current boot0 producer `[817,857)`, current same-path dump `[878,959)`. No historical dump marker survives in current circle. Difference-based contiguous offset0 write-prefix lower bound is4096 bytes, covering the complete critical chain; this does not assert that every byte individually changed. The independent oracle did not select a candidate or resolve ambiguity.

Actual nonce→status gap `[2891,2925)` is34 bytes: LF plus exact33-byte composer notice, permitted background before current status. Actual producer→dump gap `[857,878)` is LF plus logging prefix, with **no composer notice there**. Saved parser `composer_fps2=false` describes this latter gap only; it does not mean composer output was absent throughout the ring. Freshness grammar and original raw bytes replay without editing evidence or silently dropping background.

Read-only transport and content verdicts are separate original layers. `readonly-checkpoint.json` preserves aggregate `ok=false`, completed operation `ok=true/live_complete=true`, full transport proof and no content verdict. Final original report is true only after strict content parser and independent oracle comparison succeed. Both checkpoint and final report independently match original data; no raw ring, new sector or HCI binary is published here. The candidate matches [already published independent boot0 evidence](evidence/boot-complete-2026-10-12/raw.bin); receipt retains private output/hash references only.

Capture SHA256 `02e600215d0b2259a3604c86b4dd104abaac7703beb8c35325dd6563507d85b4`:10928 bytes,167 HCI records,89 ATT packets, complete GATT setup and exact directional binding of every host packet. Original ATT spans consume all traffic: setup `[0,34)`, initial identity `[34,40)`, inventory `[40,55)`, download `[55,77)`, immediate identity `[77,83)`, final identity `[83,89)`. Status ledger reconstructs to0 events. Exclusive transfer176.231ms stays inside completed host interval6/0/500; actual EOF SLOW settles before immediate identity.

Exactly three complete parameter transactions: startup remote FAST6..12/0/500 settles12; host6/6/0/500 CE1/1 settles6; remote EOF SLOW32..48/4/600 settles48. Full remote request/accept, HCI command/status/update and original timestamp/record ordering pass; DEFAULT was not exercised. Final ATT ends at HCI163, sole disconnect is HCI166 status0/reason0x16. Passive close observation2.165365s after close completion stays within8s. Owned monitor exits0 after SIGINT.

Latest actual identity remains owned/unbound, FW010004, NOTE/idle, charging, battery100, **free59589MiB**, exactly equal failed parent's final state and all new identity windows. Read-only comparison allows and observes zero capacity decrease with other raw fields equal. No new filenames/deletions: cohort70 download-confirmed + one older device-declared without download + one historical possible, maximum72. Zero new unique NOR coverage; known boot0 bytes are an existing independent control. Previous4096-byte allFF backup-slot dump remains historical evidence without an independent content oracle; no NOR flash write, restoration or post-restore boot was tested.

Original new job ran `05:54:09.054681Z`–`05:54:29.433494Z`; complete read-only stage `05:54:25.827789Z`–`05:54:26.889708Z`. Manifest SHA256 `b531d4ca4458842106f5f9632946c1b01521fd479b9eb8d5ef2b042c62491242` declares creation `05:54:02.283636Z`, before plan/job/I/O. All128 archived source and101 test lengths/hashes verify. Manifest records root's1833 tests,159 subtests and successful build; these are root's pre-I/O execution claims, not this review independently rerunning the full suite. Archived-source consistency and original chronology pass; future/current source equality is not claimed.

622 checked private input files retained identical hashes before/after review, including failed parent and prior frozen receipt. Raw HCI/ATT, identity, inventory, ring and nonce remain private. No source, original artifact, prior proof, canonical index or device was changed.

Offline reproduction from repository root, private originals available; no device I/O:

```sh
PYTHONPATH=artifacts/scratch-postmortem-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib
import json
from pathlib import Path
from rcominote.experiments import scratch_postmortem_probe as P

root=Path('artifacts/scratch-postmortem-20261014')
image=Path('artifacts/mapped-system-20261012.bin')
sha=lambda b:hashlib.sha256(b).hexdigest()
ref=lambda p:{'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}
assert 'source-snapshot/src' in P.__file__
report=json.loads((root/'report.json').read_bytes())
plan=json.loads(P.J.check_reference(root,report['plan']).read_bytes())
manifest_path=root/'source-snapshot/manifest.json'
manifest=json.loads(manifest_path.read_bytes())
assert ref(manifest_path)['sha256']=='b531d4ca4458842106f5f9632946c1b01521fd479b9eb8d5ef2b042c62491242'
assert len(manifest['source_files'])==128 and len(manifest['test_files'])==101
files={image,root/'report.json',root/'plan.json',manifest_path}
refs=[]
def collect(value):
 if isinstance(value,dict):
  if {'file','bytes','sha256'}<=value.keys():
   p=Path(value['file']);assert ref(p)['bytes']==value['bytes'] and ref(p)['sha256']==value['sha256'];files.add(p)
   if value not in refs:refs.append(value)
  if 'directory' in value and Path(value['directory']).is_dir():
   files.update(p for p in Path(value['directory']).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
  for v in value.values():collect(v)
 elif isinstance(value,list):
  for v in value:collect(v)
collect(plan['parent'])
files.update(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for entry in manifest['source_files']+manifest['test_files']:
 p=manifest_path.parent/entry['path'];data=p.read_bytes();assert len(data)==entry['bytes'] and sha(data)==entry['sha256'];files.add(p)
prior_receipt=Path('docs/evidence/scratch-reuse-live-2026-10-14.json')
assert sha(prior_receipt.read_bytes())=='ead31d037057752ff1f720337724125f158ee72ae82e12b6d645dddfaaaf76db'
files.add(prior_receipt)
original_hashes={str(p.resolve()):sha(p.read_bytes()) for p in files}
P.plan_gate(report,plan,root)
previous=P.C.source_gate(plan,image)
proof=P.replay(root,image)
assert proof['readonly']==report['readonly_proof'] and proof['content']==report['content_verification']
P.J.time_order(plan['parent']['ended_at'],manifest['created_at'],plan['planned_at'],report['started_at'],report['operation']['started_at'],report['operation']['ended_at'],report['ended_at'])
assert report['ok'] is True and report['operation']['ok'] is True
assert all(proof['readonly'][k]==0 for k in ('actions','producers','sd_writes','new_files','new_raw_nor_coverage_bytes'))
assert report['sd_write_attempted'] is False
op=report['operation'];data=(root/'retained/download.bin').read_bytes()
assert len(data)==4096 and data!=previous
assert sha(data)=='3621a69cc9215acf435ecab311088f53e8eb65d28f3d3a80cce6aca892560360'
assert sha(previous)=='a2f7c04b495717e5b851f911f6dbf24471dfbde567c8124da65eb8c9e43b446d'
content=proof['content'];fresh=content['freshness'];sector=bytes.fromhex(content['sector_hex'])
assert len(sector)==512 and sha(sector)=='72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec'
assert sector==(root/'retained/sector.bin').read_bytes()
oracle=content['oracle'];oracle_raw=Path(oracle['source']['file']).read_bytes()
assert oracle_raw[oracle['slice'][0]:oracle['slice'][1]]==sector
assert fresh['nonce_span']==[2846,2891] and fresh['status_span']==[2925,2967]
assert fresh['rows_span']==[2973,4893] and fresh['producer_span']==[817,857] and fresh['dump_span']==[878,959]
assert not fresh['historical_dump_spans'] and fresh['difference_proven_written_prefix_bytes']==4096
assert fresh['new_physical_dump_required'] and fresh['critical_chain_inside_written_prefix']
assert fresh['oracle_used_to_select_chain'] is False and fresh['composer_fps2'] is False
assert content['original_trial_ok'] is False and content['reuse_pair_complete'] is False
assert content['new_raw_nor_coverage_bytes']==0
# Composer background occurs after nonce, separately from the producer->dump gap.
assert data[2891:2925]==b'\n'+P.C.F.F.COMPOSER_FPS2
assert len(P.C.F.F.COMPOSER_FPS2)==33
assert data[857:878]==b'\n'+P.C.F.F.LOG_PREFIX
assert report['before']==op['before']==op['after']==report['after']==plan['expected_before']
assert report['after']['device']['free_capacity']==59589
assert report['state_verification']['free_capacity_decrease']==0
checkpoint=json.loads((root/'readonly-checkpoint.json').read_bytes())
assert checkpoint['ok'] is False and checkpoint['operation']==op
assert checkpoint['readonly_proof']==proof['readonly'] and checkpoint['att_packets']==report['att_packets']
assert 'content_verification' not in checkpoint and 'content_error' not in checkpoint
parent=json.loads((Path(plan['parent']['directory'])/'report.json').read_bytes())
assert parent['ok'] is False and parent['baseline']['ok'] is True
assert all(o['ok'] is False and o['live_complete'] is False for o in parent['operations'])
assert not any(f['command']==0xf0 for f in parent['operations'][0]['frames'])
assert parent['error']=='ValueError: Requires one complete actual uptime F0 line after its command'
assert plan['parent']['nonce']==plan['nonce']==parent['operations'][0]['nonce']
raw=(root/'session.btsnoop').read_bytes()
observed=P.C.P.inspect(raw,link=report['transport']['link'],final=True)
assert len(raw)==10928 and observed['records']==167 and len(observed['transactions'])==3 and not observed['pending']
assert len(report['att_packets'])==89
assert report['hci_capture']['sha256']=='02e600215d0b2259a3604c86b4dd104abaac7703beb8c35325dd6563507d85b4'
wire=P.C.common.wire_positions(report,raw)
assert len(wire)==89 and report['att_hci_binding']==P.C.dual_hci.bind(report,raw)
assert report['before_span']==[34,40] and report['file_list_span']==[40,55]
assert [op['download_start'],op['download_end']]==[55,77] and op['after_span']==[77,83] and report['after_span']==[83,89]
assert report['startup_classification']['mode']=='fast'
(disconnect,)=observed['disconnects']
assert disconnect['reason']==0x16 and disconnect['status']==0 and disconnect['record']==166
assert disconnect['record']>max(p[1] for p in wire)
assert {p:sha(Path(p).read_bytes()) for p in original_hashes}==original_hashes
print('archived full readonly/content replay passed; retained boot0 update confirmed; old trial still failed')
PY
```
