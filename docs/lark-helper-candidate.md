# LARK: closer M4 artifacts, not an approved downloader

2026-10-12. Offline pinned SDK source/binary analysis; no USB operation, helper
execution or device write. Follow-up to [actual Cortex-M4 CPUID](cpu-identity.md).

## Why this changes the next investigation

Existing public SDK is not exclusively LEOPARD/M33. It retains a **LARK M4
engineering template, boot images, helpers and drivers**, although matching
`soc/arm/actions/lark` source directories are absent from both OS trees.
This is a partial artifact set, not an acquired buildable CoMi BSP.

Source root: [pinned Actions SDK](https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk).
Paths below relative to that root:

- `bootloader/tools/mdk_clang/soc/lark/template.uvprojx` names ARMCM4_FP,
  Cortex-M4, FPU2. Generic template RAM20000000/ROM0 is not a measured CoMi map.
- Both `*/tools/prebuilt/lark/common/bin/fw_product.cfg` select helper load
  **01010000**, run01010001, protocol switchYES. Actual CoMi boot's ACTH
  load01010000 agrees; this does not prove helper RAM range/ROM compatibility.
- LARK bootloader.ini selects UART0/mfp1/2Mbaud, PSRAMmfp3, ADFUgpio21.
  These are reference settings, not CoMi entry instructions.
- LARK mbrec load01010000, unlike LEOPARD2ff70000. Public mbrec3616B is
  **not identical** to actual decoded CoMi boot3672B. Do not replace it.

[Artifact inventory](evidence/lark-artifact-inventory-2026-10-12.json) retains
paths, sizes, SHA256, literal configs and boot headers. Two source trees contain
**different same-name helpers**:

| File under tools/prebuilt/lark | zephyr | bootloader |
|---|---|---|
| common/bin/adfus.bin | 47608B, ee57bd89… | 12820B, 4a2ff5a6… |
| common/bin/adfus_u.bin | 48792B, 0aefabef… | 13896B, c2b5a010… |
| common/bin/fw_product.cfg storage-ID RAM | 01022000 | 01018000 |
| bin/mbrec.bin | 3616B, b038beb7… | identical |

Therefore even `LARK adfus.bin` is insufficient artifact identity. The audit
below selects only zephyr's47608B helper. Bootloader helper not audited.

## Actual command and NOR read paths

[Reproducible instruction evidence](evidence/lark-helper-2026-10-12.json):

```sh
uv run tools/inspect_lark_helper.py \
  /path/to/action_technology_sdk/zephyr/tools/prebuilt/lark/common/bin/adfus.bin
```

Tool verifies exact SHA256, fully decodes selected regions excluding literal
pools, and resolves PC-relative literals. It never executes the target.
Addresses below add configured01010000; runtime placement unverified.

- Dispatcher01014758 reads16B, compares halfword token against16 entries at
  file0d88, branches through table0dac; short header returns4, unknown token5.
- Tokens: gf ri rm wm is ic si rc rs ws es cf rr sf rx af.
- `rm`0101489c reads length+4/address+8. Below40000000 passes memory directly
  to output0101a75c; above that copies chunks≤4000 into local buffer first.
- `rs`01014bdc reads length+4/storage offset+8; selected storage virtual slot4
  fills buffer, then output0101a75c transmits chunks≤4000. Storage read return
  remains unchecked: transferred bytes alone do not prove a valid backup.
- `is`0101492c closes old storage via slot18, selects constructor, calls init
  and post-init slot14. Selector0 takes01012564→01013e2c NOR constructor.
- NOR table file0a28: init01013dbc, read01013c34, post-init01013cfc (returns0).
  Constructor explicitly selects **in-image driver table at01010b54**. Unlike
  inspected LEOPARD constructor, this does not fetch driver table from ROM1a4.
- Driver table init0101416c, read0101402c. NOR read wrapper delegates slot14,
  clears offset bit31 if set. Driver calls01013ec8, selects3/4 address bytes
  from info+24 bit1, then calls01015310; returns0 without propagating an error.
  Nested bus routine and initializer still require audit before execution.
- NOR initializer writes1800 to MMIO pair resolved in retained literals, calls
  driver init and chip-ID reader, may switch address mode for capacity>24.
  In-image driver init begins peripheral reset/configuration writes. This is
  **not a passive read session**, even when the eventual command is `rs`.

## Next decisive work

Prioritize LARK's complete initialization/USB framing paths and compare ROM
entry/SoC register expectations to actual CoMi boot/application. This moves
analysis to a closer architecture/address lineage and exposes driver bodies
that were missing behind LEOPARD's ROM interface. It still supplies no observed
CoMi USB identity, accepted helper, safe init, full backup or restore proof.
Do not promote LARK to physical chip identity or flash/upload this helper.
