# Actual ROM ADFU: conditional state restoration and return

2026-10-13. Fixed ROM code reads on owned idle C261CF0430/FW010004;
no launcher call, mode entry, reset, MMIO write or helper execution.

[First capture](evidence/rom-flow-first-2026-10-13.json),
[second independent connection](evidence/rom-flow-second-2026-10-13.json)
agree byte-for-byte on336B at1900..1a50. Both check the previously verified
launcher pointer and128B launcher SHA before reading its fixed direct callees.
[Raw bytes](evidence/rom-flow-2026-10-13.bin), SHA256
`0dda0a4532813627df78b506bfa1f7e5dc8ae4b9886cc32173265592defcaa67`.
[Bounded analysis](evidence/rom-flow-analysis-2026-10-13.json) excludes literal
pools and adjacent functions from the three decoded regions.

## Condition1908: threshold comparison, not a known timeout duration

The [launcher](actual-rom-adfu-entry.md) records457c() once inr6, then loops
calling1908(r6). Actual1908..192e:

1. Read word[01000908]. If nonzero, return0 immediately (launcher keeps waiting).
2. Otherwise call457c() and2980(). Compute unsigned32-bit difference between
   current457c return and saved entry value.
3. Return1 iff2980 return≤difference; otherwise return0.

A timer/timeout interpretation is plausible; the later fixed reads below resolve
the two callees, but units remain unknown. No claim of milliseconds, finite
configured timeout, wrap-safe timing, or guaranteed exit. State word can inhibit this branch.
Do not read or change it simply to force an outcome.

## Save1934 and restore1980

Save function sets low nibble of MMIO40004100 to5, saves four values in RAM
base01000010, calls2cce(01000908,0,40) with buffer-clear-shaped arguments,
then branches2b70. Those two callee bodies are unread:

| MMIO source | Saved RAM slot | Restored by1980 |
|---|---|---|
| 40001004 | 01000010 | 40001004 |
| 400010b4 | 01000068 | 400010b4 |
| 400010c4 | 0100006c | 400010c4 |
| 40000000 | 01000014 | 40000000 |

Restore1980 first calls2760(11),2578(11), then copies those saved values back,
sets40004100 low nibble to2, and **returns through saved LR** (`pop {pc}`).
The launcher restores its own saved registers/LR before tail-branching1980.
Therefore this visible path returns to launcher's caller, unlike the public
helper main's permanent loop. Register functions and earlier calls remain
unassigned; do not label them as USB reset/clock routines without more evidence.

This proves a static return path, not successful normal-app restoration.
Actual boot caller continuation, unknown callee side effects, enabled timeout
and behavior after an interrupted/invalid upload remain unresolved. A tailcall
return is not equivalent to reboot, nor proof that damaged boot is recoverable.

## Reproduction

```sh
uv run -m rcominote.experiments.firmware_identity artifacts/NEW-flow.json --rom-flow
uv run tools/inspect_rom_flow.py docs/evidence/rom-flow-2026-10-13.bin
```

Fixed profile reads table rows, verifies launcher prefix, then reads five64B
blocks plus16B. It does not accept arbitrary addresses or automatically traverse
new pointers. Both captures retain complete rows/ACK/end evidence. Existing
[normal device-info check](evidence/rom-flow-final-info-2026-10-13.json) after
captures remained same FW, idle and charging.

## Timing follow-up; further micro-audits parked

[First](evidence/rom-timing-first-2026-10-13.json) and
[second independent capture](evidence/rom-timing-second-2026-10-13.json) both
complete39/39 ACKs and end frame; their two64B fixed blocks agree. The existing
experimental profile adds `--rom-timing`; no additional hardware read is needed
to reproduce the interpretation from these retained captures.

| Code | Actual instruction interpretation |
|---|---|
| `2980..298e`, literals `2990..299b` | Return60,000,000 if word[01000074]==1, otherwise5,000,000 |
| `4570..4576`, literal4578 | Read32[4000c108], invert all bits, return |
| `457c..4584` | Call4570, logical shift right5, return |

Thus the sampled value is `(~read32(4000c108) & 0xffffffff) >> 5`, a27-bit
quantity. The caller subtracts in32 bits; no wrap-safe-duration claim follows.
Counter clock/rate remains unknown: **do not rename the two thresholds “60s/5s.”**
No MMIO access occurred: these are decoded ROM instructions, not live counter reads.

The verified [boot](boot-complete.md) also does not establish a return-to-app
continuation: `01010414` restores its caller LR before tail-branching to
`0101022c`; that wrapper restores LR and branches through ROM19c. A ROM return
therefore preserves the earlier caller's continuation, not an explicit normal
application handoff. That earlier caller context remains unresolved.

Per [current route priorities](archive/research-routes.md), park clock units, individual
callee roles and earlier caller context. Revisit together from matching platform
documentation or a justified bounded ROM corpus. For a future enumeration-only
trial, independently established reset/power-cycle escape may replace a fully
resolved software return chain; exact timer units alone cannot establish safety.
No mode entry, helper execution, full backup or restoration has been verified.

## Parked independent-reset lead

Offline follow-up on the hash-bound [actual system](init-audio-board-evidence.md):
registered `onoffkey` initializer1003d608 calls100a09e2(1), then100a09ba(4).
The former clears mask180000 and writes1<<19; the latter clears maske00000
and writes4<<21, through the same context-derived register pointer. LEOPARD's
[PMU source](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_pmu.c#L436-L511)
has corresponding function/press-time update shapes. This is an actual configured
bitfield lead with reference-derived semantics, **not verified hard reset**.
Value4 is not a demonstrated reset duration; reference8/12s uses a different bit.
Physical button association, duration and validity after ROM entry remain unknown.
Park here; no further callee capture or mode experiment follows from this lead.

Context-pointer resolution from the same retained system closes the register
address: getter`10021a38..10021a62` initializes context`1800bf48`, with
`ctx+40=40004100`; both updates access`[ctx+40]+8`, hence`40004108`.
This matches the recovered LARK PMU layout's`SYSTEM_SET_SVCC` offset108.
Helper`100a0a0a..100a0a26` also replaces a zero bits19..20 field with1.
LEOPARD source assigns1 to reset,2 to restart; this bit meaning still comes
from a different M33 platform, not a matched LARK silicon specification.

Owner reports one button, long press for normal power on/off. Follow-up2026-10-13:
no separate forced-reset/reset button seen; manual supplies no forced-reset
procedure. This does not prove absence of a PMU long-press reset function, but
closes the anticipated manual instruction as an available escape contract.
Normal firmware shutdown does not demonstrate an independent physical reset
after ROM entry. No button operation or live PMU-register snapshot was performed
for this follow-up: an enabled bit alone cannot prove button routing, hold time,
reset scope or retention after the ROM changes clocks/power state.

The supplied [three manual photographs](manual-2026-10-13.md) now provide
direct documentary evidence: normal power on/off requires≥3s; separate power
button and recording slider are shown. No forced reset, ROM/download entry or
recovery procedure appears in those photos. This corroborates the owner's
report within the supplied pages, without establishing an independent escape.
