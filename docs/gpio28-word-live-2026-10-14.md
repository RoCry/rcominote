# GPIO28 CTRL single-word observation: 2026-10-14

Owned idle CoMi FW010004. One executed `dbg mdw 40068074 1` returned **`0x00001805`** through nonce-associated logsrv text→selected slot6→new SD512→complete Boyi download. Successful original `trial-connect-c` passed seven confirmed Actions writes/seven ACKs/one F1/empty pending, complete global4/metadata32/slot512 downloads, exact unique marker→word row withinL406, ASCII-column consistency, and final identity/state comparison. Capacity59595 MiB and all other reported state fields equal.

| Invocation | Actual outcome |
|---|---|
| `trial` | Characteristic discovery timeout, lastTX`08140019000328`; zero ATT writes, no CCCD/Actions/mdw/SD dump, no raw files; poststate equal |
| `trial-connect-b` | Offline `FileNotFoundError` from a mistyped guard path; no before-info/ATT/device operation/raw files; not a device experiment |
| `trial-connect-c` | Second radio connection, first executed GPIO observation; complete success |

Original failed reports remain unchanged and hash-bound in [compact evidence](evidence/gpio28-word-live-2026-10-14.json); declaring commands in a report does not establish wire execution. This round retained seven new non-audio SD test files: two mdw guards, pointer/context preflight, three successful trial snapshots. Total31 including earlier24; none deleted.

## What the observed word supports

Actual normal-firmware setter `100219f8..10021a34` computes address`(1001a001+pin)<<2`; GPIO28 therefore maps to`40068074`. It performs ordinaryLDR32 at`10021a14`, clears`7f00` and`3f`, ORs supplied mode, thenSTR32 at`10021a20`. First actual early-init table entry`100bbf2c` is `{28,4125}`. Thus early configuration is `(old & ~0x7f3f) | 0x4125`, preserving mask-excluded bits. [Complete actual-byte evidence](evidence/board-pinmux-analysis-2026-10-12.json), [initializer and override boundary](board-pinmux-evidence.md).

Observed`0x1805 & 0x7f3f = 0x1805`, **different from early mode`0x4125`**. Field names below follow pinned public [LARK header](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/cfg_drv/pinctrl_lark.h#L14-L27); [UART0 definitions](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/cfg_drv/pinctrl_lark.h#L231-L237). Actual bytes establish address/mask/table; public source supplies semantic names.

| Field / mask | Observed1805 | Early4125 |
|---|---:|---:|
| MFP low5 bits / `001f` | 5, consistent with LARK UART0 | 5 |
| SMIT bit5 / `0020` | 0 | 1 |
| Pull field / `0f00` | `0800`=`GPIO_CTL_PULLUP`, bit11 | `0100`=`GPIO_CTL_PULLUP_STRONG`, bit8 |
| PADDRV bits12..14 / `7000` | level1 | level4 |

Drive level is an encoding, not a measured mA rating. Same-repository LEOPARD headers differ in control-register offset/drive width; they must not replace this actual address formula and LARK comparison. Register value/function definition does not demonstrate UART electrical output, baud rate, routing, pad voltage or a CoMi physical contact.

[Independent static follow-up](evidence/gpio28-remux-static-2026-10-14.json) identifies an actual later table`100bb4f4={(28,1805),(29,1805)}`. Conditional path`100226a0..100226a4` applies it through`100a086e`→the same setter, so a concrete firmware path can produce the observed configured bits. A preceding table supplies1817, separated by an unexpanded indirect call`01000871`; SDK sleep entry/return code has similar structure. This does not prove this path executed before the sample or is the sole writer. Actual UART initializer`1002fb84` itself has no direct GPIO store/pinmux call, so the result is not attributed to that initializer. Portable replay byte-checks all nine published static regions against the pinned full image without re-disassembly.

Actual recovery implementation separately saves both GPIO28/29 controls, temporarily configures a bitbang loopback, and restores both before comparing/returning (`11000c46/48`, `11000cc8/cca` in [decoded recovery](evidence/recovery-complete-2026-10-13/recovery-decoded.bin)). It restores prior words, not a guaranteed4125; this does not prove the present boot executed that path. Official ATS3085C reference schematic identifies U2 pin49 as UART0_TX/GPIO28 and pin50 as UART0_RX/GPIO29, routed toJ27.1/.2. These are reference-socket observations; CoMi package/PCB/contact mapping remains unverified. [Acquisition and reference-board boundaries](actions-official-tester-2026-10-13.md); reproducible typed schematic decoder: [inspect_testboard_pinmap.py](../tools/inspect_testboard_pinmap.py).

No silicon manual has established absence of read-clear or other read side effects. Ordinary LDR/RMW usage is software evidence for a readable configuration word, not that hardware guarantee. Only this address was targeted; no other GPIO/PMU/NOR, firmware write or recovery operation follows from this result.

## Evidence and replay

Fresh preflight follows all five context guards, two slot-layout guards, and new `100a18ee/10` wrapper plus`100251aa/24` actual word-load window. The latter contains targetLDR32 at`100251b0`; width4/count-one and stack-copy ASCII handling were previously audited in [word-handler evidence](evidence/cpuid-word-read-code-2026-10-12.json). FreshP=`180111fc`, stream=`18011254`, rd=wr206; selected index6, slot=`1800b5b0`. Trial metadata has onlylen6=406 and drop0. Marker body`[138,191)`/slot`[146,199)` precedes word row body`[195,250)`/slot`[203,258)`.

[Public samples](evidence/gpio28-word-live-2026-10-14/) total214 bytes: mdw guards34, fresh preflight36, trial global4/metadata32, exact test-path marker53, word row55. Complete private slot512 SHA256`b041a727b40775916c42c3cbd4a8a9664a0e57bca909798d0142381a714e84fe`; word row SHA256`2fbc0f6a1a5ebe881462de29f7bbf686c47d5dddf3fb377bfb8d8970fde86bdf`. No other body/stale-tail bytes, recordings, lists, complete reports or logs/HCI published.

```sh
uv run tools/verify_gpio28_word.py docs/evidence/gpio28-word-live-2026-10-14.json
uv run tools/verify_gpio28_word.py docs/evidence/gpio28-word-live-2026-10-14.json --private-root .
```

First command uses tracked files only and no device operation; second additionally hashes16 retained private inputs. Tool reuses prior slot-bundle replay and checks pinned receipt/image, code guards, failed-invocation accounting, chronology/parent hashes, small snapshots, exact selected spans/ASCII and actual early-pinmux blocks. Complete original private semantic audit used `gpio_word_contract.validate_parents`, `commands`, `validate_actions`, `verify_payload`, plus `downloaded`/`same_identity`. Compact replay records but does not rerun that ATT/state/full-slot uniqueness audit; selected spans cannot independently establish full-slot uniqueness.

Metadata/body copies are non-atomic and commands emit logs; pointer equality was checked afterward. Result does not prove current allocator ownership, that slot stayed partial, general512-byte transfer reliability, raw NOR access or a flash/recovery route.
