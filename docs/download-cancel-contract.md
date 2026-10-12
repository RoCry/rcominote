# Boyi download cancellation: request acknowledgment is not a drain barrier

2026-10-12. Actual FW010004 mapped system + pinned official CoMi 1.1.2 JS.
Static analysis only; no device I/O. [Bounded byte/instruction/source evidence](evidence/download-cancel-contract-2026-10-12.json).
Prerequisite [dispatcher](vendor-dispatch-followup.md), [normal file path](recording-download-path.md).

**`STOP_GET_FILE=0c` sets a shared stop flag and replies `0c/00` immediately.
The active worker can send another identical `0c/00` when it notices that flag.
Neither reply is a proven transport-drained/file-closed barrier.** Cancellation
can be requested on the existing connection, but that connection must not be
immediately reused for a new download based solely on the first acknowledgment.

## Actual command and worker contract

Let `C` be the pointer returned by `1000a1b0`, loaded from global `1800a96c`.
Fields below are actual offsets; inferred names follow observed uses.

| Location | Observed behavior |
|---|---|
| `1000b4ba` | Dispatcher passes payload pointer/length to `1000b368`; handler does not consume either argument. Empty payload matches official JS. |
| `1000b372..b37a` | Loads `C+18` for logging; stores byte **1** at `C+48` (`send_file_end` in actual log string). No active-worker check gates success. |
| `1000b38e..b39a` | Calls reply helper `1000b114(0c, 0, &zero, 1)`. Returns zero regardless of worker existence. No thread join, handle clear or stream flush here. |
| `1000b5b0` | Worker startup resets `C+48=0`. Cancel sent before worker reaches this point can be overwritten. |
| `1000b712..b724` | Each data-loop iteration exits if `C+18==0`, `C+48!=0`, or link-state getter `1006be84()!=2`. Getter reads byte at `180090af`; exact enum name not established. |
| `1000b726..b76c` | Reads up to 20,210 B, then calls `10051980(C+150, data, count, 2)`; no intervening stop-flag check. In-flight read/stream write may finish after command acknowledgment. |
| `1000b744..b74e` | Exiting loop calls state helper `1006bdbc(C+170,2)`, then branches to common terminal selector at `1000b646`. |
| `1000b646..b66c` | If stop flag nonzero: reply helper `(0c,0,&zero,1)` again. If zero: choose normal/error `0b` reply via `1000b76e..b77a`. |
| `1000b76e..b77a` | Flag zero and `r7<0`: `0b/01`; otherwise `0b/02`. This is worker outcome selection, not proof every transmitted byte reached host. |
| `1000b670..b684` | **After terminal reply call:** call power/state helper, close file via `1002eb10`, then clear `C+18=0` and return. |

The stop handler and worker both send the same reply with no job identifier.
Their scheduling order is not guaranteed: the worker may observe the flag and
enter its reply before the stop handler reaches its own reply call. Two replies
therefore cannot be labeled “accepted” then “closed” by arrival order.
Stop when idle still produces one `0c/00` and leaves the flag set until a later
worker startup clears it.

## Reply and data path

`1000b114` TBB at `1000b13e`, table bytes at `1000b142`:
`04 2b 5b 7f a3 ba cc db`. Index is `command-6`; `0b` selects `1000b2b6`,
`0c` selects `1000b2da`. With helper status zero, the latter copies the supplied
one-byte payload, then calls `1000a888(0c,payload,1)` through shared send code.

`1000a888` constructs Boyi header `d2 2d 01 <cmd> <length>`, copies payload,
appends CRC helper result, then writes via `10051980(C+150,frame,length+7,0)`.
The worker's audio bytes also use `C+150`, with mode argument 2. Thus the two
paths share a stream object; this alone does not establish host delivery order
across the command/offline GATT notifications.

`10051980..10051afe` is a generic stream-write routine: indirect backend write,
optional callbacks, space waits/retries and state checks. It does not access
`C+48`. Its backend and mode-to-GATT delivery/drain guarantees were not resolved
in this pass. A successful stream-write return is insufficient evidence that
the host has consumed every prior audio notification.

## Races relevant to a client

| Sequence | Consequence |
|---|---|
| Stop after worker has passed loop flag check | Up to an in-flight read/write can occur after first acknowledgment; queued offline bytes can outlive it. No measured maximum here. |
| Stop before worker startup clears flag | Startup can overwrite cancellation; first acknowledgment remains successful. |
| EOF and stop run concurrently | Worker can select `0b/02` before flag is set, or `0c/00` after it is set. Requiring exactly two cancel replies can time out on a legitimate EOF race. |
| New `0b` before old worker closes | `1000b998` overwrites `C+49` name and `C+14c` offset even when `C+18` is nonzero; it then skips new thread creation. An acknowledgment is not permission to start another job. |
| Second cancel reply reaches host | Worker has not necessarily executed its subsequent close/handle-clear instructions yet; transport queues may still contain old bytes. |

`0b`/`0c` responses and offline bytes lack an observed transfer generation token.
Counting replies or waiting for an arbitrary quiet interval cannot prove all
of these races excluded. Repeated stop requests also create additional identical
acknowledgments, defeating a fixed “two acknowledgments” rule.

## Official app: weaker completion semantics

Source member SHA-256
`167d837a68310664ecec8de6960fd96f6962036cf21a101cc546b1d9c489cc9c`:

| Byte range, end exclusive | Actual behavior |
|---|---|
| `[244253,244532)` | `stopGetFile` sends empty `0c`; returns `sendCommand.success`. Does not check reply payload or wait for worker shutdown. |
| `[232509,233642)` | `sendCommand` resolves success on the **first matching command response**, unregistering its handler; five-second default timeout. |
| `[240849,243257)` | Download listens for offline data and `0b/02`; a separate `0c` reply does not settle its download promise. Three-second idle timeout removes local listeners but does not itself send cancel. |

Copying app semantics would inherit a timeout after cancellation and does not
establish a safe same-connection resume contract.

## Client decision and next evidence

**Supported design now:** send a single empty `0c` on the active connection;
accept `00` as request acknowledgment; settle the local operation as canceled,
retain the already-written prefix and its exact length, and reject further
downloads on that connection. Continue discarding/recording late offline bytes
until disconnect; never append them to a new transfer or publish a complete MP3.

Use a fresh connection/session and fresh receive queues for any later resume.
This isolates host notification ownership; **reconnect alone has not been proved
to join the device worker or flush its backend queues**. Verify a subsequent
download's start/length and bytes against a separately completed file before
claiming cancel→resume supported. Preserve cancellation outcome separately from
full-file success; a late `0b/02` cannot turn a user-canceled file into success.

Same-connection reuse needs stronger evidence: backend queue ownership/flush
semantics, a reliable worker-idle condition, and measured cancel/EOF/late-data
sequences. This pass supports cancellation, not a proved immediate-reuse barrier.
The static pass sent no device commands. The bounded live follow-up below sent
only normal identity/list/download/stop-download/status requests.

## Bounded live observation

Owned C261CF0430, existing listed recording20261012112429 (56,912 B). Waited for
valid0b size declaration and first244 B data packet, sent0c once, observed3 seconds,
then queried device-info on the same connection and disconnected. No new download
started on that connection. [Timestamped commands and byte counts](evidence/download-cancel-live-2026-10-12.json);
audio payload deliberately not retained in this trace.

- Cancel send at0.151717 s;19,966 additional bytes arrived, total20,210 B.
- Last data at0.842694 s; identical0c/00 frames at0.843794 and0.843934 s.
- No offline bytes observed after first ACK in this sample; do not misstate this
  as evidence of post-ACK bytes. The extra data was after cancel **send**.
- No0b/02 seen in this observation; device-info succeeded afterward, recording
  state idle. Recording state is not the download worker's internal handle.
- Actual transfer stopped short of56,912 B and dual replies match static paths.
  One quiet3-second sample does not prove a general drain/worker-idle barrier,
  EOF-race behavior, reconnect semantics or reliable immediate restart.

Reproduce static evidence:

```sh
uv run tools/inspect_download_cancel.py \
  artifacts/mapped-system/mapped-system.bin \
  artifacts/apk112-final-check/device-index.js
```

Tool guards both complete input digests and decodes only explicit code spans;
TBB data and literal pools excluded. Mapped system: 927,632 B, SHA-256
`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`.
