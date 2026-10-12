# Actual CPU identity: Cortex-M4 r0p1

2026-10-12. Two independent connections to owned C261CF0430, FW010004,
read the fixed architectural CPUID register. Both return **0x410fc241**.
This establishes the executing core as Cortex-M4 r0p1, beyond firmware board
strings or manufacturer family specifications. Does not identify physical SoC
marking, flash wiring, FPU enablement, MPU layout or recovery compatibility.

## Evidence and decoding

[First successful capture](evidence/cpuid-first-2026-10-12.json),
[second successful capture](evidence/cpuid-second-2026-10-12.json).
[Post-experiment ordinary status](evidence/cpuid-final-info-2026-10-12.json)
reports same serial/FW, idle, charging, call mode and noise9.
Each capture retains exact commands, GATT log frames, word row, live code guards,
cached version/board, 19/19 ACKs and end frame with no pending bytes.

[Arm Cortex-M4 TRM, CPUID](https://documentation-service.arm.com/static/5fce431be167456a35b36ade),
§4.3: implementer bits31:24=41 (Arm), variant23:20=0, constant19:16=f,
part15:4=c24 (Cortex-M4), revision3:0=1. Result r0p1.
[CMSIS core_cm4.h](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/hal/cmsis/CMSIS/Core/Include/core_cm4.h)
independently defines read-only uint32 CPUID at SCB offset0, basee000ed00.
The successful actual read establishes access in this shell context; not a
claim about arbitrary unprivileged or secure/nonsecure accesses.

## Actual read implementation

[Offline code evidence](evidence/cpuid-word-read-code-2026-10-12.json),
verified mapped system SHA256
`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`:

- mdw wrapper100a18ee passes width4 to100a1884.
- Common parser parses hex address and explicit count; call100a18c4 passes
  address, width4, count1 to10025104. Default count not relied upon.
- Width4 branch100251aa..100251be issues `ldr.w r3,[fp]` at100251b0;
  stores result in local print buffer. ASCII rendering reads local copy, not
  the register again. Count1 limits target loads to one.
- Live experiment checks getter bytes and two aligned32-byte code guards
  covering wrapper and word-load branch before `dbg mdw e000ed00 1`.
- No SCB dump, bytewise CPUID access, alias fallback, register write, reboot,
  storage operation or firmware getter invocation.

## Reproduce

```sh
uv run -m rcominote.experiments.firmware_identity artifacts/NEW-cpuid.json --cpu
```

Requires new output path, owned idle FW010004. Default without --cpu retains
cached-version-only behavior. STOP cleanup follows attempted START; failed
captures are retained. One initial attempt failed in host range validation
because a code guard was unaligned; it never sent the CPUID command. Guards
were changed to aligned32-byte intervals; both subsequent captures succeeded.
Raw failed attempt remains local artifacts/firmware-cpuid-first.json.

## Consequence for BSP acquisition

An M33 reference build is not the actual CPU target. Require a Cortex-M4 BSP
matching the live `ats3085l_dvb_watch_ext_nor_max` configuration, then verify
peripherals and boot contracts. Shared tool/container code remains reusable
where independently corroborated. CPUID does not supply a backup mechanism.

Bounded public-source search this pass: GitHub repository queries ats3085l,
ats3085 sdk, cubie ats and actions zephyr; web exact ATS3085L SDK/source/board
queries. Returned ATSDialFactory is described as a watchface editor, not an
acquired BSP; M1cha/actions-zephyr-sdk reports size0. LVGL issue8197 comments
contain no technical response; issue body acquisition failed twice (EOF).
These are search boundaries, not proof no public L BSP exists.
