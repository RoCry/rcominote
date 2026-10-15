# Private factory1ec800: fresh RAM-prefilled pair succeeded, 2026-10-15

[Sanitized metadata](evidence/prefilled-factory-one-live-2026-10-15.json); private originals `artifacts/prefilled-factory-one-20261015`. **Fresh one-pagejob passed; only physical`[1ec800,1eca00)` adds512B private rawcoverage.** UTC14日17:00:29.314210–17:01:12.184642 = HKT15日01:00:29–01:01:12. No factorybytes/config/sector/carrierhex/contenthash/nonce, binary or systemcodec publication. [Earlierfour-pagejob](prefilled-factory-four-live-2026-10-15.md) and its fourthGATTtimeout remain failed; neither oldflags nor frozenreceipt changed.

Actualbaseline4096 first matched the adopted thirdsecond object from the earlierfailedjob, resolving prior expectedretention by a **new fullactual readback** before anywrite. Newidentity also matched expectedFW010004/NOTEidle/unbound/charging100/free59589. Then each of twofreshNORreads followed its own full4096 independentRAMoracle prefill ending48. Difference-prefix uses immediateRAMfile, marker/nonce freshness separately uses originalbaseline/lastNORcarrier; both NORstrictprefixes4096/allcriticalchain/noexemptions. Twoactual512results equal, no independentfactorybyteoracle or filling.

**266ATT/456HCI/38902B,15complete parametertransactions/0pending, one boundstatus event atATT230**; baseline+twoRAM+twoNOR=5full4096 downloads, four existing-file SDoverwrites/0newfiles. ExactACKs4,6,4,6/F1/allpendingempty/F0all0; actualstartupFAST, each write-associatedFAST ordering, host/DL/EOF SLOW windows, all immediateidentity/statebarriers and finalidentity verify. Both actual producer→dump gaps **PLAIN**; newCRLF-before-composer branch remains host-tested only. Sole normaldisconnect status0/reason16 atHCI455 after finalATT, boundedclose/ownedmonitor stop. No NOR/RAMmemory write/deletion; cohort70confirmed+1olderdeclared+1historicalpossible=max72 unchanged.

Fresh finalidentityresponse **17:01:10.006458Z**, successfulpageend17:01:12.176809Z, wholeend17:01:12.184642Z. Allactualstateobservations unchangedfree59589/NOTEidle/unbound/charging100. Current private4096 is newsecond; whole successful source/parentgate passes,62ancestorreserved+2fresh=64history (includes earlierunsentnames, not64successes). Futureoverwrite still needs freshactual4096 baseline comparison.

**Formal host-only linkownership checkpoint** `artifacts/prefilled-factory-link-checkpoint-20261015/checkpoint.json`, SHA639e5af13ab3f207cd74adda53065a363d2507ec3adb1b1a42e9b75586f85b93, created16:59:14.671143Z: replays earlierthreeacceptedpairs separately and fourth21ATT MTU/GATT-only/LEconnected→reason08/noapplicationIO. Adopts thirdsecond private4096/laststate59589/history62, **0deviceI/O/0coverage**, originalwhole/fourthfalse preserved. Oldidentity16:40:42.033534Z, oldthirdpageend16:40:44.229530Z and failedwholeend16:40:52.894850Z remain separate; checkpointcreation is not a freshdeviceobservation. Seed restricted to **unknown RAM-prefilled acquisition only**, notknowncontrol/ordinaryunprefilledjob. Newlivebaseline/identity independently confirmed the adopted bytes/state; this later success does not retroactively validate the timeout.

Frozen **147source/133tests**, manifest32c990c53544e8f2eb33d4681f7cadf5fade6a952e93be68b93859d0df1a1cfd; all280 lengths/hashes equal attachedsnapshot/isolatedcopy. FreshpreIO2634tests+159subtests/48.10s,338format/lint/build,344inputs before==after/`new_full_check_run=true`. Source16:58:41.897692Z < CPcreation < immutableplan16:59:15.350017Z < actualstart < end. All103 imported projectmodules fromsnapshot; completeancestor/CP/oldfailed/newpair source/HCI/chronology replayed, originals unchanged. No assertion that latercurrentcode ran those checks.

Coverage **strong43792B/potential198996B** = prior43280/198484 +512. With [oldfactoryfirst512](factory-first4-failed-2026-10-14.md) and [threeprefilledpairs1536](prefilled-factory-four-live-2026-10-15.md), fullypairedprivatefactory union`[1ec000,1eca00)` totals2560B; **5632B of factory8KiB still missing fullpair**. [FrozenASOF inventory](nor-backup-coverage-2026-10-14.md) unchanged/B155204 not upgraded; [systemfirst4KiB](system-first4k-raw-live-2026-10-14.md)+[bulk2048](paired-nor25000-four-live-2026-10-14.md) contiguous6144B`[24000,25800)` unchanged. Crosscapture union notatomic wholeflash. Full4MiB backup/reliable restore/ownruntime incomplete; no automaticextension/retry/deletion. User only reportedpowerbutton/recordslider; independentRESET/ROMexit/exposedremovablebattery remains unproven. [Deletion static boundary](file-deletion.md#hidden-scratch-bounded-static-follow-up-2026-10-14) unchanged.

Exact host-only frozen replay; private originals/isolatedcopy required. No device/evidence writes or privatecontent/hash/nonce output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/prefilled-factory-one-20261015/source-snapshot/src uv run python - <<'PY'
import copy,hashlib,json,sys
from datetime import datetime,UTC
from pathlib import Path
from rcominote.experiments import prefilled_nor_pages as P
A,C=P.A,P.C;root=Path('artifacts/prefilled-factory-one-20261015');pre=Path('artifacts/prefilled-factory-one-preflight-20261015');cp=Path('artifacts/prefilled-factory-link-checkpoint-20261015');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={}
def pin(p,digest=None):
 p=Path(p);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
job=json.loads(pin(root/'report.json','faea542373793c9bdcd59637d35ef6f15ce7cd13c1f024c4558a9271cc1138f7'));plan=json.loads(pin(root/'plan.json','568262bb3b6c67bef69e87acd87f049d541c9634eb8872a9eb09f1683b7bc8be'));mp=root/'source-snapshot/manifest.json';m=json.loads(pin(mp,'32c990c53544e8f2eb33d4681f7cadf5fade6a952e93be68b93859d0df1a1cfd'));review=json.loads(pin(root/'preflight-review.json'));assert len(m['source_files'])==147 and len(m['test_files'])==133
for e in m['source_files']+m['test_files']:
 for base in (mp.parent,Path(review['isolated_source'])):assert len(pin(base/e['path'],e['sha256']))==e['bytes']
before=json.loads(pin(pre/'checks-before.json'));assert before==json.loads(pin(pre/'checks-after.json')) and len(before)==344 and review['new_full_check_run'] is True
checkpoint=json.loads(pin(cp/'checkpoint.json','639e5af13ab3f207cd74adda53065a363d2507ec3adb1b1a42e9b75586f85b93'));baseline,state,parent=C.parent_gate(cp,image);assert parent==plan['parent'] and baseline==pin(cp/'baseline.bin') and len(parent['prior_names'])==62
assert checkpoint['offline_ownership_verified'] is True and checkpoint['live_capture_performed'] is False and checkpoint['original_job_ok'] is checkpoint['original_failed_page_ok'] is False and checkpoint['new_raw_nor_coverage_bytes']==0
assert parent['profile']==C.PREFILLED_LINK_CP and parent['latest_identity_response_at']=='2026-10-14T16:40:42.033534+00:00' and parent['failed_ended_at']=='2026-10-14T16:40:52.894850+00:00'
assert plan['profile']==P.PROFILE and plan['offsets']==[0x1ec800] and plan['budget']==P.budgets(1) and C.source_gate(plan,image)==baseline
C.J.time_order(m['created_at'],checkpoint['created_at'],plan['planned_at'],job['started_at'],job['ended_at']);assert job['ok'] is True and len(job['completed'])==1
proof=A.replay(root,image);current,latest,source=C.parent_gate(root,image);assert proof==job['verification']==source['verification'] and proof['paired_bytes']==512 and len(source['prior_names'])==64
proofs,again,latest_again=A.completed_prefix(job,plan,root,baseline);assert len(proofs)==1 and again==current and latest_again==latest and proofs[0]['raw_range']==[0x1ec800,0x1eca00]
slot=plan['pages'][0];directory=root/slot['directory'];r=json.loads(pin(directory/'report.json'));page=C.page_plan(plan,0,state,parent['ended_at']);assert A.validate_page(r,directory,page,baseline)==r['verification']==proofs[0]
raw=pin(directory/'session.btsnoop','2d089ff529add20bee557fed57632b3c3d84dcef5c3e1dc8f92864aa339f5a70');observed,wire,events=A.envelope(r,directory,15);assert len(raw)==38902 and observed['records']==456 and len(r['att_packets'])==266 and events['events']==1 and events['indices']==[230]
assert r['ok'] is True and r['before']==r['after']==latest==state and latest['device']['free_capacity']==59589 and r['disconnect_observation']['event']['record']==455 and r['disconnect_observation']['event']['reason']==0x16
for stage in [r['baseline'],*r['operations']]:assert len(pin(directory/stage['operation_id']/'download.bin'))==4096 and stage['ok'] is stage['live_complete'] is stage['barrier_complete'] is True
assert pin(directory/'baseline/download.bin')==baseline and pin(directory/'second/download.bin')==current
ram=P.source_ram(plan,image)
for op in r['operations']:
 data=pin(directory/op['operation_id']/'download.bin');assert op['actions_verification']['f0_frames']==0
 if op['kind']=='prefill':assert data==ram and op['ack_count']==4
 else:
  fresh=op['verification']['freshness'];assert fresh['difference_proven_written_prefix_bytes']==4096 and fresh['critical_chain_inside_written_prefix'] is True and 'prefix_policy' not in fresh and fresh['producer_dump_gap']['form']=='plain' and data[-1]!=0x48 and op['ack_count']==6;pin(directory/op['operation_id']/'sector.bin')
assert len(pin(directory/'first/sector.bin'))==512 and pin(directory/'first/sector.bin')==pin(directory/'second/sector.bin')
identity_at=datetime.fromtimestamp((wire[r['after_span'][1]-1][2]-A.P.H.EPOCH_US)/1_000_000,UTC).isoformat();assert identity_at=='2026-10-14T17:01:10.006458+00:00'
old=Path('artifacts/prefilled-factory-four-20261015')
for gate in (A.replay,C.parent_gate):
 try:gate(old,image)
 except ValueError:pass
 else:raise AssertionError('Original four-page failure promoted')
known=json.loads(Path('artifacts/prefilled-nor-known-v2-20261015/plan.json').read_bytes());known['parent']=copy.deepcopy(parent);known['expected_before']=state
try:P.P.validate_plan(known)
except ValueError as error:assert str(error)=='Pinned link checkpoint is restricted to prefilled unknown acquisition'
else:raise AssertionError('Unknown-only ownership checkpoint seeded known control')
receipt=Path('docs/evidence/prefilled-factory-one-live-2026-10-15.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for x in v.values():refs(x)
  elif isinstance(v,list):
   for x in v:refs(x)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(v.__file__).resolve() for n,v in sys.modules.items() if n.startswith('rcominote') and getattr(v,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in m['source_files']};assert all(p in allowed for p in origins);assert all(sha(p.read_bytes())==h for p,h in checked.items())
print('PASS frozenfullchain/actualunknown-onlyCP0IO0coverage/oldwholefailedretained/new1ec800pair512/twoRAMfulloracle/strict4096/266ATT456HCI38902B15txn/1boundstatus/5DL4overwrites/PLAINgaps/normal16;finalidentity',identity_at,'state59589/history64;',len(origins),'snapshotmodules;',len(checked),'pinsunchanged; no factorycontent/hash/nonce output')
PY
```
