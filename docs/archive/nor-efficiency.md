# NOR extraction efficiency audit — 2026-10-12

Broad hardware research and full recovery export paused at user request. Background
export interrupted; progress log reached94/124 blocks. Focus: reduce communication
and repeated work before resuming. No Flash write, reset, or new address probe.

## Measured baseline

[Machine-readable audit](../evidence/nor-efficiency-2026-10-12/baseline.json), reproducible offline:

```sh
uv run tools/audit_nor_efficiency.py artifacts/recovery-export
```

- 165 saved sessions:124 successful,41 failed. Successful session can still have
  insufficient double coverage; session count is not completed-sector count.
- 3565.818 seconds recorded through last notification;879.392 seconds in failed
  sessions (24.7%). Excludes some host/discovery/reconnect time; not wall-clock ETA.
- Successful-session median21.7025 seconds,232 commands for512 payload bytes.
- All41 failed sessions retained zero warm-window records;40 had already issued
  multiple NOR producers. Original raw notifications remain, but cannot be blindly
  promoted to verified windows without reconstructing command boundaries.
- Failures:20 incomplete RAM-row errors,17 timeouts,4 invalid/changing ring indices.
- Session JSON alone478,199,725 bytes; separate window copies add storage overhead.
  Cached sector file inventory93 differs from progress94: cache inventory is not
  authoritative verification, and previously sourced blocks need no new cache.

## Confirmed causes

1. **Whole-batch loss on a late error.** `capture_remaining` built a list before
   returning. An exception discarded all earlier completed windows; its caller
   assigned `batch_records` only after success. `capture_sector` then rejected
   everything whenever overall session `ok` was false. Block093 repeatedly failed
   after21 producers of22; restarting repeated nearly all work.
2. **Expensive acquisition method.** Each sector regenerates512 B NOR text22 times
   and reads22 ×256 B ring windows to establish independent coverage. Each sector
   also repeats BLE discovery/connection and identity/code/header guards. Successful
   block093 attempt007:20.172 seconds,230 commands; first fread status at8.620 seconds.
   This is diagnostic log extraction, not an efficient binary transfer protocol.
3. **Poor orchestration.** Repeated45-second polls followed by a new assistant turn
   generated status messages without changing the method. Late failures were retried
   without timely aggregate diagnosis. Waiting was real, but this was inefficient
   use of the agent and obscured the repeating failure pattern.

ACK/F1 completeness proves transport completion, not complete RAM rows. Exact cause
of every dropped/truncated row is unresolved; do not label all failures BLE loss.

## Repair and next gates

- Preserve completed windows incrementally. Finalize physical transport separately
  from a later window's content failure. Publish only individually revalidated
  windows after ACK/F1/no-pending and seed guard checks pass. Missing STOP, failed
  guard, invalid window, conflict, and insufficient double coverage still reject.
- Regression uses real captured window bytes followed by a later timeout; also
  verifies missing F1/invalid seed cannot publish partial results. This proves
  retained progress; it does not establish a live throughput improvement.
- Two bounded post-fix block093 trials:21.055/22.658 seconds,22 windows each;
  individually30/31 confirmed rows, merged32/32 without conflicts. Combined512 B
  exactly match earlier independently verified block SHA
  `26beb8820476ce103faec331af750b6a4017c5cd6c94dcf00e6fe27e9bd33566`.
  Neither trial hit a batch exception; partial-failure preservation is therefore
  proven by replay, not these live samples. [Results](../evidence/nor-efficiency-2026-10-12/trials.json),
  [44 source windows](../evidence/nor-efficiency-2026-10-12/trial-windows.tar.gz).
  Full offline checks229 tests+24 subtests, lint/shell checks and package build passed.
- Before another long export, use bounded existing-target trials; measure seconds,
  commands, preserved windows, final double coverage and hashes. No unbounded retries.
- Possible structural improvement, **deferred after user's SDK-first correction**:
  reuse immutable guards across multiple sectors in
  one bounded connection, retain per-window live ring checks and sector identity;
  then stop/retry according to missing row coverage. Both need implementation and
  explicit validation, not merely raising retry counts/timeouts.
- Mapped-system reading already achieved16 KiB/44.390–46.809 s, roughly14× the raw
  log method. This does **not** authorize assuming recovery remains mapped at
  `0x11000000`: boot mapping is static evidence, current mapping unknown, existing
  CLI has no verified recovery-memory profile. See [mapped export](../mapped-image-export.md)
  and [boot flow](../actual-boot-flow.md).
- Keep progress in the process/report; agent intervenes on completion or a changed
  failure condition. Report useful findings and milestones, not every polled block.
