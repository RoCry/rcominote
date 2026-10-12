# Offset-zero NOR sector through repeated log windows

2026-10-12, C261CF0430 / FW010004. **Recovered all512 B returned by the actual `dbg fread spi_flash 0` handler: all32 rows observed at least twice, without conflicts.** This does not establish whole-device backup, programming or recovery.

## Acquisition

The [short-tail experiment](printk-nor-tail.md) used a full help listing to flush its context read. New profile sends eight fixed `kernel version` queries instead. This reduces output written into the same static ring before sampling. It does not disable logging, alter hooks or change firmware settings.

`--ring-window` accepts0..10 only with `printk-nor-tail`. Each window reads256 B starting at `(observed_write_index − 256 − 192×window) mod4096`;64 B overlap avoids losing entire hex rows at window boundaries. All addresses remain within the previously verified static ring. Each window executes a new fixed offset-zero Flash read, rather than trying to preserve a whole4 KiB ring snapshot. Header, code/descriptor, flags, buffer/capacity and every memory row remain checked.

```sh
# Separate sessions, two passes; fresh output paths required.
for pass in first second; do
  for window in {0..10}; do
    uv run comi diag capture printk-nor-tail --ring-window "$window" \
      --duration 1 --out "artifacts/nor-overlap${window}-${pass}.json"
  done
done
uv run comi diag assemble-nor-sector artifacts/nor-overlap*-first.json \
  artifacts/nor-overlap*-second.json --out artifacts/nor-sector-zero.bin
```

`assemble-nor-sector` is offline. It rechecks original captured rows via `printk_tail.inspect`, ignores cached parsed text, and only accepts the fixed producer. Input aliases merge transitively by file SHA, original capture SHA or device/timestamp, preventing copied/reformatted records from counting as independent reads. Conflicts remain visible even among duplicate sources. Binary output requires every aligned row0..1f0 to have one value observed in at least two independent captures; exclusive-create prevents overwriting an existing export.

## Boundary bug avoided

An actual tail began `0: 5b ...`: the window had cut `1d0:` before its last digit. Accepting any hex-looking line would misassign those16 B to offset0. Parser therefore requires both CRLF boundaries inside the window and the exact eight-character offset field. It also handles actual `%2x` space-padded single-digit bytes; `%02x` parsing would incorrectly reject values below16. Partial first/last lines contribute no bytes.

## Evidence and limits

[Retained report and capture index](evidence/nor-sector-zero-2026-10-12/report.json):

- 22 distinct sessions,11 windows×2 passes; all transport/readback checks passed.
- 32/32 rows present,32/32 independently confirmed,0 missing/unconfirmed/conflicting rows.
- Output512 B, SHA-256 `72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec`.
- Sum of session notification timelines245.492 s; includes identity/guard reads and per-session overhead. This measured workflow is not yet efficient enough to assume practical full-device backup.
- Export created with the actual CLI; reassembly from retained compact evidence produces the same bytes.

 Each session retains original BLE frames, scoped command ranges and source-capture SHA; duplicate notification/write encodings are omitted in repository evidence. No F5F0 subscription, USB/ADFU transition, reset, erase or program operation is part of this procedure.

Readback proves the bytes returned by this firmware's NOR read API and dump handler. It does not independently prove physical storage mapping, absence of transformations below the API, boot authenticity or acceptance by a recovery tool. A512 B prefix is not a complete bootloader or backup. Remaining targets include mapping comparison, boot/recovery/partition/resource contents, reliable full-range export and an independently verified recovery entry/exit path.
