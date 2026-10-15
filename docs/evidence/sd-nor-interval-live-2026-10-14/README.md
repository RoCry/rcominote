Safe original byte slices only. No full ring/report/HCI or recording list.

| File | Bytes | Original source |
|---|---:|---|
| `context.bin` | 28 | Fresh context-b download |
| `baseline-dump-marker.bin` | 81 | Baseline physical ring `[1158,1239)` |
| `boot-status-rows.bin` | 1968 | Boot physical ring `[1608,3576)`; boot0 status +32 continuous rows |
| `boot-producer-marker.bin` | 40 | Boot physical ring `[3596,3636)` |
| `boot-dump-marker.bin` | 81 | Boot physical ring `[3657,3738)` |

Total2198 bytes. Current paths refer exclusively to non-audio test files. Receipt pins all hashes. Independent512-byte oracle uses existing public boot raw4096 prefix. Complete retained private4096-byte rings and HCI captures are required to recheck uniqueness/absence claims; safe spans do not establish those claims alone.
