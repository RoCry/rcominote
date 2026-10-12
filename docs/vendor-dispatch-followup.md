# Actual CoMi command dispatcher

2026-10-12. Owned-device mapped code, captured twice through the already verified
bounded log read path; offline Thumb decoding. Only existing status and NVRAM
getters were used alongside code reads. No newly discovered command was invoked;
no reset, storage write or flashing was performed for this analysis.

## Result

**`0x1000b3b4` contains a command dispatcher.** Its command table routes all 23
request identifiers declared by the official CoMi 1.1.2 Boyi JS to distinct
cases, plus an additional `0x3a` case using the actual `BT_NAME` string as a
helper argument. The latter appears to configure a Bluetooth name; exact
helper semantics and persistence remain unproven. This is
stronger evidence connecting actual recorder code to Boyi than a thread named
`vendor_read`. It still does not bind that thread to the F5F0 GATT service or
establish firmware readback/upgrade capability.

`0x1a` is the already documented backlight/always-on setter, not a newly
discovered opcode. `0x0f` and `0x19`, declared by the app as device-originated
status events, select the default case when presented to this dispatcher.

## Evidence identity and independent reconstruction

Final captures and analysis retained in the repository evidence directory:

| Capture | Timestamp UTC | SHA-256 |
|---|---|---|
| [First](evidence/vendor-handler-first-2026-10-12.json) | `2026-10-12T04:29:02.345074+00:00` | `f14bf4b8ea39d66311ac3beefbcc6ee1e65290d001229ca1f1da56e249d26f62` |
| [Second](evidence/vendor-handler-second-2026-10-12.json) | `2026-10-12T04:29:54.583727+00:00` | `4b6cc6f1fffa2e013c1537f878b25f38cd44924b54d85027e8949e115e23be7b` |

Independently checked every final read block against both raw captures using
the strict addressed-row reader; bytes matched. Contiguous dispatcher
acquisition: `[0x1000b3b4,0x1000b564)`, 432 B. The
[analysis](evidence/vendor-handler-analysis-2026-10-12.json) also contains
caller prerequisites, the `0x3a` body, its literal and helper prefix; its 580 B
scope is neither all executable code nor a firmware image.

Decode boundaries, end exclusive:

| Range | Interpretation |
|---|---|
| `[0x1000b3b4,0x1000b410)` | Prologue, preliminary gate, range check, TBB |
| `[0x1000b410,0x1000b44a)` | 58 one-byte TBB offsets; **data, not instructions** |
| `[0x1000b44a,0x1000b558)` | Case bodies, default, final NOP |
| `[0x1000b558,0x1000b564)` | Beginning of PC-relative literal pool; **data, not instructions** |

At entry `ldrb r7,[r0]` obtains the command byte. At `0x1000b404`,
`subs r3,r7,#1`; `cmp r3,#0x39`; unsigned `bhi.w 0x1000b544` rejects commands
outside `1..0x3a`, including zero. At `0x1000b40c`, `tbb [pc,r3]` uses base
`0x1000b410`. Command `c` branches to:

```text
0x1000b410 + 2 * table[c - 1]
```

Exact table bytes, 58 B:

```text
1d22272c31363b40454a4f555b9a9a61676c72777c81868b9a909a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a9a95
```

Capstone 5.0.6 independently decoded the explicit code spans. Each non-default
case below contains one direct BL followed by a branch to the shared epilogue
`0x1000b400`; handler return value is retained. Meaning column comes from the
official app's constant names, **not** decompilation of these target functions.

## Command-to-call map

At dispatcher entry, let `P` be incoming pointer and `N` its second argument.
The caller supplies `P=B+3` and `N=(payload_length+2)&0xff`; `P` therefore starts
at the Boyi command byte. Two observed argument forms:

- **A:** `r0=P`, `r1=N`.
- **B:** `r0=P+2`, `r1=(N-2)&0xff`; this points at the payload in the observed
  caller's frame layout. Explicit wrapping recovers the original unsigned
  payload length even when caller `payload_length+2` wrapped.

No extra contract, accepted length or side effect is established for these
target functions.

| Command | Official app name | Case address | Direct BL target | Args |
|---:|---|---|---|---|
| `01` | GET_SERIAL | `1000b44a` | `1000a94c` | A |
| `02` | GET_BIND_INFO | `1000b454` | `1009ed68` | A |
| `03` | BIND | `1000b45e` | `1000a978` | A |
| `04` | SET_TIME | `1000b468` | `1000aa60` | A |
| `05` | GET_DEVICE_INFO | `1000b472` | `1000aad0` | A |
| `06` | START_RECORDING | `1000b47c` | `1000abf4` | A |
| `07` | STOP_RECORDING | `1000b486` | `1000ac38` | A |
| `08` | PAUSE_RECORDING | `1000b490` | `1009edae` | A |
| `09` | RESUME_RECORDING | `1000b49a` | `1009edc2` | A |
| `0a` | GET_FILE_LIST | `1000b4a4` | `1000b328` | A |
| `0b` | GET_FILE_DATA | `1000b4ae` | `1009edd6` | B |
| `0c` | STOP_GET_FILE | `1000b4ba` | `1000b368` | B |
| `0d` | DELETE_FILE | `1000b4c6` | `1009ee42` | B |
| `10` | FORMAT_DEVICE | `1000b4d2` | `1000ad14` | B |
| `11` | SET_INDICATOR | `1000b4de` | `1000ad5c` | A |
| `12` | RESET | `1000b4e8` | `1009ee0e` | B |
| `13` | SET_USB_MODE | `1000b4f4` | `1000ada8` | A |
| `14` | SET_VOICE_CONTROL | `1000b4fe` | `1000ae14` | A |
| `15` | GET_RECORDING_INFO | `1000b508` | `1000ae54` | A |
| `16` | SET_SEGMENT_DURATION | `1000b512` | `1000af54` | A |
| `17` | SET_NOISE_REDUCTION | `1000b51c` | `1000af98` | A |
| `18` | SET_PHONE_TYPE | `1000b526` | `1000b000` | A |
| `1a` | SET_SCREEN_BACKLIGHT | `1000b530` | `1000b05c` | A |
| `3a` | Absent from app table; `BT_NAME` configuration candidate | `1000b53a` | `1000b0c0` | A |

`0e`, `0f`, `19`, and `1b..39` use table byte `9a`, branching to
`0x1000b544`. This default calls `0x10055f90` then executes `mvn r0,#0x85`,
returning signed `-134`. No symbolic error name is established. The table has
24 non-default command entries and 34 default entries.

Official source comparison: exact packaged JS SHA-256
`167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c`, byte range
`[217643,219336)` covering constants and frame builder; see
[CLI capability specification](cli-capabilities.md). No `0x3a` constant occurs
in that command table. That does not establish absence of other uses elsewhere
or by itself identify the extra command. Actual code evidence below narrows its
likely purpose independently of app constants.

## Extra command 0x3a: BT_NAME configuration candidate

Captured full 80 B function `[0x1000b0c0,0x1000b110)` and separate literal word
at `0x1000b110`. The code saves `(P,N)`, prepares a local buffer `S=sp+8`, and
performs these calls with explicitly observed arguments:

| Call site | Direct target | Arguments prepared by caller |
|---|---|---|
| `1000b0d0` | `100b96c8` | `(sp+12, 0, 28)`; caller also stores zero at `sp+8` |
| `1000b0dc` | `100b966e` | `(S, P+2, N-2, 32)` |
| `1000b0e2` | `10000cdc` | `(S)` |
| `1000b0ec` | `100ad3d6` | `(literal_100c22bb, S, previous_return+1)` |
| `1000b0fe` | `1000a888` | `(0x3a, pointer_to_one_byte, 1)` |

The final one-byte value is `00` when `0x100ad3d6` returns zero, `01` otherwise.
The original return value of that helper is returned by this `0x3a` body. This
establishes argument/result flow; the wire encoding of `0x1000a888` has not
been independently reconstructed here. The input-copy and length helpers are
also not yet named from their actual bodies.

Literal resolution is direct: `ldr r0,[pc,#0x24]` at `0x1000b0ea` reads the
word at `0x1000b110`, little-endian `bb220c10` → `0x100c22bb`. Sixteen bytes read
at that address are:

```text
42 54 5f 4e 41 4d 45 00 66 69 6c 65 5f 73 69 7a
B  T  _  N  A  M  E  \0 f  i  l  e  _  s  i  z
```

Only the NUL-terminated `BT_NAME` is an argument to this call; the adjacent
`file_siz` prefix does not describe this command. The helper prefix begins
`89f703bb`, decoded as `b.w 0x100369e0`. Bytes after that unconditional branch
belong to adjacent code, not necessarily the same function. This proves a
thunk target, not its API name.

**Inference:** payload-derived buffer, `BT_NAME` key, length-like return plus
one, and a zero/nonzero result reply strongly suggest a name configuration
operation. Pinned public SDK corroborates this shape:

- `framework/base/include/core/property_manager.h:31-32` defines `CFG_BT_NAME`
  as `"BT_NAME"`, `CFG_BLE_NAME` as `"BT_LE_NAME"`.
- `zephyr/include/drivers/nvram_config.h:22` declares
  `nvram_config_set(const char *name, const void *data, int len)`.
- `framework/bluetooth/bt_stack/src/bt_stack/property.c:364-376` has separate
  LE-name setter/getter using `CFG_BLE_NAME` and BR-name getter using
  `CFG_BT_NAME`.
- `framework/bluetooth/bt_service/core/btsrv_adapter.c:575-581`, under
  `CONFIG_BT_BR_ACTS`, reads `CFG_BT_NAME` into the BR device name.

SDK source revision: `26f51e584940d5b141cd1d09d2629d69b595f579`; fixed upstream
[property definitions](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/base/include/core/property_manager.h#L31),
[BR/LE accessors](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/bluetooth/bt_stack/src/bt_stack/property.c#L364).
API compatibility does not prove `0x100369e0` is that SDK function, its exact
revision, when a new name would take effect, or persistence behavior.

The owned recorder previously returned `BT_LE_NAME` = `CoMi Note 2F01` via the
independent read-only NVRAM diagnostic. A subsequent
[read-only query of both keys](evidence/vendor-bt-name-query-2026-10-12.json)
returned **14 B `CoMi Note 2F01` for each of `BT_NAME` and `BT_LE_NAME`**.
Equal current contents do not make them the same key or establish linked write
behavior. Do not describe `0x3a` as a confirmed BLE advertising-name setter or
infer it changes both values. No `0x3a` request or rename was sent.

## Preliminary gate and remaining uncertainty

Before the switch, `BL 0x1008ee58` at `0x1000b3d8` obtains a value compared with
`0x54`. Equality takes a separate path: store one byte `01` on the stack, call
`0x1000a888` with `(command, pointer_to_that_byte, 1)`, return zero. The callee
and returned state's meanings remain unknown. It is not yet justified to call
this busy detection, authentication, binding, update mode or a specific status
reply. A named response format would require the called code or independently
captured behavior.

No direct CRC comparison is visible in either the reconstructed receive loop
or this dispatcher's code spans. That observation does not prove CRC is ignored
throughout the device: helpers, transport or individual handlers are not yet
fully analyzed. The now-confirmed switch establishes command dispatch, resolving
the earlier uncertainty whether `0x1000b3b4` was merely a CRC routine.

Next bounded code evidence: actual helper behind `0x100369e0`, and/or
device-info target `0x1000aad0` for concrete identity/response construction.
Unknown commands remain unexecuted. A new case address alone provides no backup,
flash, partition-map or independent recovery capability.
