# NOR raw backup coverage inventory — 2026-10-14

Frozen cutoff: successful system24200 job ended **2026-10-14T06:56:01.339609Z**. Later 0x24400 acquisition excluded. Host-only inventory; no new physical read. [Machine ledger](evidence/nor-backup-coverage-2026-10-14.json) records exact file offsets, slice digests, whole-source pins, provenance classes, missing inputs, unions and holes.

Target `[0,0x400000)` = 4,194,304 bytes. Offsets below are physical addresses used by firmware SPI API; end exclusive. These captures do not constitute an independent electrical chip dump or an atomic/current whole-device snapshot.

| Tier | Acceptance | Unique bytes |
|---|---|---:|
| A | Actual raw bytes available; complete original producer inputs replayed now | 36,112 |
| B | Actual raw bytes available; historical acquisition/block manifest plus checksums, incomplete original producer inputs | 155,204 |
| C | Historical acquisition claim; required raw bytes missing | 8,636, excluded |
| A+B | Potential assemblable retained union | **191,316 / 4.5613%** |

Default assembler accepts **A only**. B requires explicit provisional policy and cannot be labelled fully replayed. C supplies no bytes and cannot authorize skipping acquisition. A covers70 complete512-byte pages plus272 bytes; A+B covers373 complete pages plus340 bytes. **373 pages are not all complete-source verified.** Full4MiB assembly must fail while policy holes remain.

| Physical range | Bytes | Tier | Actual raw source / provenance |
|---|---:|:---:|---|
| `[0,0x1000)` boot0 | 4096 | A | [raw](evidence/boot-complete-2026-10-12/raw.bin); all8 non-atomic, independently repeated row-window sets replay |
| `[0x1000,0x2000)` param0 | 4096 | A | [raw](evidence/param-slots-2026-10-13/param0-raw.bin);8 original independent SD-bridge pairs, parameter CRC |
| `[0x2000,0x3000)` boot1 | 4096 | A | [actual assembled raw](evidence/final-boot-sector-live-2026-10-14/fw1_boot.bin); complete original aggregate/source-chain replay |
| `[0x3000,0x4000)` param1 | 4096 | A | [raw](evidence/param-slots-2026-10-13/param1-raw.bin);8 original pairs; actualFF, no valid image inferred |
| `[0x4000,0x4400)` recovery head | 1024 | A | [recovery raw](evidence/recovery-complete-2026-10-13/recovery-raw.bin), offset0; blocks0/1 original44-window sets each |
| `[0x4400,0xfa00)` recovery middle | 46592 | B | Same raw offset1024;91 blocks2..92 hash-match manifest; original producer windows absent |
| `[0xfa00,0x13800)` recovery tail | 15872 | A | Same raw offset47616, length15672 + actual200-byte tail below;31 full original independent pairs |
| `[0x24000,0x24200)` system header | 512 | A | [raw](evidence/system-raw-header-2026-10-12/raw.bin);44 original repeated-row windows |
| `[0x24200,0x24400)` system24200 | 512 | A | [raw](evidence/system24200-live-2026-10-14/system24200.bin); full9-transaction/ATT/HCI/final-state/disconnect independent pair |
| `[0x1ec000,0x1ee000)` factoryRW | 8192 | C | [Sanitized historical summary](evidence/factory-rw-2026-10-13-summary.json); private raw/original captures absent |
| `[0x240000,0x240110)` DSP directory +16 | 272 | A | [Actual row hex](evidence/nor-partition-prefixes-2026-10-12/dsp/report.json);12 original sources,17 independently repeated16-byte rows; not a flat binary file |
| `[0x24d400,0x24da00)` DSP first3 | 1536 | A | [actual raw file](evidence/record-dsp-complete-2026-10-12/aerecord.dsp), offset0; original3 full-sector windows |
| `[0x24da00,0x268244)` DSP rest | 108612 | B | Same file offset1536;212 further full512 chunks match manifest plus68 bytes; complete producer inputs absent |
| `[0x268244,0x268400)` DSP extra | 444 | C | Historical last512-block claim only; bytes beyond retained file EOF missing |

A+B union: `[0,0x13800)`, `[0x24000,0x24400)`, `[0x240000,0x240110)`, `[0x24d400,0x268244)`.

| Remaining A+B hole | Bytes |
|---|---:|
| `[0x13800,0x24000)` | 67584 |
| `[0x24400,0x240000)` | 2210816 |
| `[0x240110,0x24d400)` | 54000 |
| `[0x268244,0x400000)` | 1670588 |
| Total | **4002988** |

A-only union additionally excludes recovery `[0x4400,0xfa00)` and DSP `[0x24da00,0x268244)`; A-policy holes total4,158,192 bytes. The suggested earlier82,704 replayable-byte estimate would include46,592 recovery bytes whose original producer windows are absent. Their raw bytes/manifest/checksum remain valid tierB evidence. Only head0/1 and tail93..123 complete producer inputs are retained here; no external copies were searched.

The sole newly published raw file is [actual recovery tail200 bytes](evidence/nor-backup-coverage-2026-10-14/recovery-tail-0x13738-0x13800.bin), physical `[0x13738,0x13800)`, SHA256 `0da5dd6d37c6adca9dbbb54c2bfae320a5fbf02d61fcbe8ac39768a1d58d7743`. It directly copies offsets312..512 from **both** retained `block-123-a/sector.bin` and `block-123-b/sector.bin` after complete original pair replay, including baseline/freshness/code guards/Actions frames/ring target. Original full512 SHA `a99730167d1bc02933035d02e4867fc6dc531ad155133f1be8a8df7208eb7fca`; [capture archive](evidence/recovery-complete-2026-10-13/captures.tar.gz) SHA `655be7b2cf009d46ad4d038581e8d2d3170edc4d87f4edc9e16eafceddd5e754`, unchanged before/after. This recovers already captured host evidence; it is not a new device acquisition or inferred padding. Available full63488 recovery bytes SHA `eb3daef4e00f5341108ab21b9b0cf25d08a53ccf534bee2934e873a2db59b785`; declared63288-byte image checksum does not cover extra200.

Actual DSP110148-byte file SHA `7ed5482ca4d37c39f6b70e72fc29c129f135bc77eed5d3c0889bfc8bc5fd436e` is physically bound to0x24d400 by independently replayed raw SDFS directory/size/checksum `0x96d685bb`. First215 full chunks match retained block manifest; last68 bytes exist, remaining444 do not. Full-file checksum/section parsing supports retained bytes but does not replace missing producer inputs or recover missing444 bytes. Directory272-byte raw prefix includes first16 bytes of a separate file; remaining240 bytes of that page stay unknown.

Mapped927632-byte system image, decoded images, DSP mapped/RAM sections, reencoding predictions, checksum-selected guesses, audio, and formatted4096-byte printk rings contribute **zero** additional physical raw coverage. IdenticalFF hashes at distinct physical addresses remain distinct records; union by address, reject conflicting overlaps, never deduplicate by content or fill unknown bytes. Historical factory claim requires later reacquisition; sensitive configuration/raw/value hashes are not published here.

State at cutoff: actual final identity free59589MiB, NOTE/idle, charging100; latest same-owned-file carrier4096 SHA `96a615b8f0e4d8e115fed262e2b4afa1684839194a7a0417394295342e49ef9c`. Carrier is not4096 raw NOR bytes. Original failed scratch trial remains failed. Later device state is outside this inventory. Full4MiB backup, validated restore path and own firmware/runtime remain incomplete.

Offline verification used frozen system24200 source134/test108 hash manifest; all100 loaded project modules originated there.373 explicit originals/source inputs hash-identical before/after; all available complete-source captures above replayed. No hardware/vendor executable access, source/canonical edits, or old receipt/private-original changes. JSON includes100 loose input pins and archive/source whole-file digests; each data slice has offset/count/digest (row-hex locator explicitly replaces byte offset).

Reproduce from repository root; reads existing originals and published tail only, no device access or file writes:

```sh
PYTHONPATH=artifacts/system24200-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib
import json
import struct
import sys
import tarfile
from collections import defaultdict
from pathlib import Path
from rcominote import nor_windows
from rcominote.experiments.recovery_tail import checked_read
from rcominote.experiments import status_remaining_job as J
from rcominote.experiments import scratch_system_pair_probe as P
from rcominote.printk_tail import NorTarget
from rcominote.recovery_image import verify as recovery_verify
from rcominote.param_image import inspect_slots
from rcominote.nor_codec import decode
from rcominote.sdfs_checksum import checksum32
from rcominote.sdfs_directory import parse_directory
from rcominote.dsp_sections import inspect_image

sha=lambda b:hashlib.sha256(b).hexdigest()
paths={
 'boot0_raw':'docs/evidence/boot-complete-2026-10-12/raw.bin',
 'boot0_report':'docs/evidence/boot-complete-2026-10-12/report.json',
 'boot0_windows':'docs/evidence/boot-complete-2026-10-12/windows.tar.gz',
 'boot0_first_report':'docs/evidence/nor-sector-zero-2026-10-12/report.json',
 'param0_raw':'docs/evidence/param-slots-2026-10-13/param0-raw.bin',
 'param1_raw':'docs/evidence/param-slots-2026-10-13/param1-raw.bin',
 'param_report':'docs/evidence/param-slots-2026-10-13/report.json',
 'param_captures':'docs/evidence/param-slots-2026-10-13/captures.tar.gz',
 'boot1_raw':'docs/evidence/final-boot-sector-live-2026-10-14/fw1_boot.bin',
 'boot1_receipt':'docs/evidence/final-boot-sector-live-2026-10-14.json',
 'boot1_report':'artifacts/final-boot-sector-20261014/report.json',
 'recovery_raw':'docs/evidence/recovery-complete-2026-10-13/recovery-raw.bin',
 'recovery_report':'docs/evidence/recovery-complete-2026-10-13/report.json',
 'recovery_prefix':'docs/evidence/recovery-raw-prefix-2026-10-12.bin',
 'recovery_manifest':'docs/evidence/recovery-prefix-provenance-2026-10-12.json',
 'recovery_captures':'docs/evidence/recovery-complete-2026-10-13/captures.tar.gz',
 'recovery_head_windows':'docs/evidence/boot-recovery-prefixes-2026-10-12/windows.tar.gz',
 'recovery_block1_windows':'docs/evidence/recovery-export-start-2026-10-12/block-001-windows.tar.gz',
 'system_header_raw':'docs/evidence/system-raw-header-2026-10-12/raw.bin',
 'system_header_report':'docs/evidence/system-raw-header-2026-10-12/readback.json',
 'system_header_windows':'docs/evidence/system-raw-header-2026-10-12/windows.tar.gz',
 'system24200_raw':'docs/evidence/system24200-live-2026-10-14/system24200.bin',
 'system24200_receipt':'docs/evidence/system24200-live-2026-10-14.json',
 'system24200_report':'artifacts/system24200-20261014/report.json',
 'dsp_raw':'docs/evidence/record-dsp-complete-2026-10-12/aerecord.dsp',
 'dsp_manifest':'docs/evidence/record-dsp-complete-2026-10-12/blocks.json',
 'dsp_report':'docs/evidence/record-dsp-complete-2026-10-12/report.json',
 'dsp_directory_report':'docs/evidence/nor-partition-prefixes-2026-10-12/dsp/report.json',
 'dsp_directory_parsed':'docs/evidence/nor-partition-prefixes-2026-10-12/dsp-directory.json',
 'factory_summary':'docs/evidence/factory-rw-2026-10-13-summary.json',
 'code_snapshot':'artifacts/system24200-20261014/source-snapshot/manifest.json',
}
loose={
 'boot0_first':sorted(Path('docs/evidence/nor-sector-zero-2026-10-12').glob('nor-overlap*-*.json')),
 'dsp_directory':sorted(Path('docs/evidence/nor-partition-prefixes-2026-10-12/dsp').glob('nor-dsp-prefix*-*.json')),
 'dsp_block0':sorted(Path('docs/evidence/record-dsp-header-2026-10-12/second').glob('window-*.json')),
 'dsp_block1':sorted(Path('docs/evidence/record-dsp-header-2026-10-12/end').glob('window-*.json')),
 'dsp_block2':sorted(Path('docs/evidence/record-dsp-export-2026-10-12').glob('window-*.json')),
}
protected={Path(p) for p in paths.values()}|{p for group in loose.values() for p in group}
manifest_path=Path(paths['code_snapshot']);manifest=json.loads(manifest_path.read_bytes())
assert sha(manifest_path.read_bytes())=='7524b0176e25aac3c830161ec34555c72333c9ab4d993fac8c2fd8432c2b1719'
for item in manifest['source_files']+manifest['test_files']:
 p=manifest_path.parent/item['path'];data=p.read_bytes();assert len(data)==item['bytes'] and sha(data)==item['sha256'];protected.add(p)
before={str(p):sha(p.read_bytes()) for p in protected}
class MemoryPath:
 def __init__(self,blobs,path=''):self.blobs,self.path=blobs,path
 def __truediv__(self,part):return MemoryPath(self.blobs,self.path+'/'+str(part) if self.path else str(part))
 def read_bytes(self):return self.blobs[self.path]
 def read_text(self):return self.read_bytes().decode()
 def __str__(self):return 'archive:'+self.path

def archive(key):
 with tarfile.open(paths[key],'r:gz') as tar:return {m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
def groups(blobs):
 result=defaultdict(list)
 for name,data in blobs.items():
  if not name.endswith('.json'):continue
  capture=json.loads(data)
  if 'printk_tail' in capture:result[(capture.get('nor_target'),capture.get('nor_offset'))].append(MemoryPath(blobs,name))
 return result
image=Path('artifacts/mapped-system-20261012.bin').read_bytes()
boot=Path(paths['boot0_raw']).read_bytes();proof=nor_windows.analyze(loose['boot0_first']);assert proof['complete'] and bytes.fromhex(proof['sector_hex'])==boot[:512]
for (_target,offset),members in groups(archive('boot0_windows')).items():
 proof=nor_windows.analyze(members);assert proof['complete'] and bytes.fromhex(proof['sector_hex'])==boot[offset:offset+512]
assert len(boot)==4096 and sha(boot)=='782c26c3ba9bee07a8b0b464898fb963a76eb35a2916586b854f8f45993f4166'
plain=decode(boot,block_bytes=512)[:3672];assert sum(struct.unpack('<14I',plain[:56]))&0xffffffff==0xffffffff
assert (sum(struct.unpack('<904I',plain[56:]))+0x1264aa7d)&0xffffffff==0xffffffff
param=archive('param_captures');slots=[];names=set()
for target in (NorTarget.param0,NorTarget.param1):
 chunks=[]
 for block in range(8):
  results=[checked_read(MemoryPath(param,f'{target.value}-block-{block}-{side}'),block,image=image,target=target) for side in ('a','b')]
  assert results[0][0]==results[1][0];new=set(results[0][1]+results[1][1]);assert len(new)==4 and not names&new;names.update(new);chunks.append(results[0][0])
 raw=b''.join(chunks);assert raw==Path(paths[target.value+'_raw']).read_bytes();slots.append(raw)
inspect_slots(*slots)
rec=archive('recovery_captures');tail={};names=set()
for block in range(93,124):
 results=[checked_read(MemoryPath(rec,f'block-{block:03}-{side}'),block,image=image) for side in ('a','b')]
 assert results[0][0]==results[1][0];new=set(results[0][1]+results[1][1]);assert len(new)==4 and not names&new;names.update(new);tail[block]=results[0][0]
prefix=Path(paths['recovery_prefix']).read_bytes();rec_manifest=json.loads(Path(paths['recovery_manifest']).read_bytes())
assert len(prefix)==48128 and sha(prefix)==rec_manifest['raw_sha256']
for item in rec_manifest['blocks']:assert sha(prefix[item['index']*512:(item['index']+1)*512])==item['sha256']
assert prefix[-512:]==tail[93]
full=prefix+b''.join(tail[i] for i in range(94,124));recovery_raw=Path(paths['recovery_raw']).read_bytes();assert len(full)==63488 and full[:63288]==recovery_raw
recovery_verify(recovery_raw)
for key,offset in [('recovery_head_windows',0x4000),('recovery_block1_windows',0x4200),('system_header_windows',0x24000)]:
 found=False
 for (_target,actual),members in groups(archive(key)).items():
  if actual!=offset:continue
  proof=nor_windows.analyze(members);assert proof['complete'];data=bytes.fromhex(proof['sector_hex']);found=True
  assert data==(recovery_raw[offset-0x4000:offset-0x4000+512] if offset<0x24000 else Path(paths['system_header_raw']).read_bytes())
 assert found
proof=nor_windows.analyze(loose['dsp_directory']);assert not proof['conflicts'] and proof['confirmed_rows']==17
rows=proof['rows'];assert [int(r['offset'],16) for r in rows]==list(range(0,272,16)) and all(len(r['variants'])==1 and r['variants'][0]['sources']>=2 for r in rows)
directory_raw=b''.join(bytes.fromhex(r['variants'][0]['hex']) for r in rows);directory=parse_directory(directory_raw)
dsp=Path(paths['dsp_raw']).read_bytes();blocks=json.loads(Path(paths['dsp_manifest']).read_bytes())['blocks']
assert len(dsp)==110148 and inspect_image(dsp)['bytes']==110148
entry=next(v for v in directory['files'] if v['name']=='aerecord.dsp');assert entry['absolute_offset']==0x24d400 and entry['size']==len(dsp) and int(entry['checksum_word'],16)==checksum32(dsp)==0x96d685bb
for block in range(215):assert sha(dsp[block*512:(block+1)*512])==blocks[block]['sha256'] and int(blocks[block]['nor_offset'],16)==0x24d400+block*512
for block in range(3):
 proof=nor_windows.analyze(loose[f'dsp_block{block}']);assert proof['complete'] and proof['offset']==0x24d400+block*512 and bytes.fromhex(proof['sector_hex'])==dsp[block*512:(block+1)*512]
assert not Path('artifacts/record-dsp-export').exists() and not Path('artifacts/factory-rw-2026-10-13').exists()
# Missing recovery blocks2..92 have raw/block manifests, not retained producer inputs.
assert set(range(93,124))=={int(n.split('/')[0].split('-')[1]) for n in rec}
boot1=J.replay(Path('artifacts/final-boot-sector-20261014'),Path('artifacts/mapped-system-20261012.bin'));assert boot1['partition_bytes']==4096
system=P.replay(Path('artifacts/system24200-20261014'),Path('artifacts/mapped-system-20261012.bin'));assert system['bytes']==512
latest=json.loads(Path(paths['system24200_report']).read_bytes());assert latest['after']['device']['free_capacity']==59589
assert latest['operations'][1]['download_sha256']=='96a615b8f0e4d8e115fed262e2b4afa1684839194a7a0417394295342e49ef9c'
loaded=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];snapshot={(manifest_path.parent/x['path']).resolve() for x in manifest['source_files']};assert all(p in snapshot for p in loaded)
assert {p:sha(Path(p).read_bytes()) for p in before}==before
# Publish only the actual200 archived bytes after full original paired512 audit.
sector=tail[123];assert len(sector)==512 and sector==rec['block-123-a/sector.bin']==rec['block-123-b/sector.bin']
extra=sector[312:];assert len(extra)==200 and extra==full[63288:]
public=Path('docs/evidence/nor-backup-coverage-2026-10-14/recovery-tail-0x13738-0x13800.bin')
assert public.read_bytes()==extra
catalog={key:{'file':name,'bytes':Path(name).stat().st_size,'sha256':sha(Path(name).read_bytes())} for key,name in paths.items()}
catalog['recovery_extra']={'file':str(public),'bytes':200,'sha256':sha(extra)}
slices={
 'recovery_head':{'range':[0x4000,0x4400],'sha256':sha(full[:1024])},
 'recovery_middle':{'range':[0x4400,0xfa00],'sha256':sha(full[1024:47616])},
 'recovery_tail':{'range':[0xfa00,0x13800],'sha256':sha(full[47616:])},
 'dsp_head':{'range':[0x24d400,0x24da00],'sha256':sha(dsp[:1536])},
 'dsp_rest':{'range':[0x24da00,0x268244],'sha256':sha(dsp[1536:])},
}

ledger=json.loads(Path('docs/evidence/nor-backup-coverage-2026-10-14.json').read_bytes())
for ref in list(ledger['source_catalog'].values())+ledger['loose_original_inputs']:
 raw=Path(ref['file']).read_bytes();assert len(raw)==ref['bytes'] and sha(raw)==ref['sha256']
for record in ledger['records']:
 assert record['bytes']==record['range'][1]-record['range'][0]
 if record['tier']=='C':
  assert not record['data'] and record['raw_sha256'] is None;continue
 pieces=[]
 for ref in record['data']:
  if ref['format']=='binary':raw=Path(ref['file']).read_bytes()[ref['file_offset']:ref['file_offset']+ref['bytes']]
  else:
   assert ref['format']=='json_hex_rows' and ref['file_offset'] is None
   rows=json.loads(Path(ref['file']).read_bytes())['rows']
   assert [int(r['offset'],16) for r in rows]==list(range(0,272,16))
   assert all(len(r['variants'])==1 and r['variants'][0]['sources']>=2 for r in rows)
   raw=b''.join(bytes.fromhex(r['variants'][0]['hex']) for r in rows)
  assert len(raw)==ref['bytes'] and sha(raw)==ref['sha256'];pieces.append(raw)
 raw=b''.join(pieces);assert len(raw)==record['bytes'] and sha(raw)==record['raw_sha256']
def union(tiers):
 merged=[]
 for start,end in sorted(r['range'] for r in ledger['records'] if r['tier'] in tiers):
  if merged and start<=merged[-1][1]:merged[-1][1]=max(end,merged[-1][1])
  else:merged.append([start,end])
 return merged
def holes(ranges):
 result=[];position=0
 for start,end in ranges:
  if start>position:result.append([position,start])
  position=end
 if position<0x400000:result.append([position,0x400000])
 return result
for tiers,key,expected,pages,holekey in [('A','tier_A_current_full_source_replay_union',36112,70,'holes_after_A_only'),('AB','potential_assemblable_union',191316,373,'holes_after_A_plus_B')]:
 ranges=union(tiers);assert ranges==ledger[key] and sum(b-a for a,b in ranges)==expected
 assert sum(max(0,b//512-(a+511)//512) for a,b in ranges)==pages
 assert holes(ranges)==ledger[holekey]
assert sum(r['bytes'] for r in ledger['records'] if r['tier']=='C')==8636
assert ledger['inventory_cutoff']['job']=='system24200' and ledger['inventory_cutoff']['later_trials_excluded']
assert {p:sha(Path(p).read_bytes()) for p in before}==before
print('PASS: A36112, B155204, available191316, C8636; original sources unchanged; actual200-byte tail verified')
PY
```
