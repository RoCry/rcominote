# Two known pairs in one connection: failed control, 2026-10-14

Frozen [metadata](evidence/two-known-session-failed-2026-10-14.json); private original `artifacts/paired-nor-two-known-session-20261014`. **Whole session failed; zero new NOR coverage, no new public binary.** Group0 boot0 has two complete oracle-matching candidates, but the required known4200 group and final identity did not complete. Original failed flags and success/parent rejection remain unchanged.

| Stage | Actual evidence | Acceptance boundary |
|---|---|---|
| Group0 baseline | Complete4096 equals prior first4K session's last owned ring | Readonly prerequisite only |
| Group0 boot0 first/second | Each6ACK/F1/pending0/F0=0; actualFAST→host6→DL4096→EOF SLOW→identity; prefix4096/no exemptions; both512 match independent boot0 oracle | Complete candidates, not separately accepted session/pair |
| Group1 baseline | Complete4096 exactly equals group0 second `f0b5c8c193b519d6a5695345fc1bcdecea01541b9f775f58420ba476e7a6ffd3`; real identity59589 at09:40:32.022126Z | Last file/state observation, before third overwrite attempt |
| Group1 first | Exact6ACK/F1/pending0/F0=0; producer and SD overwrite attempted; no new remote FAST, host normalization, download or after identity | Inner requiredFAST wait8s expired, TimeoutError09:40:41.148774Z; no content confirmation |
| Group1 second | Never started; no commands/files | No candidate/coverage |

**Current owned-file contents unknown; post-attempt device state unverified.** Last observed FW010004/NOTEidle/unbound/charging100/free59589 and ringf0b5…ffd3 precede the third attempted overwrite. They cannot be asserted current, nor can priora16e…14609. Final identity deliberately omitted on timeout; normal local disconnect status0/reason0x16 atHCI376 does not supply identity or file contents. No inference that overwrite failed, contents equal the planned4200, FAST would eventually arrive, or device state remained unchanged.

Independent host-only replay from frozen138source/116test snapshot **92e2ec882e0ff5cdfcd11e18c6045b24b4d052aecb67666c96fdb3a256845051** verifies every source/test length/hash, immutable plan and full successful parent chain, GATT/all222ATT↔377HCI records/31648B,11 complete parameter transactions/0pending/0status, all four downloads and real barriers, all three exact Actions sessions, original chronology, passive disconnect and clean SIGINT monitor exit. Transactions: startup1 + group0 baseline2/first3/second3 + group1 baseline2; failed first contributes0. All96 imported project modules come from this snapshot. No fabricated final identity or modified-success report.

Snapshot09:39:38.882560Z < plan09:39:39.363744Z < start09:40:00.172309Z < end09:40:43.428948Z. Frozen runtime calls requiredFAST wait8 inside stage18 and outer active60; elapsed session43.257s, failed first9.123s, consistent with inner wait expiry rather than outer60 cancellation. Manifest records root's pre-I/O2107tests+159subtests/build passed; this review verifies the manifest and actual capture, does not independently rerun that full suite. Current source is changing for an independent readonly checkpoint; no new live checkpoint/current-code success claimed.

One connection/four complete4096 downloads/three producer+existing-file overwrite attempts, two contents subsequently downloaded/zero newfiles/deletions. Cohort70 confirmed+1 older declared+1 historical possible=max72 unchanged. No firmware NOR write. Previously frozen [actual system raw first4096](system-first4k-raw-live-2026-10-14.md), SHA74807d164370bd3d4ded53ac191414a1f5ff9a50ca04647b898179a1e7d83a5c, remains unchanged: strong39184B/potential194388B, system`[24000,25000)` complete; full4MiB/restore/own firmware incomplete. No decode/comparison/publication of failed4200 data; no download exists. ACK/F1 and lack of FAST do not isolate a firmware/deferred-queue root cause. Do not repeat or extend the failed session automatically.

Exact offline replay, repository root and private originals required; no device access or file writes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/paired-nor-two-known-session-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime
from pathlib import Path
from rcominote.experiments import paired_nor_audit as A
from rcominote.experiments import paired_nor_runtime as R
root=Path('artifacts/paired-nor-two-known-session-20261014');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest()
report=json.loads((root/'report.json').read_bytes());plan=json.loads((root/'plan.json').read_bytes());mp=root/'source-snapshot/manifest.json';manifest=json.loads(mp.read_bytes());pinned={}
def pin(path,digest=None):
 p=Path(path);raw=p.read_bytes();h=sha(raw);assert digest is None or h==digest;pinned[str(p.resolve())]=h;return raw
def refs(v):
 if isinstance(v,dict):
  if {'file','bytes','sha256'}<=v.keys() and Path(v['file']).is_file():assert len(pin(v['file'],v['sha256']))==v['bytes']
  for x in v.values():refs(x)
 elif isinstance(v,list):
  for x in v:refs(x)
pin(root/'report.json','ff24dee4e05c0a17e9ab29fd60aa2e89feb2dbd937562baf11c510085c68917b');pin(mp,'92e2ec882e0ff5cdfcd11e18c6045b24b4d052aecb67666c96fdb3a256845051')
pin(root/'plan.json',report['plan']['sha256']);assert (root/'plan.json').read_bytes()==pin('artifacts/paired-nor-two-known-session-preflight-20261014/plan.json')
assert pin('artifacts/paired-nor-two-known-session-preflight-20261014/source-snapshot/manifest.json')==mp.read_bytes()
receipt_path=Path('docs/evidence/two-known-session-failed-2026-10-14.json')
if receipt_path.exists():refs(json.loads(receipt_path.read_bytes()))
assert len(manifest['source_files'])==138 and len(manifest['test_files'])==116
for item in manifest['source_files']+manifest['test_files']:assert len(pin(mp.parent/item['path'],item['sha256']))==item['bytes']
assert manifest['checks']=={'just_check':{'passed':2107,'subtests_passed':159},'uv_build':'passed'}
assert report['ok'] is False and 'verification' not in report and report['error']==report['capture_error']=='TimeoutError: '
A.C.validate_plan(plan);R.plan_gate(report,plan,root);baseline=A.C.source_gate(plan,image);refs(plan)
A.J.time_order(manifest['created_at'],plan['planned_at'],report['started_at'],report['ended_at'])
for gate in (A.replay,A.C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Failed control promoted')
raw=pin(root/'session.btsnoop','f60ee8f383f3f9ec4d38b4c05481c41cd30c4b3f13725b29a07e2a2f15fa9b06');observed=A.P.inspect(raw,link=report['transport']['link'],final=True)
assert len(raw)==31648 and observed['records']==377 and len(observed['transactions'])==11 and not observed['pending']
assert report['hci_capture']=={'bytes':len(raw),'sha256':sha(raw),'records':377}
assert report['gatt_proof']==A.A.setup(report) and report['att_hci_binding']==A.dual_hci.bind(report,raw)
assert len(report['att_packets'])==222 and all(a['monotonic_ns']<=b['monotonic_ns'] for a,b in zip(report['att_packets'],report['att_packets'][1:]))
assert A.E.verify(report)[1]['events']==0
wire=A.common.wire_positions(report,raw);start,end=[A.P.H.EPOCH_US+int(datetime.fromisoformat(report[k]).timestamp()*1e6) for k in ('started_at','ended_at')]
assert all(start<=point[2]<=end for point in wire);disc=observed['disconnects'];assert len(disc)==1 and disc[0]['status']==0 and disc[0]['reason']==22 and disc[0]['record']==376 and disc[0]['record']>max(p[1] for p in wire)
assert report['disconnect_observation']=={'observed':True,'max_wait_seconds':8,'event':disc[0]}
requested,completed,recorded=[report[k] for k in ('close_requested_us','close_completed_us','disconnect_observed_us')];assert requested<=completed<=recorded<=completed+8000000 and requested<=disc[0]['timestamp_us']<=completed+8000000
assert report['monitor_exit']==0 and report['monitor_stop']=={'signal':'SIGINT','requested':True,'delivery':'sent'}
A.E.bridge(report,report['setup_end'],report['before_span'][0]);A.A.identity(report,report,'before');assert report['before']==plan['expected_before']
assert report['predecessor_state_verification']==A.verify_state(plan['expected_before'],report['before'],sd_write=False)
A.E.bridge(report,report['before_span'][1],report['file_list_span'][0]);assert A.inventory(report,plan)==report['listed_count']
tx=observed['transactions'];assert report['startup_settlement']==tx[0] and report['startup_classification']==A.startup.classify(tx[0])
state,boundary,previous_tx,cursor,previous,ended=report['before'],report['file_list_span'][1],tx[0],1,baseline,report['started_at'];sectors=[]
for gi,g in enumerate(report['groups']):
 page=A.C.page_plan(plan,gi,state,ended);path=root/plan['pages'][gi]['directory'];warm=g['baseline'];assert g['group_index']==gi and g['nor_offset']==plan['offsets'][gi]
 assert warm['ok'] is warm['live_complete'] is True and warm['before']==state and warm['operation_id']=='baseline' and warm['name']==A.F.NAME
 A.J.time_order(ended,warm['started_at'],warm['ended_at'],report['ended_at']);A.E.bridge(report,boundary,warm['download_start'])
 if gi:assert wire[boundary-1][1]<tx[cursor]['request']['record'] and wire[boundary-1][2]<tx[cursor]['request']['timestamp_us']
 A.shared.baseline_window(report,warm,wire,previous_tx,tx[cursor],tx[cursor+1]);data=A.shared.download(report,warm,path);pin(path/'baseline/download.bin');assert data==previous;A.F.absent(data,page['future_nonces']);A.shared.barrier(report,warm,state,writing=False)
 state,boundary,previous_tx,cursor,ended=warm['after'],warm['verified_end'],tx[cursor+1],cursor+2,warm['ended_at']
 for oi,op in enumerate(g['operations']):
  assert all(op[k]==v for k,v in page['operations'][oi].items())
  if gi==1 and oi==1:
   assert op['ok'] is op['live_complete'] is False and not any(k in op for k in ('started_at','writes','producer_attempted','sd_write_attempted','download_start'));assert not list((path/'second').iterdir());continue
  assert op['before']==state and op['producer_attempted'] is op['sd_write_attempted'] is True;A.J.time_order(ended,op['started_at'],op['ended_at'],report['ended_at']);assert (datetime.fromisoformat(op['ended_at'])-datetime.fromisoformat(op['started_at'])).total_seconds()<18
  A.E.bridge(report,boundary,op['actions_start']);assert A.C.actions(report,op)==op['actions_verification'] and op['actions_verification']['f0_frames']==0
  if gi==1:
   assert op['ok'] is op['live_complete'] is False and op['error']=='TimeoutError: ' and op['actions_end']==len(report['att_packets']) and cursor==11
   assert not any(k in op for k in ('pre_download_fast','normalization','normalization_attempted','download_start','after','verification')) and not list((path/'first').iterdir());continue
  assert op['ok'] is op['live_complete'] is True;A.E.bridge(report,op['actions_end'],op['download_start']);normal,slow,cursor=A.W.parameter_stage(tx,cursor,op,previous_tx,first_fast_required=True)
  assert op['activity_fast_verification']==A.W.default_activity_fast(report,op,previous_tx,op['pre_download_fast'][0],wire);A.W.download_window(wire,op,normal,slow,report=report)
  data=A.shared.download(report,op,path);pin(path/op['operation_id']/'download.bin');decoded=A.C.payload(op,data,previous);sector=bytes.fromhex(decoded['sector_hex']);assert decoded==op['verification'] and sector==pin(path/op['operation_id']/'sector.bin') and op['oracle_verification']==A.oracle_proof(plan,gi,sector)
  assert decoded['freshness']['difference_proven_written_prefix_bytes']==4096 and not decoded['freshness']['address_padding_exemptions'];A.F.absent(data,page['future_nonces'][oi+1:]);A.shared.barrier(report,op,state,writing=True);sectors.append(sector)
  previous,state,boundary,previous_tx,ended=data,op['after'],op['verified_end'],slow,op['ended_at']
assert tx[-1]['update']['record']<wire[report['groups'][1]['operations'][0]['actions_start']][0]
assert cursor==11 and len(sectors)==2 and sectors[0]==sectors[1] and sha(previous)=='f0b5c8c193b519d6a5695345fc1bcdecea01541b9f775f58420ba476e7a6ffd3'
assert report['groups'][0]['candidate'] is report['groups'][0]['live_complete'] is True and report['groups'][1]['candidate'] is report['groups'][1]['live_complete'] is False
assert not any(k in report for k in ('after','after_span','state_verification','verification')) and report['after_error']=='Final identity omitted after timeout/cancellation; no new read command'
assert ended=='2026-10-14T09:40:32.022126+00:00' and state['device']['free_capacity']==59589
origins=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in allowed for p in origins)
assert all(sha(Path(p).read_bytes())==h for p,h in pinned.items())
print('PASS frozen failed control;222ATT/377HCI/11txn;4completeDL/3Actions;candidate-only boot0;laststatebeforeattempt59589;currentunknown;0coverage;',len(origins),'snapshot modules;',len(pinned),'pinned inputs unchanged')
PY
```
