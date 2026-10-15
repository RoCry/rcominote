# Context

Vocabulary for the CoMi Note firmware project. Glossary only; no implementation detail.

## Terms

**CoMi Note** — the recorder under study, Seeyon model `SY-N2A3F-5H2`. One unit owned; it is the daily-use device and the current experiment target.

**SoC** — Actions (炬芯) ATS3085L, Cortex-M4. Identified from CPUID and firmware board name, not from a chip marking.

**NOR** — the external 4 MiB SPI flash holding all firmware. Distinct from the **SD** (64 GB card holding recordings).

**Physical bytes / raw** — bytes as stored in NOR. The firmware reads some partitions through a transform; **mapped** bytes are the decoded view. Only raw bytes count as backup.

**Partition** — one of the 18 ACPT entries covering NOR: boot0/1, param0/1, recovery, system, user_rw, sdfs, nvram, logbuf, evtbuf, coredump, res_a, sdfs_k, temp, runtimel.

**Known slice** — a raw byte range already captured over BLE and independently repeated. Used as the oracle for a full dump.

**Full dump** — a 4 MiB physical read of the NOR by an external programmer or SWD. Two independent reads must be identical. Milestone **M1**.

**Restore** — writing a full dump back and the device booting normally. Milestone **M2**.

**RAM run** — executing own code loaded into SRAM via SWD without touching NOR. Milestone **M3**.

**Own firmware** — a bare-metal M4 image booted from NOR in place of the vendor image. Milestone **M4**. Scope (a): clocks, GPIO, UART, OLED; no audio or BLE.

**BLE CLI** — `uv run comi`, the host tool speaking the vendor BLE protocol (status, recording, file download, settings).

**BLE page export** — the retired method of extracting NOR 512 B at a time through the firmware debug shell. Evidence only.

**ADFU** — Actions' USB/UART ROM download mode. Not attempted; requires a helper that modifies NOR state.

**Helper** — a RAM-resident program the ROM loads to drive storage during ADFU. Vendor helpers write NOR state registers.

**BSP** — board support package for the exact SoC/board. No public M4 BSP for ATS3085L exists; the public SDK targets the M33 ATS3085S/3089.

**Mapped system image** — the 927 632 B decoded system partition used for offline analysis.

**Minimal image** — the self-built 948 B ACTH-wrapped M4 program that passes the vendor recovery checker offline. Not yet executed on hardware.
