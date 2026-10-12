# LARK NOR initialization writes status registers

2026-10-12. Static analysis of pinned47608B zephyr LARK adfus.bin;
SHA256 `ee57bd899a2b2623d9e9d3b5d8fa7c970ada8df717e69c122c8ce19be3d6f8d8`.
**Do not use unmodified helper initialization as a read-only backup primitive.**
The successful path attempts write-enable06, then write-status01, before any
host storage-read command. No helper was executed on CoMi.

[Previous candidate/selection audit](lark-helper-candidate.md) establishes
is→NOR constructor→driver init0101416c; it is not inferred from a function name.
[Instruction evidence](evidence/lark-nor-init-2026-10-12.json) retains complete
initializer and selected transfer/wrapper regions, raw bytes and literals.

```sh
uv run tools/inspect_lark_helper.py \
  /path/to/action_technology_sdk/zephyr/tools/prebuilt/lark/common/bin/adfus.bin \
  --initialization
```

## Data and call flow

Addresses use configured base01010000; target execution unobserved.

| Instructions | Effect |
|---|---|
| 01014296..010142a6 | Read status05 into stack+0c, then read status35 |
| 010142a8..010142bc | If35 result nonzero: replace stack word with `(status35 << 8) & ~0x4000`; length2, opcode01; call01013f1c |
| 01014312..0101431a | If35 result zero: overwrite stack word with0; length1, opcode01; branch to same call |
| 01013f1c..01013f3c | Preserve payload pointer/length; call01013edc with address0/address-length0; afterwards poll ready |
| 01013edc..01013f12 | May poll05 first; call01015304 with r1=0, then transfer01015084 with WRITE_DATA flag8 |
| 01015304..0101530e | r1=0 selects opcode06; nonzero selects04; tail-call command-only transfer |
| 010150d0..010150dc | Send command byte via01014e20 |
| 01015116..0101514c | Flag8 selects data-transmit branch; payload/length passed to01014e70 |
| 01013ec8..01013eda | Poll05 until bit0 clear, no bounded retry count in this routine |
| 010142c0..010142e6 | Read05/35/15 and print; no comparison against requested result |
| 010142ea | Returns0 after this status configuration path |

Payload interpretation from actual little-endian instructions:

- status35=0 → `01 00` (command plus one payload byte).
- status35!=0 → `01 00 (status35 & 0xbf)` (two payload bytes).
- Original status05 is discarded in both branches. The second-byte bit6 is
  cleared in the two-byte path. Existing contents are not restored afterwards
  by the inspected initialization function.

These are command attempts implied by code, not captured SPI traffic. Successful
chip-ID/configuration paths converge here; earlier ID/probe failure may return
before writing. Do not claim every failing initialization reaches the write.

## Why these are writes, not a naming assumption

The command helper passes06 to command-only transfer; transfer stores command
byte to its local buffer and sends it through01014e20. That routine loads bytes
from host buffer and writes controller data register+8 at01014e64. Status payload
uses the WRITE_DATA branch to01014e70; length1/2 takes its≤16-byte
branch01014ee4 back to the same byte-transmit routine, bypassing DMA. In contrast the read branch at0101527a
loads controller+0c into the destination buffer. The direction is independently
visible in the binary.

Pinned source corroboration (not source identity proof):
[`zephyr/drivers/flash/spinor/spinor.c`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spinor/spinor.c)
defines01 as write-status and35 as read-status2; its write-status wrapper also
uses write-data then ready polling. The helper's exact status rewrite above is
established from helper instructions, not copied from current source.

## Other effects and boundaries

- Default NOR info at fileb9b8 selects controller40028000. Initializer changes
  reset/clock/pin-related MMIO and probes chip ID. Not a passive attachment.
- Capacity-dependent path01014400 sendsb7 when info+24 bit1 is set, then reads
  status05/35/15. This is separate from the unconditional status rewrite on
  successful initialization; capacity threshold does not guard that rewrite.
- No array erase/program command is needed to demonstrate the read-only claim
  false. This pass does not prove absence of all other nested side effects.
- Persistence and bit meaning depend on exact NOR part/revision; cached CoMi
  JEDEC ID alone is insufficient to assert which settings would change or
  whether a specific write would be accepted. No claim of actual damage.
- Polling and return0 do not establish successful preservation or recovery.

## Route decision

Retain LARK as offline architecture/transport reference. Reject **unchanged
LARK init followed by rs** as a read-only backup procedure. Do not merely omit
init and issue rs: storage selection, RAM state and bus configuration are then
unestablished. A future read-only helper requires matched hardware/ROM transport,
an audited initialization path that preserves NOR state, and independent
readback/recovery evidence. Editing this blob alone would not supply those.
