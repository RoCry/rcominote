# Actual CoMi OTA container acceptance gates

2026-10-12. Read-only static audit of verified FW010004 mapped application.
No OTA subscription, package transfer or Flash write. The installed application's
parser expects an **AOTA container with a fixed 1024-byte header**. Header CRC is always
checked on open; whole-body CRC is a separate conditional operation. These are
container integrity checks, not a demonstrated backup, restore or own-firmware
boot path.

## Source and reproduction

Pinned comparison:
[`ota_image.c`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_image.c),
[`ota_manifest.c`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_manifest.c).
Actual instruction behavior below independently matches those relevant paths;
source structure alone is not treated as target validation.

```sh
uv run tools/inspect_ota_container.py artifacts/mapped-system/mapped-system.bin \
  > /tmp/comi-ota-container.json
cmp /tmp/comi-ota-container.json docs/evidence/ota-container-2026-10-12.json
```

Tool rejects any image except 927632 B, SHA-256
`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`.
[Evidence](evidence/ota-container-2026-10-12.json) retains bounded instruction
ranges, hashes and literal references, excluding literal pools from decoding.

## Layout versus enforcement

All integer fields below little-endian. Header table from pinned SDK layout;
“actual use” names the independently observed target consumer. Header location
and physical NOR location are different address spaces.

| Container offset | Size | Field | Actual use in audited paths |
|---|---:|---|---|
| 00 | 4 | magic `0x41544f41`, bytes `AOTA` | Required by `10066f46..10066f4c` |
| 04 | 4 | header checksum | CRC32 of bytes `[8,0x400)` must equal this value; computed `ffffffff` rejected |
| 08 | 2 | header_version | No check in complete header-open/check routines |
| 0a | 2 | header_size | Required `0x400` by `10066f62..10066f68` |
| 0c | 2 | file_cnt | Directory lookup iterates this count; no `<=16` check in audited open/check/lookup |
| 0e | 2 | flag | No check in audited header-open/check routines |
| 10 | 2 | dir_offset | Open copies directory from fixed `0x200`; this field does not select its location |
| 12 | 2 | data_offset | Start of conditional body CRC |
| 14 | 4 | data_size | End of conditional body CRC; also returned for NULL filename image-length query |
| 18 | 4 | data_checksum | Conditional body CRC expected value |
| 1c | 4 | reserved | Covered by header CRC, otherwise unused here |
| 40 | 0x60 | SDK new-version struct | Covered by header CRC; not consumed by these checks |
| a0 | 0x60 | SDK old-version struct | Covered by header CRC; not consumed by these checks |
| 200 | 0x200 | 16 fixed directory entries | Copied into image state on open |

Do not infer the version blocks' producer encoding or policy from this C struct.
The upgrade path reads its board/version and partitions from `ota.xml`; see
[version policy](ota-version-policy.md). An independent offline inspector should
retain raw header-version bytes and parse the actual XML, rather than treat a
struct declaration as evidence of producer layout.

Each directory entry occupies32 B: filename12 B at+0, reserved4 at+0c,
container-relative offset u32 at+10, length u32 at+14, reserved4 at+18,
CRC32 u32 at+1c. Lookup `10066b20..10066b98` compares at most12 filename bytes,
walks entries in32 B steps and trusts file_cnt. Offset/length getters
`10066ba8` / `10066c0c` return stored fields without verifying range or overlap.
This audit found no offset+length overflow, file-boundary, duplicate-name,
NUL-termination, directory-count or total-file-length gate in those routines.
Host tooling must reject these malformed conditions independently; absence of a
target check does not justify sending malformed packages.

## Actual open and checksum sequence

`10066ffc..100670e8` opens the selected backend, allocates1024 B, reads exactly
container offset0 length1024 through `100b155c`, then calls header checker
`10066f1c`. The complete checker validates only non-NULL image/backend, magic,
header_size and header CRC. CRC routine `1002db10` is the reflected standard
CRC32 implementation already traced for [OTA transport](ota-wire-contract.md),
with seed0 and complemented entry/exit state. Caller passes header+8, length1016.

After success, open copies32 B header into image state+4 and512 B directory
from container+512 into state+0x24. It frees the temporary header and returns0.
It does **not** call body CRC. Read/check failure frees temporary memory, closes
the backend, clears its pointer and returns the error. Allocation failure returns
`-ENOMEM` without the shared close cleanup; no allocation-failure experiment run.

Whole-body checker `10066e3c..10066ef6` reads `[data_offset,data_size)` in chunks
up to2048 B and chains CRC32. Read error resets calculated CRC to0. Result0 or
mismatch is rejected, including otherwise equal expected0. The routine does not
first establish `data_size>=data_offset` or package bounds. All offsets refer to
host-provided container data through the backend; this is not installed-Flash
readback.

## Which checks the actual application calls

Upgrade entry `1006635c` checks idle state and an available backend, opens the
image at `100663ae`, then at `100663ca..100663ce` tests internal state+8 bit1.
Only a set bit calls whole-body checker at `100663d2`; a clear bit branches
straight to manifest processing.

Actual initializer clears state at `10066a18..10066a20`. Flag-copy path
`10066a68..10066a98` copies input bit0 to recovery flag and input bit1 to internal
bit1, requiring bit0 if bit1 is set. The application passes input0d, whose bit1
is clear. Thus **this application's inspected initialization/check path skips
whole-body CRC before manifest parsing**. No runtime flags snapshot or later
recovery-stage validation was observed; this does not prove that the complete
upgrade skips data integrity checks.

Manifest path starts at `100663ec`, explicitly selects `ota.xml`, and calls
`100677e0`. The latter reads its directory length (requires signed length<2048),
locates its offset, allocates length+1, reads bytes, calls manifest checker,
then parses XML and checks listed file lengths against directory lengths.
Manifest checker `10067700..10067768` requires leading `<?xml`, then calls
`10066dc4`: CRC32 of the supplied manifest bytes must equal directory entry+1c.
The helper itself accepts a caller-provided buffer size; it does not compare that
size to the entry length. Its manifest caller obtains size from that entry.

These gates occur before the board/version decision in this upgrade entry.
Audited instruction ranges do not establish every later storage-side effect,
payload CRC, decompression/signature check, erase ordering or recovery acceptance.
In particular, the manifest-buffer checksum helper is not proof that every
payload has been checked before any Flash modification. Trace the storage/write
path and recovery image separately before attempting an update.

## Consequence for next work

A useful offline package inspector can now validate fixed header layout,
standard CRC32, all directory bounds and per-file CRCs more strictly than these
loader routines. Match `ota.xml` files to directory entries and report board,
version, file IDs, sizes and checksums. Its success means an internally consistent
container, not electrical compatibility, target acceptance, safe interruption or
a verified restore. The matching official CoMi OTA/production package remains
the needed reference for update/restore experiments.

Initialization is also outside a no-write claim: actual initializer
`10066a9e..10066aa0` calls `100655bc` before image-object initialization.
The corresponding SDK preparation path can erase partitions or save breakpoints.
Its complete actual side effects are unaudited here. A future client must not
assume that merely entering update mode or rejecting a package is storage-neutral.
