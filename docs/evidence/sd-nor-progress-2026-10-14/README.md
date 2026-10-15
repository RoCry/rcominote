# SD / NOR experiment progress, 2026-10-14

Compact evidence replay; no device access. From repository root:

```sh
uv run tools/verify_sd_nor_progress.py published docs/evidence/sd-nor-progress-2026-10-14.json
uv run tools/verify_sd_nor_progress.py original docs/evidence/sd-nor-progress-2026-10-14.json .
```

`published` needs only tracked files: pinned receipt, these bytes, two earlier SD-bootstrap samples, and `minimal-image-2026-10-13/original-system.bin.gz`. It verifies image SHA, seven fixed code guards, historical context structure/parent binding, exact RAM tails, and the unique missing interval `[756,1000)` in the 3,852-byte warm partial. It never fills that interval. `original` additionally checks 36 retained private input hashes; it does **not** rerun the package semantic audit or independently decode HCI.

Original reports were audited offline with `sd_nor_probe.validate_guards`, `validate_actions`, `previous`, `sd_nor_postcheck.validate_original`, `sd_bootstrap.verify_state`, and the retained HCI follow-up parser. The receipt records that audit; portable replay covers compact facts and published byte oracles. Hashes bind the private reports/HCI without publishing their contents.

| Evidence | Result / boundary |
|---|---|
| Seven XIP guards | Exact image matches; full Actions four ACKs, F1, empty pending. Header32 and handler160 reuse earlier published bytes. Read-only handler report binds its original write parent's Actions trace. Five new guards total 220 bytes. |
| Original printk-code104 | Transfer exact; original report stays failed because capacity fell 1 MiB. Retrospective bounded capacity comparison does not rewrite history. Accepted guard uses independent `printk-code-b`. |
| Context28 | Original transfer complete, final info failed with ENOSYS. Derived postcheck performs only later identity verification; copied 28 bytes are historical, **not a new context sample**. |
| Baseline4096 | Actions complete; Boyi retained only 3,852 bytes. Private printk payload omitted; no full oracle, missing offset unknown, baseline incomplete. |
| Warm existing RAM file | Tail128 exact; subsequent full read short at 3,852/4,096. Unique deletion `[756,1000)` applies only to this known-code RAM oracle. No reconstructed output. |
| Existing RAM tail512 | All 512 bytes exact; original overall report remains failed because final info returned ENOSYS. |
| Independent later identity | Equal to baseline/warm/tail512 pre-state with no capacity change. Separate observation binds original report hashes; does not retroactively complete transfers or alter failed reports. |

New raw bytes: five guards220 + historical context28 + RAM tail512 + warm tail128 + warm partial3852 = 4,740 bytes. RAM samples match known firmware code. Baseline download, recording lists, frame/monitor bodies and full HCI remain private. HCI comparison established 17 observed notifications totaling 3,852 bytes identical to the baseline partial; it does not establish eight 512-byte frames or an over-air loss location.

Mapped XIP/RAM reads are not raw NOR dumps or recovery backups. Boot/NOR producer phase was not attempted: incomplete baseline prevents advancing the gate. No patching or concatenation, and no general 512-byte transfer reliability claim.
