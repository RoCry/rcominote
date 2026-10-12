# USB LARK helper handshake: preamble, connection, protocol open

2026-10-12. Static evidence from pinned zephyr LARK adfus_u.bin48792B,
SHA256 `0aefabef3c09374b170d9a784bc5983ab6a1c904e945556de27e1fcb31b8847d`.
[Instruction evidence](evidence/lark-usb-handshake-2026-10-12.json).
No USB traffic, helper upload or target execution.

```sh
uv run tools/inspect_lark_transport.py \
  /path/to/action_technology_sdk/zephyr/tools/prebuilt/lark/common/bin \
  --handshake
```

## Observed state transitions

USB loop010126f0 checks USB state, then attempts mode1 with argument50 via
01015068; if unsuccessful, attempts mode2 with50. Only a successful gate sets
local session state and reaches dispatcher01014a88. Link-state checks remain
inside the command loop. Treat numeric timeout arguments as implementation
parameters, not measured wall-clock guarantees.

Mode1 →0101aa56:

1. If context+2 bit1 already set, returns success.
2. Otherwise calls RX callback for exactly4 bytes, timeout argument1, retries
   with decremented budget (caller subtracts1 from supplied50 first).
3. Requires little-endian word63636363: four consecutive ASCII `c` bytes.
4. Calls flush0101af74, then connector0101aa14 three times. Connector's flag
   guard means these are not necessarily three transmitted connect packets.
5. Returns connected bit1. Wrapper then calls protocol-open0101ab72.

Connector0101aa14 sends control command63 with zero payload length through
0101ab98; success sets connected bit1, retry field5, timeout field500, then
reports protocol information via0101aa04 (command72). Reporting details and
full transfer/CRC grammar are not covered by this pass.

Open0101ab72 sends command6f with four-byte little-endian payload containing
context protocol byte (configured8). On successful response it sets opened
bit2 and context+3=1. Wrapper sets separate session-ready byte only on success.
This is a control handshake layered below the16-byte gf/ri/rm/is/rs header.

Mode2 →0101a9b8 receives a framed header, requires `(first_halfword & ~0x0f00)
==1`, dispatches control command and tests opened bit2. Thus peer-initiated
control negotiation can also open the session; it is not another ROM protocol.

## Received command table independently decoded

Actual switch table filead20 has17 entries for62..72, plus separately tested52:

| Command | Handler address | Observed meaning |
|---|---|---|
| 63 /c | 0101ad42 | Respond, receive response, set connection flag, optionally report info |
| 6f /o | 0101ad62 | Compare payload first byte with configured protocol8; set opened bit2 on match; otherwise status1f |
| 64 /d | 0101ad32 | Respond and return15 |
| 62 /b | 0101ad84 | Respond then ioctl1 with payload word |
| 69 /i | 0101ad9a | Respond with context state byte+6 |
| 70 /p | 0101ad9e | Set TX/RX limits from two payload halfwords |
| 72 /r | 0101adaa | Respond success |
| 52 /R | 0101adb4 | Respond, delay using payload+1, call01012ee4(7), then loop |

Other table entries target default rejection0101adca. The reboot-shaped52 path
is not a verified recovery method. Payload validation and side effects must be
fully audited before any live host implementation.

## Primary-source corroboration and differences

Pinned source directory:
[application/bt_watch/src/libsrc/usp](https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/libsrc/usp).
`usp_protocol_inner.h` documents host preamble32 consecutive63 bytes, receiver
magic63636363 and ASCII command definitions. Actual helper confirms a4-byte
comparison, not a requirement to receive exactly32. `usp_connect.c`,
`usp_open.c`, `usp_command.c` explain naming, but are not substituted for bytes.
In particular source OPEN copies transparent_bak; actual receive-open region
here sets opened bit without that source assignment. Do not copy the source
state machine unchanged and claim helper compatibility.

## Scope boundary

This protocol runs **after the helper is executing**. It does not explain how
ROM receives/verifies/starts that helper, which download mode CoMi exposes,
which USB descriptor is selected, or how official firmware is restored.
Unmodified NOR initialization still writes status registers. Retain handshake
as host implementation evidence, not permission to run an updater/backup probe.
