# Backup boot block1: one complete read, pair incomplete

Later [independent early-session pair](dual-unknown2200-2026-10-14.md) completed this address and added512 verified bytes. The reconnect attempts below retain their original outcomes; none was promoted by the later success.

2026-10-14, owned idle CoMi FW010004. Actual CRC-valid ACPT entry2 `fw1_boot` spans`[0x2000,0x3000)`. Its first512 bytes at2000 already had independent double coverage; the new target was only`[0x2200,0x2400)`. No extrapolation from the old all-FF prefix.

| Original acquisition | Actual result |
|---|---|
| `first` | NOR producer and SD-write attempt, five ACKs/F1; subsequent Boyi connection failedENOSYS38 before interval update/download. File creation not independently confirmed. Overallfalse remains unchanged. |
| `first-b` | Separate new producer/file/connection; complete4096-byte ring, current nonce/status/32 continuous rows, HCI interval6/CE1 and final state passed. Parsed512 bytes allFF, SHA256`9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d`. No independent oracle. |
| `second` | Actions connection failedENOSYS38 before any producer/SD write. No second sector sample. Overallfalse. |

**One complete single sample, zero newly pair-verified bytes.** Existing prefix equality does not supply a second acquisition or independently validate this offset. `sd_nor_unknown.verify_pair(first-b,second,image)` correctly rejects the failed second receipt. Full single-acquisition semantic replay passed; no report was reclassified or data filled/patched.

[Compact status receipt](evidence/backup-boot-block1-2026-10-14.json), SHA256`0b9a318a125fc7594ef994bed5c20bcbd0f9db3e2b5c1f943a39cd0f419febb6`, pins all three original report hashes and the actual ACPT/prefix basis. Raw rings, complete reports and HCI remain in`artifacts/backup-boot-block1-20261014/`; public receipt exposes only status and hashes. This is a recorded audit, not a self-contained public full-payload verifier.

Private offline replay of the complete single receipt:

```sh
uv run python - <<'PY'
from pathlib import Path
from rcominote.experiments import sd_nor_probe as P
directory = Path('artifacts/backup-boot-block1-20261014/first-b')
image = Path('artifacts/mapped-system-20261012.bin').read_bytes()
report, _ = P.load(directory)
handler = Path('artifacts/live-sd-handler160-20261013')
guards = P.validate_guards([Path(r['directory']) for r in report['guards']], image, handler)
print(P.previous(directory, P.Phase.backup, guards, image, handler))
PY
```

One new SD scratch file independently confirmed by download, plus one earlier SD-write attempt without a download; current Ubuntu sequence48 confirmed, potentially49. Boyi's audio list omits these scratch files, so unchanged lists cannot confirm creation or absence; ACK/capacity delta alone does not prove the first file exists. Second failed before writing. Final reported state idle/NOTE/FW010004/charging; free59593→59592 during first write attempt, then59592 unchanged. No NOR/MMIO write, ROM entry, reset or code execution.

Repeated connection failures stop this method's unknown-target trials. Next experiment: one connection, single notification dispatcher, sequential Actions→Boyi, fixed boot0 and4200 targets with independent existing oracles. This tests setup cost and protocol switching before resuming unknown dual reads; no bulk NOR operation follows automatically.

Offline failure localization: `first/session.btsnoop` (950B, SHA256`852e26de3d43342f0ea19fc340a6954cf611ca4cfdd3c6149a4fc0bcdaed8059`) contains successful LE Enhanced Connection Complete onhandle2048, then LE Read Remote Used Features completion status`0x3e` (Connection Failed to be Established), before anyATT data. The socket'sENOSYS is therefore downstream of a captured link-setup failure, not evidence that Python failed to parse payload. Failed/successful advertisements were−61/−58dBm; these two samples do not identify RF/controller/peripheral cause. The second Actions-connection failure lacks a comparable capture and is not attributed from the first alone.
