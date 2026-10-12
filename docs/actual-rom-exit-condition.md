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

A timer/timeout interpretation is plausible, but the two callee bodies and
units are not yet known. No claim of milliseconds, finite configured timeout,
wrap-safe timing, or guaranteed exit. State word can inhibit this branch.
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

Next: inspect457c/2980 to resolve count units/configuration, and trace boot's
caller continuation. Only then consider whether a bounded mode-entry experiment
could have a credible exit path. Full backup and restoration remain unproved.
