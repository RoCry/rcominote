# LARK transport variants: UART helper versus USB helper

2026-10-12. Offline binary audit of pinned SDK; no target execution or device I/O.
[Evidence](evidence/lark-transport-2026-10-12.json) / reproduction:

```sh
uv run tools/inspect_lark_transport.py \
  /path/to/action_technology_sdk/zephyr/tools/prebuilt/lark/common/bin
```

The tool requires both exact SHA256 values, captures startup/transport setup,
callbacks, configuration tables and descriptor bytes. Paths and source commit
are embedded in output. Helpers remain external SDK artifacts.

## adfus.bin uses UART

47608B, SHA256 `ee57bd899a2b2623d9e9d3b5d8fa7c970ada8df717e69c122c8ce19be3d6f8d8`.
This is the helper previously inspected for NOR status writes; its active
startup path does not establish a USB host protocol.

- Entry01010000 uses startup literal01012541; main01012540 invokes platform
  init010124b0 then protocol loop01012610(2,0).
- Platform init010124d6..de passes `(0,1,115200)` to01013108. That initializer
  matches first two bytes of48-byte rows, selects row `(0,1)` at file770.
  Row controller40038000, divider40038010, pin configuration addresses
  40068074/40068078. These are artifact settings, not CoMi pinout instructions.
- Loop zeroes32-byte context, explicitly writes context+3=0; sets RX010131d5,
  TX01013225, ioctl01013251. Callbacks access selected controller+0c status,
  +4 RX and+8 TX directly. Divider setup and these data flows establish UART
  selection independently of `_u` filename convention.
- Protocol8 initialization at010147a8; loop calls01014d38 with mode2, timeout50.
  Mode2 invokes0101a540 framed connection wait. Context+3=0 selects framed
  branches in previously inspected read/write routines; raw16-byte command
  header is an inner protocol, not sufficient standalone UART framing.
- Entry's 115200 default differs from packaging bootloader.ini's2Mbaud;
  do not equate boot/ROM/helper baud rates. Negotiation can later change speed.

## adfus_u.bin sets different callbacks and USB descriptors

48792B, SHA256 `0aefabef3c09374b170d9a784bc5983ab6a1c904e945556de27e1fcb31b8847d`.
Main010125c0 invokes010126f0 rather than the UART loop.

- Initializes USB state via010147e0. Context+3=1; callbacks RX01014931,
  TX01014a05, ioctl01014a55, distinct from UART callbacks.
- USB setup assigns descriptor pointers from literal pool01014828 onward:
  device01010d84, config01010d96, qualifier01010db6,
  other-speed config01010dc0, string01010de0.
- Device descriptor bytes at file0d84: USB version0110, EP0 max64,
  **VID10d6/PID10d6**, bcdDevice0100, one configuration; string indexes all0.
- Config table declares one interface, two bulk endpoint descriptors:
  **81 IN /01 OUT**, max packet64 each.
- Separate other-speed config table declares **01 OUT /82 IN**, max packet64.
  This discrepancy is retained as evidence; it is not a justified host endpoint
  choice. Need actual selected descriptors/USB path before claiming usable pipes.
- Session loop checks USB state via01014a18 and attempts negotiation modes1
  then2 (timeout50) through01015068 before command dispatch01014a88.
  Setting context+3=1 does not prove a host may skip all negotiation.

These are public-helper descriptors. They do not establish ROM download-mode
VID/PID, CoMi's physical USB connectivity, or helper acceptance. The same IDs
appearing in vendor INF support lists now have an artifact-specific connection,
but remain unobserved on the owned device.

## Exit boundary

UART helper command `af` handler01014cdc accepts selector≤2, acknowledges,
waits header+8 plus30 through delay helper, closes selected storage, then:
selector0 returns6; selector1 calls01013010; selector2 calls0101301c.
The loop breaks on6, invokes0101474c and protocol close010147bc, then returns
to main which **loops forever at0101255a**. Therefore selector0 is not evidence
of automatic restoration/reboot into the original app. Other selectors' full
hardware effects and the USB variant's corresponding exit remain unproven.
No exit command was sent.

## Route correction

Use adfus_u.bin for subsequent USB-side analysis; keep adfus.bin as UART/driver
reference. Do not assume offsets, status-write behavior or storage callbacks are
identical across these files merely because much code looks similar. Next
resolve USB-specific initializer and negotiation/exit path, then compare actual
ROM entry/host framing. Existing rejection of unchanged adfus.bin init+rs as a
read-only backup stands; A subsequent [independent USB storage/exit audit](lark-usb-storage-exit.md)
confirms its own status writes and non-restoring selector0 exit.

[USB handshake follow-up](lark-usb-handshake.md) identifies63636363 preamble, connected/opened gates and protocol8. This is helper-level USP, not ROM upload framing.
