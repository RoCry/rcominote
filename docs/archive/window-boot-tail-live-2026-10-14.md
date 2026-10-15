# Fixed five-slot fw1_boot job: one verified sector, then boundary failure

2026-10-14 actual device job stopped at raw `0x2800`. The independently completed `0x2600` pair adds **512 unique verified bytes**; cumulative `fw1_boot` coverage is **2048/4096 bytes**, `[0x2000,0x2800)`. Original aggregate job and `0x2800` pair remain failed. No assembled partition was produced.

[Machine-readable evidence](../evidence/window-boot-tail-live-2026-10-14.json) · [actual verified sector2600](../evidence/window-boot-tail-live-2026-10-14/sector2600.bin).

The immutable plan fixed five offsets (`2600,2800,2a00,2c00,2e00`), ten distinct scratch nonces, maximum five connections/ten producer executions, and fail-stop without retry/resume. Preparation verified original early2200, windowRAM, successful2400 and historical2000 parent chains before hardware authorization. Captured initial state had to equal the preceding actual completed pair’s final state before any Actions. Independent offline review verified plan/hash/nonce targets, predecessor state and chronology. One complete checkpoint exists; final three host directories are empty precreated directories.

| Actual slot | Download / fresh parse | Final original result | Coverage increment |
|---|---|---|---|
| `0x2600` | Two complete4096-byte captures, separate producers/nonces,32 fresh rows each, second requires first dump; post-download barriers complete | Full Actions/ATT/HCI/window/state audit and pair replay pass |512 bytes |
| `0x2800` | Both4096-byte captures, fresh512 candidates,32 rows, strict previous dump, six complete parameter transactions and both barriers | Final exclusive Actions/download boundary audit fails; operation flags and pair remain false |0 |
| `0x2a00,0x2c00,0x2e00` | Not executed | Job stopped after2800 failure |0 |

Both executed connections have startup FAST settlement, first normalization/SLOW, mandatory second FAST, second normalization/SLOW: **six complete transactions, zero pending**. Captures bind every ATT packet exactly within direction:2600 has255 monitor records/148 ATT packets/18648 bytes;2800 has256 records/149 ATT packets/18710 bytes. Owned monitor SIGINT was sent; both monitor exits were0. Per-download interval6/latency0/timeout500 and settlement-before-identity boundaries were independently checked; original2800 full audit still rejects the gap below.

For2800 second operation, Actions span ends at ATT index115, while Boyi download starts at116. Intervening zero-based ATT[115] is one RX `cmd0x0F`,20-byte unsolicited device-status event; frame length/version/CRC pass. Parsed charging,battery,USB mode,NOTE mode,noise reduction,voice control,indicator light,segment duration and backlight equal second before/after52-byte info. Event-only `power_off_duration` and `usb_connected` are retained as status fields; the device-info parser exposes no equivalent fields. This is a legal status notification; unchanged mapped state does not satisfy current strict requirement `actions_end == download_start`. No original flag was changed or failed pair promoted. Successful component checks establish retained candidates, not verified2800 coverage.

Successful2600 pair’s512 raw storage bytes are allFF and equal across two independent producers. Public `sector2600.bin` was copied byte-for-byte from **this job’s actual2600/first/sector.bin**, after checking length512 and every byteFF. It was not substituted from a previous allFF sector. The pair has no independent content oracle. Separate address/producer provenance, not hash equality, establishes its location.

Verified earlier1536-byte prefix remains separately grounded:

- `0x2000..0x2200`: pinned historical archive,22 distinct non-atomic windows,32 confirmed rows with at least two sources per row; existing analyzer’s complete report equals pinned report and512-byte prefix.
- `0x2200..0x2400`: original successful early pair’s actual first sector; full parent replay.
- `0x2400..0x2600`: original successful composer-window pair’s actual first sector; full parent replay.

Immutable plan’s complete historical-prefix summary equals fresh offline verification. Source snapshot pins107 files and its manifest; every archived length/hash and current source equality was checked at review. Exact original job,pair,capture,plan,checkpoint and selected source hashes are in receipt. Full HCI,ATT,rings,device info and file inventory remain private.

Final actual identity is owned/unbound, FW010004, NOTE/idle, charging, battery100, free59590MiB.2600 ends at59591MiB;2800 second export decreases integer free report by1MiB within bounded SD-export allowance. Four new scratch files were independently downloaded: Ubuntu cohort62 download-confirmed, one previous device-declared without offline download, one historical possible file, maximum64. Files were retained.

Remaining unverified range is `[0x2800,0x3000)`, four512-byte sectors including failed2800. No `tail.bin` or `fw1_boot.bin` was assembled. Observations do not establish full-partition/full-NOR backup,recoverability,flashing,physical worker exit or hidden-cache clearing.

Offline reproduction from repository root, with private originals available:

```sh
uv run python - <<'PY'
from pathlib import Path
from rcominote.experiments import boot_prefix_evidence as B
from rcominote.experiments import window_nor_job as W
from rcominote.experiments import window_nor_probe as N
root = Path('artifacts/window-boot-tail-20261014')
image = Path('artifacts/mapped-system-20261012.bin')
assert B.verify()[1]['distinct_sources'] == 22
assert N.replay(root / '2600', image)['nor_range'] == [0x2600, 0x2800]
for replay, directory in ((N.replay, root / '2800'), (W.replay, root)):
    try:
        replay(directory, image)
    except ValueError as error:
        assert 'Original' in str(error)
        print('expected original failure:', error)
    else:
        raise AssertionError('failed original evidence promoted')
PY
```
