# Prefilled factory activity one: fixed pair success, 2026-10-15

[Sanitized metadata](../evidence/prefilled-factory-activity-one-live-2026-10-15.json); private originals `artifacts/prefilled-factory-activity-one-20261015`. **Independent fixed1ecc00 pair succeeded**, adding512privatephysicalbytes`[1ecc00,1ece00)`. WholeUTC14日18:43:43.274495–18:44:23.255244 = HKT15日02:43:43–02:44:23; page18:43:48.507707–18:44:23.247140. This receipt is ASOF thissingletrial; laterplans/captures require separatevalidation and receipts.

**ActualstartupFAST, no startup pulse.** NewexplicitFAST-or-DEFAULT policy was pinned; actualFAST followed the unchanged15transaction branch. IntegratedDEFAULT→threeACK/F1/zeroF0 pulse→actualFAST→host6→baseline branch **not radioexercised**. BothNORgapforms were **plain / composer-before-crlf**; newlyallowed exactwake notice and CRLF-before-composer form not exercised here. Old [notice startupfailure](prefilled-factory-notice-one-live-2026-10-15.md), [NEXT3gapfailure](prefilled-factory-next3-failed-2026-10-15.md) and otherfailures remainfailed, never reclassified by newpolicy.

**261ATT/451HCI/38700B,15completeparametertransactions/0pending/status, normaldisconnect0x16.** FullGATT/hostATT/HCI/epoch/commandcounts/downloadwindows/causalFASTordering/statebarriers replayed. Freshfull4096baseline exactly matched admittedownedSDobject before any overwrite. EachNORread followed its own **complete4096RAM prefill matching independentRAMoracle**; twofresh512NORsectors from separateproducers/nonces equal byte-for-byte. Both retainedcarrier criticalchains require strict4096differenceprefix, no exemptions, independentNORbyteoracle or fill/selection. Allfiveoriginalstages, originalpageproof and wholejobproof reproduce exactly before acceptance.

**1connection/5downloads/2RAMexports/2NORproducers/4sameownedfileSDoverwrites/0newfiles/NORwrites/deletes**. This is not zero storagewriting. Finalactualcurrentownedfile4096 and parentgate verified; before==after FW010004/NOTEidle/unbound/charging100/free59589. Actualfinalidentityresponse **18:44:21.057460Z**, distinct frompageend23.247140/wholeend23.255244. History72+2fresh=**74reservednames**; scratchcohort70confirmed+1olddeclared+1historicalpossible=max72 unchanged, different measure.

Formalhostdefaultcheckpoint `artifacts/prefilled-factory-default-checkpoint-20261015/checkpoint.json`, SHAf8709545602b0321deebaf03d4026b703935d850f60333fe1e4547079f61f248: 0deviceI/O/coverage; oldnoticeCP5eb2 observedSD4096/provenance carried forward through originalnotice-one zero-write proof and latestidentity18:13:06.952796/history72. No newSDread at thatcheckpointidentity claimed, residentprintkring not assumedunchanged. **This successfultrial supplies the requiredfreshlivebaseline reread**. Originalnotice-one/NEXT3false and oldCPs remainimmutable.

Frozen **153source/140tests/293files**, manifestaa5a0b4faf2bc4c49db74e08ecf50b9124f929d7c8c9a02d25cb5bc30b58818e. Attachedsnapshot/isolatedcopy all lengths/hashes equal; freshpreIO2786tests+159subtests/56.73s,351format/lint/build,357declaredinputs before==after. Manifest < checkpoint < immutableplan < whole/pagecapture; independent106snapshotmodules reverify fullsource/parent/CP/content/wire and successfulparentadmission. No latercurrent-root code/check claim.

Coverage overlay now **A44816/B155204/potential200020B**, factory3584completepaired/4608missing, systemcontiguous6144B`[24000,25800)` unchanged. [ASOF inventory](nor-backup-coverage-2026-10-14.md), oldfrozenreceipts/privatecaptures/publicbinaries unchanged. Factory/carrier/sector bytes/digests/hex and nonces withheld; metadata only/no newbinary. Full4MiB backup/reliable restore/ownruntime incomplete; no atomicwholeflash or restoreability claim. Futurefinite acquisition requires a newfixedplan/sourcegate; no automaticretry or extension.

[Host-only throughput context](../../artifacts/raw-export-throughput-host-review-20261015/evidence.json), SHA23ac6c5da08d874451b8335d77824cae24651bdabe47526dd922cbae7d6c6b5f: reviewedactlog/sdfs2consumer does not establish a binarybridge. Failure-free linear36s/512pair projection is81.16h/4MiB,160MiBDL/128MiBSDwrites, **not ETA or newcapability**; do not blindly scale thisroute to wholeflash. Thisreceipt pins thereview, does not independentlyrederive itsstaticsemantics.

Exact host-only frozen replay; private originals/isolatedcopy required. No device/evidence writes or privatecontenthash output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/prefilled-factory-activity-one-20261015/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime,UTC
from pathlib import Path
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_pages as N
root=Path('artifacts/prefilled-factory-activity-one-20261015');pre=Path('artifacts/prefilled-factory-activity-preflight-20261015');cp=Path('artifacts/prefilled-factory-default-checkpoint-20261015');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={}
def pin(p,h=None):
 p=Path(p);b=p.read_bytes();digest=sha(b);assert h is None or digest==h;checked[p.resolve()]=digest;return b
m=json.loads(pin(root/'source-snapshot/manifest.json','aa5a0b4faf2bc4c49db74e08ecf50b9124f929d7c8c9a02d25cb5bc30b58818e'));review=json.loads(pin(root/'preflight-review.json'));assert (len(m['source_files']),len(m['test_files']))==(153,140)
for row in m['source_files']+m['test_files']:
 for base in (root/'source-snapshot',Path(review['isolated_source'])):assert len(pin(base/row['path'],row['sha256']))==row['bytes']
checks=json.loads(pin(pre/'checks-before.json'));assert checks==json.loads(pin(pre/'checks-after.json')) and len(checks)==357 and review['new_full_check_run'] is True
checkpoint=json.loads(pin(cp/'checkpoint.json','f8709545602b0321deebaf03d4026b703935d850f60333fe1e4547079f61f248'));baseline,state,source=C.parent_gate(cp,image);assert len(baseline)==4096 and state['device']['free_capacity']==59589 and len(source['prior_names'])==72 and source['verification']['new_raw_nor_coverage_bytes']==0 and checkpoint['original_job_ok'] is False
assert source['latest_identity_response_at']=='2026-10-14T18:13:06.952796+00:00' and source['current_object_live_download_required_before_overwrite'] is True
plan=json.loads(pin(pre/'plan.json','11383ed4baffde1254aa1830593717d43c432e9b8a5585d9fb3ba3def8406939'));assert plan['parent']==source and C.source_gate(plan,image)==baseline and plan['offsets']==[0x1ecc00] and plan['gap_policy']==C.F.PREFILL_WAKE_GAP_POLICY and plan['content_policy']==C.F.STRICT_POLICY and plan['startup_policy']==C.startup.POLICY
N.source_ram(plan,image);assert plan['budget']==N.budgets(1,startup_policy=C.startup.POLICY);assert plan['budget']['max_parameter_transactions']==16 and plan['budget']['max_startup_pulses']==1 and plan['budget']['max_startup_commands']==3;C.J.time_order(m['created_at'],checkpoint['created_at'],plan['planned_at'])
job=json.loads(pin(root/'report.json','435925dd8ffb04e0f7a0d664d893f1bf434e40f4e22af5174b8b034d56b6ccda'));assert job['ok'] is True and len(job['completed'])==1
assert pin(root/'plan.json')==pin(pre/'plan.json');C.J.time_order(plan['planned_at'],job['started_at'],job['ended_at']);proof=N.A.replay(root,image);assert proof==job['verification']
page=root/plan['pages'][0]['directory'];r=json.loads(pin(page/'report.json','41299c162c2f3299bb4ee0080aad36943eb8399569ae29cc26ad7ff2d6cf0c0c'));pp=C.page_plan(plan,0,state,source['ended_at']);N.plan_gate(r,pp,page);assert r['ok'] is True and N.validate(r,page,pp,baseline)==r['verification']
raw=pin(page/'session.btsnoop','90506b4dd4cc42ec1d233968e11a91ff6739038876234482a05c969f72e797e6');observed,wire,events=N.A.envelope(r,page,15);assert len(raw)==38700 and observed['records']==451 and len(r['att_packets'])==261 and events['events']==0 and not observed['pending']
assert r['startup_classification']['mode']=='fast' and 'startup_pulse' not in r and r['verification']['startup_control']=={'mode':'fast','pulse_performed':False}
ram=N.source_ram(plan,image);transfers,context,_=N.communication(r,page,pp,baseline,ram);assert len(transfers)==4 and context['cursor']==15
assert (page/'baseline/download.bin').read_bytes()==baseline and transfers[0]==transfers[2]==ram
sectors=[];layouts=[]
for op in r['operations']:
 assert op['ok'] is op['live_complete'] is op['barrier_complete'] is True and op['sd_write_attempted'] is True
 if op['kind']=='nor':
  sector=pin(page/op['operation_id']/'sector.bin');assert len(sector)==512 and sector==bytes.fromhex(op['verification']['sector_hex']) and op['verification']['independent_oracle'] is False;sectors.append(sector)
  fresh=op['verification']['freshness'];assert fresh['difference_proven_written_prefix_bytes']==4096;layouts.append(fresh['producer_dump_gap']['form'])
assert sectors[0]==sectors[1] and layouts==['plain','composer-before-crlf'];assert r['before']==r['after']==state and r['after']['device']['free_capacity']==59589
identity_at=datetime.fromtimestamp((wire[r['after_span'][1]-1][2]-N.A.P.H.EPOCH_US)/1_000_000,UTC).isoformat();assert observed['disconnects'][0]['reason']==0x16
current,latest,admitted=C.parent_gate(root,image);assert current==transfers[-1] and len(current)==4096 and latest==r['after'] and len(admitted['prior_names'])==74
for old in ('artifacts/prefilled-factory-next3-20261015','artifacts/prefilled-factory-notice-one-20261015'):
 try:N.A.replay(Path(old),image)
 except ValueError:pass
 else:raise AssertionError('Historical failed job promoted')
receipt=Path('docs/evidence/prefilled-factory-activity-one-live-2026-10-15.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for value in v.values():refs(value)
  elif isinstance(v,list):
   for value in v:refs(value)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(v.__file__).resolve() for n,v in sys.modules.items() if n.startswith('rcominote') and getattr(v,'__file__',None)];allowed={(root/'source-snapshot'/row['path']).resolve() for row in m['source_files']};assert all(p in allowed for p in origins) and all(sha(p.read_bytes())==h for p,h in checked.items())
print('PASS originalsingle1ecc00SUCCESS/fullsourceCP/freshbaseline/fullRAMboth/strict4096independentpair512;261ATT451HCI15txn0pendingstatus/normal16;FASTnoPULSE/plain+oldcomposerONLY/DEFAULTintegrated+wakegapUNTESTED;5DL4samefilewrites0newfiles;current4096history74/finalidentity',identity_at,'free59589;',len(origins),'frozenmodules;',len(checked),'pinsunchanged;privatecontent withheld')
PY
```
