# STATUS4 known control: original failure, 2026-10-14

Frozen [metadata](evidence/status-known-failed-2026-10-14.json); private originals `artifacts/paired-nor-status-known-20261014`. **Original STATUS4 known15 control failed; zero new NOR coverage/public binary.** Group0 baseline8714/firstboot0 complete; second4096/SLOW/immediate identity and globalfinalafter complete, but originalSTATUS4 payload rejects. Group0candidate/livecomplete=false; group1 known4200 both zeroI/O, no extra baseline/continuation. First alone matches original boot0 oracle, no completedpair/control success.

Original `C.payload(second,current,first)` reproduces `ValueError: Current chain depends on tail outside difference-proven written prefix`. Exception locals: prefix4095; physical4095/current==previous ASCIIspace, **row25/column42=`12+3*10` trailing separator**, explicitly still strict in originalSTATUS4. Existing row-leading-padding/status-interior-literal policy does not exempt that separator. No secondsector.bin; no new-mask parse, second oracle/codec comparison, publication, coverage or full4096-write/root-cause claim. Firstprefix4096/statusliteralexemptions[]; this first observation alone does not exercise the status-exemption branch. Prior [v3 ASCII0 failure](continuous-known-failed-2026-10-14.md), strict/v2 and17transaction failures remain original failures.

Distinct failure receipt uses original `A.envelope(...,9)`, `A.transfer_group(...,operation_count=2)`, `A.final_identity(...,9)` without relabelling the original15-transaction success audit. Full GATT/182ATT↔319HCI/25227B, nine complete transactions/0pending/status,3complete4096 downloads/2existing-file overwrites, two exact6ACK/F1/pending0/F0=0; startupFAST, bothactualFAST-host6-download-EOF SLOW windows and all realidentity barriers. Final normaldisconnect status0/reason0x16 atHCI318 after finalATT, passive observation2.167256s≤8; clean SIGINT/monitor exit0. Zero newfiles/deletions, cohort70confirmed+1olderdeclared+1historicalpossible=max72 unchanged.

**Current file/state observed, not yet an admitted parent.** Latest2026-10-14T10:50:08.889093Z FW010004/NOTEidle/unbound/charging100/free59589; fullsecond/current4096 **ring** SHA **`02c4d169642728323622c3369455be5d7b71a448eb6898cfb6394fcf9976a6c4`**. Initial baseline exactly8714…d364; all integer capacities59589/otheridentityequal. Parentgate/directwholejobreplay reject this failed STATUS4 job.38 ancestor names+4newplanned=42reserved, not admitted-parent history; no automatic continuation/retry.

Actual preceding **offline content checkpoint** `artifacts/paired-nor-content-checkpoint-20261014/checkpoint.json`, SHA **53f83b23e3d73498882972ecdd018172f479141148393ad9548d3e857bd6e299**, created10:48:19.459016Z, adopts only complete originalv3failedsecond communication/current4096=8714…d364/state/history38. Source/role/error and all nine originaltransactions reverified; originalfailedjob/operationfalse, **0deviceI/O/0coverage**, original observation remains10:20:56.749642Z rather than a freshlive observation. Attached545snapshotmatches this control's preIOsource. STATUS4 actualbaseline matched all4096 before newoverwrite. Generic CONTENTrole extension to fully completed STATUS failures is current implementation work; no latercheckpoint/mask/live success claimed.

Frozen140source/122tests manifest **545c5f014b4d895da3586ada36acad87958d05285740eb4ae8df28cd2d64d2c4**, created10:48:18.926882Z < actualcheckpoint < immutableplan10:49:23.012360Z < start10:49:37.208304Z < end10:50:08.889093Z. All262 capture and attached-checkpoint source/test lengths/hashes verified, all98 importedprojectmodules fromsnapshot. Root preIOmanifest2294tests+159subtests/319formatted/lint/build passed; replay is independent, fullsuite not rerun and oldcheckcounts unchanged. Full original ancestor/checkpoint/failedsources replayed; no current changing-source substitution.

[Bulkraw2048](paired-nor25000-four-live-2026-10-14.md)/original [first4KiB](system-first4k-raw-live-2026-10-14.md) unchanged: **strong41232B/potential196436B/systemcontiguous6144B`[24000,25800)`**. Full4MiB backup/reliable restore/ownfirmware incomplete. Next completeformatter constant-mask proof under review, not live; no broad parser relaxation or reclassification of this failure. Existing [hidden-scratch deletion static boundary](file-deletion.md#hidden-scratch-bounded-static-follow-up-2026-10-14) unchanged; overwriting authorization does not authorize deletion, no delete operation. Private rawrings/HCI/nonce/identity not published; no source/test/device edits by this review.

Exact host-only frozen replay, repository root/private originals required; no device access or file writes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/paired-nor-status-known-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime
from pathlib import Path
from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_runtime as R
root=Path('artifacts/paired-nor-status-known-20261014');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={};error='ValueError: Current chain depends on tail outside difference-proven written prefix'
def pin(path,digest=None):
 p=Path(path);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
def refs(v):
 if isinstance(v,dict):
  if {'file','bytes','sha256'}<=v.keys() and Path(v['file']).is_file():assert len(pin(v['file'],v['sha256']))==v['bytes']
  for x in v.values():refs(x)
 elif isinstance(v,list):
  for x in v:refs(x)
report=json.loads(pin(root/'report.json','95903f2ed549f9f676af35be6504c5f8517262455f013abdde52ca02d812be21'));plan=json.loads(pin(root/'plan.json','68dda7fef8722ec5969bb0af9628e4b0081dd9d3d50d9cebf6953e5e64cc89b2'));mp=root/'source-snapshot/manifest.json';manifest=json.loads(pin(mp,'545c5f014b4d895da3586ada36acad87958d05285740eb4ae8df28cd2d64d2c4'))
assert len(manifest['source_files'])==140 and len(manifest['test_files'])==122
for e in manifest['source_files']+manifest['test_files']:
 for base in (mp.parent,Path('artifacts/paired-nor-content-checkpoint-20261014/source-snapshot')):assert len(pin(base/e['path'],e['sha256']))==e['bytes']
assert manifest['checks']=={'just_check':'2294passed+159subtests31.41s;319formatted/lint passed','uv_build':'sdist+wheel passed'}
assert report['ok'] is False and plan['profile']==A.C.STATUS_CONTROL and 'verification' not in report
R.plan_gate(report,plan,root);baseline=A.C.source_gate(plan,image);assert sha(baseline)=='87146b6b9e18eca8af8c09e3fcfe074260386d38ebed08aefbab91c98b34d364'
A.J.time_order(manifest['created_at'],plan['planned_at'],report['started_at'],report['ended_at'])
cp=Path('artifacts/paired-nor-content-checkpoint-20261014');checkpoint=json.loads(pin(cp/'checkpoint.json','53f83b23e3d73498882972ecdd018172f479141148393ad9548d3e857bd6e299'))
assert pin(cp/'source-snapshot/manifest.json')==mp.read_bytes();cp_ring,cp_state,cp_summary=A.C.parent_gate(cp,image)
assert cp_summary==plan['parent'] and cp_ring==baseline==pin(cp/'baseline.bin') and len(cp_summary['prior_names'])==38 and cp_state==plan['expected_before']
assert checkpoint['live_capture_performed'] is False and checkpoint['original_job_ok'] is checkpoint['original_operation_ok'] is False and checkpoint['new_raw_nor_coverage_bytes']==0
A.J.time_order(manifest['created_at'],checkpoint['created_at'],plan['planned_at'])

def errors(v,path=''):
 found={}
 if isinstance(v,dict):
  for k,x in v.items():
   p=path+'.'+k
   if k.endswith('error') and x:found[p]=x
   found.update(errors(x,p))
 elif isinstance(v,list):
  for i,x in enumerate(v):found.update(errors(x,path+f'[{i}]'))
 return found
assert errors(report)=={'.error':error,'.capture_error':error,'.groups[0].operations[1].error':error}
raw=pin(root/'session.btsnoop','9a41204bb945c80491e7d78155aa8f14231d151694799384aa03561002c51cfa');observed,wire,events=A.envelope(report,root,9)
assert len(raw)==25227 and observed['records']==319 and len(report['att_packets'])==182 and events['events']==0
assert report['predecessor_state_verification']==A.verify_state(plan['expected_before'],report['before'],sd_write=False)
A.E.bridge(report,report['before_span'][1],report['file_list_span'][0]);assert A.inventory(report,plan)==report['listed_count']
startup=observed['transactions'][0];assert report['startup_settlement']==startup and report['startup_classification']==A.startup.classify(startup)
g0,g1=report['groups'];first,second=g0['operations'];assert g0['group_index']==0 and g0['nor_offset']==0 and g0['candidate'] is g0['live_complete'] is False
assert g0['baseline']['ok'] is g0['baseline']['live_complete'] is first['ok'] is first['live_complete'] is True
assert second['ok'] is second['live_complete'] is False and second['barrier_complete'] is True and 'verification' not in second and 'oracle_verification' not in second
assert g0['baseline']['operation_id']=='baseline' and g0['baseline']['name']==A.F.NAME and not any(k in g0['baseline'] for k in ('actions_start','producer','sd_write_attempted'))
for stage in (g0['baseline'],first,second):
 A.J.time_order(report['started_at'],stage['started_at'],stage['ended_at'],report['ended_at']);assert (datetime.fromisoformat(stage['ended_at'])-datetime.fromisoformat(stage['started_at'])).total_seconds()<18
page=A.C.page_plan(plan,0,report['before'],plan['parent']['ended_at']);context={'state':report['before'],'boundary':report['file_list_span'][1],'previous_tx':startup,'cursor':1,'previous':baseline}
transfers,context=A.transfer_group(report,g0,page,root/plan['pages'][0]['directory'],observed,wire,context,operation_count=2);A.final_identity(report,wire,context,9)
assert len(transfers)==2 and context['cursor']==9 and context['state']==report['after']==second['after'] and report['after']['device']['free_capacity']==59589
for label in ('baseline','first','second'):pin(root/plan['pages'][0]['directory']/label/'download.bin')
proof=A.C.payload(first,transfers[0],baseline);sector=bytes.fromhex(proof['sector_hex']);assert proof==first['verification'] and first['oracle_verification']==A.oracle_proof(plan,0,sector) and pin(root/plan['pages'][0]['directory']/'first/sector.bin')==sector
assert sha(transfers[1])=='02c4d169642728323622c3369455be5d7b71a448eb6898cfb6394fcf9976a6c4' and not (root/plan['pages'][0]['directory']/'second/sector.bin').exists()
try:A.C.payload(second,transfers[1],transfers[0])
except ValueError as exc:
 assert str(exc)==error.removeprefix('ValueError: ');trace=exc.__traceback__
 while trace and trace.tb_frame.f_code.co_name!='_parse_ring':trace=trace.tb_next
 assert trace is not None;local=trace.tb_frame.f_locals;assert local['prefix']==local['physical']==4095 and transfers[1][4095]==transfers[0][4095]==0x20 and local['row']==25 and local['column']==12+3*10
else:raise AssertionError('Original frozen payload rejection no longer reproduced')
assert g1=={'group_index':1,'nor_offset':0x4200,'operations':[o|{'live_complete':False,'ok':False} for o in plan['pages'][1]['operations']],'live_complete':False,'candidate':False,'continuation':None}
assert 'baseline' not in g1 and not any(p.is_file() for p in (root/plan['pages'][1]['directory']).rglob('*'))
assert all(o['actions_verification']['f0_frames']==0 for o in g0['operations']) and observed['disconnects'][0]['record']==318
for gate in (A.replay,A.C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Original failed continuous control admitted')
assert len(set(plan['parent']['prior_names'])|set(A.C.nonces(plan)))==42
receipt=Path('docs/evidence/status-known-failed-2026-10-14.json')
if receipt.exists():refs(json.loads(receipt.read_bytes()))
origins=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in allowed for p in origins)
assert all(sha(p.read_bytes())==digest for p,digest in checked.items())
print('PASS frozen STATUS4 failure/distinct9txn communication+actualofflineCP;182ATT/319HCI/3DL;current02c4/state59589/42reserved;originalprefix4095row25col42reject;0NORcoverage/noadmission;',len(origins),'snapshot modules;',len(checked),'pinned inputs unchanged')
PY
```
