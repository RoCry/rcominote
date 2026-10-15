# Readonly owned-file recovery: live success, 2026-10-14

Frozen [metadata](evidence/owned-file-recovery-live-2026-10-14.json); private originals `artifacts/owned-file-recovery-20261014`. **New readonly checkpoint succeeded: current owned4096 file and real final state observed.** No Actions/producer/SD write/newfile/newNOR coverage; no public binary. Prior [two-known same-connection control](two-known-session-failed-2026-10-14.md) stays failed, its17-transaction contract incomplete and boot0 candidates unpromoted.

Current owned4096 **ring** SHA **`a5d8e2e773a38954f35d8b2f919fa585e09df0a13c7a9c29a6ac6da4a76f5a48`**, complete fresh download; final observed2026-10-14T10:07:03.237946Z FW010004/NOTEidle/unbound/charging100/**free59589**. File differs from the failed session's last downloadedf0b5…ffd3, as allowed after its unverified third overwrite; priora16e is also historical. This new observation resolves the earlier unknown current-object/state boundary. No NOR parsing, freshness extraction, known4200 oracle comparison or coverage counting of these new4096 bytes; changed content alone cannot validate the failed producer/control. Bounded ASCII observation finds the exact failed-third uptime command atbyte1007, producer command at3044 and dump command at3110; private nonce omitted. This shows retained command text from that attempt, so missing FAST does not imply no firmware command processing. No full intended-content/oracle/root-cause inference.

One connection/one complete4096 download, full GATT/90ATT↔168HCI records/10963B, exactly three complete transactions: actual startupFAST→host6/0/500→actual EOF SLOW after complete End. All original download/identity/barrier/state/time/wire evidence replayed, zero pending/status events, final normal disconnect status0/reason0x16 atHCI167 after finalATT; passive close observation2.163670s≤8. Clean SIGINT/monitor exit0. Initial state allowed≤1MiB integer decrease for exactly one prior unverified overwrite, actual0; readonly intermediate/final identities equalinitial with allowance0. MiB reports do not measure allocation bytes.

Frozen139source/117tests manifest **305534f3786003fe3c59a2e4917218c658ac54ec7f82d039d484b280e3b63313**, created10:06:38.167861Z before immutable plan/start10:06:45.405280Z; end10:07:03.237946Z. All256 source/test lengths/hashes checked, all96 imported project modules from snapshot. Root pre-I/O manifest records **2137tests+159subtests/build passed**; this review independently replays capture/source chain, does not rerun that full suite. Extra post-I/O source-fixture tests are separate future work, excluded from this frozen count. Current evolving source never replaces frozen capture semantics.

Frozen source gate replays the full successful ancestor chain and exact pinned failed known-control source, preserving its falseflags/no finalidentity/no third download. New successful parent admission retains26 prior planned names and accepts only the newly observed whole4096 baseline/state. Direct replay/parent admission of the old failed control still rejects. Admission does not authorize another experiment; any next control needs a separate fixed plan/source freeze/checks/review.

[Actual system raw first4KiB](system-first4k-raw-live-2026-10-14.md)/SHA74807d164370bd3d4ded53ac191414a1f5ff9a50ca04647b898179a1e7d83a5c unchanged, distinct from private owned ring. Raw coverage remains strong39184B/potential194388B, system`[24000,25000)` complete; most4MiB/system raw backup, reliable restore and own firmware remain incomplete. Cohort70 confirmed+1 older declared+1 historical possible=max72 unchanged, no deletion. Original captures, frozen receipts and failed flags untouched; no hardware/source edits by this review.

Exact offline frozen replay, repository root/private originals required; no device access or file writes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/owned-file-recovery-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from pathlib import Path
from rcominote.experiments import owned_file_recovery as O
root=Path('artifacts/owned-file-recovery-20261014');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest();checked={}
def pin(path,expected=None):
 p=Path(path);raw=p.read_bytes();digest=sha(raw);assert expected is None or digest==expected;checked[p.resolve()]=digest;return raw
def refs(value):
 if isinstance(value,dict):
  if {'file','bytes','sha256'}<=value.keys() and Path(value['file']).is_file():assert len(pin(value['file'],value['sha256']))==value['bytes']
  for child in value.values():refs(child)
 elif isinstance(value,list):
  for child in value:refs(child)
report=json.loads(pin(root/'report.json','266bedb77ff98338d353a890cfb6c6d9236edc2d75c0fd1b75715383d8fc5eb2'));plan=json.loads(pin(root/'plan.json','81a28bc5db68e1a635457567243684a99bfb603a5cfcae45f92be81e0fa8784c'))
mp=root/'source-snapshot/manifest.json';manifest=json.loads(pin(mp,'305534f3786003fe3c59a2e4917218c658ac54ec7f82d039d484b280e3b63313'));assert len(manifest['source_files'])==139 and len(manifest['test_files'])==117
assert manifest['checks']=={'just_check':'2137 passed, 159 subtests passed in 27.09s;312 formatted;lint passed','uv_build':'source distribution and wheel passed'}
for entry in manifest['source_files']+manifest['test_files']:assert len(pin(mp.parent/entry['path'],entry['sha256']))==entry['bytes']
O.C.J.time_order(manifest['created_at'],plan['planned_at'],report['started_at'],report['ended_at'])
assert report['ok'] is report['operation']['ok'] is True and report['producer_attempted'] is report['sd_write_attempted'] is False
old=Path(plan['failed']['directory']);old_before={name:sha(pin(old/name,digest)) for name,digest in O.PINS.items()}
parent_ring=O.source_gate(plan,image);current,state,summary=O.C.parent_gate(root,image)
proof=O.validate_readonly(report,root,plan);assert summary['verification']==report['verification']==proof
assert current==pin(root/'retained/download.bin') and len(current)==4096 and sha(current)=='a5d8e2e773a38954f35d8b2f919fa585e09df0a13c7a9c29a6ac6da4a76f5a48'
assert state==report['after']==report['operation']['after']==report['before'] and state['device']['free_capacity']==59589 and len(summary['prior_names'])==26
assert sha(current)!=plan['failed']['historical_ring_sha256'] and plan['failed']['current_file_unknown'] is True and summary['original_failed_retained'] is True
failed_report=json.loads((old/'report.json').read_bytes());attempt=failed_report['groups'][1]['operations'][0]
assert [current.find(attempt[k].encode()) for k in ('uptime_command','producer','dump_command')]==[1007,3044,3110]
assert proof['ownership_only'] is True and all(proof[k]==0 for k in ('actions','producers','sd_writes','new_files','new_raw_nor_coverage_bytes'))
raw=pin(root/'session.btsnoop','4d87becb8a7922f6e92ec632af36d1727c6d671f78c4b4056c98c914c880bb57');observed=O.A.P.inspect(raw,link=report['transport']['link'],final=True)
assert len(raw)==10963 and observed['records']==168 and len(report['att_packets'])==90 and len(observed['transactions'])==3 and not observed['pending'] and proof['status_events']['events']==0
assert observed['disconnects']==[report['disconnect_observation']['event']] and observed['disconnects'][0]['record']==167 and observed['disconnects'][0]['reason']==22
for gate in (O.A.replay,O.C.parent_gate):
 try:gate(old,image)
 except ValueError:pass
 else:raise AssertionError('Original failed control promoted')
assert old_before=={name:sha((old/name).read_bytes()) for name in O.PINS}
receipt=Path('docs/evidence/owned-file-recovery-live-2026-10-14.json')
if receipt.exists():refs(json.loads(receipt.read_bytes()))
origins=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];allowed={(mp.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in allowed for p in origins)
assert all(sha(p.read_bytes())==digest for p,digest in checked.items())
print('PASS frozen ownership recovery/full ancestor+failed source;90ATT/168HCI/3txn;current4096/state59589/history26;0writes/0coverage/originalfailedretained;',len(origins),'snapshot modules;',len(checked),'pinned inputs unchanged')
PY
```
