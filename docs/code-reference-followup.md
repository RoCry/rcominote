# Live code references: SDK function-name corroboration

2026-10-12, C261CF0430 / FW010004. Five noncontiguous blocks, **69 unique
mapped bytes**, read identically in two independent BLE sessions. No flash
write, reboot, helper upload, or execution of decoded bytes.

## Evidence and derivation

[First capture](evidence/code-references-first-2026-10-12.json),
[second capture](evidence/code-references-second-2026-10-12.json),
[offline comparison](evidence/code-references-analysis-2026-10-12.json).

| Address / bytes | Why read this location | Observed result |
|---|---|---|
| `1000bf20` / 16 | Current logsrv thread entry, Thumb bit cleared | Same entry bytes as previous independent samples |
| `1000c0ac` / 8 | Entry's two PC-relative LDRs: aligned PC `1000bf28` + `184` / `188` | Little-endian words `100c26ba`, `100ba51c` |
| `100c26ba` / 13 | First literal supplies r1 to call; SDK allocator macro passes `__func__` | Exact ASCII `_logsrv_init\0` |
| `100ad486` / 16 | Entry's BL target | First instruction `b.w 10050400`; subsequent bytes include adjacent routines, not necessarily this callee |
| `1000bf30` / 16 | Return address after entry's BL | LDR r3 from `1000c0b4`, arithmetic, conditional branch to `1000bf58`; final two bytes `46f0` are an incomplete instruction |

All blocks have exact lengths and independent SHA-256 values in the comparison.
The 13-byte string length was chosen from the source hypothesis before reading;
the returned bytes corroborated it. Pointer reads did not become arbitrary
pointer traversal. The second literal's target was **not** dereferenced.

## Source correspondence, not identical-firmware proof

Pinned SDK `26f51e584940d5b141cd1d09d2629d69b595f579`:

- [`log_service.c` lines 802–828][init] starts `_logsrv_init` with
  `app_mem_malloc(sizeof(*ctx))`; `_log_service_main` calls this initializer.
- [`mem_manager.h` lines 38–39,67][macro] maps app allocation to
  `mem_malloc_debug(size, __func__)`.
- [`mem_manager.c` lines 21–29][allocator] routes to `mem_pool_malloc` when
  memory debugging is disabled.

Observed entry loads r1 with `_logsrv_init`, r0 with `0x50`, then calls a stub
that branches elsewhere. **Inference:** initializer was inlined into the
logsrv entry; allocation context size is 80 bytes, and the branch stub is
consistent with the non-debug allocator route. Exact compiler, configuration,
allocator identity at `10050400`, and source revision remain unproved.

This is stronger source correspondence than thread names or decodable Thumb
bytes alone. It still supplies no physical flash offset, partition table,
complete image, exact SoC, or recovery guarantee.

## CLI reproduction and failure semantics

```sh
uv run comi diag capture code-literals --out artifacts/literals.json
uv run comi diag capture code-references --out artifacts/references-1.json
uv run comi diag capture code-references --out artifacts/references-2.json
uv run comi diag compare-references artifacts/references-1.json artifacts/references-2.json --out artifacts/references-analysis.json
```

Every session rechecks current logsrv entry before reading the entry. Literal
reads additionally require exact entry bytes; reference reads require exact
literal bytes. Addresses and counts are fixed; changed prerequisites stop the
sequence. No address/length/shell input is accepted.

`transport_ok` records framing/ACK/end completion. Bounded code profiles now
also require exactly one complete row for **every requested block**;
missing/truncated/duplicate rows set `readback_complete=false`, `ok=false`, and
CLI exits nonzero while preserving evidence. A regression reproduces a dropped
last row with otherwise complete transport. Other shell profiles still cannot
claim complete text from ACK/end alone.

After the two initial sessions, Boyi status remained idle, FW010004, capacity
59634/59632, noise9. A third capture with the new payload validation passed
`transport_ok=true`, `readback_complete=true`; raw artifact remains local.

## Next decisions

Continue bounded control-flow/reference reconstruction from known instructions:
complete the partial instruction; inspect the evidenced branch destination and
third literal; corroborate source layout before following new pointers. These
are leads, **not yet executed reads**. Prioritize finding storage/boot metadata
over expanding a sample solely to increase its byte count.

Official live web path remains blocked by HTTP500; see [recheck](official-acquisition-next.md).
Original mapped-code limits remain in [initial report](mapped-code-readback.md).

[init]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L802-L828
[macro]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/base/include/core/mem_manager.h#L38-L67
[allocator]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/base/memory/mem_manager.c#L21-L29
