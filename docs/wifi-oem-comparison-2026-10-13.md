# OEM Wi-Fi transport comparison

2026-10-13. Host-only, bounded reads of existing pinned OEM APK Blutter output.
No device command, AP connection, remote API request or new decompilation.

**AI DVR Link / UMEVO contain a concrete AP + TCP recording-transfer protocol.
Its BLE activation belongs to the F0F0 / `80 08 02` family, not the owned CoMi
Boyi E5E0 / `D2 2D 01` family. The owned firmware's complete Boyi dispatcher
also excludes their `0x1b` activation command. Keep this as a comparison oracle,
not a CoMi enablement recipe.**

## Source identity

[Acquisition/provenance and pinned analyzer](oem-protocol-lead.md):

| Shipped artifact | APK SHA-256 | arm64 `libapp.so` SHA-256 |
|---|---|---|
| Official AI DVR Link 3.2.0, `com.ai.dvrlink` | `bba153b4da1db7e1be9f239b3e93eb5b255af9b1d30528198aec5cb9a950e7bd` | `f5530f73cf43d4874c9bd7e95da06f787974806495c1269b36c915ce8a72217a` |
| Official UMEVO 1.2.5, `com.umevo.recorder` | `7d9d4a71c274ed8a7420d1aa4440711b592ab935ec5dbba49f0fa310e9c4eb06` | `013601d5085451d8ae34494b3dedd82c63be83538de33dd8d9b89d14893f2b60` |

Primary evidence below: ELF code addresses in ignored generated assembly trees
`artifacts/oem-ai-dvr-link-blutter/asm/dvrlink/` and
`artifacts/oem-umevo-blutter/asm/umevo/`. Addresses describe these exact app
versions, not recorder code or runtime traces. No physical-chip identity follows
from a Dart class or protocol enum name.

## AI DVR Link: exact gate and activation

| Path / address | Confirmed static behavior |
|---|---|
| `dvrlink_bluetooth/xlx_link/ble_mgr.dart`, `DvrLinkBleMgr::openWifi` `0x16e9744–0x16e9844` | Reads manager `field_27`; `xlx_2837` exits; only `xlx_3085s` enters request construction; every other protocol, including `slink`, exits |
| `objs.txt`, objects `1edae11/1edae31/1edae51` | Enum names/index: `xlx_3085s=1`, `slink=2`, `xlx_2837=0`; distinguishes protocol families rather than proving silicon |
| `xlx_link/bluetooth_profiles.dart`, `isUARTService3085s` `0x16dad2c` | Service check uses case-normalized literal `F0F0`; no E5E0 selection in this method |
| `protocol/cmd_3085s/key_profiles.dart`, `openWifi` `0x16b555c` | Key `0x1b`; request created with boolean true by `openWifi` |
| `protocol/cmd_3085s/setting/wifi.dart`, `DVRLinkOpenWifiRequest::createValue` `0x1d03da8` | Boolean serialized as one byte: true→1, false→0 |
| `protocol/cmd_3085s/request_3085s.dart`, `pack` `0x1cc9534` | Writes `80 08 02`, key byte, one-byte payload length, payload, then zero short; this TX path has no computed CRC |
| `ble_mgr.dart`, `closeWifi` `0x193e4f8` | Same protocol gate, same `0x1b` request, boolean false over BLE |

Thus reconstructed activation bytes for this OEM path are
`80 08 02 1b 01 01 00 00`; derived from actual serialization, **not transmitted
or validated against a recorder here**. The inspected activation method has no
additional hardware-presence predicate; that does not establish every device
classified `xlx_3085s` has Wi-Fi hardware.

Device-to-app key `0x1f` is initialized at `0x16b5594`. Its
`DVRLinkWifiInfoReportResponse::unpack` at `0x1be91d8` reads two fixed UTF byte
fields, 10 then 8 bytes; downstream manager consumes Wi-Fi information. Exact
padding/credential acceptance remains a runtime question. Key `0x20` is Wi-Fi
socket status; `0x21` means close through Wi-Fi; `0x35` is Wi-Fi heartbeat
(`key_profiles.dart` `0x16b5524`, `0x16eed08`, `0x193ee9c`).

## Concrete high-speed transport

AI DVR `dvrlink_wifi/dvrlink_wif_mgr.dart::startSocket` at `0x193ea10`
calls `dart:io Socket::connect` at `0x193eb58`, with literal
**`192.168.200.1:8475`** at `0x193eb44/0x193eb4c`. Socket receive code compares
trimmed markers `XnoteWifiHead` / `XnoteWifiTail` at
`0x193f448/0x193f4f8`; it dispatches file-transfer and OTA-related traffic.
This is local TCP binary framing, not evidence of an HTTP/FTP URL or a cloud
download service.

UMEVO independently implements the same endpoint and supplies a clearer codec:

| Path / address | Confirmed static behavior |
|---|---|
| `services/bluetooth_protocol.dart::setWifiFastTransfer` `0x961040` | BLE command `0x1b`, payload `[1]`, sent via `_sendCommandWithTimeout` at `0x9610bc`; return judged by existing response text |
| `services/wifi_fast_transfer_service.dart` constructor `0xc228d4`; constants `0xc22988/0xc22994` | Default host `192.168.200.1`, port 8475; `connect` invokes `Socket::connect` at `0x95cfec` |
| `WifiFrameCodec::encode` `0x95c498–0x95c5ec` | Header; command u8; sequence u16 LE; payload CRC16 u16 LE; payload length u32 BE; payload; tail |
| `header` `0x95c974`, `tail` `0x95c93c` | Exact ASCII literals `XnoteWifiHead  ` (two trailing spaces, 14 B) and `XnoteWifiTail   ` (three trailing spaces, 15 B) |
| `_crc16Ibm` `0x95c6a0` | Initial zero, reflected polynomial `0xa001`, final low16; input is payload only |
| `_send` `0x95c2b4` | Advances sequence counter and masks to16 bits before encoding |
| `downloadFile` `0x95685c`, calls `0x956938/0x956948` | Builds file/seek payload, sends TCP command `0x0b`; independent file download path exists |
| `closeWifi` `0x95f7a8` | Sends TCP command `0x21` with `[0]` |
| `wifi_fast_transfer_use_case.dart::transferRecordingByWifi` `0x9450ec` | Connect → download → close/reconnect Bluetooth; cleanup path also closes/reconnects after error |

The endpoint/markers corroborate related OEM implementations. Detailed socket
RX validation, file-start/end status semantics and measured throughput were not
audited in this bounded pass. The existence of code is not device execution proof.

## Applicability to actual CoMi

- Owned recorder uses Boyi E5E0 / E5E1–E5E4, envelope `D2 2D 01`, and different
  manufacturer ID/serial layout; [comparison evidence](oem-protocol-lead.md).
- Actual shipped board string is `ats3085l_dvb_watch_ext_nor_max`, tied to the
  image's version/OTA comparison path; [board identity](firmware-board-identity.md).
  `xlx_3085s` in another app does not override this evidence or identify CoMi PCB
  peripherals.
- Actual complete Boyi table at `0x1000b410` maps `0x1b..0x39` to default
  `0x1000b544`, which returns `-134`; [dispatcher reconstruction](vendor-dispatch-followup.md).
  The OEM Wi-Fi enable/status/close/heartbeat keys fall in that default range.
  Sending these bytes through Boyi is unsupported by this implementation.
- This excludes unchanged OEM activation on the known CoMi Boyi dispatcher. It
  does not exclude another GATT service, a different firmware mode, an external
  Wi-Fi component, or a later supported CoMi client path.

Useful next proof must start from actual CoMi code/app: identify a Wi-Fi driver,
external-module GPIO/SPI/UART path, linked activation handler and transport
endpoint. Finding only common Actions UUIDs or the number3085 is insufficient.
No OEM commands should be added to the CoMi CLI on this evidence.
