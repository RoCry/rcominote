# BOOT0 direct F0 visibility control failed, 2026-10-15

[Sanitized metadata](evidence/actions-fread-boot0-live-2026-10-15.json); private originals `artifacts/actions-fread-boot0-20261015`. **One fixed BOOT0 direct F0 control failed**, UTC14日17:48:36.309993–17:48:56.018215 = HKT15日01:48:36–01:48:56. Original error: `ValueError: Requires exactly32 complete contiguous fixed-width NOR rows`. No canonical NOR payload accepted, binary published, storage access/write or newcoverage. Original falseflags/errors remain unchanged.

Actual DEFAULT startup settles36, remoteFAST12 then host6/0/500 with requestedCEhints1/1 settles atHCI113, before freshafcmarkerTX115 and sole`dbg fread spi_flash 0`TX119. Three complete parametertransactions/0pending/status. Two`kernel version`fillers ofMAX8; one marker/onefread/oneoffset0status/oneexactproducer echo. CE1/1 are requestedhints, not measured eventlength.

**Host64ATT versus rawownedHCI66ATT**: all27TX identical; host37RX is strictprefix of39wireRX, differing only at final STOPACK/F1. RawHCI143records/6143B reconstructs sevenACK, two FULLF0frames(text504+29=533B), terminalF1/empty pending; originalhost records sixACK/noF1. Neither rawstream nor originalhoststream contains any canonical NORrow; both reproduce original32rows error. This is not the historical244B fragmentloss case. Complete framing/echo/status does not prove canonical NOR body delivery or hardwareflash readfailure; PRINTK route remains unresolved. Rawtail is diagnostic only: **do not append it to originalhosttrace, replace missingafteridentity or promote originalcontrol**. Original`capture_error`, session-retired`after_error`, and RX-mismatch`final_evidence_error` retained; failedreplay and storageparentgate reject.

OriginalGATT/beforeidentity, exactcommandcount, actualparameterrecords, wireepoch and normaldisconnect0x16 afterlastATT independently verified. Originalcapture has **no finalidentity**. A later productionCLI`info` exited0 on a **separateconnection without HCIcapture**; serial matches originalbefore locally, sanitized state FW010004/NOTEidle/unbound/charging100/free59589. Its outputfilemtime gives observation upperbound **2026-10-14T17:52:24.863939Z** (rounded upward to microsecond), not an exact response timestamp. This later observation cannot repair originalafter or make the original oneconnection successful.

Historical [ONEsuccess](prefilled-factory-one-live-2026-10-15.md) remains IDENTITY ONLY reference/current_owned_file_verified=False. LastfullSDobject observed is [NEXT3failedfirst](prefilled-factory-next3-failed-2026-10-15.md); latestidentityresponse in that capture was17:09:26.871464Z. Changedprivateownedfile not read back/admitted here; history70 unchanged. Earlier [applied6 RAM256 control](actions-fast-ram256-live-2026-10-15.md) succeeded under its own oracle/byteprovenance contract; that result does not establish thisNORvisibility route.0SDaccess/storagewrites/newfiles/NOR/MMIO/explicitRAMmemorywrites/newcoverage; Actions still changes transientlogRAM/sessionstate. No retry, heapprobe, outputmodechange or deletion.

Frozen **150source/136tests/286files**, manifest64e7e4c0a3e9ccfbbda5b1ba2d96193641e5e6b389c30a988bb6d68d739b2d26. All lengths/hashes equal attachedsnapshot/isolatedcopy. FreshpreIO2704tests+159subtests/43.54s,344format/lint/build;350inputs before==after, new_full_check_run=true. Source17:46:52.090915Z < plan17:46:52.993679Z < start < end. Independent replay imports105 frozenprojectmodules, source/oracle/identity/parameter/rawATT proofs verified. No latercurrent-root code/check claim.

Bounded hoststatic followup: [private pinned evidence](../artifacts/actions-ring-route-static-20261015/evidence.json), SHA92c4eda4728a89b634d286db957afc6da4822cba6b06d88459ed52884173714f; actualimage29regions plus sixSDKfiles/commit verified. Initialized shelltransport0x100a1364 calls DMA/raw0x10026edc before BLEcallback; nonzero DMAinit can write sameprintkbody0x1803ee09. LiveRAMpointers/init not read, so this is conditionalactualimage routing, not observedruntime state or a proven cause. It prevents treating MDB ring extraction as a proven passive/stable snapshot; no newprobe proposed.

Coverage unchanged **A44304/B155204/potential199508B**, factory3072paired/5120missing, systemcontiguous6144B`[24000,25800)`. [ASOF inventory](nor-backup-coverage-2026-10-14.md) and all oldreceipts/publicbinaries unchanged; cohort70confirmed+1olderdeclared+1historicalpossible=max72. Full4MiB backup/reliable restore/ownruntime incomplete. User reports only powerbutton and recording slider; independentRESET/ROMexit/cable data path unproven. All stream/frame/text hex/hash, afcmarker and factorycarrier/sector/prefix bytes/digests/nonces withheld; metadata only.

Exact host-only frozen audit; private originals/isolatedcopy required. RawHCI diagnostic never repairs originalreport; no device/evidence writes or privatecontent output:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/actions-fread-boot0-20261015/source-snapshot/src uv run python - <<'PY'
import hashlib,json,re,sys
from datetime import datetime,UTC,timedelta
from pathlib import Path
from rcominote.experiments import actions_fread_control as F
from rcominote.log_stream import Stream
C=F.C;root=Path('artifacts/actions-fread-boot0-20261015');pre=Path('artifacts/actions-fread-preflight-20261015');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={};error='ValueError: Requires exactly32 complete contiguous fixed-width NOR rows'
def pin(p,digest=None):
 p=Path(p);b=p.read_bytes();h=sha(b);assert digest is None or h==digest;checked[p.resolve()]=h;return b
r=json.loads(pin(root/'report.json','e906c4b96a3c7c4a1457866bfdea570998ffdf8366ba951e33db4fda07ae9894'));plan=json.loads(pin(root/'plan.json','5324694e8ba98e6af83de60b06a7ba7931c183a178856de773090b8307aea2ec'));mp=root/'source-snapshot/manifest.json';m=json.loads(pin(mp,'64e7e4c0a3e9ccfbbda5b1ba2d96193641e5e6b389c30a988bb6d68d739b2d26'));review=json.loads(pin(root/'preflight-review.json'));assert len(m['source_files'])==150 and len(m['test_files'])==136
for e in m['source_files']+m['test_files']:
 for base in (mp.parent,Path(review['isolated_source'])):assert len(pin(base/e['path'],e['sha256']))==e['bytes']
before=json.loads(pin(pre/'checks-before.json'));assert before==json.loads(pin(pre/'checks-after.json')) and len(before)==350 and review['new_full_check_run'] is True
oracle=F.source_gate(plan,image);C.plan_gate(r,plan,root);assert len(oracle)==512 and r['ok'] is False and r['error']==r['capture_error']==error and r['after_error']=='RuntimeError: Fixed Actions control failed; session retired' and r['final_evidence_error']=='ValueError: Owned HCI/host ATT rx sequence differs'
assert 'after' not in r and 'verification' not in r and r['after_span']==[64,64]
assert plan['state_reference']['historical_identity_only'] is True and plan['state_reference']['current_owned_file_verified'] is False
C.C.J.time_order(m['created_at'],plan['planned_at'],r['started_at'],r['ended_at']);raw=pin(root/'session.btsnoop','0d32e16d8a03e022d2308892ba74422744356e30b7e9333341c68ae4b5bad48e');o=C.A.P.inspect(raw,link=r['transport']['link'],final=True);assert len(raw)==6143 and o['records']==143 and len(o['transactions'])==3 and not o['pending'] and len(r['status_events'])==0
att=C.A.dual_hci.att_packets(raw,r['transport']['link']['handle']);assert len(att)==66 and len(r['att_packets'])==64
for direction,host_count,wire_count in (('tx',27,27),('rx',37,39)):
 host=[v['hex'] for v in r['att_packets'] if v['direction']==direction];wire_values=[v['hex'] for v in att if v['direction']==direction];assert len(host)==host_count and len(wire_values)==wire_count and host==wire_values[:len(host)]
tail=[v for v in att if v['direction']=='rx'][-2:];suffix=Stream()
for v in tail:assert v['hex'].startswith('1b1800');suffix.feed(bytes.fromhex(v['hex'])[3:])
assert [v['command'] for v in suffix.frames]==[0x10,0xf1] and suffix.acks==1 and suffix.ended
try:C.A.dual_hci.bind(r,raw)
except ValueError as exc:assert str(exc)=='Owned HCI/host ATT rx sequence differs'
else:raise AssertionError('Original missing host tail unexpectedly complete')
stream=Stream();notes=[]
for v in att:
 if v['direction']=='rx' and v['hex'].startswith('1b1800'):value=bytes.fromhex(v['hex'])[3:];stream.feed(value);notes.append(value)
assert stream.acks==7 and stream.ended and not stream.pending and stream.frames[-1]['command']==0xf1 and sum(v['command']==0xf1 for v in stream.frames)==1
text=C.text_bytes(stream.frames);texts=[bytes.fromhex(v['hex'])[8:] for v in stream.frames if v['command']==0xf0];assert list(map(len,texts))==[504,29] and len(text)==533
op=r['operation'];assert op['fillers']==2 and op['condition_applied'] is True and op['sd_write_attempted'] is False and op['ack_count']==6 and op['end_received'] is False and op['pending_hex']=='' and 'live_complete' not in op
assert [w['hex'] for w in op['writes']]==[p.hex() for p in F.recipe(plan,2)] and all(w['att_write_confirmed'] for w in op['writes'])
actions=[bytes.fromhex(v['hex'])[3:] for v in att if v['direction']=='tx' and v['hex'].startswith('121600')];assert actions==F.recipe(plan,2) and actions.count(F.producer_packet())==1 and C.text_bytes(op['frames'])==text
assert len(list(C.echo_pattern(plan['marker_command']).finditer(text)))==1 and len(list(C.echo_pattern(F.PRODUCER).finditer(text)))==1 and len(list(F.F.STATUS.finditer(text)))==1 and next(F.F.STATUS.finditer(text))[1]==b'0'
rows=re.findall(rb'(?m)^ {0,7}[0-9a-f]{1,8}: (?:(?:[0-9a-f]{2}| [0-9a-f]) ){16}\r\n',text);assert len(rows)==0
for frames in (op['frames'],stream.frames):
 try:F.parse(frames,plan,oracle)
 except ValueError as exc:assert f'ValueError: {exc}'==error
 else:raise AssertionError('Original missing32rows unexpectedly returned content')
view={'transport':r['transport'],'att_packets':att,'hci_capture':r['hci_capture']};positions=C.A.common.wire_positions(view,raw);commands=[i for i,v in enumerate(att) if v['direction']=='tx' and v['hex'].startswith('121600')];assert positions[commands[2]][0]==115 and positions[commands[3]][0]==119
assert C.C.startup.classify(o['transactions'][0],policy=plan['startup_policy'])==r['startup_classification'] and r['startup_classification']['mode']=='default' and o['transactions'][0]['update']['interval']==36 and o['transactions'][1]['update']['interval']==12
C.A.common.transaction(o['transactions'][1],origin='remote',parameters=(6,12,0,500));C.A.common.transaction(o['transactions'][2],origin='host',parameters=(6,6,0,500));assert o['transactions'][2]['update']['record']==113 and o['transactions'][2]['update']['interval']==6 and 113<positions[commands[2]][0]<positions[commands[3]][0]
start_us,end_us=[C.A.P.H.EPOCH_US+int(datetime.fromisoformat(r[k]).timestamp()*1_000_000) for k in ('started_at','ended_at')];assert all(start_us<=v['timestamp_us']<=end_us for v in att)
assert o['disconnects'][0]['record']>max(p[1] for p in positions) and r['close_requested_us']<=o['disconnects'][0]['timestamp_us']<=r['close_completed_us']+8_000_000 and r['close_completed_us']<=r['disconnect_observed_us']<=r['close_completed_us']+8_000_000
assert len(o['disconnects'])==1 and o['disconnects'][0]['status']==0 and o['disconnects'][0]['reason']==0x16 and r['disconnect_observation']['event']==o['disconnects'][0] and r['monitor_exit']==0 and r['monitor_stop']=={'signal':'SIGINT','requested':True,'delivery':'sent'}
assert C.A.A.setup(r)==r['gatt_proof'];C.A.A.identity(r,r,'before');assert r['predecessor_state_verification']==C.A.verify_state(plan['expected_before'],r['before'],sd_write=False)
for gate in (C.replay,C.C.parent_gate):
 try:gate(root,image)
 except ValueError:pass
 else:raise AssertionError('Original failed control promoted')
post_path=root/'post-failure-info.json';post=json.loads(pin(post_path));mtime_ns=post_path.stat().st_mtime_ns;upper=(datetime(1970,1,1,tzinfo=UTC)+timedelta(microseconds=(mtime_ns+999)//1000)).isoformat();assert post['serial']==r['before']['serial'] and post['bound'] is False and post['device']['free_capacity']==59589 and post['device']['version']=='010004' and post['device']['mode']=='note' and post['device']['recording_state']=='idle' and post['device']['charging'] is True and post['device']['battery']==100;C.C.J.time_order(r['ended_at'],upper)
old=Path('artifacts/prefilled-factory-next3-20261015');old_plan=json.loads(pin(old/'plan.json'));assert len(set(old_plan['parent']['prior_names'])|set(C.C.nonces(old_plan)))==70 and json.loads(pin(old/'report.json'))['ok'] is False
assert all(plan['budget'][k]==0 for k in ('sd_writes','nor_writes','mmio_writes','ram_writes','new_files','new_raw_nor_coverage_bytes'))
static=json.loads(pin('artifacts/actions-ring-route-static-20261015/evidence.json','92c4eda4728a89b634d286db957afc6da4822cba6b06d88459ed52884173714f'));blob=pin(static['image']['file'],static['image']['sha256']);assert len(blob)==static['image']['bytes'] and len(static['regions'])==29
for region in static['regions']:
 piece=blob[region['file_offset']:region['file_offset']+region['bytes']];assert piece.hex()==region['hex'] and sha(piece)==region['sha256'] and int(region['end_exclusive'],16)-int(region['address'],16)==len(piece)
for source in static['sdk']['files']:pin(source['file'],source['sha256'])
import subprocess
assert subprocess.check_output(['git','-C',static['sdk']['repository'],'rev-parse','HEAD'],text=True).strip()==static['sdk']['commit']
receipt=Path('docs/evidence/actions-fread-boot0-live-2026-10-15.json')
if receipt.exists():
 def refs(v):
  if isinstance(v,dict):
   if {'file','bytes','sha256'}<=v.keys():assert len(pin(v['file'],v['sha256']))==v['bytes']
   for x in v.values():refs(x)
  elif isinstance(v,list):
   for x in v:refs(x)
 refs(json.loads(receipt.read_bytes()))
origins=[Path(v.__file__).resolve() for n,v in sys.modules.items() if n.startswith('rcominote') and getattr(v,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in m['source_files']};assert all(p in allowed for p in origins);assert all(sha(p.read_bytes())==h for p,h in checked.items())
print('PASS originalBOOT0controlFAILEDretained;host64vsownedHCI66 exactTX27/RX37prefix39 tailSTOPACK-F1only;raw7ACK2fullF0text533/terminalF1/0pending/zeroNORrows/exactoriginalerror/default36-FAST12-host6update113beforemarker115/fread119/normal16;separateCLIinfo59589mtimeupper',upper,'NOHCI/nooriginalafterrepair;0SDcoverage/currentfileUNVERIFIED/history70;',len(origins),'frozenmodules;',len(checked),'pinsunchanged; stream/marker/privatehash withheld')
PY
```
