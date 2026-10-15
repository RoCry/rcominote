Safe original ring slices; no complete private ring/report/HCI or recording list.

| File | Bytes | Physical ring span |
|---|---:|---|
| `first-status-rows.bin` | 1971 | `[1848,3819)` |
| `first-producer_marker.bin` | 45 | `[3839,3884)` |
| `first-dump_marker.bin` | 81 | `[3905,3986)` |
| `second-status-rows.bin` | 1971 | `[137,2108)` |
| `second-producer_marker.bin` | 45 | `[2128,2173)` |
| `second-dump_marker.bin` | 81 | `[2194,2275)` |

Total4194 bytes. Both32-row sequences independently decode to the same512 raw bytes at fixed NOR0x4200. Receipt pins every sample and complete recovery oracle; safe spans alone do not prove full-ring uniqueness or absence of omitted HCI events. Test paths are exclusively new non-audio scratch files.
