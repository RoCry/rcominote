# Four fresh physical NOR pairs25000–25800: live success, 2026-10-14

Frozen [metadata/source table](../evidence/paired-nor25000-four-live-2026-10-14.json); [actual newraw2048](../evidence/paired-nor25000-four-live-2026-10-14/nor25000-25800.bin), **SHA5cc9f32531c5c4fe543d63ea8e8896752d7f19c2c43d3d6b0dc05475a3191edb**, physical`[0x25000,0x25800)`. All four original fresh512 pairs/full wire/state/final disconnect gates passed before publication. Bytes copied directly in physical order from verified actual sectors; no fill/mapped/reencoding substitution or hash-based deduplication. Old [first4KiB](system-first4k-raw-live-2026-10-14.md)/raw4096 untouched, not regenerated. Unknown pages have no independent raw-byte oracle.

| Physical page | Actual512 SHA256 | Output byte offset | Difference-proven prefixes |
|---|---|---:|---|
|25000|5333a1d92559a32fe94bb1df84189b8f9e6cd19b18c54f1a9e8aa09e9ea716a9|0|4096/4096|
|25200|f58a386271ef1076f9290dbae487c1d2170d90ee3dfa652f066bb9f4cd6faccd|512|4096/**3827**|
|25400|325f5104a8f1512bd969df3b57a6266fc35afbe6a5557b13d39e763e17e55fcb|1024|4096/4096|
|25600|dcd122125237a09f4f679be49b3b80c54fcefd6b71c3bdb01740a73745c49d75|1536|4096/4096|

All critical currentnonce/status/32canonical rows/producer/dump chains lie inside each proven prefix; no padding exemptions. **25200second does not prove whole4096 overwritten.** Eight exact6ACK/F1/pending0 sessions, individually countedF0=0; producer→dump composer flagsF,T,F,T,F,F,F,T. Each connection actualstartupFAST then two actualFAST/host6/DL/EOF SLOW producer cycles, predecessor baseline4096/full identity and final normaldisconnect16. Whole727ATT/1269HCI,36complete transactions/0pending/status;4connections/12complete4096 downloads/8existing-file overwrites/0newfiles/deletions. All integer capacity observations59589 and other identity fields unchanged; cohort70confirmed+1olderdeclared+1historicalpossible=max72 unchanged. No firmware NOR write.

Latest real finalstate2026-10-14T10:17:24.815922Z FW010004/NOTEidle/unbound/charging100/free59589; current owned4096 **ring** SHA **`f6781e2966e47b548c6b2f0f5ccd2c48d19b97cd172c1d1b4dd7d7b08a28c2a8`**, distinct from publicraw2048. First baseline equals [W0 recovery](owned-file-recovery-live-2026-10-14.md)'s actuala5d8…5a48; each later baseline equals immediately prior second. Whole parent admission passes/history34. Original failedknown17-session and failedsystem4 remain rejected; no candidate promotion.

Actualjob10:15:41.851223Z–10:17:24.815922Z, immutable plan10:15:25.695761Z. Executed unchanged isolated `/home/rocry/w/_tmp/rcominote-w0-frozen-20261014`, assets symlink repository; capture snapshot139source/117tests manifest **305534f3786003fe3c59a2e4917218c658ac54ec7f82d039d484b280e3b63313**. All256 snapshot and isolated-copy source/test lengths/hashes verified, all97 imported project modules from snapshot. Preflight-b records inherited2137tests+159subtests/build, **new_full_check_run=false**; no new fullcheck/current-evolving-code pass claim. Earlier host-only prepare tuple-serialization failure retained emptyplan; preflight-review records0I/O, -b is first actualplan. No retry/reconnection of a failed device job.

Posthoc unchanged codec/state0x0a15a191: primary32-reset each512/512 matches mapped corresponding offsets; secondary512-reset34/34/32/33 only. Full actualpair acceptance occurs independently of this comparison. No new fitting/oracle selection/key/fullsystem/checksum/flash/restore proof, no decoded publication. Comparison/source/image pins in metadata; original captures/snapshots/old receipts immutable.

Coverage overlay adds2048 only: **strong41232B/potential196436B** from prior39184/194388; frozenASOF24200 inventory unchanged, B provenance not upgraded. System contiguousraw`[24000,25800)`**6144B** available from mixedhistorical acquisition, not one atomic/fullsystem/full4MiB backup. Recovery/own firmware still incomplete. Next continuous known-content control uses a separate source/review/checks/freeze/plan; no result claimed here. This review performed no device/source/test operations.

Exact offline frozen reproduction, repository root/private originals and unchanged isolated copy required; no device access or file writes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/paired-nor25000-four-v3-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from pathlib import Path
from rcominote.experiments import paired_nor_audit as A
from rcominote.nor_codec import decode
root=Path('artifacts/paired-nor25000-four-v3-20261014');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={}
def pin(path,digest=None):
 p=Path(path);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
def refs(v):
 if isinstance(v,dict):
  if {'file','bytes','sha256'}<=v.keys() and Path(v['file']).is_file():assert len(pin(v['file'],v['sha256']))==v['bytes']
  for x in v.values():refs(x)
 elif isinstance(v,list):
  for x in v:refs(x)
job=json.loads(pin(root/'report.json','b61421ca03e9a9fbdb5d934582e8f664a10a8dc343adc27218a3173911d13882'));plan=json.loads(pin(root/'plan.json','d36dd2f42aa2572c969bb6e0dd4d2ba82f135ad911ccc987ce4fd67eacf92710'));mp=root/'source-snapshot/manifest.json';manifest=json.loads(pin(mp,'305534f3786003fe3c59a2e4917218c658ac54ec7f82d039d484b280e3b63313'))
review=json.loads(pin(root/'preflight-review.json'));assert review['new_full_check_run'] is False and review['inherited_manifest_sha256']==sha(mp.read_bytes())
assert len(manifest['source_files'])==139 and len(manifest['test_files'])==117
for e in manifest['source_files']+manifest['test_files']:
 for base in (mp.parent,Path(review['isolated_source'])):assert len(pin(base/e['path'],e['sha256']))==e['bytes']
assert pin('artifacts/paired-nor25000-four-v3-preflight-20261014-b/plan.json')==(root/'plan.json').read_bytes()
assert pin('artifacts/paired-nor25000-four-v3-preflight-20261014/plan.json')==b''
A.J.time_order(manifest['created_at'],plan['planned_at'],job['started_at'],job['ended_at']);assert job['ok'] is True and plan['offsets']==[0x25000,0x25200,0x25400,0x25600]
baseline=A.C.source_gate(plan,image);proof=A.replay(root,image);current,state,parent=A.C.parent_gate(root,image);assert proof==job['verification']==parent['verification'] and proof['paired_bytes']==2048
assert state['device']['free_capacity']==59589 and len(parent['prior_names'])==34 and sha(current)=='f6781e2966e47b548c6b2f0f5ccd2c48d19b97cd172c1d1b4dd7d7b08a28c2a8'
comparison=json.loads(pin(root/'fixed-codec-comparison.json'));assert sha(pin(image))==comparison['source_image_sha256'] and sha(pin(mp.parent/'src/rcominote/nor_codec.py'))==comparison['codec_sha256']
chunks=[];att=hci=0;prefixes=[];composers=[];previous=baseline
for i,entry in enumerate(job['completed']):
 page=json.loads(pin(root/entry['report']['file'],entry['report']['sha256']));path=(root/entry['report']['file']).parent;capture=pin(path/'session.btsnoop',entry['capture']['sha256']);observed=A.P.inspect(capture,link=page['transport']['link'],final=True)
 assert page['ok'] is True and len(observed['transactions'])==9 and not observed['pending'] and page['verification']['status_events']['events']==0
 assert (path/'baseline/download.bin').read_bytes()==previous;pin(path/'baseline/download.bin');att+=len(page['att_packets']);hci+=observed['records']
 pair=[]
 for op in page['operations']:
  ring=pin(path/op['operation_id']/'download.bin');sector=pin(path/op['operation_id']/'sector.bin');assert len(sector)==512 and op['ok'] is op['live_complete'] is True
  f=op['verification']['freshness'];assert f['critical_nonpadding_chain_inside_written_prefix'] is True and not f['address_padding_exemptions'] and op['actions_verification']['f0_frames']==0
  prefixes.append(f['difference_proven_written_prefix_bytes']);composers.append(f['composer_fps2']);pair.append(sector);previous=ring
 assert pair[0]==pair[1] and sha(pair[0])==page['verification']['sha256'];chunks.append(pair[0]);offset=plan['offsets'][i]-0x24000;expected=image.read_bytes()[offset:offset+512]
 primary,secondary=decode(pair[0],block_bytes=32),decode(pair[0],block_bytes=512);c=comparison['pages'][i];assert c['physical']==hex(plan['offsets'][i]) and c['raw_sha256']==sha(pair[0]) and c['decoded32_sha256']==sha(primary)
 assert primary==expected and c['primary_matching']==512 and c['secondary512_matching']==sum(a==b for a,b in zip(secondary,expected))
assert att==727 and hci==1269 and prefixes==[4096,4096,4096,3827,4096,4096,4096,4096] and composers==[False,True,False,True,False,False,False,True]
raw=b''.join(chunks);assert len(raw)==2048 and sha(raw)=='5cc9f32531c5c4fe543d63ea8e8896752d7f19c2c43d3d6b0dc05475a3191edb'
for failed in ('artifacts/paired-nor-two-known-session-20261014','artifacts/paired-nor-system4-20261014'):
 for gate in (A.replay,A.C.parent_gate):
  try:gate(Path(failed),image)
  except ValueError:pass
  else:raise AssertionError('Original failed job promoted')
receipt=Path('docs/evidence/paired-nor25000-four-live-2026-10-14.json')
if receipt.exists():
 v=json.loads(receipt.read_bytes());refs(v);assert raw==Path(v['public_output']['file']).read_bytes()
origins=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in allowed for p in origins)
assert all(sha(p.read_bytes())==digest for p,digest in checked.items())
print('PASS frozen fullchain/four original pairs/raw2048;727ATT/1269HCI/36txn;prefix252second3827;current59589/history34;oldfailedretained;',len(origins),'snapshot modules;',len(checked),'pinned inputs unchanged')
PY
```
