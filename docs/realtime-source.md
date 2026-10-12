# Realtime recording transport: actual e5e3 route

2026-10-12. Offline actual FW010004 and shipped CoMi1.1.2 JavaScript; no device I/O. [Exact bytes/instructions/slices](evidence/realtime-source-2026-10-12.json).

**The recording ring consumer's channel1 maps to the actual e5e3 notify attribute.** This closes the backend gap in [recorder-stream-path.md](recorder-stream-path.md). The official app subscribes during connection and forwards notifications unchanged. Actual delivery and codec remain live-verification questions.

## Actual firmware chain

Mapped-system927632 B, base`10000000`, SHA256`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`. RAM initializers below use [proved startup copy](startup-memory-readback.md): `image = RAM − 18000000 + 100dd500`.

| Step | Actual evidence |
|---|---|
| Context producer | Getter`1000a1b0` returns global`1800a96c`. Initializer`1000a1bc..1000a264` allocates context178 hex B; factory return stored context+150 at`1000a1e2`. |
| Stream factory | `1000a87c` passes parameters`100ba978` and ops`100ba9b8` to generic creator`100513d4`. Ops initializer=`1000a6e9`; extended write at ops+20=`1009ebf9`, both Thumb pointers. |
| Pointer bindings | Initializer`1000a7c6..d0` copies parameter+18/+1c into private+20/+24. Actual parameter values at`100ba990/994` are RAM attributes`180017c4/180017d8`. |
| Async writer | Consumer`1000de1e..36` loads context+150 stream and calls`10051980` with r3=1. This is channel selection, preserved by extended write. |
| Dispatch | `100519e6..f4` calls stream.ops+20 with original r3. Handler`1009ebf8..1009ec38` forwards r3 to`1009eb16`. |
| Channel1 | `1009ebaa..c2` selects private+20/+24, passes buffer slice and length to`1006bfc8`. No command header/CRC added here. |
| Attribute identity | `180017d8` value attribute UUID pointer=`18002564`; mapped initializer bytes=`00 00 e3 e5`, UUID type16/valuee5e3. Declaration`180017c4` userdata=`1800172c`; its properties byte+6=`10` (notify). |
| Notify helper | `1006c024..42` tests declaration properties bit10 and calls`100b241e` with connection, value attribute, buffer slice, length. Other branches support indication/error. This report does not audit callee internals or claim radio delivery. |

`1009eb16` clips chunks first to512 B, then to `u16(manager_getter−3)` before invoking transport. Thus capture ring chunks and BLE notifications need not share boundaries. The async consumer's larger `u16((getter−3)*2)` read size does not imply one notification contains twice the ATT payload. No byte prefix, sequence counter or checksum is added by these audited send routines; earlier capture encoding and lower transport remain separate layers.

Realtime CCC callback=`1000a471`, installed by`1000a81e..20` into CCC userdata+2c. It inserts CCC value into private flags bits1..2 (`1000a4b6`). Writer checks private flag bit0 plus mask6 before sending (`1009eb2e..3a`), with additional connection/resource checks in the transport helper. These are observed shared-state gates, not proof of per-channel subscription isolation or successful send. The recording ring consumer's runtime flag/NULL target gates and enqueue-before-file-write behavior remain as previously documented.

## Official app behavior

APK member`assets/public/assets/index-Btih_BUR.js`,588988 B, SHA256`167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c`. Byte ranges zero-based/end exclusive.

| Range | Observation |
|---|---|
| `[223361,223943)` | Boyi connection opens BLE, discovers required write+command characteristics, then immediately calls setupNotifications. |
| `[225371,226223)` | Command notification first; realtime notification when characteristic discovered; offline notification next. No recording-state condition or separate enable opcode in this method. |
| `[236151,236691)` | startRecording sends START_RECORDING06 without payload; checks parsed response status/name. No e5e3 subscription or stream-start command here. |
| `[230463,230647)` | handleRealtimeData logs length and emits `{type:"realtime_data",data:e}`. No header stripping, CRC, decryption, decoding or packet reorder. |
| `[389925,389998)` | Pw forwards the same data to app event bus `nc.emit("realtime_data",n.data)`. |

Connection subscription is independent of an active recording; this does not establish whether enabling notifications can itself alter device state. No packet codec can be inferred from this byte-forwarding handler. In particular, firmware `opus_ringbuf` naming is insufficient: [actual encoding dispatch](recorder-codec-dispatch.md) selects the MP3-labelled hardware/DSP path for the inspected format1 configuration. Compare captured output with an independently recognized downloaded recording before advertising a realtime decoder.

## Short live proof needed

1. Preserve command/event channel while explicitly subscribing e5e3; bounded idle observation records whether audio appears without recording.
2. Start one short recording, save every notification's raw bytes, order, length and receipt timestamp; stop and retain stop reply/file identity.
3. Download that exact file through existing verified offline route. Compare concatenated realtime bytes against file bytes, retaining any prefix/suffix omissions or mismatch instead of assuming equality.
4. Use an independent audio/frame tool on both artifacts. A few matching bytes or an `opus` label do not prove codec, continuous stream, completeness, timing, or decoded audio.

This static result proves a transport route for the inspected configuration. It does not prove a complete realtime client, data delivery while paused/disconnected, packet-loss recovery, or all recording modes.
