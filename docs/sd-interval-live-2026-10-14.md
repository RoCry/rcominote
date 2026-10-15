# One complete RAM4096 download under observed interval6 policy

2026-10-14, owned idle CoMi FW010004. **One existing RAM test file downloaded completely:4096 bytes, exactly equal to the independently pinned image slice.** HCI verifies one fresh owned connection, one parameter-update request accepted/applied before download, and unchanged applied condition through its completion. No new SD file, Actions command, recording, NOR operation or reconnect.

| Evidence | Actual observation |
|---|---|
| Baseline connection, record18 | handle2048, interval36×1.25ms=45ms, latency0, timeout500×10ms=5s |
| Unique request, record77 | min=max6 (7.5ms), latency0, existing timeout500; CE-length hints1/1 |
| Command Status / Update Complete | records78/79, bothstatus0; update interval6/latency0/timeout500 on samehandle |
| Full transfer | oneoffset0 request;4096-byte declarationrecord83,18 owned data notificationsrecords84..101, explicit endrecord102 |
| Data / identity | `full.bin` and HCI data both SHA256`35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b`; complete52-byte pre/post device-info equal, capacity59593MiB |
| Cleanup | disconnectrecord114 after download-end timestamp; not a data-phase disconnect |

Data notifications total`16×244 +24 +168=4096`; no repair or joining. Only Boyi serial/bind/info queries, oneexisting-file download and finalqueries occurred. Original file-creation parent retains complete fourACK/F1/empty-pending Actions and valid state; its original3852/4096 download failure remains failed. This later read does not rewrite that history.

This was an **observed interval6/latency0/current-timeout/CE-hints1 policy trial**, not a pure interval-only single-variable experiment. CE hints were requested onwire; Update Complete confirms interval/latency/timeout, not actual connection-event duration. Baseline was45ms, not15ms. Older failed downloads differ in connection/history/conditions; they do not form a controlled15ms→7.5ms comparison. One success does not establish causality, reliable bulk downloading or a complete firmware backup route.

The unsuffixed invocation failed on stdinEOF before authorization/capture (`ValueError: Expected one nonempty password line`): zero device operations, no HCI/download artifact. `...-b` was the **first actual hardware trial**, not a retry after a device trial. Both original reports remain unchanged and hash-bound. SD residue unchanged; this trial only read `/SD:/RECORDER/Call-rc6ae65544fe.mp3`.

[Compact receipt](evidence/sd-interval-live-2026-10-14.json) publishes only six necessary owned-controller/connection/parameter/cleanup records:3/18/77/78/79/114,90 packet bytes, original record numbers/timestamps and decoded fields. No full HCI, complete private report, device-info payload or transfer body published. Oracle is reconstructed from tracked full image`[dd500,de500)`; existing public firmware bytes need no duplication. Full private capture:115records/8554bytes, SHA256`da5319b1cc6c83fd48d8676046d68a00a04849c6a4abc951644cd6235635ef94`; successfulreport SHA256`fa0c07e18122186f62a969ad9fea491dc286adad0347dbee5f8bceb8ab2071ad`.

```sh
uv run tools/verify_sd_interval.py docs/evidence/sd-interval-live-2026-10-14.json
uv run tools/verify_sd_interval.py docs/evidence/sd-interval-live-2026-10-14.json --private-root .
```

Public mode needs tracked files only: checks pinned receipt/parsers, image/oracle, raw parameter-event decoding/order/applied gate, existing parent Actions/state summaries and invocation accounting. It cannot prove full-capture uniqueness or replay4096 HCI bytes from six selected events alone. Private mode additionally hashes five originals and replays complete HCI epoch/update gate, ACL/ATT reassembly, Boyi CRC/declaration/data/end, exact4096 oracle, both identities/state, original parent Actions/state and zero-I/O failure. Existing stdlib parsers are reused; no device tools imported or called. Corrupted evidence fails; historical partials remain incomplete.
