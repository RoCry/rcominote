# Prefilled factory activity next4b: failed whole, acceptedprefix512, 2026-10-15

[Sanitized metadata](../evidence/prefilled-factory-activity-next4b-live-2026-10-15.json); private originals `artifacts/prefilled-factory-activity-next4b-20261015`. **Originalfour-page whole failed**, completedprefix=onepair: page0-1ed600 adds512privatephysicalbytes`[1ed600,1ed800)`. Page1-1ed800 service-discovery timeout, page2-1eda00/page3-1edc00 zeroI/O. WholeUTC14日18:56:29.085249–18:57:31.566596 = HKT15日02:56:29–02:57:31. Originalwhole/page1false and `TimeoutError: [Errno 110] Connection timed out`/captureerror retained; successfulprefix is not successfulwhole/parentadmission.

Acceptedpage0 originallysuccessful: **262ATT/452HCI/38735B,15complete/0pending/status, normal0x16**. ActualFAST/no startup pulse; freshfull4096baseline equals actual [next4a parent](prefilled-factory-activity-next4a-live-2026-10-15.md). Both4096RAMprefills match independentoracle; twofreshNORproducers/nonces produce byte-identical512 sectors with strict4096differenceprefix/no exemptions or independentNORbyteoracle. Completeoriginal5stages, source/plan/parent, GATT/ATT/HCI/epoch, downloadwindows, actualFASTordering/statebarriers and completedledgerentry replayed. **5downloads/2RAM/2NOR/4sameownedfileSDoverwrites/0newfiles/NORwrites**; newlyintegratedDEFAULT and wake form stillnotradioexercised.

Failedpage1: **21ATT/58HCI/2242B**, successfulownedLEconnect atrecord18/status0/initial48,4,600; disconnect57/status0/reason0x08 after unansweredFindInformation. TXopcodes02,10,03,10,10,10,08,08,04,04,04 are MTU/discovery only; zeroATT12/16/18/52 writes, CCC/application/identity/inventory/download/Actions/RAMexport/NORproducer/SDwrite. Originaltransport{} and missingbefore/after/setup proof stay unchanged. Baseline+fourstage slots exactuntouched/false, allstagedirs empty. RawHCIderivedlink is used only for forensicbinding; host/wire eachdirection matches exactly, **no sorting/dropping/resynchronization**, no repairedreport. This was LEconnected then partialGATT supervisiontimeout, not failure to establish anyLElink. Laterpages have nofiles/reports/I/O.

Total **283ATT/510HCI/40977B/15complete/0pending/status**, one normal0x16 and one timeout0x08. Lastactualcompleteownedfile is **page0second4096**, before laterfailedpage's zero-write path; not freshlyread back afterfailure and wholeparentgate stillrejects. Acceptedpage0 finalidentity **18:57:20.885464Z** FW010004/NOTEidle/unbound/charging100/free59589; pageend23.084480 distinct fromfailedpage23.821348–31.566412/wholeend31.566596. Reserve all82+8plannednames=**90**, includingunsent; scratchcohort70confirmed+1olddeclared+1historicalpossible=max72 unchanged and different measure.

Later productionCLIinfo succeeded on a **separateconnection, without HCIcapture**; locallyserialmatches and sanitizedstateFW010004/NOTEidle/unbound/charging100/free59589. Infofilemtime observationupperbound **19:00:39.549829Z** is not exactresponse time. It cannot fill originalfailedpageafter, make originalwhole successful or verify ownedSDfile. Newhelper offline review is separate from capturedaa5a semantics; thisreceipt claims no newhelperfullcheck/freeze, formalcheckpoint, newplan or liveexecution. Any futureadmission requires its own completechecks and frozencheckpoint/plan; no automaticretry.

Inherited unchanged **aa5a153source/140tests/293files**; allattachedsnapshot/isolatedlengths/hashes equal. Originalcheckwindow2786tests+159subtests/56.73s,351format/lint/build/357declaredinputs before==after; **new_full_check_run=false** for next4b. Manifest < actual4aparentend < immutableplan < whole/pagecapture; independent106snapshotmodules validate completeoriginalsource and acceptedprefix/failurewire. Newmutable-source checks are not substituted for originalpolicy; originalfailedreplay and parentgate reject.

Coverage overlay **A47376/B155204/potential202580B**, factory**6144/8192B** actualcontiguous`[1ec000,1ed800)`, missing2048`[1ed800,1ee000)`; systemcontiguous6144B`[24000,25800)` unchanged. [FrozenASOF inventory](nor-backup-coverage-2026-10-14.md), firstsegmentCRC observation, oldONE/4a/notice/BOOT0receipts/captures unchanged. No newpublicbinary or factory/carrier/sector bytes/hash/hex/nonce. Full4MiB backup/reliable restore/ownruntime incomplete; no atomicwholefactory/runtime-active/restore proof. [Hostthroughput boundary](prefilled-factory-activity-one-live-2026-10-15.md) remains non-ETA/no binarybridge.

Exact frozen host-only acceptedprefix and originalfailure forensicreplay; private originals/isolatedcopy required. No device/evidence writes or privatecontenthash output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/prefilled-factory-activity-next4b-20261015/source-snapshot/src uv run python - <<'PY'
import copy,hashlib,json,sys
from datetime import datetime,UTC,timedelta
from pathlib import Path
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_pages as N
from rcominote.experiments.hci_monitor import Snoop
A=N.A;root=Path('artifacts/prefilled-factory-activity-next4b-20261015');pre=Path('artifacts/prefilled-factory-activity-next4b-preflight-20261015');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={};error='TimeoutError: [Errno 110] Connection timed out'
def pin(p,h=None):
 p=Path(p);b=p.read_bytes();digest=sha(b);assert h is None or digest==h;checked[p.resolve()]=digest;return b
m=json.loads(pin(root/'source-snapshot/manifest.json','aa5a0b4faf2bc4c49db74e08ecf50b9124f929d7c8c9a02d25cb5bc30b58818e'));review=json.loads(pin(root/'preflight-review.json'));assert (len(m['source_files']),len(m['test_files']))==(153,140)
for row in m['source_files']+m['test_files']:
 for base in (root/'source-snapshot',Path(review['isolated_source'])):assert len(pin(base/row['path'],row['sha256']))==row['bytes']
inherited=Path(review['inherited_check_directory']);checks=json.loads(pin(inherited/'checks-before.json'));assert checks==json.loads(pin(inherited/'checks-after.json')) and len(checks)==357 and review['new_full_check_run'] is False
plan=json.loads(pin(root/'plan.json','8b42920a0da2d8aa6f940911c2cd2d4d2a61b2c265a93302c6054dbf4ac68ee6'));assert pin(pre/'plan.json')==pin(root/'plan.json') and plan['offsets']==[0x1ed600,0x1ed800,0x1eda00,0x1edc00] and len(plan['parent']['prior_names'])==82
baseline=C.source_gate(plan,image);ram=N.source_ram(plan,image);job=json.loads(pin(root/'report.json','b8a3ee5051e3e815c99ceb2096766923be3f80945a853e5524530f603784a1c1'));assert job['ok'] is False and job['error']==error and len(job['completed'])==1
C.J.time_order(m['created_at'],plan['parent']['ended_at'],plan['planned_at'],job['started_at'],job['ended_at']);proofs,current,state=A.completed_prefix(job,plan,root,baseline);assert len(proofs)==1 and proofs[0]['bytes']==512 and proofs[0]['independent_oracle'] is False
page=root/plan['pages'][0]['directory'];r=json.loads(pin(page/'report.json','ad67d0e30e9b8fb079f2f02bd9288cef7fc093f027bca2cba303192f0f406a0c'));raw=pin(page/'session.btsnoop','918d592d25804b578d11d30f744b0ce686245d76bfc0b75103987d95f4568987');observed,wire,events=A.envelope(r,page,15);assert len(raw)==38735 and observed['records']==452 and len(r['att_packets'])==262 and events['events']==0
pp=C.page_plan(plan,0,plan['expected_before'],plan['parent']['ended_at']);assert N.validate(r,page,pp,baseline)==r['verification'] and r['startup_classification']['mode']=='fast' and 'startup_pulse' not in r
transfers,context,_=N.communication(r,page,pp,baseline,ram);assert transfers[0]==transfers[2]==ram and context['cursor']==15 and current==transfers[-1]==pin(page/'second/download.bin') and len(current)==4096
sectors=[];forms=[]
for op in r['operations']:
 if op['kind']=='nor':
  sector=pin(page/op['operation_id']/'sector.bin');assert sector==bytes.fromhex(op['verification']['sector_hex']) and len(sector)==512;sectors.append(sector);fresh=op['verification']['freshness'];assert fresh['difference_proven_written_prefix_bytes']==4096;forms.append(fresh['producer_dump_gap']['form'])
assert sectors[0]==sectors[1] and state==r['after']==r['before'] and state['device']['free_capacity']==59589 and observed['disconnects'][0]['reason']==0x16
identity_at=datetime.fromtimestamp((wire[r['after_span'][1]-1][2]-A.P.H.EPOCH_US)/1_000_000,UTC).isoformat();assert identity_at=='2026-10-14T18:57:20.885464+00:00';accepted_end=r['ended_at']
slot=plan['pages'][1];d=root/slot['directory'];failed=json.loads(pin(d/'report.json','dc0144b22f8035784b91e077f74b0423a9b39c4e40b3d74787399ce9d66c1714'));pp=C.page_plan(plan,1,state,accepted_end);N.plan_gate(failed,pp,d);C.J.time_order(accepted_end,failed['started_at'],failed['ended_at'],job['ended_at'])
assert failed['ok'] is False and failed['error']==failed['capture_error']==error and failed['transport']=={} and failed['status_events']==[] and failed['monitor_exit']==0 and failed['monitor_stop']=={'signal':'SIGINT','requested':True,'delivery':'sent'}
assert not any(k in failed for k in ('before','after','before_span','after_span','setup_end','gatt_proof','file_list_span','startup_settlement','verification')) and failed['baseline']=={'operation_id':'baseline','name':C.F.NAME,'ok':False,'live_complete':False}
for op,s in zip(failed['operations'],slot['operations'],strict=True):assert op==s|{'ok':False,'live_complete':False}
for label in N.STAGES:assert not any(p.is_file() for p in (d/label).rglob('*'))
for s in plan['pages'][2:]:assert not any(p.is_file() for p in (root/s['directory']).rglob('*'))
raw=pin(d/'session.btsnoop','6e850776414bd8bc9ba6e122a33e6a12c7ef5d797ca8f03cf63f3ce46f7022e3');snoop=Snoop();snoop.feed(raw,final=True);assert len(raw)==2242 and snoop.records==58 and [e['kind'] for e in snoop.events]==['controller','connect','disconnect']
controller,connect,disconnect=snoop.events;assert connect['status']==0 and connect['record']==18 and connect['address']==A.P.H.PEER and [connect[k] for k in ('interval','latency','timeout')]==[48,4,600] and disconnect['record']==57 and disconnect['status']==0 and disconnect['reason']==8
link={'peer':connect['address'],'controller':'hci0','local':controller['address'],'handle':connect['handle']};view=copy.deepcopy(failed);view['transport']={'link':link};p=A.P.inspect(raw,link=link,final=True);assert not p['transactions'] and not p['pending'] and A.dual_hci.bind(view,raw)['packets']==21
packets=A.dual_hci.att_packets(raw,connect['handle']);tx=[int(row['hex'][:2],16) for row in packets if row['direction']=='tx'];assert tx==[2,16,3,16,16,16,8,8,4,4,4] and packets[-1]['direction']=='tx' and packets[-1]['hex'].startswith('04') and not any(v in tx for v in (0x12,0x16,0x18,0x52))
assert len(failed['att_packets'])==21 and failed['hci_capture']=={'bytes':len(raw),'sha256':sha(raw),'records':58};assert all(type(row['monotonic_ns']) is int for row in failed['att_packets']) and all(a['monotonic_ns']<=b['monotonic_ns'] for a,b in zip(failed['att_packets'],failed['att_packets'][1:]))
start_us,end_us=[A.P.H.EPOCH_US+int(datetime.fromisoformat(failed[k]).timestamp()*1_000_000) for k in ('started_at','ended_at')];assert all(start_us<=row['timestamp_us']<=end_us for row in packets) and start_us<=connect['timestamp_us']<=disconnect['timestamp_us']<=end_us
assert len(set(plan['parent']['prior_names'])|set(C.nonces(plan)))==90
for gate in (A.replay,C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Original failed whole promoted')
postpath=root/'post-failure-info.json';post=json.loads(pin(postpath));assert post['serial']==state['serial'] and post['bound'] is False and post['device']['free_capacity']==59589 and post['device']['version']=='010004' and post['device']['mode']=='note' and post['device']['recording_state']=='idle' and post['device']['charging'] is True and post['device']['battery']==100
ns=postpath.stat().st_mtime_ns;upper=(datetime(1970,1,1,tzinfo=UTC)+timedelta(microseconds=(ns+999)//1000)).isoformat();C.J.time_order(job['ended_at'],upper)
receipt=Path('docs/evidence/prefilled-factory-activity-next4b-live-2026-10-15.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for value in v.values():refs(value)
  elif isinstance(v,list):
   for value in v:refs(value)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(v.__file__).resolve() for n,v in sys.modules.items() if n.startswith('rcominote') and getattr(v,'__file__',None)];allowed={(root/'source-snapshot'/row['path']).resolve() for row in m['source_files']};assert all(p in allowed for p in origins) and all(sha(p.read_bytes())==h for p,h in checked.items())
print('PASS originalwholeFAILED/acceptedprefix1equalpair512/strict4096/fullRAMsource;failure21ATT58HCIonlyMTUdiscovery/no appwrite/identity/DL/Actions/SD;LEconnectedthenreason08;283ATT510HCI40977B15txn0pendingstatus;current4096frompage0second/history90/lastidentity',identity_at,'state59589;separateinfoNOHCI upper',upper,'doesnotrepairfailure;',len(origins),'frozenmodules;',len(checked),'pinsunchanged;privatecontent withheld')
PY
```
