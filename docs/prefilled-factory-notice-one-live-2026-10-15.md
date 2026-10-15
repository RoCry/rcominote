# Prefilled factory notice one: startup failure, 2026-10-15

[Sanitized metadata](evidence/prefilled-factory-notice-one-live-2026-10-15.json); private originals `artifacts/prefilled-factory-notice-one-20261015`. **Unique fixed1ecc00 trial failed, zero completedpairs/newcoverage**. WholeUTC14日18:12:53.718677–18:13:09.027473 = HKT15日02:12:53–02:13:09; page18:12:58.973261–18:13:09.027036. Originalerror/captureerror: `ValueError: Startup tuple is outside its explicit FAST/DEFAULT policy`. Originalwhole/pagefalse preserved; no retry, newlive or extension.

**Wake-gap-v3 radio branch UNREACHED.** Fixedplan selected exactwakegap-v3 plus strictfull4096prefix, targetonly1ecc00, max1connection/5downloads/2RAMexports/2NORproducers/4samefileoverwrites/15transactions/512newbytes. Runtime still invokes legacyFAST-only startup. ActualremoteDEFAULT24..40/0/500 accepted and fullyapplied36; originalclassifier rejects it before baseline start. Diagnostic broad-policy classification verifies actualDEFAULT, never changes the originalpolicy or promotes the failure. No FAST or hostnormalization occurred. This trial does not test the newgap grammar, NORcontents or writefreshness.

**61ATT/123HCI/5123B, one completeparametertransaction/0pending/status, normaldisconnect0x16 at122.** FullGATT and exacthostATT/HCI binding verified; allapplicationtraffic partitions into beforeidentity34..40, inventory40..55, finalidentity55..61 aftersetup34. Both identities complete and equal expectedcheckpointstate: FW010004/NOTEidle/unbound/charging100/free59589. Actualfinalidentityresponse **18:13:06.952796Z**, distinct frompageend09.027036/wholeend09.027473. Baseline and allfourstage slots remain exactuntouched/false, no stage started_at/attemptflag, allstage directories empty. **0downloads/Actions/RAMexports/NORproducers/SDwrites/newfiles/coverage**; inventory and identity reads did occur. No firmwareflash readfailure inference.

Formal host-only noticecheckpoint `artifacts/prefilled-factory-notice-checkpoint-20261015/checkpoint.json`, SHA5eb25bddf858cc4453e692470114048da81c7811153d2fab36f2d16ea894f21b: 0deviceI/O/coverage, original [NEXT3failure](prefilled-factory-next3-failed-2026-10-15.md) stillfalse; original9transaction completecommunication/currentownedSD4096/free59589/history70 and originalthree-gap contentfailure independently replayed. It adopts observedownedSDobject/provenance, not an unchangedresidentprintkring assumption. Intervening [RAMcontrol](actions-fast-ram256-live-2026-10-15.md), [BOOT0failure](actions-fread-boot0-live-2026-10-15.md) and separateCLIinfo had0SDwrites. This newtrial also0SDwrites, but **no livebaseline reread**, so do not call its ownedfile freshlyverifiedcurrent. CheckpointASOF70 remainsimmutable; two newplannedunsent NORnames must remainreserved, futurehistory**72**. This differs from scratchcohort70confirmed+1olddeclared+1historicalpossible=max72; neither count means two newfiles or producers ran.

Frozen **151source/138tests/289files**, manifestdd58df82ee91e6f4807df2f372b1609eff8b86d5e13bd744aa0125e108966669. Attachedsnapshot/isolatedcopy all lengths/hashes equal; freshpreIO2745tests+159subtests/48.62s,347format/lint/build,353declaredinputs before==after. Source18:11:11.256548Z < checkpoint18:11:29.460591Z < immutableplan18:11:30.181168Z < whole/pagecapture. Independent104snapshotmodules reverify completeparent/source/CP/originalfailure/rawparameter/GATT/identity/inventory/time proofs. No latercurrent-root code/check claim.

Coverage unchanged **A44304/B155204/potential199508B**, factory3072completepaired/5120missing, systemcontiguous6144B`[24000,25800)`. [ASOF inventory](nor-backup-coverage-2026-10-14.md) and all oldfrozenreceipts/binaries/captures unchanged. Factory/carrier/sector bytes/digests/hex and nonces private; no newbinary. Full4MiB backup/reliable restore/ownruntime incomplete. Futurehostdesign must explicitly admit DEFAULT, require actualFAST **beforebaseline**, and preserve all72reserved names; merely reconnecting untilFAST or relaxing the oldfailedpolicy is not a validnewresult. No furthercheckpoint or nextplan created after this startup failure; no automaticrepeat/scale-up.

Exact frozen host-only replay; private originals/isolatedcopy required. No device/evidence writes or contenthash output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/prefilled-factory-notice-one-20261015/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime,UTC
from pathlib import Path
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_pages as N
A=N.A;sha=lambda b:hashlib.sha256(b).hexdigest();checked={};error='ValueError: Startup tuple is outside its explicit FAST/DEFAULT policy'
root=Path('artifacts/prefilled-factory-notice-one-20261015');pre=Path('artifacts/prefilled-factory-notice-preflight-20261015');image=Path('artifacts/mapped-system-20261012.bin');cp=Path('artifacts/prefilled-factory-notice-checkpoint-20261015')
def pin(p,h=None):
 p=Path(p);b=p.read_bytes();digest=sha(b);assert h is None or digest==h;checked[p.resolve()]=digest;return b
job=json.loads(pin(root/'report.json','cd342e8f91b1efcedb4fa8322553ff5070f8dbbb3d4b9798c43e1af6b2f56ae3'));plan=json.loads(pin(root/'plan.json','31aa34bcfa141d258f36366cb27735bffd5bfc4e372c253c1a3e9f6ed66e00b9'));mp=root/'source-snapshot/manifest.json';m=json.loads(pin(mp,'dd58df82ee91e6f4807df2f372b1609eff8b86d5e13bd744aa0125e108966669'));review=json.loads(pin(root/'preflight-review.json'));assert (len(m['source_files']),len(m['test_files']))==(151,138)
for row in m['source_files']+m['test_files']:
 for base in (mp.parent,Path(review['isolated_source'])):assert len(pin(base/row['path'],row['sha256']))==row['bytes']
checks=json.loads(pin(pre/'checks-before.json'));assert checks==json.loads(pin(pre/'checks-after.json')) and len(checks)==353 and review['new_full_check_run'] is True
checkpoint=json.loads(pin(cp/'checkpoint.json','5eb25bddf858cc4453e692470114048da81c7811153d2fab36f2d16ea894f21b'));baseline,state,source=C.parent_gate(cp,image);assert len(baseline)==4096 and state['device']['free_capacity']==59589 and len(source['prior_names'])==70 and source['verification']['new_raw_nor_coverage_bytes']==0 and checkpoint['original_job_ok'] is False and checkpoint['original_failed_content_ok'] is False
assert plan['parent']==source and C.source_gate(plan,image)==baseline and plan['offsets']==[0x1ecc00] and plan['gap_policy']==C.F.PREFILL_WAKE_GAP_POLICY and plan['content_policy']==C.F.STRICT_POLICY;N.source_ram(plan,image);assert plan['budget']==N.budgets(1)
assert job['ok'] is False and job['completed']==[] and job['error']==error and job['profile']==plan['profile'] and job['budget']==plan['budget'];C.J.check_reference(root,job['plan']);C.J.time_order(m['created_at'],checkpoint['created_at'],plan['planned_at'],job['started_at'],job['ended_at'])
page=root/plan['pages'][0]['directory'];r=json.loads(pin(page/'report.json','cd42f081c4b208c8c860856f89cd28d917a0df05b8a8e394a3b357919f557d23'));pp=C.page_plan(plan,0,state,source['ended_at']);N.plan_gate(r,pp,page);assert r['ok'] is False and r['error']==r['capture_error']==error and set(k for k in r if 'error' in k)=={'error','capture_error'} and 'verification' not in r
C.J.time_order(job['started_at'],r['started_at'],r['ended_at'],job['ended_at']);assert r['startup_policy']==C.startup.LEGACY_POLICY and 'startup_settlement' not in r and 'startup_classification' not in r
assert r['baseline']=={'operation_id':'baseline','name':C.F.NAME,'live_complete':False,'ok':False}
for op,slot in zip(r['operations'],pp['operations'],strict=True):assert op==slot|{'ok':False,'live_complete':False}
for label in N.STAGES:assert not any(p.is_file() for p in (page/label).rglob('*'))
raw=pin(page/'session.btsnoop','0430812dfff8e9a52da0546e5194d20728e82b384a3403926da7a82728118076');observed,wire,events=A.envelope(r,page,1);assert len(raw)==5123 and observed['records']==123 and len(r['att_packets'])==61 and events['events']==0 and not observed['pending']
transaction=observed['transactions'][0];classification=C.startup.classify(transaction,policy=C.startup.POLICY);assert classification['mode']=='default' and classification['parameters']==[24,40,0,500] and classification['requires_fast_before_normalization'] is True and transaction['update']['interval']==36
try:C.startup.classify(transaction,policy=r['startup_policy'])
except ValueError as exc:assert f'ValueError: {exc}'==error
else:raise AssertionError('Original legacyFAST rejection not reproduced')
assert r['before']==r['after']==state and r['before_verification']==A.A.identity(r,r,'before') and r['after_verification']==A.A.identity(r,r,'after')
assert r['predecessor_state_verification']==A.verify_state(state,r['before'],sd_write=False);A.E.bridge(r,r['before_span'][1],r['file_list_span'][0]);assert A.inventory(r,pp)==r['listed_count'];A.final_identity(r,wire,{'state':state,'boundary':r['file_list_span'][1],'cursor':1},1)
assert r['setup_end']==34 and r['before_span']==[34,40] and r['file_list_span']==[40,55] and r['after_span']==[55,61];assert not any(v['direction']=='tx' and v['hex'][:6] in ('121600','521600') for v in r['att_packets'])
identity_at=datetime.fromtimestamp((wire[r['after_span'][1]-1][2]-A.P.H.EPOCH_US)/1_000_000,UTC).isoformat();assert observed['disconnects'][0]['reason']==0x16 and observed['disconnects'][0]['record']==122
assert len(set(source['prior_names'])|set(C.nonces(plan)))==72 and len(C.nonces(plan))==2
for gate in (A.replay,C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Original failed whole incorrectly promoted')
receipt=Path('docs/evidence/prefilled-factory-notice-one-live-2026-10-15.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for value in v.values():refs(value)
  elif isinstance(v,list):
   for value in v:refs(value)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(v.__file__).resolve() for n,v in sys.modules.items() if n.startswith('rcominote') and getattr(v,'__file__',None)];allowed={(mp.parent/row['path']).resolve() for row in m['source_files']};assert all(p in allowed for p in origins) and all(sha(p.read_bytes())==h for p,h in checked.items())
print('PASS originalwholeFAILED/legacyFASTrejectsactualcompleteDEFAULT36/wakegapUNREACHED;61ATT123HCI1txn0pendingstatus/fullGATTbefore-list-after/normal16;0DL-Actions-RAMexport-NORproducer-SDwrites-coverage;CP70hostASOF/plannedunsent2/history72/cohort72distinct;currentSDnotfreshread;',identity_at,'finalidentity59589;',len(origins),'frozenmodules;',len(checked),'pinnedinputsunchanged;privatecontent withheld')
PY
```
