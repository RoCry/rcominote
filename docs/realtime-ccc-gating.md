# Shared CCC gating: disabling realtime can suppress command replies

2026-10-12. Offline audit of validated actual FW010004; no device I/O in this audit. [Prior realtime route and image identity](realtime-source.md). **All three Boyi notify CCC callbacks overwrite the same two subscription bits; every outgoing Boyi channel checks these bits before channel selection.** Therefore realtime CCC disable can prevent subsequent command replies even while command notifications remain subscribed at the BLE client.

## Exact shared state

Mapped-system927632 B at`10000000`, SHA256`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`. Code disassembled with Capstone5.0.6. Code ranges below exclude following literal pools; full instructions for realtime callback/writer and initializer binding are retained in [realtime source evidence](evidence/realtime-source-2026-10-12.json). Newly audited command/offline callbacks and attribute finder addresses permit reproduction directly from this image.

Initializer`1000a6e8` creates one stream-private object. Callback installation:

| Notify channel | Private CCC pointer | CCC RAM attribute | Install instructions | Installed Thumb callback |
|---|---|---|---|---|
| e5e2 command | +1c | `180017b0` | `1000a812..18` | `1000a4d5` |
| e5e3 realtime | +28 | `180017ec` | `1000a81a..20` | `1000a471` |
| e5e4 offline | +34 | `18001828` | `1000a822..28` | `1000a40d` |

These are the same vendor stream. Factory parameter fields +14/+20/+2c at`100ba98c/998/9a4` contain these three CCC pointers; initializer copies them into the private fields above. Each install loads the attribute's userdata pointer at+0c and stores cfg_changed at userdata+2c.

Attribute finder`1000a324..1000a388` walks five registered stream slots at`18045fb0`. For each stream it loads stream+54 private state and matches incoming attribute against private+14,+18,+1c,+38,+20,+24,+28,+2c. Thus command and realtime CCC attributes resolve to the **same stream/private state**. Its omission of offline value/CCC (+30/+34) is relevant separately: this exact matcher does not establish successful resolution for offline CCC. The callback's existence/installation alone is insufficient to claim that offline CCC toggling has the same live effect. Command and realtime CCC are both explicitly matched.

Each callback loads stream+54, then the **same byte private+40**, and applies the same BFI:

| Callback code range | Load byte | Bitfield overwrite | Store byte |
|---|---|---|---|
| command`1000a4d4..1000a526` | `1000a516` | `1000a51a`: `bfi r2,r5,#1,#2` | `1000a51e` |
| realtime`1000a470..1000a4c2` | `1000a4b2` | `1000a4b6`: `bfi r2,r5,#1,#2` | `1000a4ba` |
| offline`1000a40c..1000a45e` | `1000a44e` | `1000a452`: `bfi r2,r5,#1,#2` | `1000a456` |

`r5` is the cfg_changed callback's second argument. Instruction semantics: `flags = (flags & ~0x06) | ((ccc_value & 0x03) << 1)`. This is an overwrite, not a per-channel set/clear or reference count. A zero realtime CCC value clears bits1..2, retaining bit0 and all other bits.

## Why command replies stop

Outgoing helper`1009eb16..1009ebf8` preserves channel in sb (`1009eb24`). Its loop starts:

- `1009eb2e` loads private+40.
- `1009eb32..34` requires flag bit0; otherwise returns bytes sent.
- `1009eb36..3a` tests **mask06**; if zero, returns bytes sent.
- Only later does it select channel0 at`1009eb8a..9c`, channel1 at`1009ebaa..bc`, or channel2 at`1009ebdc..ee`.

Consequently this subscription gate applies to command channel0 as well as realtime channel1. With no earlier bytes sent, closed gate returns0 (`1009ebd4..d8`). The command response builder`1000a888` loads the same stream from context+150 (`1000a8fc`), supplies channel0 (`1000a900`), and calls extended stream-write (`1000a906`). Thus subscribing e5e2 once does not protect command responses against a later e5e3 CCC disable.

The low-level BLE attribute's own CCC state and transport resources still matter. Opening this common gate does not guarantee delivery on an unsubscribed channel. No evidence here establishes malformed reply bytes, incoming command rejection, a disconnect, or recording corruption; this path alone explains **response suppression**.

## Live correlation and remaining proof

A bounded live probe on the owned FW010004 device kept one connection and left e5e2 command CCC untouched. [Retained live report](evidence/realtime-ccc-live-2026-10-12.json):

| Realtime notification operation | Next device-info05 observation |
|---|---|
| enabled | Valid device-info response, idle |
| disabled | No matching response within3 s |
| re-enabled | Valid device-info response, idle |

The report was read from `artifacts/realtime-probe/ccc-report.json` during this audit; final retained copy is published by the parent investigation. This enable→disable→enable outcome matches the static prediction. The protocol has no transaction identifier: repeated05 replies cannot independently distinguish a new reply from a delayed earlier reply. Thus the final response proves delivery resumed, not unique ownership by the final05 request; the static common-state gate supplies the mechanism. No over-air CCC write capture or private-state RAM snapshot was collected by this audit.

Earlier short-recording capture additionally found command responses while realtime remained subscribed, followed by device-info timeout after realtime unsubscribe. Retain original capture separately for audio/payload claims. Enabling a different CCC remains a separate hypothesis, especially given the offline CCC finder omission.

Client lifecycle implication supported by static evidence: retain e5e3 subscription for the BLE connection lifetime after enabling it; closing a capture should detach its local byte consumer, then disconnect once all work finishes. Explicitly disabling it and continuing command requests requires a verified gate-repair procedure. This is a client workaround for observed firmware coupling, not proof that every device revision behaves identically.
