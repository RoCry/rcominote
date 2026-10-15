# Private factory raw: first pair complete, four-page job failed, 2026-10-14

Sanitized [metadata](evidence/factory-first4-failed-2026-10-14.json); originals private `artifacts/paired-nor-factory-first4-20261014`. **Original four-pagejob failed after one complete512B pair.** Only privatephysical`[1ec000,1ec200)` adds512B strong raw coverage. Next`1ec200`first accepted512 observation remains unpaired/zero coverage; second full4096/barrier/finalafter completes but originalv3prefix rejects. Targets`1ec400/1ec600` zeroI/O. No factory bytes/configuration values/content hashes/public binary or system-codec decode; transport/source/report provenance digests only.

| Original stage | Verified evidence | Coverage |
|---|---|---:|
|1ec000 first/second|Original fullpair acceptance, two actual512 results equal; all wire/nonce/previous/window/state/finaldisconnect gates pass; both prefixes4096|512 private bytes|
|1ec200 first|Original accepted512, full4096/barrier; prefix4096|0, unpaired|
|1ec200 second|Full4096/DL/SLOW/immediate identity/globalfinalafter/normaldisconnect; originalv3payload rejects/no sector.bin|0|
|1ec400/1ec600|No files/commands/deviceI/O|0|

Exact original rejection replays: prefix4095, physical4095/current==previous ASCII`f`, **column41 variable low hexadecimal payload digit**, outside the proof prefix. This is not a formatterconstant or row-leading space. **A constant-only formatter mask cannot prove this variable byte.** No newmask parse, second sector/oracle comparison, data filling or originalflag promotion; equal tail does not establish shortwrite or its cause. First of failedpage cannot stand in for the rejected independent second. Wholejobreplay/parent admission still reject; no newcurrent communicationcheckpoint exists.

Original accepted prefix is verified separately with frozen `A.completed_prefix`. Failedpage has distinct `A.envelope(...,9)` + `A.transfer_group(...,operation_count=2)` + `A.final_identity(...,9)`:182ATT/318HCI each actualconnection, total364ATT/636HCI/50426B,18complete transactions/0pending/status,6complete4096 downloads/4existing-file overwrites, four exact6ACK/F1/pending0/F0=0. Both sole normaldisconnect status0/reason0x16 atHCI317 after finalATT; clean ownedmonitor stops. All realstage/finalidentity observations FW010004/NOTEidle/unbound/charging100/free59589, integer capacity decrease0.0newfiles/deletions, cohort70confirmed+1olderdeclared+1historicalpossible=max72 unchanged. No firmware NOR write.

**Latest current4096 object and finalstate known, wholejob not admissible.** Final2026-10-14T11:16:39.193113Z, privatecurrent file is failedpage1second, contenthash withheld; fullwire/state proof complete.42ancestor names+8originalplanned=50reserved, not successfulparenthistory. No automatic retry/extension. Latest user physical-control inventory exactly **“只有电源键和录音滑键”**; RESET/hole/exposedremovablebattery access not confirmed, longpresspower independentROMexit unproven. This does not assert absence of all unobserved hidden points; no button/device experiment performed.

Predecessor actualStage1 **STATUS CONTENT communication checkpoint** `artifacts/paired-nor-status-content-checkpoint-20261014/checkpoint.json`, SHA44671cc064c673c0643621d4e20a35b884589e2c8ab5dec3d3d6b12420503f48, created11:14:50.265626Z, replays prior [STATUS4 failure](status-known-failed-2026-10-14.md)'s fullninecommunication/originalpolicyerror/current4096/state/history42.0deviceI/O/coverage, originaljob/operationfalse; originalobservedafter remains10:50:08.889093Z, no freshlive capture atcheckpointcreation. Newfactorybaseline matched every4096byte before firstoverwrite. This checkpoint adopts ownership/state only, not failedNORcontent; oldv3/STATUS4/17 failures stayfailed.

Capture frozen140source/122tests manifest **9af7580903246d32070e9e59933b126b79cb72c335216ecf9a365d6563e7ff24**, all262 lengths/hashes equal snapshot and isolatedStage1copy. Manifest11:14:49.712217Z < plan11:15:40.569276Z < actualstart11:15:46.521263Z < end11:16:39.193113Z. Preflight inherits2301tests+159subtests/319formatted/lint/build, **new_full_check_run=false**; no newfullsuite/current-source claim. All98 imported projectmodules fromsnapshot, fulloriginalancestor/checkpoint/acceptedprefix/failedcommunication replayed, originals unchanged.

Coverage overlay: **strong41744B/potential196948B**, prior41232/196436 + only512. Factory8KiB has512 fullyreplayableprivatebytes, **7680B still missing**; failedpagefirst not counted. [FrozenASOFinventory](nor-backup-coverage-2026-10-14.md) unchanged; [oldsystemraw](system-first4k-raw-live-2026-10-14.md) plus [bulk2048](paired-nor25000-four-live-2026-10-14.md) still contiguous6144B`[24000,25800)`, no regeneration. Full4MiB backup/reliable restore/ownfirmware incomplete. Currentvariable-byte issue needs a separate justified method; no automaticrepeat or broad mask. [Verified RAM-prefill known0/4200 control](verified-prefill-control-plan-2026-10-14.md) is a **plan/implementation only, not live**: oneconnection/fiveDL/four owned-filewrites/15transactions/0newcoverage, strict4096prefix+independentoracles mandatory. It does not retroactively validate this failed variable tail.

Exact frozen host-only reproduction, private originals/isolatedcopy required; no device/file writes. Script consumes privatebytes locally but prints no factorycontent or digest:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/paired-nor-factory-first4-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime
from pathlib import Path
from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_runtime as R
root=Path('artifacts/paired-nor-factory-first4-20261014');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={};error='ValueError: Current chain depends on tail outside difference-proven written prefix'
def pin(path,digest=None):
 p=Path(path);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
job=json.loads(pin(root/'report.json','ff4b584ca01ad11ab0f2c5775e08500acc2688b9ef631b725d947e8c385b97c3'));plan=json.loads(pin(root/'plan.json','a5736ce9d45f8204dab7c71088199095bf3010ef6505c1e0f34beba0ebba65be'));mp=root/'source-snapshot/manifest.json';manifest=json.loads(pin(mp,'9af7580903246d32070e9e59933b126b79cb72c335216ecf9a365d6563e7ff24'));review=json.loads(pin(root/'preflight-review.json'))
assert len(manifest['source_files'])==140 and len(manifest['test_files'])==122 and review['new_full_check_run'] is False and review['private_factory_raw'] is review['no_system_codec_decode'] is True
for e in manifest['source_files']+manifest['test_files']:
 for base in (mp.parent,Path(review['isolated_source'])):assert len(pin(base/e['path'],e['sha256']))==e['bytes']
assert job['ok'] is False and job['error']==error and 'verification' not in job and plan['offsets']==[0x1ec000,0x1ec200,0x1ec400,0x1ec600]
A.J.time_order(manifest['created_at'],plan['planned_at'],job['started_at'],job['ended_at']);baseline=A.C.source_gate(plan,image)
cp=Path('artifacts/paired-nor-status-content-checkpoint-20261014');checkpoint=json.loads(pin(cp/'checkpoint.json','44671cc064c673c0643621d4e20a35b884589e2c8ab5dec3d3d6b12420503f48'));cp_ring,cp_state,cp_summary=A.C.parent_gate(cp,image)
assert cp_summary==plan['parent'] and cp_ring==baseline==pin(cp/'baseline.bin') and len(cp_summary['prior_names'])==42 and checkpoint['live_capture_performed'] is False and checkpoint['new_raw_nor_coverage_bytes']==0
proofs,previous,state=A.completed_prefix(job,plan,root,baseline);assert len(proofs)==len(job['completed'])==1 and proofs[0]['raw_range']==[0x1ec000,0x1ec200] and proofs[0]['paired_bytes']==512
accepted_path=root/plan['pages'][0]['directory'];accepted=json.loads(pin(accepted_path/'report.json','db765e41b3c270f90e2bc482a52443344a011b40eddc56cb02e91bdf9f5b705e'));pin(accepted_path/'session.btsnoop','4991ddf64c7e899f6f14488fcf4519652dc92130623c773e943f7e00d24f0dd6')
assert accepted['ok'] is True and len(accepted['att_packets'])==182 and accepted['hci_capture']['records']==318 and accepted['verification']['status_events']['events']==0
assert len(pin(accepted_path/'first/sector.bin'))==512 and pin(accepted_path/'first/sector.bin')==pin(accepted_path/'second/sector.bin')
for label in ('baseline','first','second'):pin(accepted_path/label/'download.bin')
slot=plan['pages'][1];path=root/slot['directory'];report=json.loads(pin(path/'report.json','3ced0d93deb87e7e69f4cd533378909f6eeea7af1566cb2035071b346d6aaa05'));page=A.C.page_plan(plan,1,state,job['completed'][0]['ended_at']);R.plan_gate(report,page,path)
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
assert errors(job)=={'.error':error} and errors(report)=={'.error':error,'.capture_error':error,'.operations[1].error':error}
assert report['ok'] is False and 'verification' not in report and len(report['operations'])==2
warm,first,second=report['baseline'],*report['operations'];assert warm['ok'] is warm['live_complete'] is first['ok'] is first['live_complete'] is True
assert second['ok'] is second['live_complete'] is False and second['barrier_complete'] is True and 'verification' not in second and not (path/'second/sector.bin').exists()
for stage in (warm,first,second):
 A.J.time_order(report['started_at'],stage['started_at'],stage['ended_at'],report['ended_at']);assert (datetime.fromisoformat(stage['ended_at'])-datetime.fromisoformat(stage['started_at'])).total_seconds()<18
A.J.time_order(job['started_at'],accepted['ended_at'],report['started_at'],report['ended_at'],job['ended_at']);raw=pin(path/'session.btsnoop','d9f8239a7c3bbe6bb3a72ac55ce52265f3b4ac3cfe8dafdcd42f4592f05deedb');observed,wire,events=A.envelope(report,path,9)
assert len(raw)==25213 and observed['records']==318 and len(report['att_packets'])==182 and events['events']==0
assert report['before']==state and report['predecessor_state_verification']==A.verify_state(state,report['before'],sd_write=False)
A.E.bridge(report,report['before_span'][1],report['file_list_span'][0]);assert A.inventory(report,page)==report['listed_count'];startup=observed['transactions'][0]
assert report['startup_settlement']==startup and report['startup_classification']==A.startup.classify(startup)
context={'state':state,'boundary':report['file_list_span'][1],'previous_tx':startup,'cursor':1,'previous':previous};transfers,context=A.transfer_group(report,report,page,path,observed,wire,context);A.final_identity(report,wire,context,9)
for label in ('baseline','first','second'):pin(path/label/'download.bin')
first_proof=A.C.payload(first,transfers[0],previous);assert first_proof==first['verification'] and pin(path/'first/sector.bin')==bytes.fromhex(first_proof['sector_hex'])
try:A.C.payload(second,transfers[1],transfers[0])
except ValueError as exc:
 assert str(exc)==error.removeprefix('ValueError: ');trace=exc.__traceback__
 while trace and trace.tb_frame.f_code.co_name!='_parse_ring':trace=trace.tb_next
 assert trace is not None;v=trace.tb_frame.f_locals;assert v['prefix']==v['physical']==4095 and v['column']==41 and transfers[1][4095]==transfers[0][4095]==ord('f')
 assert 10<=v['column']<=57 and (v['column']-10)%3 in (0,1)
else:raise AssertionError('Original variable-byte failure no longer reproduced')
assert context['previous']==pin(path/'second/download.bin') and context['state']==report['after'] and report['after']['device']['free_capacity']==59589
assert len(set(plan['parent']['prior_names'])|set(A.C.nonces(plan)))==50 and all(o['actions_verification']['f0_frames']==0 for p in (accepted,report) for o in p['operations'])
for later in plan['pages'][2:]:assert not any(p.is_file() for p in (root/later['directory']).rglob('*'))
for gate in (A.replay,A.C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Original failed factory whole job admitted')
receipt=Path('docs/evidence/factory-first4-failed-2026-10-14.json')
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
print('PASS frozen privatefactory acceptedpair512+failed9comm;364ATT/636HCI/18txn/6DL;currentprivate4096/state59589/50reserved;variable-lowhex-tailreject/0promotion;',len(origins),'snapshot modules;',len(checked),'pinned inputs unchanged; no private content/hash printed')
PY
```
