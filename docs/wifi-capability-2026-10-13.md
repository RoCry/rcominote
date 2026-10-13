# CoMi Wi-Fi capability: chip, reference SDK, actual device

2026-10-13. Host-only source/image inspection; no new device commands. Root reviewed manufacturer material and shipped artifacts; Astra reviewed reference SDK. [Machine evidence](evidence/wifi-capability-2026-10-13.json).

**External Wi-Fi is a concrete Actions reference design, but CoMi Wi-Fi hardware and a usable fast-transfer path remain unconfirmed. Do not assume a large recording implies a second radio.**

Later exact-model follow-up: [radio index and decision](wifi-radio-model-2026-10-13.md)
finds SY-N2A3F-5H2 listed as Bluetooth equipment/module in a third-party approval
index. Primary certificate remains unverified. Together with actual firmware,
this favors treating original-firmware Wi-Fi as unavailable, rather than assuming
a hidden switch. Owner confirms Wi-Fi was an analogy to other recorders.

| Layer | Evidence | Conclusion |
|---|---|---|
| ATS3085L | Actions identifies dual-mode Bluetooth SoC; documents Bluetooth RF/baseband, M4F, DSP, SPI peripherals | No integrated Wi-Fi capability specified; SPI offers a plausible external-module interface |
| Acquired REC_JX3 SDK | ESP32-C3 coprocessor, SPI_2 at configured 20 MHz; AP + WebSocket + actual recording-file reads | Concrete external Wi-Fi host implementation; different M33 board, not CoMi BSP |
| Actual CoMi FW010004 | Five Wi-Fi literals in linked `record_wifi_ota_view.c` UI code | Positive UI lead, not proof of a radio, working transport, or file export |
| CoMi App 1.1.2 | Wi-Fi commands live in Mova adapter; owned recorder uses Boyi | Cannot use those commands as CoMi Boyi protocol |
| Owner manual / live work | Manual supplies Bluetooth/charging instructions; successful recording exports use BLE | No demonstrated Wi-Fi transfer; absence from manual alone is not exclusion |

## Manufacturer and development-board sources

[Actions current product page](https://www.actions-semi.com/index.php?id=3873) describes Bluetooth RF/baseband and lists ATS3085L, M4F128 MHz/DSP192 MHz and SPI interfaces, without a Wi-Fi specification. Current prose says Bluetooth5.4 while its table says6.0; retained [manufacturer brochure](ats3085l-primary-sources.md) says5.4. Do not silently substitute these family marketing versions for this recorder's actual configuration.

[CubieDVB-ATS3085 vendor](http://www.cubietech.com/product-detail/cubiedvb-ats3085/) likewise describes Bluetooth and expansion pins, without an advertised Wi-Fi module. Neither omission proves every possible board lacks external Wi-Fi. The useful engineering conclusion is that a third-party firmware cannot create a missing Wi-Fi radio; a matching coprocessor, wiring, RF hardware and driver/firmware are required.

## SDK: implementation exists, integration is not fully closed

[Detailed fixed-source audit](wifi-sdk-reference-2026-10-13.md) traces BLE request → ESP32 AP → phone WebSocket → recording-file reads → SPI chunks. Real modules are enabled; mock is excluded. This is useful architecture/reference code, not merely a directory named Wi-Fi.

Limits: LEOPARD/M33 versus CoMi LARK/M4; ordinary BLE activation bypasses the manager's initialization sequence in this snapshot; matching C3 slave source was not located under the documented names. Configured SPI speed is not measured file throughput. These gaps preclude calling this a ready-to-flash implementation.

## Actual CoMi firmware: a bounded positive lead

Retained original system image: 927632 bytes, SHA-256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`. ASCII scan finds:

- `0x100c398a`: `view_id == WIFI_OTA_VIEW`
- `0x100c39a3`: `WEST_TOPDIR/application/bt_watch/src/recorder/record/record_wifi_ota_view.c`
- `0x100c39ef`: `wifi_ota_state == %d`
- `0x100c3a05` / `0x100c3a22`: layout-update / view-handler names.

Aligned pointers lie at `0x10015b38–0x10015b78`. A bounded Thumb disassembly before this pool contains view handling and log calls; e.g. `0x10015afe` loads the state-format pointer and `0x10015b12` calls `0x10055f90`. It does not establish a transport initializer or a downloadable-file endpoint. Could be active upgrade UI or retained shared UI; neither interpretation is confirmed. Exact matching view source was not found in the two reference scopes Astra searched.

No ASCII-run hits for `ssid`, `wlan`, `lwip`, `esp32`, `esp_hosted`, `spihd`, `socket`, `tcp`, `udp`, `802.11`, `wi-fi`. This is only a reproducible literal-search boundary, not a proof of absent networking. External coprocessors can hide their network stack from the host image.

## App: avoid mixing device families

Hash-verified main JS has three occurrences each of `setWifiEnabled` and `getWifiStatus`: implementation plus wrapper declaration/call. Implementation uses Mova `WIFI_SWITCH=243`; `WIFI_INFO=244` notifications produce `wifi_info`. Manager `MC` explicitly maps `on.Mova` to `LC` and `on.Boyi` to its separate adapter. [Prior app provenance and service identifiers](app-upgrade.md).

The owned Boyi E5E device is not the Mova Nordic-UART-style service. No Boyi Wi-Fi opcode was established. These methods therefore provide neither permission nor protocol justification to send 0xf3/0xf4 to CoMi. Scope is extracted 1.1.2 main JS; not all versions/assets, and not logged-in 1.2.4 runtime.

## Follow-up: actual UI and App loading path

[Actual view trace](wifi-actual-view-2026-10-13.md) follows registered view0x58 and its0x96 status consumer. The inspected handler creates/releases UI and switches to the recording launcher on one status; no transport initializer was established. Do not promote the Wi-Fi name into a working radio/transfer capability. Direct-call coverage does not exclude indirect or dynamically selected paths.

[Whole packaged App audit](wifi-app-paths-2026-10-13.md) adds an important coverage correction: shipped1.1.2 defaults to a remote Capacitor frontend, `https://doll.familyrobot.site/noteweb/`. Packaged JS is therefore not a complete runtime-feature inventory. Root GET on2026-10-13 returned HTTP500/nginx,186 B; [response digest and supplemental transport references](evidence/wifi-transport-followup-2026-10-13.json). This is one current server observation, not permanent unavailability or an observed App launch.

Supplemental actual-system pointer scan: SPI_2 name100c9e3f points only from descriptor100ba2e0; that descriptor points only from init entry100b9edc. UART_1 name100c98b9 points only from its descriptor. This does not reproduce the reference SDK's explicit SPI_2 name binding, but cannot exclude computed names, direct MMIO or a different bus. Full image digest and exact aligned references are retained in the same JSON.

[Related-app Wi-Fi comparison](wifi-oem-comparison-2026-10-13.md) supplies another concrete protocol, rather than a CoMi command: AI DVR Link's3085S path uses0x1b for Wi-Fi activation. Rechecking the **actual CoMi** complete Boyi table at1000b410 maps0x1b,0x1f,0x20 to1000b544, whose default returns−134. The retained JSON includes table bytes and default disassembly. Thus transplanting that related recorder's Wi-Fi opcodes into this Boyi endpoint is ruled out by actual firmware; a different endpoint remains a separate question.

## More than file transfer: conditional capabilities

The acquired REC_JX3 Wi-Fi protocol has handlers for handshake, file list, sync, delete, stop and FOTA ([source audit](wifi-sdk-reference-2026-10-13.md)). These are potential reusable designs **if matching Wi-Fi hardware/transport is established**, not features exposed by the current CoMi CLI. Firmware updating remains a separate acceptance/recovery problem even if a faster link becomes available. No source-bound path yet establishes live audio streaming, direct cloud upload, LAN discovery or an arbitrary remote shell on CoMi Wi-Fi.

## Next useful evidence / stopping condition

The bounded view trace supplies no transport entry; park repeated inspection of that handler. Next useful material is the actual remote/runtime frontend or a matching Boyi transport implementation, not more strings from the same view. `adb devices -l` returned no attached Android devices during this follow-up, so no current installed-app/cache observation was possible; earlier connected-phone state is not current evidence. Existing owner preference to defer login remains in force. A concrete Boyi command or external-module initialization would justify a targeted real-device trial. OTA UI alone does not imply recording-file transfer. Do not send Mova commands or re-run the exhausted normal-USB reconnect experiment.

No new CLI Wi-Fi command, faster-transfer claim, hardware change or flashing claim follows from this pass. Existing BLE transfer progress and measured throughput remain the available client capability.
