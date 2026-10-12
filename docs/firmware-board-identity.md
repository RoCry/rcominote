# Actual firmware board identity: ATS3085L lead

2026-10-12. Owned C261CF0430, FW010004. Two independent BLE log sessions read
only instruction-derived code/SRAM ranges. No Flash read, erase/program, reboot,
OTA subscription, getter execution or arbitrary pointer chasing.

**Firmware-declared board: `ats3085l_dvb_watch_ext_nor_max`.**
Version name: **`1.04_2602030950`**. This is substantially narrower than the
previous generic Actions/LEOPARD hypothesis. It identifies the shipped firmware's
board-name contract, not the physical chip marking or exact PCB pinout.

## Why these bytes are relevant

[SHA-bound actual getter/consumer instructions](evidence/firmware-identity-getter-2026-10-12.json)
from complete validated mapped-system:

1. `100a0b00..100a0b0a` loads word at `01000004`, adds`2e8`, returns pointer.
2. `10027798..100277a6` calls this getter, passes returned source, fixed destination
   `1800ecb8`, length`80` to copy call `100b9652`.
3. Remaining getter fetches8 B of version configuration. Missing configuration
   takes a setter path at `100277d0`; successful fetch replaces destination words
   +4/+8. **We did not call this getter**; only its code and source SRAM were read.
   Board bytes at+`50` are outside those two overwritten words.
4. Diagnostic printer `10027812..10027826` prints strings at+`10` and+`50`.
   OTA comparator `1006652e..10066546` compares current+`50` with candidate board
   name before the version decision. This ties the board string to acceptance,
   rather than identifying an unrelated build-path string.

Both fresh sessions first verified exact16 B getter bytes at `100a0b00`, then
read boot SRAM `01000000..01000010` and required pointer`01000040` at+4.
Therefore source is **`01000328`**, directly after the independently CRC-verified
[ACPT table](partition-readback.md). Reads of `01000320`/64,
`01000360`/64 and `010003a0`/16 cover the128 B source, with bounded alignment
padding. Any changed getter/pointer aborts before parameter reads.

## Independent observations

[First capture](evidence/firmware-identity-first-2026-10-12.json),
[second capture](evidence/firmware-identity-second-2026-10-12.json): all128 source
bytes agree. SHA256:
`4e9d0059884cd1294c258d7f5bc43e5975641963d043c4d41eba420af0d22dc1`.
Both sessions have complete expected ACK counts, final log-end frame and no
pending fragment. Parsing requires every declared row, not ACK-only success.
Board is source+`50`; version name source+`10`. Raw128 B and all frames retained.

```sh
uv run -m rcominote.experiments.firmware_identity artifacts/NEW-identity.json
uv run tools/inspect_ota_version.py --identity artifacts/mapped-system/mapped-system.bin
```

The experiment has no arbitrary address option and refuses an existing output
file. It checks serial/FW/idle state, leaves log mode through STOP and retains
failed evidence instead of claiming incomplete text succeeded.

## SDK/tool implications

Pinned SDK contains no exact matching board string in the inspected tree.
A bounded exact-name public web search returned no results; that is not proof
that no matching SDK exists. However, its
[audio demo external-NOR packaging configuration](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/app_demo/audio_demo/boards/ats3085s_dev_watch_ext_nor/fwimage.cfg)
explicitly says `CHIP_NAME = "ATS3085L"`, despite the directory's `ats3085s` name.
Several other demo configurations use the same value. Thus neither directory
suffix nor the earlier ATS3089 example should be used alone to choose hardware.

Next: prioritize matching ATS3085L vendor board/configuration and production
package, compare actual peripherals and startup settings. A matching OTA board
string is one parser requirement, not a safe-board substitution recipe. Exact
silicon, USB ROM identity, compatible helper, full backup and restore remain
unverified. [Public helper initialization audit](helper-nor-initialization.md)
shows why even an apparently read-only helper workflow needs compatibility and
initialization evidence first.

Follow-up [manufacturer PDFs and reference comparison](ats3085l-primary-sources.md) identify ATS3085L as M4F; the public LEOPARD/M33 build is not a matching default. Subsequent [live CPUID reads](cpu-identity.md) confirm Cortex-M4 r0p1.
