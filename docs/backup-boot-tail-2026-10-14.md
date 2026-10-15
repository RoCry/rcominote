# Fixed backup-boot tail job, 2026-10-14

**Job stopped at the first0x2400 pair; new pair-verified coverage0 bytes.** First execution completed a fresh4096-byte ring download and512-byte allFF single-read candidate, including its own identity/HCI barrier. Second execution completed Actions and requested its new file, but received no offline payload before a second host HCI parameter request violated the fixed condition. Original pair/job remain failed; no full partition binary published. Existing verified `fw1_boot` coverage stays1024/4096 bytes.

## Exact plan and actual execution

Actual ACPT identifies `fw1_boot`, storage0/mirror1, NOR`[0x2000,0x3000)`,4096 bytes. Existing coverage`[0x2000,0x2400)` comes from original512-byte backup-boot prefix and separately pair-verified raw0x2200 sector. Their allFF content is not an oracle for unread addresses.

Immutable pre-I/O plan fixed six offsets`0x2400,0x2600,0x2800,0x2a00,0x2c00,0x2e00`, one fresh short BLE connection/two distinct producer executions/new files per offset. Maximum six connections/twelve producers/twelve new SD test files; first failure stops remaining slots without retries. Actual execution used only2400 connection. Five later slots contain only precreated empty host directories: no producer, file export or download executed there.

| Original2400 operation | Actual outcome |
|---|---|
| First | `ok=true`, `live_complete=true`, single-operation pair flagfalse; five confirmed Actions writes/ACKs/F1/empty pending; complete4096 bytes;32 canonical rows and unique current marker; own final identity/HCI barrier passed |
| Second | `ok=false`, pair flagfalse; five confirmed Actions writes/ACKs/F1/empty pending; exact new-nonce GET_FILE request transmitted; CRC-valid reply declares4096 bytes; retained download0 bytes, no sector or completed identity barrier |
| Entire pair/job | Pair `ok=false`, final auditfalse, after identity unavailable; job `ok=false`, `completed=[]`; new verified coverage0, no `tail.bin`/`fw1_boot.bin` assembly |

First512-byte candidate SHA256`9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d`; original ring4096 SHA256`0b0ca27c9ac95206999c33782150b958a3db95507b5204faba77913dbc83bbe0`. Independent offline prefix audit reproduced actual Actions, complete Boyi transaction, before/after identity, stable HCI condition through its checkpoint, strict freshness proof and retained bytes. Before/first-checkpoint free59592MiB and all other reported state fields match. This is a complete single read without an independent byte oracle; required second read did not finish, so it is not promoted to pair-verified coverage. Same allFF hash as other offsets does not authorize copying their bytes into this sector.

## Second parameter request interrupted download

Complete retained capture has191 records/12040 bytes, zero reported drops and no timestamp inversions. All117 host ATT packets bind exactly to retained HCI packets within each direction. Original error is `ValueError: Second parameter request/update: experimental condition changed`; final identity then failed with `ConnectionError: CoMi request did not finish; reconnect before another request`. Monitor received owned-process SIGINT and exited0. This is a transport-condition violation, not the earlier mixed-timestamp ingestion problem.

Times below are seconds from owned Connection Complete record18. Early policy explicitly normalizes initial interval48/latency4/timeout600 to min=max6/latency0/timeout500 with CE hints1/1 before initial identity/Actions; physical baseline remains preserved.

| Captured event | Time / result |
|---|---|
| Experiment request80 / Update Complete82 | 2.120723 / 4.024093; actual6/0/500 |
| First Actions | 4.177194→4.445171 |
| First GET_FILE TX130 / Boyi end | 4.446629→4.641171 |
| First identity barrier | 4.694177 |
| Second Actions | 4.696083→4.925195 |
| Second GET_FILE TX183 / declared-size reply185 | 4.926292→4.970179; exact new file declares4096, zero offline data received |
| Remote L2CAP CID5/code0x12 request186 | 5.015178; min32/max48/latency4/timeout600 |
| Host L2CAP accept188 / HCI request189 | 5.015291 / 5.015313; matching slow parameters, CE hints0/0 |
| HCI command status190 / final event191 | 5.016081 status0 / 5.023098 |

No Update Complete for request189 or disconnect appears in retained capture. Slow parameters were requested/accepted for processing; they are **not demonstrated effective**. Request189 still violates the one-request contract and prevents promotion. First early update required1.903370s after its request; a previously successful short trial cannot guarantee future sessions finish before later parameter traffic.

Static FW010004 analysis makes a cached EOF-associated slow request compatible with this chronology: first EOF/stop/read-error shares speed2 handling, and second-file worker has sleep-call argument100 before fast-entry handling. This is inference from actual firmware bytes and timing, not observation of CPU flags/branch execution or proof of a universal5s timer. No device memory or firmware was changed to suppress the request.

## Preserved evidence, health and limits

[Metadata receipt](evidence/backup-boot-tail-2026-10-14.json) binds immutable plan, original job, failed pair, first checkpoint/download/sector, empty second download, full private HCI and14-file source snapshot. Original files remain unchanged; failed replay is expected rather than repaired.

| Private source relative to `artifacts/backup-boot-tail-20261014/` | SHA256 |
|---|---|
| `job-plan.json` | `35dd7791569983dc458e6c9293f9bcb03cce28180f7e4ae7a5a200e1fff8a5a7` |
| `report.json` | `78b49cfcd8d719c2992741481fe9209e44cb6c66d8814a08474dccaa5f185ce5` |
| `2400/report.json` | `1e0e0ce09f2bc48eca2c7fa553918239d6b5ae4525b04dafb9a75e1ab84d89cf` |
| `2400/session.btsnoop` | `0a16f0ac150fcd6fc162196ec438fc8eba3e5556f18fc57e68b66700b49aa67c` |
| `source-snapshot/manifest.json` | `0d8eb6661b070fbc8050499b8343d838148ba8d32013ce1e279b3c3de932863c` |

Separate later read-only health query succeeds: owned/unbound, FW010004 NOTE/idle/charging/battery100/free59591MiB. It does not replace original failed session's after-barrier or promote its pair. Current Ubuntu scratch accounting: **54 download-confirmed files + one current device-declared4096 file with unverified content/zero received payload + one historical possible file**, maximum56. Second file is not merely possible and was actually requested. No automatic deletion occurred.

Offline replay explicitly refuses both failed originals:

```sh
uv run python - <<'PY'
from pathlib import Path
from rcominote.experiments import boot_tail_job as J
job = Path("artifacts/backup-boot-tail-20261014")
image = Path("artifacts/mapped-system-20261012.bin")
for replay, directory in [(J.replay, job), (J.pair_replay, job / "2400")]:
    try:
        replay(directory, image)
    except ValueError as error:
        print(f"Expected rejection: {error}")
    else:
        raise AssertionError("Failed original promoted")
PY
```

No missing bytes, old prefix or assumedFF padding assembled. Public evidence contains metadata only: no complete private ring/report/HCI/device-info/audio inventory or candidate/full-partition binary published. Remaining pair-unverified range stays`[0x2400,0x3000)`, six512-byte sectors. This result establishes neither complete partition, full4MiB NOR backup, sustained scaling, flashing nor restoration. Evidence preparation performed no device action or original-file modification.
