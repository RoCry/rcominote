# Recovery second-stage entry: retained-prefix candidate

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
| `11000884..110008d0` | Separate permission-shaped helper: calls `110014c8(2,&value)`; nonzero value returns1. Otherwise reads `REC_OTA_FLAG`, compares against `yes` through ROM wrappers. Its callers and exact library semantics are not established here. |
| `110008e0..11000908` | Separate `ota_main` log loop, incrementing counter and calling `1100894c(500,0)` indefinitely. Reaching this loop from boot failure is not established by this bounded decode. |

This already warns against copying the reference SDK's recovery control flow:
the inspected candidate routes both success and failure through the same flag
clear request. Whether an independent outer condition retries remains unknown.
Names of calls are deliberately not promoted from SDK similarity alone.

```sh
uv run tools/inspect_recovery_prefix.py --entry \
  docs/evidence/recovery-decoded-prefix-2026-10-12.bin \
  > /tmp/comi-recovery-entry.json
cmp /tmp/comi-recovery-entry.json docs/evidence/recovery-prefix-entry-2026-10-12.json
```

Next evidence: trace candidate callees `1100a122`, `11005b88`, permission-helper
callers and actual boot handoff; retain provisional status until the complete
recovery checksum can be validated through an efficient acquisition path.
[Mapping lifetime audit](recovery-mapping-lifetime.md) still excludes blind reads
of `11000000` during application execution. No full NOR dump was restarted.
