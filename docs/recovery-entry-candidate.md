# Recovery second-stage entry: retained-prefix candidate

2026-10-13后续：[完整本机recovery与应用交接](recovery-complete.md)已取得并通过头/正文校验，补齐此前缺失尾部。下文保留阶段证据；缺字节/未绑定实际交接的限制以新报告为准，运行与整机恢复仍未验证。

2026-10-12. Offline only. Input: 48128 B partial decoded recovery,
SHA256 `cff7225f49d502a3e6cf52a8d2df12cbee44625cc2120c3c7a03a96d77e577b7`.
**Full body checksum remains unavailable. All instruction interpretations below
are provisional candidates, not validated recovery behavior or restore proof.**

The retained prefix already contains a useful second-stage candidate; no new
physical read is needed to locate it. [Instruction/literal evidence](evidence/recovery-prefix-entry-2026-10-12.json)
excludes literal pools and preserves exact bytes and addresses.

| Candidate interval | Observation in retained bytes |
|---|---|
| `110007ec..1100086c` | Logs `ota app init`; zeroes16 B argument, sets low three flag bits to7, supplies `spi_flash`, calls `110061cc`, saves result to `180017c8`. This differs from application's argument flags `0d`; callee interpretation still needs tracing. |
| `11000910..1100099c` | Logs `ota recovery main`, calls initializer above, then `1100a122` with saved object. Zero result follows `skip ota recovery` branch. Nonzero calls `110007a4`, whose failure log names TEMP initialization. |
| `11000978..11000998` | Passes object to `11005b88`; zero return goes to `11000940`. Nonzero logs `ota upgrade failed`, calls `110097c2(1000)`, then also branches to `11000940`. |
| `11000940..11000952` | Calls `11003b40("REC_OTA_FLAG", "no", 4)` then `1100141c(2,0)` and returns through `11000968`. Callee persistence and pstore semantics remain unverified. Both preceding upgrade return paths reach these requests; do not assume failure preserves permission to retry. |
| `11000884..110008d0` | Separate permission-shaped helper: calls `110014c8(2,&value)`; nonzero value returns1. Otherwise reads `REC_OTA_FLAG`, compares against `yes` through ROM wrappers. Outer caller at `110006b8` is now retained below; exact library semantics remain unverified. |
| `110008e0..11000908` | Separate `ota_main` log loop, incrementing counter and calling `1100894c(500,0)` indefinitely. Outer entry branches here on partition-invalid/reboot-to-OTA paths; detailed callees remain provisional. |

This already warns against copying the reference SDK's recovery control flow:
the inspected candidate routes both success and failure through the same flag
clear request. The outer gate and inner state test below constrain any next retry; persistence of the clear requests remains unknown.
Names of calls are deliberately not promoted from SDK similarity alone.

```sh
uv run tools/inspect_recovery_prefix.py --entry \
  docs/evidence/recovery-decoded-prefix-2026-10-12.bin \
  > /tmp/comi-recovery-entry.json
cmp /tmp/comi-recovery-entry.json docs/evidence/recovery-prefix-entry-2026-10-12.json
```

## Outer permission, inner state and handoff follow-up

Still provisional: same partial image, no live state or complete checksum.
The expanded evidence contains complete selected intervals, not a claim that
all recovery behavior has been reconstructed.

- Outer entry `11000634..110006d8` calls `11000884` at `110006b8`.
  Zero skips `11000910` and proceeds toward application handoff; nonzero calls
  `110099b2` then the second-stage entry at `110006c2`.
- Inside that entry, `1100a122` adds `294` to the object and calls `1100a20a`,
  which reads byte+3. Predicate returns1 only for states3,4,`0a`; all other byte
  values return0, including `0f`. This is an exact byte predicate; semantic state
  names and state changes during initialization need independent confirmation.
- Thus an eligible inner state alone does not bypass the outer permission gate.
  If both outer permission sources are actually cleared, no observed branch
  retries this stage merely because an inner failure state remains. Conversely,
  ignored/failed persistence can leave permission set. Neither outcome was tested.
- `110006c6..110006ce` calls `11001edc`, then `110099aa` with wrapper arguments
  `(0,0)` into `110013b8`. The latter logs `boot main=%d`, changes BASEPRI and
  tail-calls `11001348` with `(2,0,0)`.
- `11001348` obtains a partition via `110019d4`, logs `app offset` and a flag
  from entry byte`0b` bit0, stores entry word+`14` at `01000008`, then calls
  `110024b8` for this mode. Exact partition lookup semantics remain unaudited.
- `110024b8` invokes **RAM `18000451`** through literal `110024e8`. Startup's
  copy-shaped operation maps image `1100e098` to RAM `18000000`; under that copy
  interpretation, Thumb code at `18000450` comes from **image `1100e4e8`**.
  The retained prefix ends at `1100bc00`, so this target is genuinely absent.
  Its function length is unknown; a few bytes would not prove mapping behavior.
- If the handoff returns, outer entry requests `11000f24(700)`; if that call
  also returns, it branches to the `ota_main` loop at `110008e0`. Earlier
  partition-invalid and reboot-type`700` paths also call this loop. No ROM USB
  rescue or automatic rollback follows from these branches alone.

Next decisive evidence: validate the complete recovery body and acquire the
missing RAM handoff implementation through an efficient route; trace persistence
and partition lookup before declaring retry or mapping semantics. This removes
blind application-time recovery-address reads from the next-step rationale.
[Mapping lifetime audit](recovery-mapping-lifetime.md) still excludes blind reads
of `11000000` during application execution. No full NOR dump was restarted.
