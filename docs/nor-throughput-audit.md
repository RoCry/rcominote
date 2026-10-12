实测后续：[同连接批量读回](nor-warm-capture.md)已完成，231 ACK、21.762 s，32/32行双覆盖。下文为实现前估算；最终实现每次producer后读取新鲜28 B状态，不额外增加producer前状态读取。

# NOR log-window throughput: bounded offline audit

2026-10-12; read-only analysis of existing CLI and 22 actual offset-zero captures. No device I/O. **Use one guarded BLE session for multiple fresh producer/window operations.** Retain one new `fread` per window; this avoids depending on an old ring snapshot surviving successive reads.

## Measured baseline

Inputs: ignored raw `artifacts/nor-overlap{0..10}-{first,second}.json`; retained counterparts and report in [sector-zero evidence](evidence/nor-sector-zero-2026-10-12/report.json). Raw notifications preserve elapsed timestamps; compact retained captures preserve frames and command attribution. Recomputed from all 22 raw records:

| Quantity | Observed |
|---|---:|
| Fixed text commands | 1,346 |
| ACKs, including PREPARE/START/STOP | 1,412 |
| Repeated pre-producer guard/query commands per capture | 49 |
| Sum of last-notification elapsed times | 245.492 s |
| Mean last-guard ACK elapsed from capture origin | 9.370 s |
| Last-guard ACK → final payload-flush ACK | 0.659–0.900 s; mean 0.733 s |

Timing calculation: locate exact ACK notifications `1d108107007f0400a0860100`; ACK indices0/1 are PREPARE/START, then one per fixed command, final STOP. Useful phase starts at ACK immediately preceding the declared `dbg fread` and ends at ACK immediately preceding STOP. This is a measured subsection of the old workflow, **not a measured warm-session throughput**. It excludes final duration wait, STOP and reconnect/setup.

The 49-command preflight executes thread/entry/literal checks, eight64 B mapped-header reads, printk code/flags/hook checks, fixed ring initialization/context checks, and fread entry/descriptor checks. Every small range currently adds `help` for flush. Repeating this unchanged for every256 B retained-log window dominates the baseline.

## Concrete session design

1. Keep owned identity, known512 B header SHA, immutable instruction/literal/descriptor checks once per bounded connection. Start with one pass of11 windows per connection; second pass uses a separate connection. Do not cache across reconnects.
2. Before each subsequent producer, refresh fixed28 B context at `1800e008`, then flush/require both complete rows. Check capacity4096, buffer`1803ee09`, valid indices, fresh `init=1, panic=0`. This refresh costs one `mdb` plus one `help` before the new producer, when overwriting earlier log text is harmless.
3. Execute fresh fixed producer, then fresh28 B context and bounded version-query flush, followed by the same256 B ring window and complete row/ACK checks. Context bytes20/21 are RAM`1800e01c/1d`: init/panic. Validate them again before payload scheduling; current `context()` discards these bytes and current branch check uses older startup flags.
4. End the batch with STOP/F1. Any disconnect, changed guard, missing row, malformed transport or conflicting bytes aborts; no automatic continuation using stale guards.

All addresses remain within existing fixed profiles. Character hook is only selected when init=0, so active-DMA proof depends on fresh init/panic; device/hook observations remain session preflight evidence. Fresh metadata is still non-atomic and cannot exclude a subsequent asynchronous state change.

For two11-window sessions, preserving existing eight-query flush and adding two preflight commands before each of20 subsequent windows predicts **412 ACKs**:98 initial commands +268 useful commands (including four observed ring-wrap commands) +40 metadata-refresh commands +6 control frames. Baseline1,412 →412, 3.43× fewer command ACKs. Reusing measured phase times gives about37 s plus new metadata-refresh/processing costs, versus245.492 s baseline; only a live bounded batch can establish actual speed and reliability.

## Required state and attribution changes

Current `log_capture.py` cannot simply append another copy of the command list:

- `range_frame_spans` is keyed by command string. Repeated context commands overwrite earlier spans; duplicate ring ranges can also collide. Each producer/window needs its own operation identity and span namespace.
- `printk_tail.verify_producer()` requires exactly one producer in a capture. Keep child operation captures or explicit operation slices; never relax to accepting any producer somewhere in a whole session.
- Reset operation-local `tail_flush_queries`, `tail_appended`, pending row list and producer/context boundaries. Preserve connection-level Stream, cumulative ACK count and received frames until STOP.
- Guard evidence may be referenced from a session preflight interval, but operation-local producer status/echo and context/payload rows must stay scoped to that operation. Do not count inherited guards or duplicate records as independent NOR reads.
- Two windows from one producer are not two independent reads. Every operation here retains a new `fread`; repeated coverage still requires distinct operation identities and conflict checks.

`range_frame_spans[last_fread_guard][1]` currently closes before producer transmission. Preserve that boundary; broadening it into later operations would allow stale status/echo text to satisfy attribution.

## Optional adaptive flush, same operation

Replayed all22 raw notification streams through actual `Stream.feed()` and checked fresh context rows using actual `observed_block()`, starting at each saved28 B context frame boundary. In every capture, both16 B and12 B rows were present while cumulative ACK count represented **three completed version queries**; fourth query may already have been transmitted. This supports trying four queries or adaptive early completion, not assuming three are sufficient.

Prefer adaptive maximum8 queries: after each request/ACK, process available notifications and test complete scoped context rows; stop sending queries once rows exist. If missing after the cap, retain bounded pump timeout then fail before payload. Do not infer success from ACK alone or empty queues. Four rather than eight queries would save88 commands across22 windows and reduce self-overwriting text, predicting324 ACKs with the conservative metadata refresh above; unmeasured until tested.

SDK context: pinned [log_service.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c) defines504 B payload buffers; `_logsrv_put_log` commits full buffers, and `_logsrv_send_log` drains committed indices. This explains why tiny output needs additional queries. It does not establish byte-identical runtime buffering under the proposed operation sequence.

## Acceptance

First prove one bounded11-window pass plus independent second pass: all requested rows, unique producer attribution, live28 B metadata before producer/after producer, complete transport and STOP/F1, original sector SHA`72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec`. Measure elapsed time/ACKs from new raw captures. Then extend only to already validated named NOR/file bounds. This optimization does not establish raw-address mapping, full backup, programming or recovery.
