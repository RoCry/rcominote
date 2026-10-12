# Actual CoMi Bluetooth OTA wire contract

2026-10-12. Static audit of validated FW010004 mapped application. No OTA
subscription, device traffic, code execution, reset, erase, or programming.

**F5F0 OTA is a device-pull image transport:** device requests ranges of a host
image; host supplies those bytes. The complete five-entry receive dispatcher
contains no firmware export opcode. This route can support a future updater,
but does not provide a backup of installed Flash. Package acceptance and
[actual version policy](ota-version-policy.md) remain separate contracts.

## Reproduce and scope

```sh
uv run tools/inspect_ota_wire.py artifacts/mapped-system/mapped-system.bin \
  > /tmp/comi-ota-wire.json
cmp /tmp/comi-ota-wire.json docs/evidence/ota-wire-2026-10-12.json
```

Input 927,632 B, SHA-256
`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`.
Tool rejects other images. [Evidence](evidence/ota-wire-2026-10-12.json) retains
command-table bytes, complete dispatcher/handler instruction intervals, region
hashes, and literal references. Analysis uses Capstone 5.0.6 Thumb MCLASS;
literal pools are excluded. This is mapped application evidence, not raw Flash.

[F5F0 definition](f5f0-firmware-definition.md) establishes F5F1 host writes,
F5F2 device notifications, and subscription's application upgrade-state side
effect. Byte stream callbacks buffer BLE/SPP fragments; a BLE notification or
write need not equal one protocol command.

Pinned comparison source:
[`ota_backend_bt.c`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/ota_backend_bt.c).
Names below use that source where actual instructions independently agree.

## Framing and complete receive dispatch

Packed five-byte service header: `09 CMD 80 LEN_LO LEN_HI`. Length covers body
only. Control TLV: `TYPE LEN_LO LEN_HI VALUE`; integers little-endian. No Boyi
`e5e*` framing or CRC16 is present in this dispatcher.

Actual sender `10063c80..10063cc4` stores service 09, main type 80 and body
length at unaligned +3. `100642c8..100643b0` requires idle state, reads exactly
five bytes, validates 09/80, then scans all five entries. Table RAM `18001ccc`
is initialized from image `100df1cc`:

| Host opcode | Actual Thumb handler | Body / effect |
|---|---|---|
| 01 | `10063cd1` | Upgrade request; TLVs 09 feature byte, 0a OTA type u32; other TLVs skipped |
| 02 | `10063e4d` | Connection negotiation; nominal empty request; nonzero length logged |
| 09 | `10063b59` | Negotiation result; TLV01 byte read, then negotiation_done=1 |
| 04 | `100b14a3` → `10064018` | Raw image-data body: PSN byte, data |
| 0b | `100b149d` → `10064018` | Raw image-data body: PSN byte, CRC32 u32, data |

04/0b bodies are **not TLV encoded**. The dispatcher has no inbound 03, 05,
06, 07, 08, or 0a handler. In particular SDK enum names `CANCEL_UPGRADE` and
`REPORT_STATUS` do not establish implemented inbound commands. Unknown opcodes
fall through with return 0, without consuming the declared body; this is not
an extensible command endpoint.

## Device messages and transfer direction

| Device opcode | Actual sender | Body |
|---|---|---|
| 01 | `10063cd0` | TLV7f u32 status 100000 success / 100010 OTA-type rejection; TLV04 byte 30 battery threshold; if host_features nonzero, TLV09 byte01 CRC capability |
| 02 | `10063e4c` | TLV01 u16=3 app wait timeout; TLV02 u16=5 restart timeout; TLV03 u16 negotiated unit size; TLV04 u16=0 interval; TLV05 byte0 ACK enable |
| 03 | `10063f10` | TLV01 u32 image offset; TLV02 u32 requested length; TLV03 byte0 read mask |
| 06 | `1006419c` | TLV01 byte validity (`is_valid != 0`) |

03 starts a host-image read. It stores caller-provided destination RAM pointer,
length, image offset, zero counters, and last PSN ff; emits the request via the
stream sender. Backend API RAM `18001cac` / image `100df1ac` routes `.read` to
`100643e1`, `.read_prepare` to `10063fb5`, `.read_complete` to `100644c9`.
`.read` calls 03 sender, dispatches host replies until its receive counter equals
the requested size, and can retry once after dropping buffered RX for 500 ms.
The host receives a request for image contents it already owns; offset is not
an arbitrary device memory/NOR address.

04/0b handler checks a non-NULL destination, nonzero requested length and nonzero
body length. PSN must increment by one modulo 256, starting at 00 for each 03
request. It reads at most the remaining requested bytes into that destination,
checks optional CRC32 over this segment, and rejects remaining body bytes.
Success updates both byte counters and PSN. CRC field is read little-endian;
actual CRC routine `1002db10` complements seed and result and uses a reflected
nibble table; caller uses zero seed. No live packet capture or updater execution
has yet verified this protocol.

## Differences from pinned SDK that matter

Actual table and framing agree with the SDK. Copying its current implementation
unchanged would nevertheless import assumptions absent from CoMi:

- Actual 01 always resets feature/type fields and responds; 02 always responds;
  09 always sets negotiation_done. SDK's repeated-negotiation guards are absent.
  09 reads/logs its result byte but does not require that byte to mean success.
- Actual image-data handler omits SDK's explicit 4 KiB destination-length guard
  and does not drain the stream on invalid NULL/zero input. Client must obey
  requested ranges and exact lengths; no malformed-packet experiment was run.
- Actual ioctl handles only `10001..10004`. Its max-size branch computes
  `unit_size × 60` when unit_size ≤230; SDK uses 50 and includes additional
  `GET_CONNECT_TYPE` / `EXECUTE_EXIT` branches.
- Actual synchronous read retry lacks SDK's connection-type guard. Neither a
  second read request nor reconnect can be treated as proof of update recovery.

Connection callback `100638e4` chooses SPP unit650; BLE uses MTU−15 when
100≤MTU≤230, otherwise230; fallback unit256. This matches SDK arithmetic,
independently visible in actual instructions. Negotiation values are protocol
parameters, not measured timing or a demonstrated safe payload for this Mac.

## Next useful boundary

An offline host responder can now be built from a concrete wire grammar.
Enabling the OTA service remains an application state change, so no live updater
is added from this static audit. First tie accepted package format, image IDs,
partition selection, checksums, and interruption/recovery behavior to actual
code and a matching official package. The complete dispatcher excludes a direct
backup command only within this backend; other USB/ROM/storage paths remain
separate research routes.
