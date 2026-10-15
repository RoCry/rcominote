# Fresh boot0 NOR→SD chain, 2026-10-14

Owned idle CoMi FW010004 completed a fresh **512-byte raw NOR offset0 read** through `dbg fread spi_flash 0`→printk ring→new SD4096 file→complete Boyi download. All32 consecutive sixteen-byte rows match the independently acquired boot0 oracle: SHA256`72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec`. This establishes the complete guarded chain for this fixed sector; it does not acquire the full4MiB NOR or prove restoration/flashing.

| Phase | Actual result |
|---|---|
| Original `context` | Service-discovery timeout110; zero ATT writes/Actions/SD writes; final state equal. Original remains failed. |
| New `context-b` | Fresh28-byte sample, four confirmed Actions writes/ACKs, F1, empty pending; rd=wr1284, used0, capacity4096, buffer`1803ee09`, init1/panic0. No failed payload reused. |
| New `baseline` | New SD4096 file, four Actions ACKs/F1; complete4096-byte download. Full private ring contains one complete current nonce/dump marker and no NOR rows. |
| New `boot` | Exact fixed producer followed by new ring export; five Actions ACKs/F1; complete4096-byte download, unique current marker, boot0 status and32 continuous rows; decoded512 bytes equal oracle. |

Seven previously acquired live XIP guards were revalidated against the pinned complete mapped system image, with original Actions/state evidence and the read-only handler's original write-parent receipt. Fresh context→baseline→boot receipts form a hash-bound parent chain. Three new non-audio SD test files retained; cumulative45 including earlier42. No automatic deletion. All phase state comparisons remained equal, including reported free59593MiB; filesystem writes were expected and separately accounted for.

Both4096-byte downloads used the same bounded profile: captured fresh owned-peer central connection, original45ms interval/latency0/timeout500; one HCI LE Connection Update requested min=max6, latency0, timeout500, **both CE hints1**; actual Update Complete status0/interval6 preceded download and remained valid through its end. Interval6 means7.5ms; timeout500 means5s; CE hint1 means0.625ms. This is a combined interval/CE-hint profile, not an isolated interval-only comparison or general reliability guarantee. Complete retained HCI captures have116 records each and zero reported drops; private replay rejects reconnects, second updates, truncation and altered receipts.

The raw NOR observation is separate from mapped-system XIP bytes. Fixed boot0 `fread` already existed; the new result completes its live ring→SD→full-download route that previously stalled at3852/4096 bytes. No arbitrary NOR offset, NOR write, ROM entry, helper execution, reset or firmware installation occurred.

Both original captures waited for their55s hard timeout. This is not a scalable throughput measurement. Subsequent monitor cleanup signals only its held sudo child withSIGINT, retaining the55s timeout fallback; full parse/hash/parameter gates remain mandatory. A separate no-device sudo→timeout→dummy Bash trial flushed its signal trap and exited0 in0.0043s (`artifacts/owned-monitor-stop-20261014/report.json`). Later [two independent raw offset4200 trials](sd-nor-offset4200-live-2026-10-14.md) also verified actual btmon early-flush/exit0 plus complete HCI gates and recovery-raw[512:1024] oracle agreement. This closes the known nonzero-offset gate; no unknown-sector batch follows automatically.

## Evidence and limits

[Pinned receipt](evidence/sd-nor-interval-live-2026-10-14.json), SHA256`34ccb6c8345f8afdc8939c11b6a8bc414db1cbb5283e29d9fed52109f55cf447`, binds25 retained private files. [Safe samples](evidence/sd-nor-interval-live-2026-10-14/) total2198 bytes: context28, baseline current marker81, boot status+rows1968, producer marker40, boot current marker81. Oracle reuses first512 bytes of existing public [boot raw4096](evidence/boot-complete-2026-10-12/raw.bin); no duplicate sector binary published.

No complete private ring/report/HCI capture, recording list or unrelated/stale ring data is published. Selected HCI parameter packets expose only link/parameter metadata. Public safe spans independently reproduce the32-row sector and selected parameter gates; they cannot establish absence of rows in the unpublished baseline, full-ring uniqueness or absence of omitted HCI updates. Those claims require the separate full private audit.

```sh
uv run tools/verify_sd_nor_interval.py docs/evidence/sd-nor-interval-live-2026-10-14.json
uv run tools/verify_sd_nor_interval.py docs/evidence/sd-nor-interval-live-2026-10-14.json --private-root .
```

First mode uses stdlib and tracked prerequisites only; replays the existing compact guard bundle, context, selected parameter bytes, markers, status/rows and independent oracle. Second mode additionally hashes25 original files and runs existing project semantic validators over complete Actions traces, full identity/state, all guards, fresh parent chain, full rings and complete HCI captures. It runs those validators through the installed project `uv` environment without sync. Both modes are offline, perform no device access and do not reconstruct missing/private bytes.
