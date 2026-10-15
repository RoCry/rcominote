# Two known NOR reads on one actual connection

2026-10-14, owned idle CoMi FW010004. **One connection completed boot offset0, then recovery offset0x4200:** each operation used fresh SD scratch file, five actual Actions writes/ACKs, F1/empty pending, complete4096-byte Boyi declaration/data/end, exact512-byte known-sector oracle and actual post-download identity barrier. Independent `dual_nor_probe.replay` passed against full original reports, retained HCI/ATT, data and known-parent chains.

| Observation | Result |
|---|---|
| Real session proof | One initial GATT/CCCD sequence;150 ATT packets bound exactly within each direction to224 HCI records/17460bytes; no synthetic second discovery |
| Boot0 | 4096-byte ring complete; decoded512-byte sector SHA256`72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec` |
| Recovery0x4200 | 4096-byte ring complete; decoded512-byte sector SHA256`51327e9d7a7d8d4c3538c83688753b5f99735b85e981756effb63efd1dc33713` |
| Parameter policy | Baseline45ms/latency0/timeout5s; unique requestrecord126: min=max6 (7.5ms), latency0, timeout500, CE hints1/1; status127/update128 success |
| State/cleanup | Initial, two barriers and final identity redecoded from actual requests/replies; capacity59592MiB throughout, other state unchanged; owned monitor SIGINT sent, exit0 |
| Retention | Both raw rings/sectors and immediate checkpoints preserved; two new SD test files retained |

First Actions occurred **before** parameter update. Applied interval6 condition covered first download/barrier, second Actions/download/barrier and final identity. CE hints are requested parameters, not measured event duration. Single observed success does not isolate interval causality or establish scalable/unknown-address backup. Each4096-byte object is a printk ring: fixed producer, unique current marker and hex-row parsing recover the known512-byte NOR sector; ring bytes are not raw NOR bytes. These two sectors already had independent oracles: **raw coverage did not increase**.

Actual HCI timing excludes authentication/scanning wait: connectrecord18→final owned ATTrecord224 **4.069503s observed active span**; first PREPARE→final identity **1.776980s workload**. Boyi request→explicit end: **180.992ms boot**, **179.861ms recovery**. Capture contains no Disconnect Complete;4.069503s is not a closed connection lifetime. Do not divide session host `started_at`/`ended_at` by useful NOR bytes or treat transported8192 ring bytes as8192 new NOR bytes.

[Compact status receipt](evidence/dual-known-nor-live-2026-10-14.json) retains hashes, trace spans, decoded necessary parameter events and timing. Private report SHA256`0f74ac3023f5635740e214ecc9b05bc5b84153dee89c5bb8d2c3201c1c28985d`; HCI SHA256`fec7195c55d2df3ebe583a08357e54881e89f5115c5faa49ab6cab10284050ff`. Full trace, rings, device-info payloads and private audio inventory remain ignored. Checkpoints preserve each completed live prefix immediately; neither checkpoint independently includes final full-capture HCI audit. Final replay performs that audit.

```sh
uv run python -c 'from pathlib import Path; from rcominote.experiments.dual_nor_probe import replay; print(replay(Path("artifacts/dual-known-nor-20261014"), Path("artifacts/mapped-system-20261012.bin")))'
```

Replay is offline and requires retained private directory plus its original known-parent/guard chains and pinned full image. Public receipt alone is a status summary, not equivalent to full replay. No new parser or hardware operation needed.

Cumulative confirmed scratch files: **48+2=50 retained**; one earlier unconfirmed first attempt may have left another, so **at most51**. Audio-list omission does not prove scratch absence; no files deleted.

Subsequent [unknown2200 pair](dual-unknown2200-2026-10-14.md) implemented strict nearest-status/rows/producer/dump association, mandatory previous-dump anchor and failed-new-read negative tests. A failed initial session remains unchanged; a separate early6/0/500 session then completed both independent512-byte reads. Unknown sectors have no independent oracle. This historical known-target receipt still records only its original success and zero new coverage. Its six observed source files were archived byte-for-byte under private `artifacts/dual-known-nor-20261014/source-snapshot/` before shared code evolved; original receipt source hashes were not rewritten. Current complete replay of this original session still passes.

Retrospective strict audit of actual full rings passed independently; all spans below are physical-ring half-open byte ranges. Each had one current dump, the nearest exact producer, exactly one matching fread status/32 contiguous rows, exact oracle agreement, and no intervening second status/producer/failure. This validates these observations, not the still-unmodified generic parser.

| Retained ring | Status | 32 rows | Nearest producer | Current dump |
|---|---|---|---|---|
| Separate4200 first | 1848..1893 | 1899..3819 | 3839..3884 | 3905..3986 |
| Separate4200 second | 137..182 | 188..2108 | 2128..2173 | 2194..2275 |
| Dual boot0 | 1132..1174 | 1180..3100 | 3120..3160 | 3181..3262 |
| Dual4200 | 652..697 | 703..2623 | 2643..2688 | 2709..2790 |

Rows→producer gap in all four is the20-byte prefix`\r\n[logsrv][I][679]: `, not only whitespace. Future strict parsing must preserve actual producer framing rather than reject this valid prefix.
