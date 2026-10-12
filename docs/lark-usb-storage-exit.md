# USB LARK helper: status writes and non-restoring normal exit

2026-10-12. Offline analysis of **adfus_u.bin**, not transferred offsets from
UART helper.48792B, SHA256
`0aefabef3c09374b170d9a784bc5983ab6a1c904e945556de27e1fcb31b8847d`.
[Evidence](evidence/lark-usb-storage-exit-2026-10-12.json) fixes source/path,
actual bytes, tables and decoded regions. No device operation.

```sh
uv run tools/inspect_lark_transport.py \
  /path/to/action_technology_sdk/zephyr/tools/prebuilt/lark/common/bin \
  --usb-storage
```

## Independent storage-selection chain

16-token table file0e06, pointers0e28; `is`→01014c5c,
`af`→0101500c. All addresses use configured01010000 base.

- is selector0 calls010125e0→01013e9c constructor.
- Constructor sets NOR object table01010a24, driver table01010b50;
  tables give NOR init01013e2c and driver init01014200 respectively.
- NOR initializer calls driver init via slot0 before chip-ID read; its success
  path is not just RAM setup. Driver body4200..445c retained in evidence.
- 0101432a reads05,01014338 reads35; if35 nonzero,01014340..4350 replaces
  payload with `(status35 << 8) & ~0x4000`, then sends opcode01 length2.
- Zero35 branch010143a6..43ae supplies zero payload, opcode01 length1.
- Write-status01013fb0→write-data01013f70; latter calls01015634 with r1=0
  selecting06, then calls transfer010153b4 with WRITE_DATA flag8.
- Original status05 is discarded. Two-byte form clears second-byte bit6.
  As with UART, these are attempted commands, not measured NOR state changes.
  Persistence/acceptance on the actual device remains unknown.

**Consequence:** changing from adfus.bin to adfus_u.bin does not remove the
status-write objection to using an unchanged helper for read-only backup.
No array erase or program command is required to disprove that assumption.

## Ordinary exit does not restore the application

Actual USB `af` handler0101500c:

1. Accepts selector0..2 from header+2; invalid selector reports1.
2. Reports success, waits header+8 plus30 via01013008, closes selected storage
   via virtual slot18 if an object exists. Storage-close effects not fully audited.
3. Selector0 returns6. Selector1 calls01013110; selector2 calls0101311c.
   Neither additional selector is authorized as a recovery recipe by this audit.

USB main loop at01012732..2738 dispatches and breaks on6. It clears session
state01014a7c, closes protocol01014aec, then USB cleanup0101483c (interrupt/state
changes, controller bit manipulation and deeper cleanup callbacks). Loop returns
to010125d6, which branches to itself forever. The visible caller does not hand off to application vectors; deeper cleanup
callbacks are not fully audited. No claim that a later watchdog/external reset
could not occur.

Selector1's observed01013110 writes5f to literal-selected MMIO then loops;
full hardware/reset semantics remain unverified. Selector2 has additional power
and delay calls; do not infer safe recovery from these command names.

## Remaining transport boundary

[USB descriptor and startup audit](lark-transport-selection.md) remains valid:
actual ROM USB identity, upload handshake, chosen endpoints and original-app
restoration still unobserved. Keep USB protocol work offline until these and
non-writing initialization are established; do not patch out one write and
call the result a safe backup helper. Full firmware backup is still unavailable.
