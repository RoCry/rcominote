# Actions applied6: fixed RAM256 stream complete, 2026-10-15

[Sanitized metadata](evidence/actions-fast-ram256-live-2026-10-15.json); private originals `artifacts/actions-fast-ram256-20261015`. **One fixed knownRAM256 Actions control succeeded**, no storage access/writes/NORcoverage. UTC14日17:32:34.920695–17:32:51.616471 = HKT15日01:32:34–01:32:51. Fullstreamhex/hash and afcmarker withheld because the stream may contain private residenthistory; no newbinary. Known256-byte oracle is a fixed mapped-image/RAM source, not a NORread.

Actualorder: originalstartupremoteFAST fully settles to12; PREPARE/START and STARTACK complete; **host6/0/500 with requestedCEhints1/1 settles before freshafcmarker/MDB**. Fixedcommand`dbg mdb 18000000 100` reads256B. Appliedinterval6=7.5ms; CE1/1 are hosthints, not measured eventlength guarantees. Both completeparametertransactions/0pending/status verified. No DEFAULT branch in this trial, extraFAST, help, retry or versionfillers; plannedMAX8fillers, actual0.

**72ATT/144HCI/7202B, four FULLF0frames/fiveACK/terminalF1/emptypending**. Uniqueafcmarker then sixteen contiguouscanonicalRAMrows exactly match independent256-byte oracle; address/order/hex/ASCII/framing verified. Every marker/RAM/command-echo byte binds to actualRX after its originatingTX, not merely completion of a mixed frame. Fulloriginalstream framing, GATT/ATT/HCI, applied6window throughSTOP/F1, before/afteridentity and sole normaldisconnect16 atHCI143 verify. This is one completed condition control, not a general throughput/reliability result.

Fresh finalidentityresponse **17:32:49.553447Z**, end17:32:51.616471Z: FW010004/NOTEidle/unbound/charging100/free59589, before==after. Historical [ONEsuccess](prefilled-factory-one-live-2026-10-15.md) is **IDENTITY ONLY** expectedstate reference, explicitly`current_owned_file_verified=False`. Intervening [NEXT3failure](prefilled-factory-next3-failed-2026-10-15.md) changed ownedSDfile to failed1ecc00first. This control neither reads nor admits that object; lastfullSDobservation remains17:09:26.871464Z, originalNEXT3wholefalse/unadmitted. No storageparent role from thisRAMsuccess. Ownedrcnoncehistory70 unchanged; newafcmarker belongs a different namespace.0SDaccess/writes/newfiles/NOR/MMIO/explicitRAMmemorywrites/coverage; Actions still modifies transientlogRAM/sessionstate. Cohort70confirmed+1olderdeclared+1historicalpossible=max72 unchanged.

[Host-only interval comparison](../artifacts/actions-interval-host-review-20261015/astra.json), SHAf988a6608aa824371d5f27120d6814be94adf442827e0bf7335025a3df19708b, pins three oldcaptures. Their lossbursts ran at actual45/45/60ms, **none at applied6**; laterFAST requests wherepresent follow the loss. Newactualcondition is host6 **afterSTARTACK+settledFAST, beforemarker/MDB**; earlierhostnoteproposal wording is not the executedpolicy. This identifies a new testedcondition, not an isolated causal fix: CEhints/order/marker/outputhandling differ, onecontrol does not prove longtermreliability, restart/recovery or an enlargedNORpath. Historical failedcaptures remain failed.

Frozen **149source/135tests**, e5aa1bfda26bebc0ca8399ac6c167f5fb5c88ff5bbd58f80a1700feb2ff3f495; all284 lengths/hashes equal attachedsnapshot/isolatedfastcopy. FreshpreIO2675tests+159subtests/43.17s,342format/lint/build,348inputs before==after/`new_full_check_run=true`. Source17:29:47.042159Z < immutableplan17:29:47.971123Z < start < end. All104 imported projectmodules fromsnapshot; historicalidentitysource/independentRAM/fullwire/byteprovenance/oldtimingpins replayed, originals unchanged. No latercurrent-root source/check claim.

Coverage unchanged **strong44304B/potential199508B**, factory3072paired/5120missing, systemcontiguous6144B`[24000,25800)`. [FrozenASOF inventory](nor-backup-coverage-2026-10-14.md)/historicalB notupgraded; all oldfrozenreceipts/privatecaptures/publicbinaries unchanged. Full4MiB backup/reliable restore/ownruntime still incomplete; no reboot/independentRESET/ROMexit/cable proof. FutureNOR/owned-file work requires separatefixedplan and validcurrent/state/admission; thisRAMcontrol grants no automaticrepeat, extension or deletion. [Deletion static boundary](file-deletion.md#hidden-scratch-bounded-static-follow-up-2026-10-14) unchanged.

Exact host-only frozen replay; private originals/isolatedcopy required. No device/evidence writes or stream/marker/privatehash output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/actions-fast-ram256-20261015/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from datetime import datetime,UTC
from pathlib import Path
from rcominote.experiments import actions_fast_control as C
from rcominote.experiments.hci_monitor import Snoop
root=Path('artifacts/actions-fast-ram256-20261015');pre=Path('artifacts/actions-fast-preflight-20261015');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={}
def pin(p,digest=None):
 p=Path(p);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
report=json.loads(pin(root/'report.json','2f88353129df638763eeca0cb39610b5350f0933107054cef6d68df3c84d0b3e'));plan=json.loads(pin(root/'plan.json','9b5decbbadc29940f05ea861bc7f69303185f02ba21bed4d8f3e5976a6c87e1d'));mp=root/'source-snapshot/manifest.json';m=json.loads(pin(mp,'e5aa1bfda26bebc0ca8399ac6c167f5fb5c88ff5bbd58f80a1700feb2ff3f495'));review=json.loads(pin(root/'preflight-review.json'));assert len(m['source_files'])==149 and len(m['test_files'])==135
for e in m['source_files']+m['test_files']:
 for base in (mp.parent,Path(review['isolated_source'])):assert len(pin(base/e['path'],e['sha256']))==e['bytes']
before=json.loads(pin(pre/'checks-before.json'));assert before==json.loads(pin(pre/'checks-after.json')) and len(before)==348 and review['new_full_check_run'] is True
oracle=C.source_gate(plan,image);proof=C.replay(root,image);assert proof==report['verification'] and report['ok'] is True and len(oracle)==256
ref=plan['state_reference'];assert ref['historical_identity_only'] is True and ref['current_owned_file_verified'] is False and ref['directory']==str(Path('artifacts/prefilled-factory-one-20261015').resolve())
C.C.J.time_order(m['created_at'],plan['planned_at'],report['started_at'],report['ended_at']);assert plan['profile']==C.PROFILE and plan['mdb_command']=='dbg mdb 18000000 100' and plan['filler_command']=='kernel version' and C.MARKER.fullmatch(plan['marker'])
raw=pin(root/'session.btsnoop','e26c967ca318025d96a9d6c32b32bc286f291285f9eac2966a84a420afafcdab');observed,wire,events=C.A.envelope(report,root,2);assert len(raw)==7202 and observed['records']==144 and len(report['att_packets'])==72 and events['events']==0
op=report['operation'];assert op['fillers']==0 and op['phase']=='complete' and op['condition_applied'] is op['live_complete'] is op['end_received'] is True and op['sd_write_attempted'] is False and op['ack_count']==5 and op['pending_hex']=='' and op['frames'][-1]['command']==0xf1
assert sum(f['command']==0xf0 for f in op['frames'])==4 and sum(f['command']==0xf1 for f in op['frames'])==1
assert C.A.A.action_frames(report,op,expected=C.recipe(plan,0))['acks']==5 and C.parse(op['frames'],plan,oracle)==op['content_verification']==proof['content'] and proof['content']['rows']==16 and proof['content']['bytes']==256 and proof['content']['oracle_used_to_select_chain'] is False
assert report['startup_classification']['mode']=='fast' and observed['transactions'][0]==report['startup_settlement'] and observed['transactions'][1]==op['normalization']
normal=observed['transactions'][1];C.A.common.transaction(normal,origin='host',parameters=(6,6,0,500));assert normal['update']['interval']==6 and normal['request']['min_length']==normal['request']['max_length']==1
assert proof['text_origin'] and proof['applied_interval']==6 and proof['requested_ce_hints']==[1,1] and proof['fillers']==0 and proof['parameter_transactions']==2
assert report['before']==report['after']==plan['expected_before'] and report['after']['device']['free_capacity']==59589 and report['disconnect_observation']['event']['reason']==0x16 and report['disconnect_observation']['event']['record']==143
identity_at=datetime.fromtimestamp((wire[report['after_span'][1]-1][2]-C.A.P.H.EPOCH_US)/1_000_000,UTC).isoformat();assert identity_at=='2026-10-14T17:32:49.553447+00:00'
assert all(plan['budget'][k]==0 for k in ('sd_writes','nor_writes','mmio_writes','ram_writes','new_files','new_raw_nor_coverage_bytes')) and proof['new_raw_nor_coverage_bytes']==0
try:C.C.parent_gate(root,image)
except ValueError:pass
else:raise AssertionError('RAM Actions success incorrectly admitted as storage parent')
old=Path('artifacts/prefilled-factory-next3-20261015');old_plan=json.loads(pin(old/'plan.json'));assert len(set(old_plan['parent']['prior_names'])|set(C.C.nonces(old_plan)))==70 and json.loads(pin(old/'report.json'))['ok'] is False
hostnote=Path('artifacts/actions-interval-host-review-20261015/astra.json');note=json.loads(pin(hostnote,'f988a6608aa824371d5f27120d6814be94adf442827e0bf7335025a3df19708b'));assert len(note['captures'])==3
for e in note['captures']:
 old_raw=pin(e['path'],e['sha256']);s=Snoop();s.feed(old_raw,final=True);assert s.records==e['records'];connect=next(v for v in s.events if v['kind']=='connect' and v['record']==e['connection_record']);updates=[v for v in s.events if v['kind'] in ('connect','update') and v.get('handle')==connect['handle'] and v.get('status')==0]
 for n in e['notification_records']:
  last=max((v for v in updates if v['record']<=n),key=lambda v:v['record']);assert {k:last[k] for k in ('interval','latency','timeout')}==e['effective_at_all_loss_notifications'] and last['interval'] in (36,48)
 assert all(v['record']>max(e['notification_records']) for v in e['parameter_and_epoch_events'] if v['kind']=='request' and v.get('min')==6 and v.get('max')==12)
receipt=Path('docs/evidence/actions-fast-ram256-live-2026-10-15.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for x in v.values():refs(x)
  elif isinstance(v,list):
   for x in v:refs(x)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(v.__file__).resolve() for n,v in sys.modules.items() if n.startswith('rcominote') and getattr(v,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in m['source_files']};assert all(p in allowed for p in origins);assert all(sha(p.read_bytes())==h for p,h in checked.items())
print('PASS frozenActionsRAM256exactoracle/4fullF0+5ACK+terminalF1/0fillers/per-byteRXaftercommands/settledFASTthenhostap6CEhints1beforemarkerMDB/72ATT144HCI2txn0pendingstatus/normal16;finalidentity',identity_at,'state59589;0SD-NORcoverage/currentownedfileUNVERIFIED/history70;oldlosses45-60ms/noneap6;',len(origins),'snapshotmodules;',len(checked),'pinsunchanged; stream/marker/privatehash withheld')
PY
```
