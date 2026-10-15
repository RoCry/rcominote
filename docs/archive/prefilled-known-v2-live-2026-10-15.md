# RAM-prefilled known0/4200 control succeeded, 2026-10-15

[Sanitized metadata](../evidence/prefilled-known-v2-live-2026-10-15.json); private originals `artifacts/prefilled-nor-known-v2-20261015`. **Fresh v2 control passed both independently known targets with strict4096 difference-prefix proof.** HKT2026-10-15 00:10:49–00:11:31; capture UTC2026-10-14 16:10:49.743806–16:11:31.894453.0new rawcoverage/publicbinary. All baseline/currentcarrier hashes withheld: SDfile prefill does not clear residentring, which may retain private factory history outside the accepted knownchain.

| Original stage | Verified result |
|---|---|
|Readonly baseline|All4096 bytes match actual v1 CONTENTcheckpoint; real identity unchanged|
|prefill-first|4ACK/F1/pending0/F0=0; full4096 independent RAMoracle match, lastbyte48; full FAST/host/DL/EOF SLOW/barrier|
|NOR0|6ACK/F1/pending0/F0=0; strictprefix4096/criticalchain inside/noexemptions; independent boot0 512B oracle matches|
|prefill-second|Fresh complete RAM4096/independentoracle/barrier again;4ACK/F1/F0=0|
|NOR4200|6ACK/F1/F0=0; strictprefix4096/criticalchain/noexemptions; independent recovery4200 512B oracle matches|

Every NOR stage physically follows verified RAMfile and changes its final48 byte. Difference-prefix uses that immediate RAMpredecessor; marker/nonce freshness separately uses actual retained lastNORcarrier (first uses originalbaseline, second uses firstNOR). These dual predecessors remain distinct. This supports the fixed contiguous-prefix model in this control; it does not prove SD atomicity, truncation, absence of private residenthistory, arbitrary unknown-address reads, or scalable reliability.

**Both actual producer→dump gaps were PLAIN.** Explicit v2 closed grammar permits plain plus two exact composer/CRLF layouts; the newly added CRLF-before-composer branch is **host-tested only, not exercised on this radio trial**. No arbitrary log/whitespace normalization. [Originalv1 separator failure](prefilled-known-failed-2026-10-14.md) remains failed; newpolicy does not reparse/admit its NOR content.

Full frozen audit: **266ATT/456HCI/38893B,15complete transactions/0pending, one full bound asynchronous status event atATT97**, five4096 downloads/twoRAMexports/twoNORproducers/four existing-file SDoverwrites/0newfiles. All Actions frame streams/F0/F1, GATT/ATT/HCI, actual startupFAST, each write-associatedFAST ordering, host/DL/EOF windows, every immediate identity and globalfinalidentity verify. Sole normaldisconnect status0/reason16 atHCI455 after finalATT; clean ownedmonitor stop. Ordering does not establish unique deferred-trigger causality. No NOR/RAMmemory writes or deletion.

Final **16:11:31.894453Z (00:11:31 HKT15)** FW010004/NOTEidle/unbound/charging100/free59589; before, allstagebarriers and finalafter identical. Current private4096 ownedobject and state fully known; whole successful v2 source/parentgate passes, history52+2freshnonces=54. Future overwrite still requires actual fresh4096 baseline bytecomparison. Cohort70confirmed+1olderdeclared+1historicalpossible=max72 unchanged.

Actual preceding **v1 CONTENT communication checkpoint** `artifacts/prefilled-nor-content-checkpoint-20261015/checkpoint.json`, SHA3a351682aed84f94e0817c4ef85f76dcee00c0fb5e4827129ddfca5cb1cc6427, created16:10:21.013351Z: full original9communication/RAMoracle/strictv1gaperror/currentprivate4096/state59589/history52, **0deviceI/O/coverage**. Original observedend remains11:52:36.513316Z, not checkpointcreation; originalv1job/NORfalse preserved. Newbaseline exactly matched this adopted object. Earlier factory512 acceptedprefix and rejected variablelowhex tail remain separate/unchanged.

Frozen **145source/129tests**, cf72f9e3c5d325ddbdcdbb34d168e5bebcd4aaa9c43124cb11087e80f0139767: all274 lengths/hashes equal attachedsnapshot/isolatedv2copy;337checkinputs before==after. Source16:10:20.399992Z < checkpointcreation < plan16:10:48.910501Z < actualstart < end. Inherited justcheck2547+159subtests/40.04s,331format/lint/build; plan `new_full_check_run=false`, no claim of another/current-source suite. All101 imported projectmodules fromsnapshot; full ancestor/checkpoint/originalfailed/currentv2 replayed, originals unchanged.

Coverage unchanged **strong41744B/potential196948B**; [frozen inventory](nor-backup-coverage-2026-10-14.md), [systemfirst4KiB](system-first4k-raw-live-2026-10-14.md), [bulk2048](paired-nor25000-four-live-2026-10-14.md) and [privatefactorypair512](factory-first4-failed-2026-10-14.md) immutable. Systemcontiguous6144B`[24000,25800)`; factory7680B still missing fullpair, historicalB not upgraded. This independent control passes the fixed [prefill method](verified-prefill-control-plan-2026-10-14.md) for known0/4200; it authorizes no automatic extension/retry/deletion. Full4MiB backup/reliable restore/ownruntime incomplete. User controls exactly “只有电源键和录音滑键”; RESET/exposed removablebattery connector unconfirmed, independentlongpressROMexit unproven, no inference that all hiddenpoints are absent. [Deletion static boundary](../file-deletion.md#hidden-scratch-bounded-static-follow-up-2026-10-14) remains unchanged.

Exact host-only frozen reproduction; private originals/isolatedcopy required, no device/evidence writes or carrierhash output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/prefilled-nor-known-v2-20261015/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from pathlib import Path
from rcominote.experiments import prefilled_nor_control as P
from rcominote.experiments import prefilled_nor_checkpoint as H
C=P.C;sha=lambda b:hashlib.sha256(b).hexdigest();checked={};root=Path('artifacts/prefilled-nor-known-v2-20261015');pre=Path('artifacts/prefilled-nor-known-v2-preflight-20261015');image=Path('artifacts/mapped-system-20261012.bin')
def pin(p,digest=None):
 p=Path(p);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
report=json.loads(pin(root/'report.json','f188a4e10784dff8e6c54d1fbb64db69c38fcb724e4881652c1571e558855989'));plan=json.loads(pin(root/'plan.json','20db668806f36fdde6fa9e590a0673fe5a9bf30d569c1b1b5ab1e37a32027aea'));mp=root/'source-snapshot/manifest.json';manifest=json.loads(pin(mp,'cf72f9e3c5d325ddbdcdbb34d168e5bebcd4aaa9c43124cb11087e80f0139767'));review=json.loads(pin(root/'preflight-review.json'))
assert len(manifest['source_files'])==145 and len(manifest['test_files'])==129
for entry in manifest['source_files']+manifest['test_files']:
 for base in (mp.parent,Path(review['isolated_source'])):assert len(pin(base/entry['path'],entry['sha256']))==entry['bytes']
assert json.loads(pin(pre/'checks-before.json'))==json.loads(pin(pre/'checks-after.json'))
assert len(json.loads((pre/'checks-before.json').read_bytes()))==337 and review['new_full_check_run'] is False
cp=Path('artifacts/prefilled-nor-content-checkpoint-20261015');checkpoint=json.loads(pin(cp/'checkpoint.json','3a351682aed84f94e0817c4ef85f76dcee00c0fb5e4827129ddfca5cb1cc6427'));baseline,state,parent=C.parent_gate(cp,image)
assert parent==plan['parent'] and baseline==pin(cp/'baseline.bin') and len(parent['prior_names'])==52 and state==plan['expected_before']
assert checkpoint['failure_role']==H.ROLE and checkpoint['original_capture_profile']==P.PROFILE and checkpoint['live_capture_performed'] is False and checkpoint['original_job_ok'] is checkpoint['original_operation_ok'] is False and checkpoint['new_raw_nor_coverage_bytes']==0
assert checkpoint['failed']['communication']['ram_prefill_oracle_verified'] is True and checkpoint['failed']['communication']['content_error_reproduced']==H.CONTENT_ERROR
C.J.time_order(manifest['created_at'],checkpoint['created_at'],plan['planned_at'],report['started_at'],report['ended_at'])
assert report['ok'] is True and plan['profile']==P.PROFILE_V2 and plan['gap_policy']==C.F.PREFILL_GAP_POLICY and P.source_gate(plan,image)==baseline
proof=P.replay(root,image);current,latest,source=C.parent_gate(root,image);assert proof==report['verification']==source['verification']
assert current==pin(root/'second/download.bin') and len(current)==4096 and latest==report['after']==state and latest['device']['free_capacity']==59589 and len(source['prior_names'])==54
raw=pin(root/'session.btsnoop','89deae8908b878c69b1b49f97e81c99b2c0957e1dae86c16cb927c4d288d5ed0');observed,wire,events=P.A.envelope(report,root,15)
assert len(raw)==38893 and observed['records']==456 and len(report['att_packets'])==266 and events['events']==1
assert report['disconnect_observation']['event']['record']==455 and report['disconnect_observation']['event']['reason']==0x16
ram,oracle=P.ram_source(image);assert oracle==plan['ram_oracle'] and ram[-1]==0x48 and pin(root/'baseline/download.bin')==baseline
previous,history=baseline,baseline
for op in report['operations']:
 data=pin(root/op['operation_id']/'download.bin');assert len(data)==4096 and op['ok'] is op['live_complete'] is op['barrier_complete'] is True and op['before']==op['after']==state
 assert op['actions_verification']['f0_frames']==0 and P.actions(report,op)==op['actions_verification']
 expected=P.content(op,data,previous,ram,plan,history);assert expected==op['verification']
 if op['kind']=='prefill':assert data==ram and op['ack_count']==4
 else:
  assert op['ack_count']==6 and data[-1]!=0x48 and previous==ram
  fresh=expected['freshness'];assert fresh['difference_proven_written_prefix_bytes']==4096 and fresh['critical_chain_inside_written_prefix'] is True and 'prefix_policy' not in fresh
  assert fresh['producer_dump_gap']['form']=='plain' and fresh['marker_previous_ring_sha256']==sha(history)
  assert pin(root/op['operation_id']/'sector.bin')==bytes.fromhex(expected['sector_hex']);history=data
 previous=data
assert proof['new_raw_nor_coverage_bytes']==proof['new_files']==0 and proof['downloads']==5 and proof['sd_writes']==4 and proof['parameter_transactions']==15
for gate in (P.replay,C.parent_gate):
 try:gate(Path('artifacts/prefilled-nor-known-20261014'),image)
 except ValueError:pass
 else:raise AssertionError('Original v1 failedcontrol promoted')
receipt=Path('docs/evidence/prefilled-known-v2-live-2026-10-15.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for x in v.values():refs(x)
  elif isinstance(v,list):
   for x in v:refs(x)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in allowed for p in origins)
assert all(sha(p.read_bytes())==h for p,h in checked.items())
print('PASS frozen fullchain/actualv1CP0coverage/v2known0+4200strict4096+independentoracles/twoRAM4096/266ATT456HCI15txn/5DL4overwrites/PLAINgaps/currentprivate4096/state59589/history54/0coverage/originalv1failedretained;',len(origins),'snapshotmodules;',len(checked),'inputs unchanged; all carrier hashes withheld')
PY
```
