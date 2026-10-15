# System first4KiB actual raw assembled after final two pairs

New fixed v3 **24c00 and24e00 pairs both succeeded**, adding1,024 actual raw bytes. All8 physical512-byte pages now assemble **`[0x24000,0x25000)` =4,096 bytes**, SHA256 **`74807d164370bd3d4ded53ac191414a1f5ff9a50ca04647b898179a1e7d83a5c`**. This combines historical captures: original header is44 non-atomic guarded row windows; later7 pages are complete independent pairs. **Not one atomic snapshot, fullsystem raw,4MiB backup or restore proof.**

[Compact receipt/source table](../evidence/system-first4k-raw-live-2026-10-14.json) · [actual raw4096](../evidence/system-first4k-raw-live-2026-10-14/system-first4k-raw.bin) · [unchanged as-of24200 inventory](nor-backup-coverage-2026-10-14.md).

| Physical page / assembled file offset | Actual512 SHA256 | Original provenance |
|---|---|---|
|24000 /0|`28b2e50ba95630f6485bd5e3ccfbd8ebe5f1406ffa36d6c0c4e35c4c71af0678`|[44 original guarded windows](../evidence/system-raw-header-2026-10-12/readback.json),32 independently repeated rows; non-atomic |
|24200 /512|`f9337ab9cd70ccd0f6d5c94c9104a25388b1109ff3af4fc217931ea67cc3227e`|[Original fixed pair](system24200-live-2026-10-14.md) |
|24400 /1024|`d3a2b5564684592b84ee83ca186955c4cda909cbb60ce8295df1fc565797ce2e`|[Successful v2 pair](paired-nor24400-live-2026-10-14.md) |
|24600 /1536|`3243e15bfa66ac634643eea56e50739f57a3a29cc44247356a7749c3bc4759f5`|[Completed original prefix of failedjob](paired-nor-system4-live-2026-10-14.md) |
|24800 /2048|`41eba1831fd85ec647cbcd9d19a11a49467655a22df613e7647e4cb2c931afd3`|Same failedjob, separate fully completed pair/source |
|24a00 /2560|`6234e0aaaa13bbf929045308e789ad7b1a991cda8e99c3652ff6d07304ebdb9f`|[Fresh successful v3](paired-nor24a00-v3-live-2026-10-14.md), never old failedcandidate |
|24c00 /3072|`d2084fec597f060133c9e5344f3aa5318e73e778715ac22f7f16aed88bab0f6c`|New original v3 pair, all gates complete |
|24e00 /3584|`dc59a1b64691aebb9d079b1c576253f86b82ba6ab16ddd404e8125623f3685c6`|New original v3 pair, all gates complete |

Independent review replayed new wholejob and complete frozen parent chain: legacy24200, v2/246–248 completed prefix, distinct zero-coverage failed-communication checkpoint, fresh24a v3. Original failedsystem4 success/parent gates still reject; old failed24a candidate supplies no assembly bytes. Separately replayed all44 original24000 windows from pinned archive, then required exactly8 unique physical offsets,512 bytes each, every pair's actual first/second equality, exact address-order concatenation, no overlap/gap/fill/content-hash dedup. Only actual4096 binary published; JSON pins original raw/report/HCI/job sources rather than duplicating wire proofs. Firmware SPI API offsets, not mapped addresses or independent electrical chip dump.

| New original page | ATT / HCI records / capture bytes | Prefix / exemptions | Producer→dump composer | Normal disconnect |
|---|---|---|---|---|
|24c00|182 /318 /25211|4096 both /none|true,true|status0/reason16,record317 |
|24e00|182 /316 /25146|4096 both /none|false,true|status0/reason16,record315 |

Both connections: actual strict startupFAST; each9 complete transactions/0pending, full GATT/ATT/HCI, exact6ACK/F1 per producer, individually countedF0=0, status0, unique current nonce/dump/status/32canonical rows, actual predecessor binding, EOF SLOW before identity and final normal disconnect. All new producer prefixes4096/no exemptions under original contiguous-write model; does not imply every byte individually changed. FAST-after-Actions proves ordering, not unique trigger. Owned monitor exits0 after SIGINT; passive disconnect observations2.166325s/2.165916s within8s. Two connections/6complete4096 downloads/4NOR-read producers/4existing-file SD overwrites/0newfiles/0deletions, cohort70 confirmed+1 declared+1 historical possible=max72 unchanged. No firmware NOR write command attempted.

New24c baseline matches prior24a current6249…2258a. Its second ringe821…70e23 becomes24e actual baseline; second24e is latest owned4096 **`a16e83146f8957a06240a781df08f476cdcfd8dd76d6843aa26ce60eb6a14609`**. All original initial/intermediate/final owned identities remain FW010004/NOTEidle/unbound/charging100/**free59589**, each overwrite observes0MiB integer decrease. Latest observed09:10:35Z; capacity is not allocation-byte measurement. Successful new parent retains22 prior planned names.

Predeclared fixed codec hypothesis beforeI/O, then posthoc comparison after raw success: new24c/24e primary reset32 each512/512 match mapped`[0xc00,0xe00)`/`[0xe00,0x1000)`; secondary reset512 matches32/512 and33/512 only. Full assembled4096 fixed32 decode equals mappedfirst4096 SHA **`f029faa09f76b6bf9bd735984aec23fa8cf26a9167074193e9767fffa96bc647`**. Existing effective state0x0a15a191/codec unchanged; first header32 bytes originally helped solve that state. No new fitting, oracle selection, reencoding substitution, decoded publication, efuse-key/fullsystemchecksum/boot/flash/restore claim. Root posthoc SHA `194e838bdaa56d14f2dc3ba0f44844fab3df565783bcb608a1b09e221dee7c7a` independently matches.

Original job09:09:38.117408Z–09:10:35.332473Z, plan09:08:06.656070Z. Frozen138source/114test manifest `d546d8dccdc58465a8c87d386852b87ecbe80632c62cf1e948bbee6b12cd9428` reused unchanged, all252 lengths/hashes verified, all96 imported project modules fromsnapshot. Preflight explicitly reuses prior2062+159/build and says `new_full_check_run=false`; no new full-suite run claimed. Root saved95-module frozen replay SHA `fb1707ff853866d0dfbe5274880812b4e643bd959dccb860619d681970e4918c` agrees. Current source now changes for a future known-content connection-reuse control; it is not used as this capture's semantics or claimed passed. Old captures/receipts/inventory unchanged; no device/source operations by this review.

FrozenASOF24200 inventory staysA36112/B155204/available191316B. Later6 pages add3072 unique bytes once: **strong39184B/potential194388B**; B not upgraded, factory8KiB/DSPextra444B still missing. Only first4KiB of system complete; remaining system raw backup and most4MiB coverage remain incomplete. No further I/O this turn. Next known connection-reuse control needs its own source review/checks/freeze and fixed plan, not automatic continuation.

Exact offline reproduction from repository root, private originals required; no device access or file writes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/paired-nor-system-first4k-v3-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys,tarfile
from pathlib import Path
from rcominote import nor_windows
from rcominote.experiments import paired_nor_audit as A
from rcominote.nor_codec import decode
root=Path('artifacts/paired-nor-system-first4k-v3-20261014');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest()
receipt=json.loads(Path('docs/evidence/system-first4k-raw-live-2026-10-14.json').read_bytes());job=json.loads((root/'report.json').read_bytes());manifest_path=root/'source-snapshot/manifest.json';manifest=json.loads(manifest_path.read_bytes());assert sha(manifest_path.read_bytes())=='d546d8dccdc58465a8c87d386852b87ecbe80632c62cf1e948bbee6b12cd9428'
assert len(manifest['source_files'])==138 and len(manifest['test_files'])==114;checked={}
def refs(v):
 if isinstance(v,dict):
  if {'file','bytes','sha256'}<=v.keys():
   p=Path(v['file']);raw=p.read_bytes();assert len(raw)==v['bytes'] and sha(raw)==v['sha256'];checked[p.resolve()]=sha(raw)
  for x in v.values():refs(x)
 elif isinstance(v,list):
  for x in v:refs(x)
refs(receipt)
for item in manifest['source_files']+manifest['test_files']:
 p=manifest_path.parent/item['path'];raw=p.read_bytes();assert len(raw)==item['bytes'] and sha(raw)==item['sha256'];checked[p.resolve()]=sha(raw)
proof=A.replay(root,image);assert proof==job['verification'] and proof['paired_bytes']==1024 and job['ok'] is True
current,state,parent=A.C.parent_gate(root,image);assert sha(current)=='a16e83146f8957a06240a781df08f476cdcfd8dd76d6843aa26ce60eb6a14609' and state['device']['free_capacity']==59589 and len(parent['prior_names'])==22
old=Path('artifacts/paired-nor-system4-20261014')
for gate in (A.replay,A.C.parent_gate):
 try:gate(old,image)
 except ValueError:pass
 else:raise AssertionError('Original failedjob promoted')
archive=Path(receipt['assembly']['pages'][0]['original_windows']['file'])
with tarfile.open(archive,'r:gz') as tar:blobs={m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
class MemoryPath:
 def __init__(self,name):self.name=name
 def read_bytes(self):return blobs[self.name]
 def read_text(self):return self.read_bytes().decode()
 def __str__(self):return 'archive:'+self.name
members=[MemoryPath(name) for name,b in blobs.items() if name.endswith('.json') and json.loads(b).get('nor_offset')==0x24000];header=nor_windows.analyze(members);assert len(members)==header['input_files']==header['distinct_sources']==44 and header['complete']
chunks=[]
for i,page in enumerate(receipt['assembly']['pages']):
 assert page['physical_range']==[0x24000+i*512,0x24200+i*512] and page['output_offset']==i*512
 raw=Path(page['raw_sources'][0]['file']).read_bytes();assert len(raw)==512 and sha(raw)==page['sha256']
 for ref in page['raw_sources'][1:]:assert Path(ref['file']).read_bytes()==raw
 if i==0:assert raw==bytes.fromhex(header['sector_hex'])
 else:
  original=json.loads(Path(page['original_report']['file']).read_bytes());assert original['ok'] is True and all(op['nor_offset']==page['physical_range'][0] for op in original['operations'])
 chunks.append(raw)
assert len(chunks)==8;raw=b''.join(chunks);public=Path(receipt['public_output']['actual_raw4096']['file']);assert raw==public.read_bytes() and len(raw)==4096 and sha(raw)=='74807d164370bd3d4ded53ac191414a1f5ff9a50ca04647b898179a1e7d83a5c'
assert decode(raw,block_bytes=32)==image.read_bytes()[:4096]
origins=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];allowed={(manifest_path.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in allowed for p in origins)
assert {p:sha(p.read_bytes()) for p in checked}==checked
print('PASS frozen fullchain/newpairs1024/header44/eightactualpages4096/oldfailedretained/current59589;',len(checked),'pinned inputs unchanged')
PY
```
