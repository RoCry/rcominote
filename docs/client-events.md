# Boyi unsolicited events

Implemented 2026-10-12. No device I/O during implementation; source semantics and
replayed transport behavior are distinct from live device proof.

```sh
uv run comi watch --duration 5
uv run comi watch --duration 30 --out artifacts/events.json
```

Read-only: select exact advertised serial, connect, subscribe to the existing
command/offline notification channels, verify serial/bind-info/device-info,
then observe for the requested duration (0.1–300 seconds). No setting writes,
recording commands, realtime-audio or OTA subscription. Output includes events
received during identity queries as well as the observation interval. An empty
successful result means no recognized events arrived in that interval; it does
not prove unsupported events. Output destination must not already exist.

## Source contract

Official CoMi 1.1.2 APK SHA-256
`b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118`;
`assets/public/assets/index-Btih_BUR.js` SHA-256
`167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c`.
Rechecked actual pinned member before implementation. Zero-based, end-exclusive
byte ranges: Y8 `[220352,220806)`, Z8 `[220806,220992)`.
[Existing source specification](cli-capabilities.md#discovery-files-events-and-diagnostics).

| Event | Minimum payload | Parsed fields |
|---|---|---|
| `0f device_status` | 20 B | charging0 (`!=0`), battery1, usb_mode2 (`==1`), mode3 (`1=call`, otherwise memo), power_off_duration4, noise_reduction5, voice_control6, indicator_light7, segment_duration8, screen_backlight9, usb_connected10 (`==1`) |
| `19 voice_control` | 5 B | enabled0 (`==1`), file_size1..4 (u32 big-endian) |

Voice/indicator/backlight values `ff` map to null; other bytes map to `==1`.
Power-off/segment duration units and meanings beyond these source fields remain
unverified. `raw` retains **all** payload bytes, including device-status bytes
11..19 and extensions; `frame` retains the complete CRC-checked wire packet.
No unused byte is assigned a speculative field meaning.

## Routing and limits

Notification callbacks validate Boyi framing/CRC, parse recognized events, then
place them in a separate event queue. Ordinary responses/offline bytes stay in
the transaction queue. Events therefore survive idle periods and interleaving
with command, file-list and download responses. `Connection.watch(duration)`
consumes each event once; concurrent watch consumers **split** events rather
than receiving copies. Use one event consumer per connection.

Command/file-list deadlines stay absolute. Download inactivity resets only for
its size declaration or nonempty offline data, never status/voice events.
Both queues hold at most 256 notifications; watch results hold at most 256
events. Overflow fails clearly instead of dropping notifications or consuming
unbounded memory. Malformed known events, malformed frames, overflow and
disconnect store a session failure and wake both transaction/event waiters.
Reconnect for a fresh session after failure; do not reuse a failed session.

## Evidence boundary

`tests/test_events.py` uses independently specified Y8/Z8 payloads and literal
wire fixtures whose CRCs were calculated with crcmod, not production framing.
It checks idle delivery, command/list/download interleaving, no duplicate event
delivery, uninterrupted download bytes, short payload/CRC rejection,
disconnect/overflow wakeups, bounded output and fixed timeout behavior under
continuous event traffic. These prove client behavior under the documented
wire contract; they are not live event captures.

Existing live control/download/noise evidence remains valid independently.
Each event field needs its own correlated live observation before claiming its
meaning or availability on FW010004. Passive observation can acquire raw events
without login or settings changes; later evidence should record exact frames,
observation interval, and any independent state comparison.

Live bounded check: `comi watch --duration 5` completed serial/bind/device-info
queries on C261CF0430 and returned zero events. [Saved result](evidence/client-events-passive-2026-10-12.json).
This proves the new connection/observer path completes on the device; it does
not verify event fields or prove absence of event support. No settings changed.
