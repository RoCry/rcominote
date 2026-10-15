# Private factory: three new pairs passed; four-page job failed, 2026-10-15

[Sanitized metadata](evidence/prefilled-factory-four-live-2026-10-15.json); originals private `artifacts/prefilled-factory-four-20261015`. **Original wholejob failed after three complete private512B pairs.** Only physical`[1ec200,1ec800)` adds1536B strong rawcoverage. Fourth`1ec800` has zero application writes/downloads/NORproducers/coverage. UTC14日16:38:49.868992–16:40:52.894850 = HKT15日00:38:49–00:40:52. No factory raw/config/sector/carrierhex/contenthash/nonce publication, binary or systemcodec comparison.

| Original target | Actual result |
|---|---|
|1ec200|Full twofreshNOR reads, each independently RAM-prefilled; strictprefix4096, twoactual512 results equal;512 private bytes accepted|
|1ec400|Same full originalpair/allwire/state/window/nonce/dualprevious gates;512 private bytes|
|1ec600|Same full originalpair; first producer→dump exact oldcomposer-before-CRLF form, second plain;512 private bytes|
|1ec800|Owned LEconnect succeeds, partialMTU/GATTdiscovery then supervisiontimeout; no identity/baseline/Actions/RAMexport/NOR/SDwrite;0bytes|

Three successfulconnections independently revalidate with frozen `A.completed_prefix`/originalpageaudit: **787ATT/1357HCI/116240B,45complete parameter transactions/0pending/status,15full4096 downloads/sixRAMexports/sixNORproducers/12existing-file overwrites/0newfiles**. Every prefill matches independent RAM4096 oracle ending48; every NOR has strict4096 logicaldifference-prefix against immediateRAMfile, wholecriticalchain/noformatterexemptions, separate retainedNORmarker/nonce predecessor, twofresh results equal. All exact4/6ACK/F1/F0streams retained, actualFAST/host/DL/EOF SLOW windows, eachidentity/statebarrier and finalnormaldisconnect verified. ActualfourstageACKs eachpage4,6,4,6/F0all0; allsixNORprefixes4096. Gaps plain×5/oldcomposer-before-CRLF×1; newly addedCRLF-before-composer form still notradioexercised. No independent factorybyteoracle or oracle-filling.

**Fourth failure is incomplete GATT after LE established, not “LE never connected”.** Captured58HCI/2242B, exact21host/HCI ATT packets; connect#18 status0/initial48,4,600, disconnect#57 status0/reason08, errno110. TXopcodes02,10,03,10,10,10,08,08,04,04,04 are MTU/discovery only; lastFindInformation04 has noresponse. No12/16/18/52 ATTwrite/prepare/execute/command, completeGATT/CCC, identity, startupsettlement, baseline/download or application action. Derivedownedlink exists only in offline localview to bind original21packets; originalreport transport remains{}, falseflags/emptyfourstages untouched. Clean ownedmonitor stop; whole `TimeoutError: [Errno 110] Connection timed out`/captureerror retained. Whole replay/parentgate reject, no retry.

**Last verified identity response:** UTC16:40:42.033534Z on thirdconnection; thirdpage ends16:40:44.229530Z. FW010004/NOTEidle/unbound/charging100/free59589 unchanged across completedstages. Fourthstarts16:40:44.857300Z/ends16:40:52.894702Z, wholeends16:40:52.894850Z; **no fourth/postfailure identity**. Last fullprivate4096 file is thirdsecond; absence of fourthapplicationwrites supports expectedretention, not a fresh postfailure readback/state. Originalwhole remains inadmissible until a separate proven checkpoint/recovery; none exists for this failure.54ancestor+8planned=62reserved names, including fourthtwo unsent; not62successfulobservations. Cohort70confirmed+1olderdeclared+1historicalpossible=max72 unchanged; no deletes/NORmemorywrites/RAMmemorywrites.

Source **146source/132tests**, ab996996de7b2da0c35153fd79b872da95a6c7fe1ca6d97f15f513b465198635; all278 lengths/hashes equal attachedsnapshot/isolatedfactorycopy. FreshpreIO **2610tests+159subtests/45.77s,336format/lint/build**,342inputs before==after, `new_full_check_run=true`. Source<immutableplan<start/end; all102 imported projectmodules fromsnapshot. Complete parent [knownv2control](prefilled-known-v2-live-2026-10-15.md), precedingCONTENTcheckpoint/originalv1failure/factoryoldprefix chain replayed. Original accepted512 factorypair and all oldfailedflags/receipts immutable. No current-source test assertion beyond the frozen capture.

Coverage overlay **strong43280B/potential198484B** = prior41744/196948 +1536. With [historicalfactoryfirstpair512](factory-first4-failed-2026-10-14.md), fullypaired privatefactory union`[1ec000,1ec800)` totals2048B; **6144B of factory8KiB still lacks fullpair**, including fourth512. [FrozenASOF inventory](nor-backup-coverage-2026-10-14.md) unchanged/B155204 not upgraded; [systemfirst4KiB](system-first4k-raw-live-2026-10-14.md)+[bulk2048](paired-nor25000-four-live-2026-10-14.md) contiguous6144B`[24000,25800)` unchanged. Multi-capture union is not a wholeflash atomic snapshot. Full4MiB backup/reliable restore/ownruntime incomplete; no automatic retry or extension. User controls remain only reportedpowerbutton/recordslider; RESET/exposedremovablebattery/independentROMexit still unproven. [Deletion static boundary](file-deletion.md#hidden-scratch-bounded-static-follow-up-2026-10-14) unchanged/no deletion authorization.

Exact host-only frozen replay; private originals/isolatedcopy required. No device/evidence writes or privatecontent/hash/nonce output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/prefilled-factory-four-20261015/source-snapshot/src uv run python - <<'PY'
import copy,hashlib,json,sys
from datetime import datetime,UTC
from pathlib import Path
from rcominote.experiments import prefilled_nor_pages as P
from rcominote.experiments.hci_monitor import Snoop
A,C=P.A,P.C;root=Path('artifacts/prefilled-factory-four-20261015');pre=Path('artifacts/prefilled-factory-four-preflight-20261015');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={};error='TimeoutError: [Errno 110] Connection timed out'
def pin(p,digest=None):
 p=Path(p);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
job=json.loads(pin(root/'report.json','5c8d1b61681f1a8fce3f7d1bfb0c4185d644f90f87d2a0351b7fdc79ee0269a0'));plan=json.loads(pin(root/'plan.json','96ad9ddeb5768af833cb7f88eb57bb570f7e69a067b1e288ede475ce96f709fc'));mp=root/'source-snapshot/manifest.json';m=json.loads(pin(mp,'ab996996de7b2da0c35153fd79b872da95a6c7fe1ca6d97f15f513b465198635'));review=json.loads(pin(root/'preflight-review.json'));assert len(m['source_files'])==146 and len(m['test_files'])==132
for e in m['source_files']+m['test_files']:
 for base in (mp.parent,Path(review['isolated_source'])):assert len(pin(base/e['path'],e['sha256']))==e['bytes']
before=json.loads(pin(pre/'checks-before.json'));assert before==json.loads(pin(pre/'checks-after.json')) and len(before)==342 and review['new_full_check_run'] is True
assert job['ok'] is False and job['error']==error and 'verification' not in job and len(job['completed'])==3 and plan['profile']==P.PROFILE and plan['offsets']==[0x1ec200,0x1ec400,0x1ec600,0x1ec800]
C.J.time_order(m['created_at'],plan['planned_at'],job['started_at'],job['ended_at']);baseline=C.source_gate(plan,image);assert len(plan['parent']['prior_names'])==54 and len(C.nonces(plan))==8
proofs,current,state=A.completed_prefix(job,plan,root,baseline);assert len(proofs)==3 and sum(p['paired_bytes'] for p in proofs)==1536 and [p['raw_range'] for p in proofs]==[[0x1ec200,0x1ec400],[0x1ec400,0x1ec600],[0x1ec600,0x1ec800]]
previous,ended=baseline,plan['parent']['ended_at'];totals=[0,0,0];status=[];forms=[];last_identity=None
for i,slot in enumerate(plan['pages'][:3]):
 directory=root/slot['directory'];r=json.loads(pin(directory/'report.json'));page=C.page_plan(plan,i,r['expected_before'],ended);assert A.validate_page(r,directory,page,previous)==r['verification']==proofs[i]
 raw=pin(directory/'session.btsnoop');observed,wire,events=A.envelope(r,directory,15);totals=[x+y for x,y in zip(totals,[len(r['att_packets']),observed['records'],len(raw)],strict=True)];status.append(events['events'])
 assert r['ok'] is True and r['after']==state and all(o['ok'] is o['live_complete'] is o['barrier_complete'] is True for o in [r['baseline'],*r['operations']])
 assert observed['disconnects'][0]['reason']==0x16 and not observed['pending']
 for stage in [r['baseline'],*r['operations']]:pin(directory/stage['operation_id']/'download.bin')
 for o in r['operations']:
  assert o['actions_verification']['f0_frames']==0
  if o['kind']=='nor':
   fresh=o['verification']['freshness'];assert fresh['difference_proven_written_prefix_bytes']==4096 and fresh['critical_chain_inside_written_prefix'] is True and 'prefix_policy' not in fresh;forms.append(fresh['producer_dump_gap']['form']);pin(directory/o['operation_id']/'sector.bin')
 assert pin(directory/'first/sector.bin')==pin(directory/'second/sector.bin') and len(pin(directory/'first/sector.bin'))==512
 previous=pin(directory/'second/download.bin');ended=r['ended_at'];last_identity=datetime.fromtimestamp((wire[r['after_span'][1]-1][2]-A.P.H.EPOCH_US)/1_000_000,UTC).isoformat()
assert previous==current and len(current)==4096 and state['device']['free_capacity']==59589 and totals==[787,1357,116240]
slot=plan['pages'][3];directory=root/slot['directory'];r=json.loads(pin(directory/'report.json'));page=C.page_plan(plan,3,state,ended);P.plan_gate(r,page,directory);C.J.time_order(ended,r['started_at'],r['ended_at'],job['ended_at'])
assert r['ok'] is False and r['error']==r['capture_error']==error and r['transport']=={} and r['status_events']==[] and r['monitor_exit']==0 and r['monitor_stop']=={'signal':'SIGINT','requested':True,'delivery':'sent'}
assert not any(k in r for k in ('before','after','before_span','after_span','setup_end','gatt_proof','file_list_span','startup_settlement','verification'))
assert r['baseline']=={'operation_id':'baseline','name':C.F.NAME,'ok':False,'live_complete':False}
for o,s in zip(r['operations'],slot['operations'],strict=True):assert o==s|{'ok':False,'live_complete':False}
for label in P.STAGES:assert not any(p.is_file() for p in (directory/label).rglob('*'))
raw=pin(directory/'session.btsnoop','23c57119fb9f6a1718d8d0c8cebd329c27d1d88a4243596a8390d12f8a63892d');snoop=Snoop();snoop.feed(raw,final=True);assert snoop.records==58 and len(raw)==2242 and [e['kind'] for e in snoop.events]==['controller','connect','disconnect']
controller,connect,disconnect=snoop.events;assert connect['status']==0 and connect['record']==18 and connect['address']==A.P.H.PEER and [connect[k] for k in ('interval','latency','timeout')]==[48,4,600] and disconnect['record']==57 and disconnect['status']==0 and disconnect['reason']==8
link={'peer':connect['address'],'controller':'hci0','local':controller['address'],'handle':connect['handle']};view=copy.deepcopy(r);view['transport']={'link':link};observed=A.P.inspect(raw,link=link,final=True);assert not observed['transactions'] and not observed['pending'] and A.dual_hci.bind(view,raw)['packets']==21
wire=A.dual_hci.att_packets(raw,connect['handle']);tx=[int(p['hex'][:2],16) for p in wire if p['direction']=='tx'];assert tx==[2,16,3,16,16,16,8,8,4,4,4] and wire[-1]['direction']=='tx' and wire[-1]['hex'].startswith('04') and not any(code in tx for code in (0x12,0x16,0x18,0x52))
assert r['hci_capture']=={'bytes':len(raw),'sha256':sha(raw),'records':58} and len(r['att_packets'])==21
assert all(type(row['monotonic_ns']) is int for row in r['att_packets']) and all(a['monotonic_ns']<=b['monotonic_ns'] for a,b in zip(r['att_packets'],r['att_packets'][1:]))
start_us,end_us=[A.P.H.EPOCH_US+int(datetime.fromisoformat(r[k]).timestamp()*1_000_000) for k in ('started_at','ended_at')];assert all(start_us<=row['timestamp_us']<=end_us for row in wire) and start_us<=connect['timestamp_us']<=disconnect['timestamp_us']<=end_us
assert len(set(plan['parent']['prior_names'])|set(C.nonces(plan)))==62
for gate in (A.replay,C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Original partial failedwhole admitted')
receipt=Path('docs/evidence/prefilled-factory-four-live-2026-10-15.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for x in v.values():refs(x)
  elif isinstance(v,list):
   for x in v:refs(x)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(v.__file__).resolve() for n,v in sys.modules.items() if n.startswith('rcominote') and getattr(v,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in m['source_files']};assert all(p in allowed for p in origins);assert all(sha(p.read_bytes())==h for p,h in checked.items())
print('PASS frozenfullchain/threeprivatepairs1536/strict4096/RAMoracle/failedfourth21ATTMTU-GATTonly/LEconnectthenreason08/zeroappwrite/wholefailedretained;total808ATT1415HCI118482B/45txn15DL12overwrites;lastidentity',last_identity,'lastsuccessfulpageend',ended,'state59589/62reserved;',len(origins),'snapshotmodules;',len(checked),'inputsunchanged; no factorydata/hash/nonce printed')
print('Actualstatuscounts',status,'NORgapforms',forms)
PY
```
