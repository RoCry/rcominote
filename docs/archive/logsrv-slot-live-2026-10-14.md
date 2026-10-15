# Fresh known short read → logsrv slot → SD: 2026-10-14

First complete trial of this route on owned idle CoMi FW010004: exact `dbg mdb 1000ab40 10` output survived in a saved logsrv slot and a newly created512-byte SD file downloaded completely through Boyi. Independent offline audit passed original parent chain, seven confirmed Actions writes/seven ACKs/one F1/empty pending, all three complete downloads, exact nonce→known-row check, and final state comparison. SD capacity reported59596→59595 integer MiB; all other device fields equal.

| Evidence | Observed |
|---|---|
| Fresh preflight | Two new code guards `1000bd30/32`, `1000bd80/48`; independent global4 and context32; required existing five code guards revalidated |
| Fixed pointer / selected slot | `P=180111fc`, stream `18011254`; index204→slot4 at`1800b1b0` |
| Trial metadata | flags3, type/requested0, rd=wr204, lengths`[0,0,0,0,431,0,0,0]`, drop0 |
| Nonce marker | Exact completion line for this trial's random global-snapshot path; body`[138,191)`, slot`[146,199)` |
| Known code row | Exactly one addressed`1000ab40` row after marker within recordedL431; body`[195,274)`, slot`[203,282)` |
| Code16 | `5e348df8123094f87034bdf800208df8`; SHA256`d189dd2643c977534f18711d4a2f247fb69d2c7a55f94a9190c83043b07706b0`; exact pinned mapped-image bytes |
| Complete private slot512 | SHA256`f66ea7d4f7f24ce96684c7f6c5ea630701c3905aa1c5591678985ba0fa829e1e` |

Seven Actions commands: PREPARE, START, fixed global4 dump to new nonce path, exact known mdb16, context32 dump, fixed slot4/512 dump, STOP. No nonce argument appended to mdb; no alternate slot, retry, filler, producer, NOR/MMIO access or firmware operation. Context and slot were copied before STOP; immutable files downloaded afterward. Pointer equality was checked after downloads, not before the historical-pointer dereference.

This establishes one fresh-marker-associated known short read exported through slot→new SD512→complete Boyi. Metadata and slot copies occur at different times; commands emit logs. `rd==wr`, L431 and retained known text do not establish an atomic snapshot or that the slot stayed partial. Alignment/RAM bounds and later pointer equality do not establish current allocator ownership. One completed512-byte download does not establish general transfer reliability. No raw NOR backup, firmware write or recovery route is proven.

[Compact receipt](../evidence/logsrv-slot-live-2026-10-14.json) pins original report hashes; [public raw samples](../evidence/logsrv-slot-live-2026-10-14) total284 bytes: two code guards80, fresh preflight36, trial global4/metadata32, marker53, known row79. Only the two exact whitelist spans are exported from the private slot. Full first431-byte body, stale tail, recording lists, full reports and logs/HCI remain private. Seven new SD test files retained; total24 including earlier17; none deleted. Earlier [historical context evidence](logsrv-context-live-2026-10-14.md) remains bound to its original session.

Offline replay, tracked files only; no device access:

```sh
uv run tools/verify_logsrv_slot.py docs/evidence/logsrv-slot-live-2026-10-14.json
```

Optional original-input hash check, when ignored artifacts are available:

```sh
uv run tools/verify_logsrv_slot.py docs/evidence/logsrv-slot-live-2026-10-14.json --private-root .
```

Replay pins compact receipt/full image/shared guard bundle; checks seven code guards, fresh parent hashes, fixed commands, raw small snapshots, historical context, selected-span bounds, exact marker and code row. Optional private mode hashes12 retained inputs including full slot512. Neither mode reruns private ATT/state/complete-slot uniqueness audit; that audit used `logsrv_slot_contract.validate_parents`, `commands`, `validate_actions`, `verify_payload`, plus `same_identity` and `downloaded`. Public spans alone cannot reproduce full-slot uniqueness. Corrupted receipt/raw bytes fail; no reconstruction or joining.
