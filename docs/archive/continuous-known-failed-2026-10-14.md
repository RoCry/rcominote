# Continuous two-known-pair control: original failure, 2026-10-14

Frozen [metadata](../evidence/continuous-known-failed-2026-10-14.json); private originals `artifacts/paired-nor-continuous-known-20261014`. **Original15-transaction/two-group control failed; zero new NOR coverage, no new public binary.** Group0 boot0 baseline/first completed, second4096 download/SLOW/immediate real identity completed but originalv3 payload proof rejected. Group0candidate=false; group1 known4200 both zeroI/O, no extra baseline/continuation. No completed independentpair or known-content control success.

Distinct failure receipt replays original `A.envelope(...,9)`, `A.transfer_group(...,operation_count=2)` and `A.final_identity(...,9)`; never changes the15-transaction success audit or original flags. Full GATT/181ATT↔317HCI/25164B, startupFAST plus baselinehost/SLOW and twoFAST-host-SLOW producer cycles: nine complete transactions/0pending/status. Three complete4096 downloads/two existing-file overwrite attempts, both exact6ACK/F1/pending0/F0=0, actual download windows and all real barriers; final normaldisconnect status0/reason0x16 atHCI316 after finalATT, passive observation2.166227s≤8, clean SIGINT/monitor exit0. Zero newfiles/deletions; cohort70confirmed+1olderdeclared+1historicalpossible=max72 unchanged.

**Current file and final state observed, but parent admission rejects.** Latest2026-10-14T10:20:56.749642Z FW010004/NOTEidle/unbound/charging100/free59589; complete second/current4096 **ring** SHA **`87146b6b9e18eca8af8c09e3fcfe074260386d38ebed08aefbab91c98b34d364`**. Initial baseline exactly matches successfulbulkf678…c2a8; all integer capacities59589, other identity fields unchanged. Unlike prior [17-transaction timeout](two-known-session-failed-2026-10-14.md), this failure has a complete finalidentity, so currentfile/state are notunknown. Yet wholejob/source parent stays failed;34 successful ancestor names +4 original planned nonces=38 reserved names, not an admitted-parent history. No automatic continuation/retry.

Frozen original `C.payload(second,current,first)` reproduces exactly `ValueError: Current chain depends on tail outside difference-proven written prefix`. Exception locals show differenceprefix4095, first unproven physical4095/current==previous ASCII`0`, within status literal`buf=0x`. That non-space status byte lies outside the original proof prefix and is not an allowedv3 row-address padding-space exemption. No whole4096 overwrite/precise root-cause inference. First boot0 independently matches its original oracle; **second has no accepted payload/sector.bin**, no new-policy parse, NOR/codec/oracle comparison, public bytes or coverage. Original failure not upgraded by this review.

Immutable plan10:20:12.872372Z, job10:20:24.389882Z–10:20:56.749642Z. Snapshot139source/119tests manifest **de1e5023031b69a370b918c77f082594ca37451172568df0376333817c8e3a35**, created10:20:12.347186Z beforeplan/start. All258 lengths/hashes verified, all97 imported project modules fromsnapshot. Manifest records root pre-I/O2216tests+159subtests/314formatted/lint/build passed; independent replay does not rerun that full suite or change oldW0's2137 count. Full successfulbulk/W0/failed17/older source chain replayed; directfailed15 replay and parentadmission still reject.

[Bulk2048](paired-nor25000-four-live-2026-10-14.md) and original [first4KiB](system-first4k-raw-live-2026-10-14.md) remain frozen, **strong41232B/potential196436B/systemcontiguous6144B`[24000,25800)` unchanged**. Full4MiB backup/reliable restore/own firmware incomplete. Next narrow formatter proof/independent communication checkpoint is under review only; no implementation/live result claimed here. Rawrings/HCI/nonce/identity bytes stay private; no source/test/device operations by this review.

Exact host-only frozen replay, repository root/private originals required; no device access or file writes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/paired-nor-continuous-known-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime
from pathlib import Path
from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_runtime as R
root=Path('artifacts/paired-nor-continuous-known-20261014');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={};error='ValueError: Current chain depends on tail outside difference-proven written prefix'
def pin(path,digest=None):
 p=Path(path);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
def refs(v):
 if isinstance(v,dict):
  if {'file','bytes','sha256'}<=v.keys() and Path(v['file']).is_file():assert len(pin(v['file'],v['sha256']))==v['bytes']
  for x in v.values():refs(x)
 elif isinstance(v,list):
  for x in v:refs(x)
report=json.loads(pin(root/'report.json','cf756524d4d95db28f135a419a5881d39cee25dc07286aa9aa370b8aea01bc87'));plan=json.loads(pin(root/'plan.json','5d11450e6239d96b182c85f1711f374b16f513f167dc942f41618c933ac2239c'));mp=root/'source-snapshot/manifest.json';manifest=json.loads(pin(mp,'de1e5023031b69a370b918c77f082594ca37451172568df0376333817c8e3a35'))
assert len(manifest['source_files'])==139 and len(manifest['test_files'])==119
for e in manifest['source_files']+manifest['test_files']:assert len(pin(mp.parent/e['path'],e['sha256']))==e['bytes']
assert manifest['checks']=={'just_check':'2216 passed,159 subtests passed in31.62s;314formatted/lint passed','uv_build':'sdist+wheel passed'}
assert report['ok'] is False and plan['profile']==A.C.CONTINUOUS_CONTROL and 'verification' not in report
R.plan_gate(report,plan,root);baseline=A.C.source_gate(plan,image);assert sha(baseline)=='f6781e2966e47b548c6b2f0f5ccd2c48d19b97cd172c1d1b4dd7d7b08a28c2a8'
A.J.time_order(manifest['created_at'],plan['planned_at'],report['started_at'],report['ended_at'])
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
raw=pin(root/'session.btsnoop','2f06088f01477e9f96ceeae38c32b9cd24931bdc4a77f61ea2556f622b04ef96');observed,wire,events=A.envelope(report,root,9)
assert len(raw)==25164 and observed['records']==317 and len(report['att_packets'])==181 and events['events']==0
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
assert sha(transfers[1])=='87146b6b9e18eca8af8c09e3fcfe074260386d38ebed08aefbab91c98b34d364' and not (root/plan['pages'][0]['directory']/'second/sector.bin').exists()
try:A.C.payload(second,transfers[1],transfers[0])
except ValueError as exc:
 assert str(exc)==error.removeprefix('ValueError: ');trace=exc.__traceback__
 while trace and trace.tb_frame.f_code.co_name!='_parse_ring':trace=trace.tb_next
 assert trace is not None;local=trace.tb_frame.f_locals;assert local['prefix']==local['physical']==4095 and transfers[1][4095]==transfers[0][4095]==ord('0') and b'buf=0x' in local['status'][0]
else:raise AssertionError('Original frozen payload rejection no longer reproduced')
assert g1=={'group_index':1,'nor_offset':0x4200,'operations':[o|{'live_complete':False,'ok':False} for o in plan['pages'][1]['operations']],'live_complete':False,'candidate':False,'continuation':None}
assert 'baseline' not in g1 and not any(p.is_file() for p in (root/plan['pages'][1]['directory']).rglob('*'))
assert all(o['actions_verification']['f0_frames']==0 for o in g0['operations']) and observed['disconnects'][0]['record']==316
for gate in (A.replay,A.C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Original failed continuous control admitted')
assert len(set(plan['parent']['prior_names'])|set(A.C.nonces(plan)))==38
receipt=Path('docs/evidence/continuous-known-failed-2026-10-14.json')
if receipt.exists():refs(json.loads(receipt.read_bytes()))
origins=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in allowed for p in origins)
assert all(sha(p.read_bytes())==digest for p,digest in checked.items())
print('PASS frozen failed15 control/distinct9txn communication;181ATT/317HCI/3DL;current8714/state59589/38reserved;originalprefix4095ASCII0reject;0NORcoverage/noadmission;',len(origins),'snapshot modules;',len(checked),'pinned inputs unchanged')
PY
```
