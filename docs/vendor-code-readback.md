# Actual vendor_read: Boyi framing, not the public SDK upload parser

2026-10-12 · owned C261CF0430, FW010004. **380 mapped bytes independently
read twice and identical**, including 340 contiguous bytes from `vendor_read`
entry through the instruction immediately before its first evidenced literal pool.
Together with the earlier logsrv samples, 449 unique mapped bytes are retained;
none establishes physical flash layout or a complete firmware backup.

## Acquisition and safeguards

- [First capture](evidence/vendor-code-first-2026-10-12.json),
  [second capture](evidence/vendor-code-second-2026-10-12.json),
  [offline comparison](evidence/vendor-code-analysis-2026-10-12.json).
- Each session first retrieves `kernel threads`; requires exactly one
  `vendor_read` entry `1000a01d` and one `vendor` entry `10009e9d`.
  Thumb bit cleared yields respective code addresses `1000a01c`, `10009e9c`.
- Initial independent 16-byte reads established vendor_read bytes
  `8fb5544c544b55485549564fdff88081`. Every subsequent session requires these
  exact bytes before reading literals or the continuation.
- Six entry LDRs independently determine the literal locations below.
  The bounded code span stops at the first such pool (`1000a170` exclusive);
  no guessed physical offset, RAM pointer traversal, or unknown service write.
- Exact single rows required for every read; missing/short/duplicate output is
  failure even with all ACKs/end frame. Both final sessions: 32 ACKs,
  `transport_ok=true`, `readback_complete=true`.
- Contiguous transport rows are merged before Thumb decoding. A 32-bit
  instruction at `1000a06a` crosses the 16-byte row boundary at `1000a06c`;
  per-row decoding would lose or misinterpret it. Captured regression covers this.
- Before/after Boyi info: idle, FW010004, capacity59634/free59632, noise9,
  unbound, charging100. Local captures `artifacts/vendor-before.json` and
  `artifacts/vendor-code-after.json`. No restart, upload, erase, or flash write.

```sh
uv run comi diag capture vendor-code --out artifacts/vendor-1.json
uv run comi diag capture vendor-code --out artifacts/vendor-2.json
uv run comi diag compare-references artifacts/vendor-1.json artifacts/vendor-2.json --vendor --out artifacts/vendor-analysis.json
```

## Entry and literal facts

Thumb PC-relative address = align(instruction address + 4, 4) + immediate.

| Instruction | Register / offset | Literal location | Observed LE value |
|---|---|---|---|
| `1000a01e` | r4 /150 | `1000a170` | `100ba564` |
| `1000a020` | r3 /150 | `1000a174` | `100ba36c` |
| `1000a022` | r0 /154 | `1000a178` | `01850031` |
| `1000a024` | r1 /154 | `1000a17c` | `100c1fe7` |
| `1000a026` | r7 /158 | `1000a180` | `01290031` |
| `1000a028` | r8 /180 | `1000a1ac` | `01710011` |

At `1000a02c`, code subtracts the first two values, shifts left5, masks ff00,
ORs into r0, then calls `10055f90` with r1 unchanged. This is consistent with
the public SDK's log-module ID and packed line/level fields
([act_log.h][actlog], [log_core.h][logcore]); **these constants are not all
pointers**. None of their target addresses was dereferenced this round.
The second entry (`vendor`) zeros a 20-byte stack region through call
`100b96c8`; its callee identity remains inferred, not verified.

## Recovered receive loop

The actual thread's code differs materially from the public vendor source:

| Address | Observed instructions / constrained interpretation |
|---|---|
| `1000a03c–a048` | Loads global through literal at `1000a184` (not yet read), gets context+150, calls `100516b4` with stack buffer and length5. Read-like semantics inferred from subsequent use and repetition. |
| `1000a050–a062` | Loads first header halfword and swaps bytes **in place**. |
| `1000a07c–a086` | Compares swapped halfword against immediate **d22d**; matches on-wire **D2 2D**. Wrong header takes a draining/read-like loop, not command dispatch. |
| `1000a0b0–a0c2` | Copies five header bytes into context+168 buffer. Header byte4 is payload count. First halfword in the copied buffer is now host-order, not original wire bytes. |
| `1000a0e2–a10a` | Repeated read-like calls append payload; subtracts each returned count from remaining count. |
| `1000a0c8–a0d4` | When payload remaining is zero, requests another two bytes into stack+6. |
| `1000a10c–a116` | Swaps that two-byte trailer in place. No subsequent use/comparison of that local appears in the recovered caller. |
| `1000a11a–a138` | Calls `1009b354` on context+4 with argument2710 (10000), handles nonzero result by logging; lock-like interpretation only. |
| `1000a13e–a14c` | Calls **1000b3b4** with r0=buffer+3 and r1=`u8(header byte4 + 2)`. This span corresponds to command + payload length + payload, excluding first3 header bytes and trailer. **Callee not yet read; do not label it a proven command dispatcher or CRC function.** |
| `1000a168–a16e` | Calls `1009b450` on context+4, then loops to a03c. |

The five-byte header, D22D magic, one-byte payload length and two-byte trailer
corroborate the independently verified [Boyi envelope](protocol.md), unlike
the public SDK's service01/command/type80/TLV-length upload header. This is
device-code evidence that CoMi adapted the vendor thread implementation.

**Not proved:** binding of this context to a particular GATT service;
F5F0 purpose; version-byte validation; CRC algorithm or enforcement; handler
table; backup/upgrade commands. The caller does not visibly validate header
byte2 or compare the trailer. Absence here is not absence elsewhere. Read-like
calls' exact implementation and short-read guarantees remain unknown; no
malformed-packet testing performed.

## Next discriminating reads

The directly observed call to `1000b3b4` is the strongest next anchor for
identifying command handling. The literal at `1000a184` anchors the context
global, but RAM contents should not be mistaken for immutable firmware.
Prioritize code/data references from these instructions over blind UUID scans.
The [bounded app-artifact search](f5f0-artifact-search.md) found no F5F0 handler;
the public SDK route remains separately documented in
[vendor-service audit](vendor-service-followup.md).

[actlog]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/logging/act_log.h#L53-L58
[logcore]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/logging/log_core.h#L104-L111
