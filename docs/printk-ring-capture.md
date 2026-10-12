# Static printk ring: actual RAM readback and self-overwrite

2026-10-12, C261CF0430 / FW010004. Android login remains deferred.

**4096 B static log RAM readback works; whole-ring snapshots do not recover reliable prior log output.** No Flash command, storage write, reboot, USB mode change or OTA subscription performed in this capture.

## Evidence

- [Actual ARM retention analysis and simulation](printk-ring-retention.md).
- [Retained BLE frames, scoped reads and result](evidence/printk-ring-live-2026-10-12.json). Source capture SHA recorded; notifications/writes omitted as duplicate transport data. Raw capture remains ignored under `artifacts/`.
- `uv run comi diag capture printk-ring --duration 1 --out artifacts/printk-ring-first.json`
- `uv run comi diag inspect-printk-ring artifacts/printk-ring-first.json`

Profile verifies owned device and known image header, existing printk instructions, actual init call and literal words before reading context. Confirms fixed buffer `1803ee09`, capacity `1000`, active DMA branch before payload. Never follows returned pointers. Payload reads cover exactly `[1803ee09,1803fe09)` using ≤64 B requests; every emitted row must arrive within its command frame span. Context indices may equal capacity before next-operation normalization.

Actual run: 182 ACKs, final F1, all requested rows present. Before/after context reads are separate, non-atomic observations:

| Field | Before | After |
|---|---:|---:|
| read index | 2191 | 1895 |
| write index | 2203 | 1907 |
| used | 0 | 0 |
| capacity | 4096 | 4096 |
| buffer | 1803ee09 | 1803ee09 |

Flags init=1, panic=0. Payload contains help listings and this run's `logsrv: cmd(...) dbg mdb ...` messages, including reads of the ring itself. This directly demonstrates sampling perturbs the retained logs; consuming UART bytes does not erase them, but subsequent diagnostic output overwrites them. Indices cannot count total wraps or establish an atomic snapshot. A transport-complete result means all requested rows arrived, not that those rows existed simultaneously.

## Consequence for firmware extraction

Do not parse this whole-ring capture as a Flash dump, or treat stale hex text as a new read. The previous “UART-only output” obstacle now has a candidate RAM route, but the ordinary full-ring reading sequence overwrites its source.

Next experiment must bound producer output and acquire a short target slice before overwrite, associate it with that specific producer invocation, then repeat independently. Only matching complete byte counts and stable repeated raw-NOR data would establish a usable export path. Current CLI intentionally exposes a diagnostic snapshot, not `backup` or `flash`.
