# Four-page NOR job failed after two complete independent pairs

Original fixed job `[0x24600,0x24e00)` **failed** after completing0x24600 and0x24800. Independently replayed original completed ledger verifies **1,024 new raw bytes** at `[0x24600,0x24a00)`, not the planned2,048. Third-page first full4096 download fails original strict freshness-prefix gate; third-page second and fourth page never perform I/O. Whole-job success/admissible-parent replay continues to reject.

[Frozen receipt](../evidence/paired-nor-system4-live-2026-10-14.json) · [actual paired0x24600 raw512](../evidence/paired-nor-system4-live-2026-10-14/nor24600.bin) · [actual paired0x24800 raw512](../evidence/paired-nor-system4-live-2026-10-14/nor24800.bin) · [required successful24400 parent](paired-nor24400-live-2026-10-14.md) · [original uptime-gated failure](scratch-reuse-live-2026-10-14.md) · [unchanged as-of24200 coverage inventory](nor-backup-coverage-2026-10-14.md).

| Original page | Raw result / SHA256 | Actual disposition |
|---|---|---|
|0x24600|512, `3243e15bfa66ac634643eea56e50739f57a3a29cc44247356a7749c3bc4759f5`|Both original producers/full transfers/all gates pass; pair counts512 once|
|0x24800|512, `41eba1831fd85ec647cbcd9d19a11a49467655a22df613e7647e4cb2c931afd3`|Both original producers/full transfers/all gates pass; pair counts512 once|
|0x24a00|**0 accepted raw bytes**|Baseline and first4096 transfer/identity complete; first payload rejected, no512 output/success checkpoint; second0commands|
|0x24c00|**0**|Only precreated empty stage directories; no report/capture/connection/producer/download|

Frozen137-source/112-test snapshot imports96 project modules, all hash-verified archive entries. Full successful24400/pinned legacy24200 admission and older known4200/boot0-postmortem/original-failed-partial/static-identity/final4096-backup/nested3584-RAM-control-state sources replay. Immutable original plan binds exact four physical offsets, one owned file,8 distinct fresh nonces,59589 prestate, strict startupFAST/status/Actions policies and finite4connection/12download/8overwrite/36parameter budget. Original completed ledger is exactly its first2 pages; no failed-job promotion or retry.

Each completed page independently consumes9 complete FAST/host/SLOW transactions, every original GATT/ATT/HCI packet, final identity and sole normal disconnect; only then accepts both actual512 candidates. Actual baseline comes from predecessor's last4096 object; second producer uses its own actual first4096 ring. All future nonces absent from actual predecessor at each executed stage. Both candidates derive from unique fresh nonce/new physical dump/exact target status/32 canonical rows, no raw oracle or mapped selection. Every critical chain lies inside original difference-proven contiguous-offset0 write-prefix lower bound4096; this is not proof every byte changed.

| Stage chain | Baseline4096 SHA256 | First4096 SHA256 | Second4096 SHA256 |
|---|---|---|---|
|24600|`513cf0d3…14649ab`|`9409901f…e68b917`|`4d9e383b…fe47a12`|
|24800|`4d9e383b…fe47a12`|`91642ec7…c1f77efda`|`39af21e2…a3a4784`|
|Failed24a00|`39af21e2…a3a4784`|**`4c5e92d95b936c73b2cf3e4e08050d051461273ca523494aa2f048a78dd4ae96`**|Not attempted|

Complete file/slice hashes and freshness spans reside in receipt. All5 actual Actions streams have exact6ACK/F1/pending0; **F0=0 individually counted for all5**, preserved policy does not require uptime body.24600second producer→dump contains allowed exact composer notice (`composer_fps2=true`); other completed producer gaps do not.24600first and24800first nonce→status gaps also contain allowed background composer notice; these distinct gaps are retained independently. Background is not dropped to fit grammar. Original uptime-body-gated trial stays failed.

Failure is original `ValueError: Current chain depends on tail outside difference-proven written prefix`. Failed first transfer contains all declared/received4096 bytes, original SD attempt and immediate identity barrier complete, real FAST/host6/EOF SLOW settled, no pending parameter event. Last physical differing byte is4094, so **difference-proven written-prefix lower bound4095**. Physical byte4095 equals previous/current `0x20`; original parser finds critical-chain dependency outside proven prefix and rejects. This observation cannot distinguish an unwritten byte from a rewritten identical space. **No actual short write, corruption or definitive root cause is established here.** No gate relaxation, last-byte inference, mapped filling, failed-candidate publication or raw coverage promotion. Original third first/page/whole-job flags remainfalse; third second flagsfalse/unattempted.

Actual latest owned-file contents are failed first4096 ring `4c5e…ae96`, superseding last successfully paired24800 ring `39af…4784`. Complete original Boyi download proves these current observed bytes despite payload rejection. Actual first immediate state barrier and final identity both verify59589; state selection uses real `barrier_complete`, not `ok/live_complete`. Initial/all intermediate/final owned identities remain exactly NOTE/idle, FW010004/unbound, charging100/free59589. Stable free capacity does not imply stable file content. Failed original job remains ineligible as successful source parent.

| Captured page | ATT | HCI records / bytes | Complete transactions | Last ATT → normal disconnect |
|---|---:|---:|---:|---|
|24600|182|319 /25239|9|315→318, status0/reason0x16|
|24800|184|320 /25281|9|316→319, status0/reason0x16|
|Failed24a00|135|242 /18052|6|238→241, status0/reason0x16|
|Total|**501**|**881 /68572**|**24**|Each original owned epoch separately bound|

All3 captures: full GATT, exact ATT/HCI within-direction binding, all ATT partitioned with no unexplained gap, pending0/status-events0, monotonic host timestamps and wire/disconnect UTC within each page interval. FAST6..12/0/500 applies12, host6/6/0/500 CE1/1 applies6, EOF SLOW32..48/4/600 applies48. Failed first still has all6 actual negotiations and EOF-SLOW-before-identity; failure is after transport/state completion at strict payload proof. Sole normal local disconnect follows final ATT in each epoch; passive observations2.164479/2.165132/2.469836s after close completion satisfy8s, monitors exit0 via SIGINT. Ordering of each new FAST request after Actions proves ordering, not unique firmware trigger attribution.

Actual totals3connections/8complete4096downloads/5NOR-read producers/5same-file SD overwrites/0newfiles/0deletions. No firmware NOR writes; cohort70 download-confirmed +1 older declared without download +1 historical possible, maximum72 unchanged. Completed prefix remains historical accepted raw even though later same-file content changes and whole job fails.

Immutable codec hypothesis SHA256 `3354440446426a95c34fe08001c5ed0f193312a0686e0f4c823fd3c7ab7dfafc`,07:51:59.309235Z, predates plan/I/O and fixes existing codec SHA `81bad4b8eea615ff1198294f1f2540e9c6d9d1f36b572d3d0fadaacb1f278f3a`, effective state0x0a15a191/reset32 primary/reset512 observation only. Independent postfacto comparison uses **only the two completed raw pairs**, never failed24a00 data:

| Physical page / mapped slice | Primary reset32 | Secondary reset512 |
|---|---|---|
|24600 / `[0x600,0x800)`|512/512, SHA `8968585e35b729a4c1eb5d15856110afb832a5435a894c1c3c3480f1c5ab80f6`|34/512, decodedSHA `635962cdf50983384bc1502bb58dd3d4410f3c39ac7fcc0918685399d333a970`|
|24800 / `[0x800,0xa00)`|512/512, SHA `9d2a7a6698c46ae10210aeebf80c2d0c14b0a708d67819ecbee5dcc6bf5194ff`|35/512, decodedSHA `1da4d01e4766d580292b3d50d758660ab553953b3b2267932e253dd6748c2e4e`|

Root posthoc08:19:57.817142Z SHA256 `55efb4a7e898cba0982c970c421e2c699f68ca8a79494cdb01e00de72b5ef3c0` matches independent review for completed2 only; saved frozen-source prefix replay08:19:57.819779Z also preserves whole-jobfalse.

Fixed mapping corroboration only; no algorithm/state/reset fitting, efuse key recovery, full-system raw checksum or boot/flash/restore claim. Codec result never gates raw acceptance or repairs failed page. No decoded binary published.

Source manifest SHA256 `2bd251f02f9e3b2f62c1a7c0b52fc14335d064699d51633b52cc01f413847b5c`, creation07:42:08.502240Z, reused unchanged from24400 preflight with2021 tests/159 subtests/build success. New pre-I/O source-reference07:52:00.157881Z records reuse/current-source match; this review verifies frozen source lengths/hashes/internal consistency, not future/current equality or a new full-suite run. Plan07:51:59.743186Z < job07:52:24.284353Z; completed pages end07:52:58.486529Z/07:53:21.771913Z; failed page07:53:22.195231Z–07:53:40.180215Z; whole job ends07:53:40.181319Z.

1677 checked original inputs retain identical hashes before/after. Only two actual paired512 firmware sectors published. Original rings/HCI/identity/inventory/nonces remain private; original failure flags, source/canonical/old receipts and as-of24200 coverage inventory unchanged. Whole4MiB backup/validated restoration/own runtime remain incomplete. No future retry/profile is executed or authorized by this receipt.

Offline reproduction from repository root, private originals retained; no device access/file writes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/paired-nor-system4-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_runtime as R
from rcominote.experiments.hci_interval import EPOCH_US
from rcominote.nor_codec import decode
root=Path('artifacts/paired-nor-system4-20261014');preflight=Path('artifacts/paired-nor-system4-preflight-20261014');image=Path('artifacts/mapped-system-20261012.bin')
sha=lambda b:hashlib.sha256(b).hexdigest();ref=lambda p:{'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}
job=json.loads((root/'report.json').read_bytes());plan=json.loads(A.J.check_reference(root,job['plan']).read_bytes());manifest_path=root/'source-snapshot/manifest.json';manifest=json.loads(manifest_path.read_bytes());hyp_path=preflight/'codec-hypothesis.json';hyp=json.loads(hyp_path.read_bytes());source_ref=preflight/'source-reference.json';source_claim=json.loads(source_ref.read_bytes())
assert sha((root/'report.json').read_bytes())=='18ea9488572527e70f96abfa6ee65c4bbe80297561ca5085a35bc0ab3010b202'
assert sha((root/'plan.json').read_bytes())=='f8d69bdfcb831d646eaa8774fa1bfc1024a7e937ef15f9a8754da34d2bbd41dc'
assert sha(manifest_path.read_bytes())=='2bd251f02f9e3b2f62c1a7c0b52fc14335d064699d51633b52cc01f413847b5c'
assert len(manifest['source_files'])==137 and len(manifest['test_files'])==112 and plan['offsets']==[0x24600,0x24800,0x24a00,0x24c00]
files={image,manifest_path,hyp_path,source_ref};refs=[]
def collect(v,base=None):
 if isinstance(v,dict):
  if 'directory' in v and Path(v['directory']).is_dir():
   base=Path(v['directory']);files.update(p for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
  if {'file','bytes','sha256'}<=v.keys():
   p=Path(v['file'])
   if not p.is_absolute() and not p.exists():
    assert base is not None;p=base/p
   actual=ref(p);assert actual['bytes']==v['bytes'] and actual['sha256']==v['sha256'];files.add(p)
   if actual not in refs:refs.append(actual)
  for child in v.values():collect(child,base)
 elif isinstance(v,list):
  for child in v:collect(child,base)
current=plan;visited=set()
while isinstance(current.get('parent'),dict):
 collect(current['parent']);p=Path(current['parent']['directory'])/'plan.json';assert p not in visited;visited.add(p);current=json.loads(p.read_bytes())
files.update(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts);files.update(p for p in preflight.iterdir() if p.is_file())
for item in manifest['source_files']+manifest['test_files']:
 p=manifest_path.parent/item['path'];assert p.stat().st_size==item['bytes'] and sha(p.read_bytes())==item['sha256'];files.add(p)
for p in (Path('docs/evidence/nor-backup-coverage-2026-10-14.json'),Path('docs/nor-backup-coverage-2026-10-14.md'),Path('docs/evidence/paired-nor24400-live-2026-10-14.json')):files.add(p)
before={str(p.resolve()):sha(p.read_bytes()) for p in files}
assert 'source-snapshot/src' in A.__file__ and job['ok'] is False and len(job['completed'])==2
A.job_gate(job,plan,root);baseline=A.C.source_gate(plan,image);proofs,last_success_ring,last_success_state=A.completed_prefix(job,plan,root,baseline)
assert len(proofs)==2 and [p['raw_range'] for p in proofs]==[[0x24600,0x24800],[0x24800,0x24a00]]
for gate in (A.replay,A.C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Failed whole job promoted')
A.J.time_order(manifest['created_at'],hyp['created_at'],plan['planned_at'],source_claim['verified_at'],job['started_at'],job['ended_at'])
assert source_claim['source_snapshot']['sha256']==sha(manifest_path.read_bytes()) and source_claim['checks_reused_without_source_changes']==manifest['checks']
page_summaries=[];previous=baseline;state=plan['expected_before'];ended=plan['parent']['ended_at']
def wire_proof(report,directory,expected_tx):
 raw=(directory/'session.btsnoop').read_bytes();observed=A.P.inspect(raw,link=report['transport']['link'],final=True);wire=A.common.wire_positions(report,raw)
 assert report['gatt_proof']==A.A.setup(report) and report['att_hci_binding']==A.dual_hci.bind(report,raw)
 assert report['hci_capture']=={'bytes':len(raw),'sha256':sha(raw),'records':observed['records']} and len(observed['transactions'])==expected_tx and not observed['pending']
 assert len(wire)==len(report['att_packets']) and all(type(row['monotonic_ns']) is int for row in report['att_packets']) and all(a['monotonic_ns']<=b['monotonic_ns'] for a,b in pairwise(report['att_packets']))
 _,events=A.E.verify(report);assert events['events']==0
 (disc,)=observed['disconnects'];assert disc['status']==0 and disc['reason']==0x16 and disc['record']>max(p[1] for p in wire)
 assert report['disconnect_observation']=={'observed':True,'event':disc,'max_wait_seconds':8}
 requested,completed,recorded=[report[k] for k in ('close_requested_us','close_completed_us','disconnect_observed_us')]
 assert requested<=completed<=recorded<=completed+8000000 and requested<=disc['timestamp_us']<=completed+8000000
 start_us=EPOCH_US+int(datetime.fromisoformat(report['started_at']).timestamp()*1000000);end_us=EPOCH_US+int(datetime.fromisoformat(report['ended_at']).timestamp()*1000000)
 assert all(start_us<=p[2]<=end_us for p in wire) and start_us<=disc['timestamp_us']<=end_us
 assert report['monitor_exit']==0 and report['monitor_stop']=={'signal':'SIGINT','requested':True,'delivery':'sent'}
 return observed,wire,disc
for index in range(2):
 directory=root/plan['pages'][index]['directory'];report=json.loads((directory/'report.json').read_bytes());page_plan=A.C.page_plan(plan,index,state,ended)
 assert A.validate_page(report,directory,page_plan,previous)==proofs[index]
 observed,wire,disc=wire_proof(report,directory,9);warm=report['baseline'];assert A.shared.download(report,warm,directory)==previous
 operations=[]
 for op in report['operations']:
  current=A.shared.download(report,op,directory);decoded=A.C.payload(op,current,previous);fresh=decoded['freshness'];sector=(directory/op['operation_id']/'sector.bin').read_bytes()
  assert decoded==op['verification'] and bytes.fromhex(decoded['sector_hex'])==sector and len(sector)==512
  assert fresh['previous_ring_sha256']==sha(previous) and fresh['difference_proven_written_prefix_bytes']==4096
  actions=A.C.actions(report,op);assert actions==op['actions_verification'] and actions['f0_frames']==sum(f['command']==240 for f in op['frames'])==0
  operations.append({'operation':op['operation_id'],'download':ref(directory/op['operation_id']/'download.bin'),'sector':ref(directory/op['operation_id']/'sector.bin'),'checkpoint':ref(directory/op['operation_id']/'checkpoint.json'),'started_at':op['started_at'],'ended_at':op['ended_at'],'actions':actions,'activity':op['activity_fast_verification'],'freshness':{k:v for k,v in fresh.items() if k!='nonce'},'state':op['state_verification']})
  previous=current
 assert (directory/'first/sector.bin').read_bytes()==(directory/'second/sector.bin').read_bytes()
 assert report['before']==warm['before']==warm['after']==report['operations'][0]['before']==report['operations'][0]['after']==report['operations'][1]['before']==report['operations'][1]['after']==report['after']==state
 page_summaries.append({'page_index':index,'nor_offset':page_plan['nor_offset'],'report':ref(directory/'report.json'),'capture':ref(directory/'session.btsnoop'),'baseline':ref(directory/'baseline/download.bin'),'started_at':report['started_at'],'ended_at':report['ended_at'],'operations':operations,'att_packets':len(wire),'hci_records':observed['records'],'transactions':observed['transactions'],'disconnect':disc,'last_att_record':max(p[1] for p in wire),'close_observation_us':report['disconnect_observed_us']-report['close_completed_us'],'final_state':report['state_verification']})
 state,ended=report['after'],report['ended_at']
assert previous==last_success_ring and state==last_success_state
failed_dir=root/plan['pages'][2]['directory'];failed=json.loads((failed_dir/'report.json').read_bytes());failed_plan=A.C.page_plan(plan,2,state,ended)
assert failed['ok'] is False and all(failed[k]==failed_plan[k] for k in A.C.FIELDS) and failed['plan']==job['plan']
R.plan_gate(failed,failed_plan,failed_dir)
error='ValueError: Current chain depends on tail outside difference-proven written prefix';assert failed['error']==failed['capture_error']==job['error']==error
warm=failed['baseline'];first,second=failed['operations'];assert warm['ok'] is True and warm['live_complete'] is True and first['ok'] is False and first['live_complete'] is False and second['ok'] is False and second['live_complete'] is False
assert first['producer_attempted'] is True and first['sd_write_attempted'] is True and first['barrier_complete'] is True and first['error']==error and 'verification' not in first
assert not any(k in second for k in ('writes','actions_start','download_start','started_at','producer_attempted','sd_write_attempted')) and not list((failed_dir/'second').iterdir()) and not any(p.is_file() for p in (root/plan['pages'][3]['directory']).rglob('*'))
observed,wire,disc=wire_proof(failed,failed_dir,6);startup,normal,slow=observed['transactions'][:3]
assert failed['startup_settlement']==startup and failed['startup_classification']==A.startup.classify(startup)
A.E.bridge(failed,failed['setup_end'],failed['before_span'][0]);A.A.identity(failed,failed,'before');A.E.bridge(failed,failed['before_span'][1],failed['file_list_span'][0]);assert A.inventory(failed,failed_plan)==failed['listed_count'];A.E.bridge(failed,failed['file_list_span'][1],warm['download_start'])
assert failed['before']==warm['before']==state and failed['predecessor_state_verification']==A.verify_state(state,failed['before'],sd_write=False)
previous=A.shared.download(failed,warm,failed_dir);assert previous==last_success_ring;A.F.absent(previous,failed_plan['future_nonces']);A.shared.baseline_window(failed,warm,wire,startup,normal,slow);A.shared.barrier(failed,warm,state,writing=False)
A.E.bridge(failed,warm['verified_end'],first['actions_start']);A.E.bridge(failed,first['actions_end'],first['download_start']);assert A.C.actions(failed,first)==first['actions_verification'] and first['actions_verification']['f0_frames']==0
normal,slow,cursor=A.W.parameter_stage(observed['transactions'],3,first,warm['slow_settlement'],first_fast_required=True);assert cursor==6
assert first['activity_fast_verification']==A.W.default_activity_fast(failed,first,warm['slow_settlement'],first['pre_download_fast'][0],wire)
A.W.download_window(wire,first,normal,slow,report=failed);current=A.shared.download(failed,first,failed_dir);A.shared.barrier(failed,first,state,writing=True)
assert len(current)==4096 and sha(current)=='4c5e92d95b936c73b2cf3e4e08050d051461273ca523494aa2f048a78dd4ae96'
prefix=max(i+1 for i,(a,b) in enumerate(zip(current,previous,strict=True)) if a!=b);assert prefix==4095 and current[4095]==previous[4095]==0x20
try:A.C.payload(first,current,previous)
except ValueError as ex:assert str(ex)==error.removeprefix('ValueError: ')
else:raise AssertionError('Failed candidate promoted')
assert not (failed_dir/'first/sector.bin').exists() and not (failed_dir/'first/checkpoint.json').exists()
A.E.bridge(failed,first['verified_end'],failed['after_span'][0]);A.A.identity(failed,failed,'after');A.E.bridge(failed,failed['after_span'][1],len(failed['att_packets']))
assert R.final_state(failed)==first['after']==failed['after']==state and failed['state_verification']==A.verify_state(first['after'],failed['after'],sd_write=False)
assert state['device']['free_capacity']==59589
A.J.time_order(ended,failed['started_at'],warm['started_at'],warm['ended_at'],first['started_at'],first['ended_at'],failed['ended_at'],job['ended_at'])
for stage in (warm,first):assert (datetime.fromisoformat(stage['ended_at'])-datetime.fromisoformat(stage['started_at'])).total_seconds()<=18
assert not any(k in failed for k in ('after_error','disconnect_error','final_evidence_error'))
assert first['before']==warm['after']==state and first['state_verification']['allowed_decrease']==1
codec_path=Path(sys.modules['rcominote.nor_codec'].__file__)
assert sha(codec_path.read_bytes())==hyp['codec_source']['sha256']=='81bad4b8eea615ff1198294f1f2540e9c6d9d1f36b572d3d0fadaacb1f278f3a'
assert hyp['primary_reset_bytes']==32 and hyp['secondary_observation_only_reset_bytes']==512 and hyp['effective_state']=='0x0a15a191'
assert hyp['physical_offsets']==plan['offsets'] and len(image.read_bytes())==hyp['mapped_image']['bytes']==927632 and sha(image.read_bytes())==hyp['mapped_image']['sha256']
comparison_path=root/'codec-comparison.json';comparison=json.loads(comparison_path.read_bytes())
assert sha(comparison_path.read_bytes())=='55efb4a7e898cba0982c970c421e2c699f68ca8a79494cdb01e00de72b5ef3c0'
assert comparison['original_whole_job_ok'] is False and comparison['completed_pages']==2 and len(comparison['observations'])==2
assert comparison['hypothesis']['sha256']==sha(hyp_path.read_bytes()) and comparison['codec_source_sha256']==sha(codec_path.read_bytes())
A.J.time_order(job['ended_at'],comparison['compared_at'])
for index,observation in enumerate(comparison['observations']):
 offset=plan['offsets'][index];directory=root/plan['pages'][index]['directory'];raw=(directory/'first/sector.bin').read_bytes();mapped_ref=hyp['mapped_slices'][index]
 assert observation['physical_range']==[offset,offset+512] and observation['raw_sha256']==sha(raw) and observation['mapped_slice']==mapped_ref
 mapped=image.read_bytes()[mapped_ref['mapped_offset']:mapped_ref['mapped_offset']+512];assert sha(mapped)==mapped_ref['sha256']
 profiles=[]
 for reset in (32,512):
  decoded=decode(raw,block_bytes=reset);profiles.append({'reset_bytes':reset,'decoded_sha256':sha(decoded),'mapped_bytes_equal':sum(a==b for a,b in zip(decoded,mapped,strict=True)),'mapped_complete_match':decoded==mapped})
 assert profiles==observation['profiles'] and profiles[0]['mapped_bytes_equal']==512 and profiles[1]['mapped_bytes_equal']==(34 if index==0 else 35)
saved_prefix_path=root/'snapshot-prefix-replay.json';saved_prefix=json.loads(saved_prefix_path.read_bytes())
assert saved_prefix['original_whole_job_ok'] is False and saved_prefix['completed_prefix_verification']==proofs and saved_prefix['all_project_modules_from_snapshot'] is True
A.J.time_order(job['ended_at'],saved_prefix['verified_at'])
snapshot_entries={(manifest_path.parent/e['path']).resolve() for e in manifest['source_files']}
assert len(saved_prefix['modules'])==saved_prefix['imported_module_count']==95 and all(Path(p).resolve() in snapshot_entries for p in saved_prefix['modules'].values())
loaded=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];snapshot={(manifest_path.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in snapshot for p in loaded)
assert {p:sha(Path(p).read_bytes()) for p in before}==before

receipt=json.loads(Path('docs/evidence/paired-nor-system4-live-2026-10-14.json').read_bytes())
def check_refs(v):
 if isinstance(v,dict):
  if {'file','bytes','sha256'}<=v.keys():assert ref(Path(v['file']))=={k:v[k] for k in ('file','bytes','sha256')}
  for child in v.values():check_refs(child)
 elif isinstance(v,list):
  for child in v:check_refs(child)
check_refs(receipt)
for index,offset in enumerate((0x24600,0x24800)):
 directory=root/plan['pages'][index]['directory'];public=Path(f'docs/evidence/paired-nor-system4-live-2026-10-14/nor{offset:x}.bin')
 assert public.read_bytes()==(directory/'first/sector.bin').read_bytes()==(directory/'second/sector.bin').read_bytes()
 raw=public.read_bytes();mapped_ref=hyp['mapped_slices'][index];mapped=image.read_bytes()[mapped_ref['mapped_offset']:mapped_ref['mapped_offset']+512]
 assert sha(mapped)==mapped_ref['sha256']
 for reset,expected in ((32,512),(512,34 if index==0 else 35)):
  decoded=decode(raw,block_bytes=reset);assert sum(a==b for a,b in zip(decoded,mapped,strict=True))==expected
assert receipt['result']['original_whole_job_ok'] is False and receipt['result']['completed_pair_raw_bytes']==1024
assert receipt['failed_page24a00']['difference_prefix']==4095 and receipt['failed_page24a00']['raw_coverage_bytes']==0
assert {p:sha(Path(p).read_bytes()) for p in before}==before
print('PASS:2completepairs/1024 only; originaljobfalse; failedfirstfull4096/prefix4095reject;501ATT/881HCI/24tx; latest59589; originalsunchanged')
PY
```
