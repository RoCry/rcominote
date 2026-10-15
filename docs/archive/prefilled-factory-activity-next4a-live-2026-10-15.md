# Prefilled factory activity next4a: finitefour-page success, 2026-10-15

[Sanitized metadata](../evidence/prefilled-factory-activity-next4a-live-2026-10-15.json); private originals `artifacts/prefilled-factory-activity-next4a-20261015`. **Originalfour-page whole succeeded**, new2048privatephysicalbytes`[1ece00,1ed600)`. WholeUTC14日18:49:29.122987–18:52:07.798133 = HKT15日02:49:29–02:52:07. Independent fixedoffsets1ece00/1ed000/1ed200/1ed400; later4b plans/captures are not part of thisreceipt.

Allfour actualstartups **FAST/no pulse**,15completeparametertransactions each/0pending. **One boundstatus20 event atpage2-1ed200 ATT96**, otherpages0; unchangedUSB-connected statuspolicy independently validates it. Normaldisconnect0x16 each. ATT262/263/263/265=**1053**; HCI450/453/453/455=**1811**, bytes38670/38770/38797/38840=**155077**. EightNORgapforms fourplain/fouroldcomposer-before-crlf; **integratedDEFAULT/pulse and newwake/CRLF-before-composer forms remain unexercised**. Originalnotice/NEXT3/BOOT0 failures remain unchanged.

Eachpage's freshfull4096baseline matches completeactualpredecessor beforeoverwrites. EightRAMprefills each fullymatch independent4096RAMoracle; eightfreshNORproducers each retainedstrict4096differenceprefix chain, pairedtwo512byte-for-byte equal at eachtarget. No independentNORbyteoracle, inference/fill/exemptions or codec selection. All original5stages/page and allfourcompletedledgerentries/wholeproof replay exactly with fullsource, immutableplan, GATT/ATT/HCI/epoch, downloadwindows/actualFASTordering/statebarriers and disconnects; successfulparentgate agrees.

**4connections/20downloads/8RAMexports/8NORproducers/16sameownedfileSDoverwrites/0newfiles/NORwrites/deletes**; active60s perpage unchanged. Latestcurrentownedfile4096 verified; finalidentityresponse **18:52:05.581566Z**, distinct fromlastpageend18:52:07.769037/wholeend18:52:07.798133. FW010004/NOTEidle/unbound/charging100/free59589 unchanged. History74+8=**82reservednames**, distinct from scratchcohort70confirmed+1olddeclared+1historicalpossible=max72.

Inherited unchanged **aa5a153source/140tests/293files**, allattachedsnapshot/isolated lengths/hashes equal. Originalcheckwindow2786tests+159subtests/56.73s,351format/lint/build/357declaredinputs before==after; **new_full_check_run=false** for this4a plan. Parent is actual [activityONEsuccess](prefilled-factory-activity-one-live-2026-10-15.md); manifest < parentend < immutableplan18:46:40.715882Z < wholecapture. Independent107snapshotmodules include boundedformatvalidator; no freshcheck or latermutable-root source claim.

Host-only [sanitized firstsegment check](../../artifacts/factory-first-segment-format-20261015/sanitized-summary.json): eightacceptedpairsectors from1ec000 through1ece00 assemble exactly4096privatebytes`[1ec000,1ed000)`, no FFfill/unreadpadding. ExistingNVSRversion1 headerCRC plus12boundedrecords' CRC/namehash/spans/padding pass; firstmeasuredemptyheader416 and actualremaining3680BFF. Fullancestor plus newpage0 provenance verified, full4a now independentlysuccessful. This strengthens completefirstsegmentformat evidence, **not complete8KiB/atomic/runtime-active/restore proof or extra coverage**. HeaderCRC is not a whole-segmentCRC; allkeys/values/contenthashes/binary stayprivate.

Coverage overlay **A46864/B155204/potential202068B**, factory5632completepaired/2560missing; systemcontiguous6144B`[24000,25800)` unchanged. [ASOF inventory](nor-backup-coverage-2026-10-14.md), oldONE and allfrozenreceipts/privatecaptures/publicbinaries unchanged. No newpublicbinary/factorycarrier/sector/nonce hashes or hex. Full4MiB backup/reliable restore/ownruntime incomplete. Laterfinite acquisitions require their ownfixedplan/sourcegate; no automaticretry/extension. [Priorhostthroughput boundary](prefilled-factory-activity-one-live-2026-10-15.md) remains non-ETA/no newbinarybridge.

Exact host-only frozen fullreplay and boundedprivateformat check; private originals/isolatedcopy required. No device/evidence writes or privatecontenthash output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/prefilled-factory-activity-next4a-20261015/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime,UTC
from pathlib import Path
from rcominote.experiments import paired_nor_plan as C
from rcominote.experiments import prefilled_nor_pages as N
from rcominote import nvram_image as NV
root=Path('artifacts/prefilled-factory-activity-next4a-20261015');pre=Path('artifacts/prefilled-factory-activity-next4a-preflight-20261015');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={}
def pin(p,h=None):
 p=Path(p);b=p.read_bytes();digest=sha(b);assert h is None or digest==h;checked[p.resolve()]=digest;return b
m=json.loads(pin(root/'source-snapshot/manifest.json','aa5a0b4faf2bc4c49db74e08ecf50b9124f929d7c8c9a02d25cb5bc30b58818e'));review=json.loads(pin(root/'preflight-review.json'));assert (len(m['source_files']),len(m['test_files']))==(153,140)
for row in m['source_files']+m['test_files']:
 for base in (root/'source-snapshot',Path(review['isolated_source'])):assert len(pin(base/row['path'],row['sha256']))==row['bytes']
inherited=Path(review['inherited_check_directory']);checks=json.loads(pin(inherited/'checks-before.json'));assert checks==json.loads(pin(inherited/'checks-after.json')) and len(checks)==357 and review['new_full_check_run'] is False
plan=json.loads(pin(root/'plan.json','49e0ea56171f5c85671d83dc6942b7eb66b79ce7df50554d58d735fc74920625'));assert pin(pre/'plan.json')==pin(root/'plan.json') and plan['offsets']==[0x1ece00,0x1ed000,0x1ed200,0x1ed400] and plan['startup_policy']==C.startup.POLICY and plan['gap_policy']==C.F.PREFILL_WAKE_GAP_POLICY
baseline=C.source_gate(plan,image);assert len(baseline)==4096 and len(plan['parent']['prior_names'])==74;ram=N.source_ram(plan,image)
job=json.loads(pin(root/'report.json','5dc165e9c50ec4299354f5da6256b43c1430b06eb54e1ade5a257e88e5f803cd'));assert job['ok'] is True and len(job['completed'])==4 and N.A.replay(root,image)==job['verification'];C.J.time_order(m['created_at'],plan['planned_at'],job['started_at'],job['ended_at'])
proofs,current,state=N.A.completed_prefix(job,plan,root,baseline);assert len(proofs)==4 and all(p['bytes']==512 and p['independent_oracle'] is False for p in proofs)
previous,latest,ended=baseline,plan['expected_before'],plan['parent']['ended_at'];counts=[];forms=[];identity_at=None
for index,slot in enumerate(plan['pages']):
 page=root/slot['directory'];r=json.loads(pin(page/'report.json'));pp=C.page_plan(plan,index,latest,ended);assert N.validate(r,page,pp,previous)==r['verification']
 raw=pin(page/'session.btsnoop');observed,wire,events=N.A.envelope(r,page,15);assert not observed['pending'] and events['events']==int(index==2) and r['startup_classification']['mode']=='fast' and 'startup_pulse' not in r
 transfers,context,_=N.communication(r,page,pp,previous,ram);assert context['cursor']==15 and transfers[0]==transfers[2]==ram and (page/'baseline/download.bin').read_bytes()==previous
 sectors=[]
 for op in r['operations']:
  if op['kind']=='nor':
   sector=pin(page/op['operation_id']/'sector.bin');assert sector==bytes.fromhex(op['verification']['sector_hex']) and len(sector)==512;sectors.append(sector);fresh=op['verification']['freshness'];assert fresh['difference_proven_written_prefix_bytes']==4096;forms.append(fresh['producer_dump_gap']['form'])
 assert sectors[0]==sectors[1] and r['before']==r['after']==latest and observed['disconnects'][0]['reason']==0x16
 identity_at=datetime.fromtimestamp((wire[r['after_span'][1]-1][2]-N.A.P.H.EPOCH_US)/1_000_000,UTC).isoformat();counts.append((len(r['att_packets']),observed['records'],len(raw)));previous,latest,ended=transfers[-1],r['after'],r['ended_at']
assert counts==[(262,450,38670),(263,453,38770),(263,453,38797),(265,455,38840)] and set(forms)=={'plain','composer-before-crlf'} and forms.count('plain')==4
adopted,latest2,source=C.parent_gate(root,image);assert adopted==current==previous and state==latest==latest2 and state['device']['free_capacity']==59589 and len(source['prior_names'])==82
formatdir=Path('artifacts/factory-first-segment-format-20261015');summary=json.loads(pin(formatdir/'sanitized-summary.json'));parts=[]
for directory in summary['source_pair_directories']:
 d=Path(directory);first=pin(d/'first/sector.bin');assert first==pin(d/'second/sector.bin') and len(first)==512;parts.append(first)
raw4096=b''.join(parts);assert len(raw4096)==4096 and raw4096==pin(formatdir/'raw4096.bin') and NV._header(raw4096,0)['header_crc_valid'] is True
items=NV._items(raw4096,0);assert items['item_count']==12 and items['erased_tail_bytes']==3680 and all(i['item_crc_valid'] and i['name_hash_valid'] for i in items['items']) and raw4096[416:]==b'\xff'*3680
for old in ('artifacts/prefilled-factory-next3-20261015','artifacts/prefilled-factory-notice-one-20261015'):
 try:N.A.replay(Path(old),image)
 except ValueError:pass
 else:raise AssertionError('Original failed whole promoted')
receipt=Path('docs/evidence/prefilled-factory-activity-next4a-live-2026-10-15.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for value in v.values():refs(value)
  elif isinstance(v,list):
   for value in v:refs(value)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(v.__file__).resolve() for n,v in sys.modules.items() if n.startswith('rcominote') and getattr(v,'__file__',None)];allowed={(root/'source-snapshot'/row['path']).resolve() for row in m['source_files']};assert all(p in allowed for p in origins) and all(sha(p.read_bytes())==h for p,h in checked.items())
print('PASS independent4pages/2048privatebytes/fullsource-parent-content-wire;1053ATT1811HCI155077B/60txn0pending/1boundstatusATT96page2/4normal16;actualFASTnoPULSE/plain+oldcomposerONLY/DEFAULT+wakeUNTESTED;20DL16samefilewrites0newfiles;current4096/history82/finalidentity',identity_at,'state59589;actualfirstsegment4096/12CRCrecords/empty416/tail3680FF/no fill/noextra coverage;',len(origins),'snapshotmodules;',len(checked),'pinsunchanged;privatecontent withheld')
PY
```
