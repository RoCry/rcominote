# NOR offset-zero read: repeated 32-byte tail via static log RAM

2026-10-12, C261CF0430 / FW010004. **Two independent fixed `fread spi_flash 0` sessions returned matching complete hex rows for offsets `1e0` and `1f0`.** This advances the UART-only output obstacle; it is not a complete sector, full NOR backup, flash tool, or recovery proof.

## Method and retained evidence

```sh
uv run comi diag capture printk-nor-tail --duration 1 --out artifacts/nor-tail.json
```

1. Verify owned identity, known image header, printk instructions/flags, static ring address/capacity, fread descriptor and handler entry.
2. Execute only `dbg fread spi_flash 0`: existing source-audited 512 B read path. No arbitrary device, offset, shell command or write accepted by this profile.
3. Read 28 B fixed context at `1800e008`, flush with help, derive last 256 B from its write index. Split only at fixed ring boundary. Never follow a returned pointer; buffer must equal `1803ee09`, capacity4096.
4. Read that short region, flush, require every actual memory row plus transport ACK/F1. Result is explicitly non-atomic retained log text.

[Session second](evidence/printk-nor-tail-second-2026-10-12.json) and [session third](evidence/printk-nor-tail-third-2026-10-12.json) retain frames, commands, scoped memory rows, parsed tail and original capture SHA; duplicate notifications/writes omitted. The first attempt hit a host-side incomplete-capture validation error after context capture and before requesting the tail. It performed the same fixed read, returned no usable tail, and motivated a regression test for scheduling during an active capture.

| Observation | Second | Third |
|---|---|---|
| read / write indices | 1481 / 1493 | 1388 / 1400 |
| retained tail start | `1803f2de` | `1803f281` |
| bytes captured | 256 | 256 |
| ACK count | 57 | 57 |
| final F1 / all memory rows | pass | pass |

Both tails contain the following complete rows, followed by `logsrv: cmd(21) dbg fread spi_flash 0`, then the beginning of that session's context printout:

```text
1e0: b7 13 b7 80 78 f2 cd 58 e3 7b 82 e2 c3 86 2e a2
1f0: 9f 8b 4b 71 c1 a8 d7 8e 2e 69 f7 cc 8b b5 48 e1
```

The earlier partial `1d0` row lacks its complete offset label and is not counted. Context printout differs between sessions, and read windows follow their separate write positions. Actual handler prints byte offsets relative to its 512 B buffer; requested Flash offset is0, giving candidate raw NOR offsets `[1e0,200)` for these32 B. This attribution rests on the actual handler and captured command sequence, not a standalone hex-string search. Independent external Flash/programmer comparison is still absent.

The mapped system header has32 zero bytes at its own offsets `[1e0,200)`, unlike this tail. These are different address spaces/regions; this comparison establishes neither encryption nor a physical mapping formula.

后续[重叠窗口采集](nor-sector-zero.md)已取得完整512 B双覆盖；本页保留最初32 B实验方法和边界。

## Remaining work

The prior whole-ring snapshot self-overwrites. This short window survived twice, but help/output volume, background logs, drops and non-atomic indices still constrain reliability. No claim that arbitrary repeated sessions always succeed. Current CLI emits diagnostic text, not a verified backup file.

Next: reduce flush output and measure how much earlier dump text survives; cover all512 B with per-window command attribution, exact length and independently repeated bytes before scaling to other offsets. Boot/recovery/resource partitions and independent recovery remain unverified. Android login remains deferred; no F5F0 subscription, mode change, Flash erase/program or reboot performed.
