# Fresh v3 NOR0x24a00 pair succeeds; original v2 failure preserved

New fixed v3 trial **succeeded**, independently recovering identical512 raw bytes at **`[0x24a00,0x24c00)`**, SHA256 **`6234e0aaaa13bbf929045308e789ad7b1a991cda8e99c3652ff6d07304ebdb9f`**. Two fresh nonces/producers, two existing-file SD overwrites and complete transport/state/disconnect proof establish **512 new raw bytes**. No independent content oracle or mapped selection. Original four-page v2 job/failed24a00 candidate remain failed; its candidate is not recovered or promoted by this new policy.

[Frozen receipt](evidence/paired-nor24a00-v3-live-2026-10-14.json) · [actual independently paired raw512](evidence/paired-nor24a00-v3-live-2026-10-14/nor24a00.bin) · [original failed v2 job](paired-nor-system4-live-2026-10-14.md) · [prior24400 success](paired-nor24400-live-2026-10-14.md) · [unchanged as-of24200 inventory](nor-backup-coverage-2026-10-14.md).

The separate **offline communication checkpoint contributes0 raw NOR bytes and performs0 device I/O**. Its SHA256 `fb81e584b319d614c1713682f4711720771e211f69af18967dc452894d0b58ea` binds the original failed first actual4096 download `4c5e92d9…dd4ae96`, complete6-transaction wire/state proof, original strict-v2 source249-entry snapshot, exact two completed-prefix pairs and actual final59589 state. Created08:47:37.027145Z from observed failed-job end07:53:40.181319Z; all original failure flagsfalse, no `ok` field, original strict content rejection reproduced. Failed whole-job success/parent replay still rejects. New runtime must first download and byte-compare its actual current owned file against checkpoint; new baseline does exactly that.

| New actual stage | Proof |
|---|---|
| Read-only baseline | Full4096 exactly equals failedfirst/checkpoint `4c5e…ae96`; real host6/EOF SLOW/identity |
| First fresh24a00 producer |6ACK/F1/pending0/F0=0; full4096 transfer, actual FAST/host6/EOF SLOW/identity; v3 accepts only one known address-padding exemption |
| Second fresh24a00 producer | Separate nonce/producer; predecessor is first actual4096; full transfer and whole critical chain inside3872-byte proven prefix, no exemption |
| Pair acceptance | Both independently parsed512 outputs equal after9 complete transactions, full GATT/ATT/HCI, final identity and normal disconnect |

Baseline4096 SHA256 `4c5e92d95b936c73b2cf3e4e08050d051461273ca523494aa2f048a78dd4ae96`; first `58dca7949bb66db67c2092e966552600fa63e10a0a7cb5c1d01e2b497fa2674c`; second/latest owned file **`6249cf346719e093304b4f8076103822304810022dc29a9bfeff6f4e2062258a`**. Both nonces distinct from all16 prior planned names and absent from actual baseline; second nonce absent from actual first ring. Successful new parent retains18 names. Zero new device files/deletions; host-only checkpoint baseline copy is not a new device file.

**Complete4096 download is not proof of full4096 overwrite.** Original contiguous offset0 write model yields these lower bounds:

| New producer | Difference-proven prefix | Allowed unproven critical bytes | Data proof |
|---|---:|---|---|
| First |4095|Physical4095, row30/column2, previous/current=`20`|Only deterministic leading space of canonical row-relative address `1e0` in width8; all other critical bytes proved |
| Second |3872|None|All nonce/status/32rows/producer/current-dump bytes lie below3872 |

v3 requires explicit immutable policy `canonical-row-address-leading-spaces-only-v3`; only row0..31 address-leading columns before its known hex offset may be exempt. Value high spaces, hex digits, delimiters, CRLF, nonce/status/producer/dump bytes remain strict data evidence. Proof preserves actual lower bound, records each exemption, and states `critical_nonpadding_chain_inside_written_prefix`; it never reports all4096 written. First new read still fails strict-v2 parser; second independently passes strict parser without exemption. Identical trailing spaces do not establish an actual short write or definitive cause. Root separately reports a host-only format diagnostic on archived failed24a00 using the new rule: physical4095/row28/column0 only,512 returned transiently in process. That diagnostic never accepts, publishes, counts or codec-compares the original candidate; strict original rejection remains reproduced and failed. This review accepts only the new two-producer acquisition.

First physical chain: nonce `[2162,2207)`, status `[2241,2287)`, rows `[2293,4213)` across4096 wrap, producer `[137,183)`, current dump `[204,285)`, no historical dump. Second: nonce `[1652,1697)`, status `[1731,1777)`, rows `[1783,3703)`, producer `[3723,3769)`, current dump `[3790,3871)`; first dump `[204,285)` remains historical before current nonce in anchored circle. Both nonce→status gaps exactlyLF+33-byte composer background; both producer→dump gaps exactlyLF+logging prefix (`composer_fps2=false` for that separate gap). All5 critical spans checked against each prefix/exemption set. No oracle selects a chain or supplies missing raw data.

Capture SHA256 `c65c9309c71760380a1f0d597d179ca63a9fbebec01269089ab2b8a11135ec61`:25141 bytes/316 HCI records/180 ATT. Full original GATT, exact host-wire binding within direction and disjoint complete ATT partition pass; status0/pending0. Exactly9 complete negotiations: startup FAST, then baseline host6/EOF SLOW, first FAST/host6/EOF SLOW, second FAST/host6/EOF SLOW. FAST6..12/0/500 applies12; host6/6/0/500 CE1/1 applies6; SLOW32..48/4/600 applies48. Downloads remain inside their completed host6 windows, EOF SLOW before each identity. Transfer durations180.865/190.806/197.595ms; DEFAULT not exercised.

First Actions HCI154..178 precedes FAST179; second229..253 precedes FAST254. Ordering does not establish unique firmware trigger; earlier identity could schedule delayed work. Final ATT312 precedes sole local normal disconnect315 status0/reason0x16. Passive observation2.167141s after close completion fits8s; monitor exits0 after SIGINT. Original ATT/disconnect timestamps fit declared page UTC interval. Both actual Actions streams individually contain6ACK/F1/pending0/**F0=0**, without uptime-body requirement; all original frames retained. Three stage checkpoints remain aggregatefalse until final original page/jobtrue.

Actual initial/baseline/first/second/final identities exactly equal required owned/unbound FW010004/NOTEidle/charging100/**free59589**. Each SD overwrite allows at most1MiB integer-report decrease and observes0; read-only barriers allow/observe0, not byte allocation measurement.1connection/3downloads/2NOR-read producers/2existing-file SD overwrites/0newfiles/0deletions; cohort70 confirmed+1 older declared+1 historical possible=max72. No firmware NOR write command attempted. Latest actual state/file observed at08:48:38Z, superseding failedfirst4c5e object.

Codec comparison remains postfacto observation, independent of raw acceptance. New pre-I/O hypothesis08:38:46.767158Z SHA `74b7ea903306869e9469415fbb9d6df3ecfbfdd3757b40ce8a95e92694d2b823` retains old predeclared system4 expectation SHA `3354440446426a95c34fe08001c5ed0f193312a0686e0f4c823fd3c7ab7dfafc`, which predates even original failed trial. Existing codec sourceSHA `81bad4b8eea615ff1198294f1f2540e9c6d9d1f36b572d3d0fadaacb1f278f3a`, effective state0x0a15a191/reset32 primary/reset512 secondary are unchanged. No algorithm/state/reset/mapping fitting.

| Fixed profile / mapped `[0xa00,0xc00)` | Decoded SHA256 | Match |
|---|---|---|
| Primary reset32 | `3067efa03b698560a6962e4adad9f62deb9db0c07fb1eb5b0aa9dccbb86ce391` |512/512 |
| Secondary reset512 | `776bcd63620d3f9f056c6140fda965c4bdc47d3d7f43ce4208d26cc29b0e507b` |33/512 |

Posthoc08:49:51.055033Z SHA `117f036e8b110d4e255140f1f68d8be1bb6d08c259a5705e53c8cb8591ba424d` independently reproduced; only new accepted raw compared. Corroborates fixed conversion on this page, not efuse key recovery/fullsystem raw checksum/boot/flash/restore ability. No decoded binary published.

Frozen138-source/114-test manifest SHA `d546d8dccdc58465a8c87d386852b87ecbe80632c62cf1e948bbee6b12cd9428`, created08:47:36.572757Z < checkpoint < plan08:47:37.478367Z < job08:48:02.483054Z. Page08:48:09.900966Z–08:48:38.370024Z; whole job ends08:48:38.376738Z. Manifest records root2062 tests+159 subtests/build; this review independently verifies all252 archived lengths/hashes and complete source/wire chain, not a new full-suite execution. All96 imported project modules resolve to frozen snapshot. Root's95-module saved replay08:50:36.146470Z SHA `d40bd3f42a154d4bbf91c52f5cc74333d3152deb329751f844f890d7258dc1b8` agrees and preserves original v2 failure.1950 explicit original inputs hash-identical before/after; old immutable receipts/inventory remain unchanged. Future/current source equality not claimed.

Only actual paired512 is copied publicly after complete replay; raw rings/HCI/identity/inventory/nonces remain private. New overlay adds512 to prior strong37648/potential192852 → **strong38160/potential193364**; B historical-only provenance unchanged. System raw `[0x24000,0x24c00)`3072B; first4KiB still lacks24c00/24e00. Frozen as-of24200 inventory is not rewritten. No further I/O or address expansion occurred here; future24c/e requires a separate fixed plan. Full4MiB backup, validated restoration and own runtime remain incomplete.

Exact offline reproduction from repository root; reads private originals/published512 only, no device access/file writes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=artifacts/paired-nor24a00-v3-20261014/source-snapshot/src uv run python - <<'PY'
import hashlib,json,sys
from pathlib import Path
from rcominote.experiments import paired_nor_audit as A
from rcominote.nor_codec import decode
root=Path('artifacts/paired-nor24a00-v3-20261014');image=Path('artifacts/mapped-system-20261012.bin');sha=lambda b:hashlib.sha256(b).hexdigest()
receipt=json.loads(Path('docs/evidence/paired-nor24a00-v3-live-2026-10-14.json').read_bytes());job=json.loads((root/'report.json').read_bytes());plan=json.loads(A.J.check_reference(root,job['plan']).read_bytes());page=root/plan['pages'][0]['directory'];report=json.loads((page/'report.json').read_bytes())
manifest_path=root/'source-snapshot/manifest.json';manifest=json.loads(manifest_path.read_bytes());assert sha(manifest_path.read_bytes())=='d546d8dccdc58465a8c87d386852b87ecbe80632c62cf1e948bbee6b12cd9428'
assert len(manifest['source_files'])==138 and len(manifest['test_files'])==114
checked={}
for item in manifest['source_files']+manifest['test_files']:
 p=manifest_path.parent/item['path'];raw=p.read_bytes();assert len(raw)==item['bytes'] and sha(raw)==item['sha256'];checked[p.resolve()]=sha(raw)
def refs(v):
 if isinstance(v,dict):
  if {'file','bytes','sha256'}<=v.keys():
   p=Path(v['file']);raw=p.read_bytes();assert len(raw)==v['bytes'] and sha(raw)==v['sha256'];checked[p.resolve()]=sha(raw)
  for x in v.values():refs(x)
 elif isinstance(v,list):
  for x in v:refs(x)
refs(receipt)
baseline,state,parent=A.C.parent_gate(Path(plan['parent']['directory']),image);assert parent==plan['parent'] and parent['verification']['new_raw_nor_coverage_bytes']==0
proof=A.replay(root,image);assert job['ok'] is True and proof==job['verification'] and proof['paired_bytes']==512 and proof['independent_oracle'] is False
current,latest,admitted=A.C.parent_gate(root,image);assert sha(current)=='6249cf346719e093304b4f8076103822304810022dc29a9bfeff6f4e2062258a' and latest['device']['free_capacity']==59589 and len(admitted['prior_names'])==18
checkpoint=json.loads(Path(receipt['offline_checkpoint']['checkpoint']['file']).read_bytes());assert checkpoint['new_raw_nor_coverage_bytes']==0 and checkpoint['original_job_ok'] is False and 'ok' not in checkpoint
old=Path(checkpoint['failed']['directory'])
for gate in (A.replay,A.C.parent_gate):
 try:gate(old,image)
 except ValueError:pass
 else:raise AssertionError('Original failure promoted')
first,second=report['operations'];assert first['verification']['freshness']['difference_proven_written_prefix_bytes']==4095 and second['verification']['freshness']['difference_proven_written_prefix_bytes']==3872
assert first['verification']['freshness']['address_padding_exemptions']==[{'physical_index':4095,'row_index':30,'column':2,'current':'20','previous':'20'}] and second['verification']['freshness']['address_padding_exemptions']==[]
raw=Path(receipt['public_output']['actual_direct_copy']['file']).read_bytes();assert len(raw)==512 and sha(raw)=='6234e0aaaa13bbf929045308e789ad7b1a991cda8e99c3652ff6d07304ebdb9f' and raw==(page/'first/sector.bin').read_bytes()==(page/'second/sector.bin').read_bytes()
for op,saved in zip(report['operations'],receipt['operations'],strict=True):
 assert op['actions_verification']==saved['actions'] and op['actions_verification']['f0_frames']==0 and {k:v for k,v in op['verification']['freshness'].items() if k!='nonce'}==saved['freshness']
mapped=image.read_bytes()[2560:3072];profiles=receipt['codec_observation']['profiles']
for reset,saved in zip((32,512),profiles,strict=True):
 decoded=decode(raw,block_bytes=reset);assert sha(decoded)==saved['decoded_sha256'] and sum(a==b for a,b in zip(decoded,mapped,strict=True))==saved['mapped_bytes_equal']
assert [p['mapped_bytes_equal'] for p in profiles]==[512,33]
origins=[Path(m.__file__).resolve() for n,m in sys.modules.items() if n.startswith('rcominote') and getattr(m,'__file__',None)];source_paths={(manifest_path.parent/e['path']).resolve() for e in manifest['source_files']};assert all(p in source_paths for p in origins)
assert {p:sha(p.read_bytes()) for p in checked}==checked
print('PASS frozen fullchain+pair512;checkpoint0;prefix4095/3872;originalfailedretained;59589;',len(checked),'pinned inputs unchanged')
PY
```
