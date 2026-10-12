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

## Follow-up: pause/resume exact comparison

[Bounded owned-device evidence](evidence/realtime-pause-live-2026-10-12.json),
FW010004, same reported call mode, noise9, charging. New recording
`20261012231500`; no settings mutation, existing-file deletion or firmware action.

- Recording3 s → pause1 s settling +3 s stable observation → resume3 s → stop1 s tail.
  Each control reply named the same file; every requested state was read back.
- 171 notifications,118–168 B:83 after start,2 during pause command,1 during
  resume command,84 after resume,1 during stop command. None during initial idle,
  either paused interval or post-stop tail. Labels mark host command/readback
  windows, not exact device transition times; do not use the pause ACK as a
  universal no-more-bytes barrier.
- Realtime24520 B equals fresh-connection full download24520 B byte for byte.
  Both SHA256 `eccf7ce1d908356619996b7a8325b12eb1b0061f0c6b54581308886803cbcea5`.
- `ffprobe`:MP3,16000 Hz,mono,32000 bit/s,estimated6.130 s.
  Whole-file `ffmpeg -v error -i realtime.bin -f null -` exits0.
- Final device state idle. One short pause/resume sample supports gap-free raw
  concatenation across this pause; it does not establish long-window reliability,
  reconnect recovery, every recording mode or exact sample-level pause timing.

Reproduce explicitly on the idle owned device; creates and preserves a new recording:

```sh
uv run -m rcominote.experiments.realtime_pause artifacts/NEW-pause-probe
```

The package experiment rejects an existing output directory, checks exact serial
and idle state, retains raw audio locally, and attempts stop cleanup after an
attempted START even if a control/readback fails. It keeps e5e3 subscribed until
disconnect and compares against a complete same-name offline export. Failed runs
retain `report.json` and partial audio; no failed output is declared complete.
Audio is intentionally excluded from committed evidence.
