# Slot0 mapping configuration: two independent word observations

2026-10-14, owned idle CoMi FW010004. Two separate fixed `mdw ... 1` trials completed through nonce-associated logsrv text→selected slot→new SD512→Boyi. **Observed CPU word`40010300=1000000f`; offset word`40010304=00024000`.** These are independent historical samples, not an atomic mapping-entry snapshot or proof configuration stayed constant between them.

| Target | Fresh logsrv counter / selected slot | Observed word | Trial result |
|---|---|---|---|
| `map0-cpu`, `40010300` | 208 / slot0=`1800a9b0` | `1000000f` | Seven confirmed Actions writes/seven ACKs/F1/pending0; complete4/32/512-byte files; final state equal |
| `map0-offset`, `40010304` | 210 / slot2=`1800adb0` | `00024000` | Same complete transport checks; capacity59594→59593 integer MiB allowed, all other reported state equal |

Each target required the same nine original code guards, then its own complete global4 and context32 preflight. P=`180111fc`, stream=`18011254`; trial metadata flags3, type/requested0, rd=wr at its parent counter, drop0, only selected slot length406. Each saved body contains exactly one current random-path completion marker followed by exactly one target-word row with matching little-endian ASCII column. Marker body`[138,191)`/slot`[146,199)`; row body`[195,250)`/slot`[203,258)`. No other MMIO target, mapping write or alias read was performed by these trials.

## Actual read basis and interpretation boundary

Complete checksum-verified [actual recovery](../evidence/recovery-complete-2026-10-13/recovery-decoded.bin), SHA256`19625b7b70eb8e4a91c889792c0ca383f51ea205629e67565b59c47d15e09906`, supplies ordinaryLDR32 evidence. [Handoff evidence](../evidence/recovery-complete-2026-10-13/handoff.json) maps image`1100e098`→RAM`18000000` as a static relocation interpretation:

| Actual runtime / image location | Bytes / fact |
|---|---|
| `18000462..468` / `1100e4fa..e500` | `134d134a17682968`; load register-address literals, thenLDR offset and CPU words |
| `180004b0/4b4` / `1100e548/54c` | Literals`40010300/40010304` |
| `18000224` / `1100e2bc` | `41f00101`: mapper helper ORs **1**, notF |
| `180004b8` / `1100e550` | Caller literal already`1000000f` |
| `18000470` / `1100e508` | Conditional OR`80000000` into offset argument |

Thus observed CPUword matches the actual handoff caller template: upper bits excluding low nibble`10000000`, low nibble`f`; helper additionally sets bit0. This does not identify every hardware control bit or window extent. Actual boot has a different helper that ORsF; reference SDK's general mapper uses`~3f | 1f` with a32MiB comment. Neither licenses inferring a size from this observed lowF. [Actual boot](../actual-boot-flow.md), [complete recovery handoff](../recovery-complete.md).

Offsetbit31 is clear; removing bit31 leaves nominal physical-offset candidate`24000`, consistent with the existing ACPT system file offset. Pinned reference `soc_memctrl_mapping(...,enable_crc)` names offsetbit31 as CRC mapping attribute. This is **not ACPT partition encryption bit1**, image-header flag4, or encryption-request bit31 used by a different OTA write API. A clear mapping CRC attribute does not prove physical NOR unencrypted, byte-identical to the mapped image, or invertible across the chip. [Flag-context audit](../boot-security-source-audit.md), [ACPT evidence](../partition-readback.md).

Ordinary recoveryLDR usage supports software treatment as readable configuration words; no silicon manual has established absence of read-clear or other hardware side effects. Two observations do not establish an accessible raw alias, all other mapping slots, mapping lifetime, raw physical-byte representation, or a recovery/flash-writing route. No new alias or mapping operation is authorized or executed by the offline verifier.

## Failed historical context and publication

Original `offset-context` completed four ACKs/F1 and32-byte download but final identity failed with `OSError: [Errno 38] LE ATT connect failed`; no final info exists. Overallfalse remains unchanged. Its original32 bytes are published as **historical failed sample**, never accepted as parent or converted to success. `offset-context-b` is a separately created/downloaded32-byte file with successful final state, referencing the same complete offset-pointer parent; only it gates the offset trial. No postcheck or reused-download derivation.

[Compact receipt](../evidence/map0-entry-live-2026-10-14.json) and [safe samples](../evidence/map0-entry-live-2026-10-14) retain392 bytes: two targets×(preflight36 + trial global4/metadata32 + marker53/row55)=360, plus failed historical context32. Existing nine guard sources are pinned through the preceding [word bundle](gpio28-word-live-2026-10-14.md). Two complete private slot512 hashes:

| Trial | Complete private slot SHA256 |
|---|---|
| CPU | `02b36eebc278a71aedba467ec0e00500750a1a76241b9d5f177102f7cc2f461d` |
| Offset | `a228f1eb1217e359e41d34ada73c44f2a88ea4d86f18a8ec06337fa538e15678` |

Only exact test-path completion markers and one-word rows are selected from those slots. Other body/stale-tail bytes, recordings, lists, full reports and HCI remain private. This round retained11 new non-audio SD files; preceding series31→42; none deleted. Metadata/body copies are non-atomic and commands emit logs; pointer equality is checked afterward, not before dereferencing. No current allocator-ownership, still-partial or general512-byte reliability claim.

Offline replay, tracked files only; optional second mode checks19 retained private-input hashes:

```sh
uv run tools/verify_map0_entry.py docs/evidence/map0-entry-live-2026-10-14.json
uv run tools/verify_map0_entry.py docs/evidence/map0-entry-live-2026-10-14.json --private-root .
```

Verifier reuses prior word/slot evidence replay and common helpers; checks pinned recoveryLDR/literal/helper/caller bytes, nine guard hashes, separate chronology/parent chains, complete small samples, target commands, selected spans/ASCII, and retained failed-context boundary. Original private semantic audit used `gpio_word_contract.validate_parents`, `read_basis`, `commands`, `validate_actions`, `verify_payload`, plus `downloaded`/`same_identity`. Public compact replay records but does not rerun ATT/state/full-slot uniqueness audit; selected spans alone cannot reproduce full-slot uniqueness. No device access, missing-byte repair or joining.
