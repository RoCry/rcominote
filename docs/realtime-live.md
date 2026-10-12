# Realtime audio: first exact offline comparison

2026-10-12; owned C261CF0430, firmware010004, reported mode `call`, charging.
[Raw metadata](evidence/realtime-live-2026-10-12.json); audio remains local under
`artifacts/realtime-probe/`, not published. [Static route](realtime-source.md).

## Observed

- Initial recording state idle; e5e3 subscription then2 s idle: zero bytes.
- Empty06 started recording `20261012222510`; approximately5 s later07 stopped
  it, reported20204 B and readback idle. No setting change or file deletion.
- 141 notifications, lengths108–166 B;139 while recording and2 during stop.
  No packet after stop during the1 s observation tail.
- Concatenated bytes exactly equal the20204 B same-name recording downloaded
  afterward over a fresh connection. SHA256 for both:
  `4e85939ef508a93ae7305126282340608acb27f84ccf852444a1145a5346e37f`.
- Independent `ffprobe`: MP3,16000 Hz,mono,32000 bit/s,estimated5.051 s.
  `ffmpeg -v error -i realtime.bin -f null -` decoded entire capture,exit0.

This sample requires no application packet header stripping, decryption or Opus
decoder. BLE notification boundaries are transport chunks, not a codec contract.
No claim of loss-free long recordings, other modes, pause/resume, reconnect,
backpressure handling or recovered dropped packets follows from one short sample.

## Discovered subscription hazard

First run unsubscribed e5e3 after verified stop/idle. A subsequent05 info query
timed out; original report retains this error rather than calling the whole
experiment successful. Fresh connection identity/list/download succeeded.

A second, non-recording experiment kept e5e2 subscribed throughout:
enablee5e3→05 reply; disablee5e3→05 timeout3 s; reenablee5e3→05 reply.
[Live evidence](evidence/realtime-ccc-live-2026-10-12.json),
[actual shared CCC implementation](realtime-ccc-gating.md).
The protocol has no transaction identifier; restored same-opcode response alone
does not independently identify which queued request it answers.

Client implementation should keep notification subscriptions for the connection
lifetime and stop consuming audio at the application layer. Do not implement
capture cleanup by disabling e5e3 while expecting other transactions to continue.
Disconnect still ends the session. The reusable [realtime CLI](cli.md#实时音频)
now implements this lifetime, bounded capture and explicit recording ownership;
its own acceptance run is retained separately in
[CLI evidence](evidence/realtime-cli-live-2026-10-12.json).
