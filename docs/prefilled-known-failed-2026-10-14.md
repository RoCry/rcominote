# Verified RAM prefill passed; strict known NOR control failed, 2026-10-14

[Sanitized metadata](evidence/prefilled-known-failed-2026-10-14.json); private originals `artifacts/prefilled-nor-known-20261014`. **Original fixed known0/4200 control failed after RAM-prefill and first NOR download.** No NOR sector accepted, no new coverage or public binary. Both initial factory baseline and new current carrier hashes withheld: SD RAM-prefill overwrites the file, **does not clear the resident log ring**; a knownboot0 target cannot establish that the carrier contains no earlier private factory values.

| Actual stage | Original result |
|---|---|
|Readonly baseline|Complete4096 exactly equals admitted private factory current; identity barrier passes|
|prefill-first|4ACK/F1/pending0/F0=0; actual FAST→host6→4096 download→EOF SLOW/identity; all bytes match independent RAM oracle ending48; originalsuccess|
|first NOR0|6ACK/F1/pending0/F0=0; actual FAST→host6→4096 download→SLOW/barrier/finalidentity all complete; original strict content rejects; no sector.bin/oracle comparison|
|prefill-second/second4200|Untouched originalfalse slots; no files/deviceI/O|

Exact original rejection: `ValueError: Unexpected text after current producer before dump`. Actual producer→dump gap is54B `\n\r\n[composer][I][742]: post fps 2\n\r\n[logsrv][I][679]: `; original grammar permits `b'\n' + COMPOSER_FPS2 + LOG_PREFIX`, whose CRLF placement differs. Frozen original parser reproduces the failure; no new separator policy/mask/reparse/oracle comparison or failedflag promotion. Difference against verified RAMfile proves logical prefix4096 under the contiguous-prefix model; lastbyte38 differs from prefill48. This observation does not complete the rejected NOR chain, establish SD atomicity, clear resident history, or prove a short-write cause.

Distinct failed-communication review consumes **175ATT/310HCI/24835B, nine complete transactions/0pending/status, three full4096 downloads, one RAMexport/one NORproducer/two existing-file SDoverwrites**. Exact Actions recipes, all F0/F1 framing, original GATT/ATT/HCI binding, startupFAST and both write-associatedFAST orderings, host/download/EOF windows, each real identity barrier and globalfinalidentity verify. Sole normaldisconnect status0/reason16 atHCI309 follows finalATT; clean ownedmonitor exit. Request ordering does not identify a unique hidden deferred trigger. Original wholecontrol replay and parentgate still reject.

Final **11:52:36.513316Z** actualFW010004/NOTEidle/unbound/charging100/free59589; before, all stage barriers and finalafter identical. Current retained4096 fully observed but not an admitted successfulparent; contenthash private.50 ancestor reservednames+2 predeclared newNORnonces=52reserved, not52successes.0newfiles/deletions/NORwrites; cohort70confirmed+1olderdeclared+1historicalpossible=max72 unchanged.

Actual **factory CONTENT ownership checkpoint** `artifacts/paired-nor-factory-content-checkpoint-20261014/checkpoint.json`, SHA36dbcc78e13140681e5d08f28a6ebddea7f26466431aa8400bb951f487ac52e8, created11:51:24.303859Z: separately replays [factory acceptedprefix512 and failed second fullcommunication](factory-first4-failed-2026-10-14.md), originalv3variable-lowhex error/currentprivate4096/state59589/history50.0deviceI/O/coverage; originalfactoryjob/secondfalse retained. Observedfactoryend stays11:16:39.193113Z, not a newlive observation at checkpointcreation. New readonlybaseline matched all4096bytes before prefill.

Frozen **144source/127tests** manifest9139f449cc69785dfbde1c86c5bb007f076dacfa0c2479c587797d608fb47fe5: all271 lengths/hashes equal attachedsnapshot and isolatedprefillcopy; before/after334checkinputs equal. Manifest11:51:23.711198Z < checkpointcreation < plan11:51:59.541495Z < actual11:52:06.889815Z < end. Preflight inherits2445tests+159subtests/36.76s,328format/lint/build; `new_full_check_run=false` for this plan, not a newcurrent-source suite. All100 imported projectmodules fromsnapshot. Original reports/plan/source/privateinputs unchanged.

Coverage unchanged **strong41744B/potential196948B**, systemraw contiguous6144B`[24000,25800)`, factory private512B fullypaired/7680B still missing. [Frozen ASOF inventory](nor-backup-coverage-2026-10-14.md), [system first4KiB](system-first4k-raw-live-2026-10-14.md), [bulk2048](paired-nor25000-four-live-2026-10-14.md) immutable; historicalB not upgraded. Full4MiB backup/reliable restore/ownruntime incomplete. [Prefill plan](verified-prefill-control-plan-2026-10-14.md) now has this failed actualv1 result; no successful two-known control. A narrowly justified separator policy and distinct communication-only checkpoint are **next source/review work, not live/adopted success**. No automatic retry/deletion. User controls exactly “只有电源键和录音滑键”; RESET/exposed removablebattery connector unconfirmed, longpresspower independentROMexit unproven, allhiddenpoints absence not inferred. [Deletion static boundary](file-deletion.md#hidden-scratch-bounded-static-follow-up-2026-10-14) grants no deletion authorization.

Exact host-only replay; private originals/isolatedcopy required. No device or evidence writes, no privatecontent/hash output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/prefilled-nor-known-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime
from pathlib import Path
from rcominote.experiments import prefilled_nor_control as C
A=C.A
root=Path('artifacts/prefilled-nor-known-20261014');pre=Path('artifacts/prefilled-nor-known-preflight-20261014');image=Path('artifacts/mapped-system-20261012.bin');checked={};sha=lambda b:hashlib.sha256(b).hexdigest();error='ValueError: Unexpected text after current producer before dump'
def pin(path,digest=None):
 p=Path(path);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
r=json.loads(pin(root/'report.json','a17e06b5f2763b6dfefa266ebaea70f7f15417e0c9f7b0e928cfb144141f3ffd'));plan=json.loads(pin(root/'plan.json','5e4c3b6889da2291b78462c8ce3dee19459702f1646ac418dbfb8e2786fc3fdf'));mp=root/'source-snapshot/manifest.json';manifest=json.loads(pin(mp,'9139f449cc69785dfbde1c86c5bb007f076dacfa0c2479c587797d608fb47fe5'));review=json.loads(pin(root/'preflight-review.json'))
assert len(manifest['source_files'])==144 and len(manifest['test_files'])==127
for entry in manifest['source_files']+manifest['test_files']:
 for base in (mp.parent,Path(review['isolated_source'])):assert len(pin(base/entry['path'],entry['sha256']))==entry['bytes']
before=json.loads(pin(pre/'checks-before.json'));assert before==json.loads(pin(pre/'checks-after.json')) and len(before)==334
assert review['new_full_check_run'] is False and review['full_checks_inherited']=='2445tests+159subtests/328format/lint/build;334inputsunchanged'
assert r['ok'] is False and r['error']==r['capture_error']==error and 'verification' not in r
C.plan_gate(r,plan,root);baseline=C.source_gate(plan,image);ram,oracle=C.ram_source(image);assert oracle==plan['ram_oracle']
cp=Path('artifacts/paired-nor-factory-content-checkpoint-20261014');checkpoint=json.loads(pin(cp/'checkpoint.json','36dbcc78e13140681e5d08f28a6ebddea7f26466431aa8400bb951f487ac52e8'));current,state,source=A.C.parent_gate(cp,image)
assert current==baseline==pin(cp/'baseline.bin') and source==plan['parent'] and state==plan['expected_before'] and len(source['prior_names'])==50
assert checkpoint['live_capture_performed'] is False and checkpoint['original_job_ok'] is False and checkpoint['new_raw_nor_coverage_bytes']==0 and checkpoint['failure_role']=='complete-page-second-transfer-content-proof-only'
A.J.time_order(manifest['created_at'],checkpoint['created_at'],plan['planned_at'],r['started_at'],r['ended_at'])
observed,wire,events=A.envelope(r,root,9);raw=pin(root/'session.btsnoop','97bbb72903e0a4be40b096f7f84240e553210bfc031febbc55275fe3ebe5abde')
assert len(raw)==24835 and observed['records']==310 and len(r['att_packets'])==175 and events['events']==0
assert r['predecessor_state_verification']==A.verify_state(state,r['before'],sd_write=False)
A.E.bridge(r,r['before_span'][1],r['file_list_span'][0]);assert A.common.file_list(r)==r['listed_count']
for row in A.E.rows(r,*r['file_list_span'])[1:]:
 _,data=A.Boyi.parse(bytes.fromhex(row['hex'])[3:])
 if data[:1]==b'\0':assert A.Boyi.parse_file_entry(data).name not in {A.C.F.NAME,*C.nonces(plan)}
startup=observed['transactions'][0];assert r['startup_settlement']==startup and r['startup_classification']==A.C.startup.classify(startup)
warm=r['baseline'];assert warm['ok'] is warm['live_complete'] is True and warm['before']==r['before'] and not any(k in warm for k in ('actions_start','sd_write_attempted','producer'))
A.E.bridge(r,r['file_list_span'][1],warm['download_start']);A.shared.baseline_window(r,warm,wire,startup,*observed['transactions'][1:3]);previous=A.shared.download(r,warm,root);assert previous==baseline;A.C.F.absent(previous,C.nonces(plan));A.shared.barrier(r,warm,state,writing=False)
state,boundary,settled,cursor,ended=warm['after'],warm['verified_end'],warm['slow_settlement'],3,warm['ended_at']
for index,op in enumerate(r['operations'][:2]):
 assert op['before']==state and op['sd_write_attempted'] is True and op['barrier_complete'] is True
 assert op['ram_export_attempted' if index==0 else 'producer_attempted'] is True
 A.J.time_order(ended,op['started_at']);A.E.bridge(r,boundary,op['actions_start']);A.E.bridge(r,op['actions_end'],op['download_start']);assert C.actions(r,op)==op['actions_verification']
 normal,slow,cursor=A.W.parameter_stage(observed['transactions'],cursor,op,settled,first_fast_required=True)
 assert op['activity_fast_verification']==A.W.default_activity_fast(r,op,settled,op['pre_download_fast'][0],wire)
 A.W.download_window(wire,op,normal,slow,report=r);data=A.shared.download(r,op,root);pin(root/op['operation_id']/'download.bin');A.shared.barrier(r,op,state,writing=True)
 if index==0:
  assert op['ok'] is op['live_complete'] is True and data==ram and C.content(op,data,previous,ram,plan,baseline)==op['verification'];A.C.F.absent(data,C.nonces(plan))
 else:
  assert op['ok'] is op['live_complete'] is False and op['error']==error and 'verification' not in op and not (root/'first/sector.bin').exists()
  assert previous==ram and previous[-1]==0x48 and data[-1]==0x38 and max(i for i,(x,y) in enumerate(zip(data,ram,strict=True)) if x!=y)+1==4096
  try:C.content(op,data,previous,ram,plan,baseline)
  except ValueError as exc:
   assert str(exc)==error.removeprefix('ValueError: ');trace=exc.__traceback__
   while trace and trace.tb_frame.f_code.co_name!='_parse_ring':trace=trace.tb_next
   assert trace is not None;local=trace.tb_frame.f_locals;assert len(local['gap'])==54 and local['gap']==b'\n\r\n[composer][I][742]: post fps 2\n\r\n[logsrv][I][679]: '
  else:raise AssertionError('Original strict grammar failure not reproduced')
 previous,state,boundary,settled,ended=data,op['after'],op['verified_end'],slow,op['ended_at']
for op,slot in zip(r['operations'][2:],plan['operations'][2:],strict=True):
 assert op==slot|{'ok':False,'live_complete':False} and not any(p.is_file() for p in (root/op['operation_id']).rglob('*'))
A.final_identity(r,wire,{'state':state,'boundary':boundary,'cursor':cursor},9)
for stage in [warm,*r['operations'][:2]]:
 A.J.time_order(r['started_at'],stage['started_at'],stage['ended_at'],r['ended_at']);assert (datetime.fromisoformat(stage['ended_at'])-datetime.fromisoformat(stage['started_at'])).total_seconds()<=18
assert state==r['after']==plan['expected_before'] and state['device']['free_capacity']==59589 and len(set(source['prior_names'])|set(C.nonces(plan)))==52
assert [o['ack_count'] for o in r['operations'][:2]]==[4,6] and all(o['actions_verification']['f0_frames']==0 for o in r['operations'][:2])
def errors(v,path=''):
 result={}
 if isinstance(v,dict):
  for k,x in v.items():
   p=path+'.'+k
   if k.endswith('error') and x:result[p]=x
   result.update(errors(x,p))
 elif isinstance(v,list):
  for i,x in enumerate(v):result.update(errors(x,path+f'[{i}]'))
 return result
assert errors(r)=={'.error':error,'.capture_error':error,'.operations[1].error':error}
for gate in (C.replay,A.C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Original failed control admitted')
for gate in (A.replay,A.C.parent_gate):
 try:gate(Path('artifacts/paired-nor-factory-first4-20261014'),image)
 except ValueError:pass
 else:raise AssertionError('Original failed factory job admitted')
receipt=Path('docs/evidence/prefilled-known-failed-2026-10-14.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for x in v.values():refs(x)
  elif isinstance(v,list):
   for x in v:refs(x)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in allowed for p in origins)
assert all(sha(p.read_bytes())==digest for p,digest in checked.items())
print('PASS frozen fullchain/factoryCP0coverage/strictRAM4096/failedNOR originalseparator;175ATT/310HCI/9txn/3DL/2overwrites;state59589/52reserved;0NORaccepted;',len(origins),'snapshot modules;',len(checked),'inputs unchanged; private content/hashes withheld')
PY
```
