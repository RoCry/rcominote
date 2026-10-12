# OTA payload selection, readback CRC and success ordering

2026-10-12. Offline audit of verified CoMi FW010004 mapped application,
927632 B, SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`.
[Instruction/literal evidence](evidence/ota-commit-2026-10-12.json).
No device I/O or live package acceptance. Names use the pinned SDK where actual
instructions agree; observed branches, calls and unchecked returns govern claims.

## Decision

The application's flags `0d` select the **staging** branch, but the payload writer
does **not** enforce a TEMP-only file-ID whitelist. It resolves manifest files to
partitions and writes eligible non-boot/non-param entries. TEMP type/file ID is
tested later to choose breakpoint `UPGRADE_PENDING`, after writing and readback
verification. A future updater needs a package/partition preflight; checking only
container CRC or trusting the recovery flag is insufficient.

The success notification means this application completed its write/verify path
and requested persistence of the next state. It precedes the application's
reboot request and any execution of recovery/new firmware. It cannot prove the
next boot works, or even that breakpoint/property stores succeeded.

## Selected application path

`10066828..10066834` masks internal flags with3 and compares1. Actual flags `0d`
therefore branch to `10066878`: store overall breakpoint2 (`WRITING_IMG`), call
writer `1006586c` at `10066882`. Other flag combinations use the direct-upgrade
branch. This audit follows the observed application, not a hypothetical recovery
image built from the SDK.

Each 32 B manifest file record begins OTA state+`b4`: type byte+`0d`, file ID
byte+`0e`, destination+`10`, stored length+`14`, original length+`18`, CRC+`1c`.
The loop count is state+`a8`. Selection in `100658e4..1006598e`:

1. Call mirror lookup `100276b0(file_id)`. It scans30 ACPT slots and accepts an
   entry whose mirror predicate `100a1fde` is nonzero: entry mirror differs from
   current mirror and is not`f`.
2. If no mirror exists, require recovery bit0; retrieve current file ID
   `100a1fce`, and current/non-mirror entry `1002766c(file_id)`. Null entry or
   file ID equal to the current executable's ID logs and **skips that record**
   (`1006591a..1006592e`); this differs from pinned SDK's immediate error return.
   The mirror-found path does not perform this fallback current-file check.
3. Require original length ≤ partition `offset + size - file_offset` via
   `100a1f96`. Failure returns`-22`.
4. Set destination to partition file offset. Type1 boot and type6 param entries
   are skipped. Others enter breakpoint/write processing; no type5/ID`fe`
   restriction appears here. Verification repeats the same selection/skips.

For a manifest record with ID`fe`, the verified cached ACPT entry is `fw0_temp`,
type5, storage0, mirror0, destination`2f0000`, capacity`100000` (1 MiB).
With current mirror0 this uses fallback; with current mirror1 it uses mirror
selection. This is a conditional mapping, not a measured runtime mirror or proof
that every accepted package contains ID`fe`. Other eligible manifest IDs resolve
their own configured entries. Manifest parsing and a matching official package
remain independent prerequisites.

## Write, erase and per-file state

File state dispatch `100659bc..100659d2` has seven explicit jump-table entries.
States6/7 already written/verified skip another payload write at `10065b24`;
later verification still checks selected files. State1 starts at zero without
erase; state5 resumes saved offsets without erase; state3 resumes with erase
requested; state2 and other values start zero with erase requested. With flags`0d`, requested
erase reaches `1006550c` at `10065bda`; its return is not checked before updating
offset bookkeeping. [Preparation/erase implementation](ota-initialization-side-effects.md)
already establishes its physical driver erase path and persistence limitations.

Write-start state2 copies current file/offsets into RAM at `100b15ee..100b160c`
but does not itself save. Writing state3 updates checkpoint offsets when forced,
unchanged, or advanced by at least`80000` (512 KiB); other file states request a
save. The actual raw path forces the initial writing checkpoint before first
write (`10065dde..10065df0`), and updates offsets only after successful writes
(`10065fa0..10065fd6`). This is checkpoint ordering, not power-cut proof.

Raw payload bytes from the receive ring reach `10065f20` with
`(storage, file.offset + original_offset, buffer, output_length)` and call
`10064bdc`. For NOR type0, its loop reaches the actual device API write slot+4
at `10064d22`. Negative driver return becomes`-5`; caller checks any nonzero
storage-write return and fails. Nonnegative lower-driver results are treated as
success; no short-write accounting is visible. Compression also reaches this
write call, but its complete codec/error behavior is outside this selected audit.

After receive worker wait, the writer records state6 (`WRITE_DONE`) at
`10065d38..10065d46`, before the later readback CRC. The wait/join return at
`10065cf6` is discarded. Special file ID`0a` has additional `res_b` handling;
do not extend the plain TEMP/raw model to every resource update.

## Verification and commit order

The readback loop uses original length and destination offset. It calls storage
read `10064d74` at `100660f0`, then CRC32 `1002db10` at `100660fc`; **the read
return is discarded**. NOR read itself detects negative driver errors, but its
caller can CRC a buffer after a failed read. CRC mismatch stores file state`0f`
and retries the whole writer once; a second mismatch fails. Match stores state7
(`VERIFY_PASS`) at `1006612e`. This is stronger than input-only checks, but is
not reliable evidence of successful I/O under every failure mode.

After writer returns0 on the selected application branch:

| Actual instructions | Ordered effect |
|---|---|
| `1006688a..100668a8` | Scan manifest records: any type5 **and** file ID`fe` chooses overall state3 (`UPGRADE_PENDING`); otherwise state`0a` (`UPGRADE_DONE`). This does not re-check whether that record was written. |
| `100668e8..100668ea` | Request overall breakpoint update/store before reporting success. |
| `100668f8..100668fe` | Report final progress. |
| `10066902..1006690a` | Image ioctl`10001`, value1: Bluetooth sends opcode06, TLV01 byte1. Return is ignored. |
| `1006690e..10066912` | Change in-memory OTA state to2 (`OTA_DONE`); invoke application callback. |
| `100047de..100047f4` | Callback requests `REC_OTA_FLAG="yes"`, `OTA_UPG_FLAG="done"`, property flush; returns unchecked. |
| `100047f8..10004820` | Call pstore setter with tag2/value1, then send `main` an async message with type`11`, command2 (SDK: `MSG_REBOOT`, `REBOOT_REASON_OTA_FINISHED`). Neither request proves next boot. |

`10067b00` writes overall state byte and clears per-file bookkeeping for state3
or`0a`, then calls save `1006792c` and unconditionally returns0. Per-file update
`100b15d8` likewise ignores sync/save returns. Sync `100b14da` performs work only
for storage types2/4, and returns0 for NOR type0. The earlier
[NVRAM audit](ota-initialization-side-effects.md#actual-breakpoint-persistence-path)
traces breakpoint save to actual driver writes; this call ordering does not
establish durable atomic commit.

## Reproduce and remaining boundary

```sh
uv run tools/inspect_ota_commit.py artifacts/mapped-system/mapped-system.bin \
  > /tmp/comi-ota-commit.json
cmp /tmp/comi-ota-commit.json docs/evidence/ota-commit-2026-10-12.json
```

SHA-bound decoder emits complete selected code intervals, exact bytes/hashes,
literal references and separate switch tables; literal pools are excluded.
SDK references: [write/verify and upgrade control](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_upgrade.c#L917),
[breakpoint persistence](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_breakpoint.c#L163),
[application callback](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/ota/ota_app_foreground.c#L384).
No OTA transfer, interrupted-write experiment, completed recovery validation or
new-firmware boot occurred. The write setup additionally calls `100a52d2` with
`1000` (SDK `nvram_config_clear`); its concrete storage side effects require a
separate bounded audit before claiming all writes are inventoried here.
