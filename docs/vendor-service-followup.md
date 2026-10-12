# Vendor thread/service: incoming file transfer, no established firmware readback

2026-10-12 · offline public-SDK source audit; no hardware I/O or application commands.

**Result:** `vendor_read` in the public SDK consumes incoming BLE commands. Its
complete dispatch table supports time setting, file **upload to device**, and
message submission. No firmware/storage identity, file download, physical readback,
or OTA-entry handler exists in this table. CoMi exposes a different vendor UUID;
matching thread names alone cannot transfer these command semantics to CoMi.

## Evidence and source identity

- SDK pinned at [`26f51e584940d5b141cd1d09d2629d69b595f579`](https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579).
- `application/bt_watch/src/vendor/vendor_app.c` SHA-256:
  `7837b2a2a51a54af1dbd6032b55b3991efe108017ab939fee7a1976945282208`.
- Adjacent `vendor_app.h` SHA-256:
  `39e10305990487237c88bccb1ffb4e22e7d79f4d1b01f282eaea212ec57855d2`.
- Owned-device [thread capture](evidence/code-references-first-2026-10-12.json):
  `vendor_read` entry `0x1000a01d`, `vendor` entry `0x10009e9d`; both priority 13.
  These are observed names/pointers, not a binary match to SDK functions.
- Owned-device [GATT discovery](evidence/gatt-2026-10-12.json): four services,
  including log `e49a3001…`, unknown stream `0000f5f0…`, Boyi `0000e5e0…`,
  and battery `0000180f…`. No public-SDK OTA or vendor UUID below observed.

## Actual UUID initializers, not their stale comments

Long UUID suffix below: `-f69a-11e8-8eb2-f2801f1b9fd1`.

| SDK component | Service | Device RX / host writes | Device TX / host subscribes | CoMi discovery |
|---|---|---|---|---|
| Vendor app | `f48a23c0…` | `f48a24c1…` | `f48a25c2…` | Absent |
| OTA foreground | `e49a25f8…` | `e49a25e0…` | `e49a28e1…` | Absent |
| Log service | `e49a3001…` | `e49a3002…` | `e49a3003…` | Present |

Vendor UUID arrays are little-endian BLE byte order. Service initializer is
`d1 9f 1b 1f 80 f2 b2 8e e8 11 9a f6 c0 23 8a f4`; reverse all 16 bytes to
obtain `f48a23c0-f69a-11e8-8eb2-f2801f1b9fd1`. RX/TX tails are `c1 24 8a f4`
and `c2 25 8a f4`. Source comments incorrectly retain OTA UUID strings.
[Vendor GATT definitions][vendor-gatt]; [actual OTA definitions][ota-gatt].

Vendor RX exposes write/write-without-response; TX exposes notify. Although the TX
attribute permission bits include READ, its characteristic has no read property
or read callback. This is a stream transport, not a GATT-readable firmware region.
A bounded case-insensitive source search for `0xf5f0/1/2`, `0xe5e0/1/2/3/4` and
canonical short-service UUID strings found no definitions in SDK `application`,
`framework`, `zephyr/include/bluetooth`, or `zephyr/subsys` C/H/CPP/conf files.
Numeric hits elsewhere in font/charset/DSP tables are unrelated. This does not
exclude bytewise UUID construction, prebuilt libraries, or CoMi-specific additions.

## Vendor command dispatch and file direction

`vendor_read_thread()` loops over `ble_stream_read()` when the BLE stream is ready.
The parser reads a packed five-byte header:

```text
service:u8=01 | command:u8 | parameter_type:u8=80 | parameter_length:u16 LE
```

It accepts only service `SVC_WATCH=0x01`, non-null entries within a four-entry table,
and parameter type `0x80`. Complete incoming command table:

| Command | Handler | Source-established effects |
|---|---|---|
| `00` | null | Rejected/no handler. |
| `01` | `cmd_set_time` | Parses date/time TLV; sends current app a `BT_MAP_SET_TIME_EVENT`. State-changing. |
| `02` | `cmd_send_file` | Parses name/type/date/length TLVs; `save_file()` writes incoming stream into `/NAND:/<name>`. State-changing. |
| `03` | `cmd_send_msg` | Parses app/title/text/date; logs message; UI delivery remains TODO. |
| `04` | no incoming entry | `CMD_D2H_RESULT`, used only in replies containing command/result TLVs. |

`save_file()` calls `file_stream_create`, opens `MODE_OUT`, receives BLE bytes,
then calls `stream_write` on the file. Incomplete transfer calls `fs_unlink`.
`vendor_read` therefore means **reading the BLE receive stream**; neither the
thread name nor file-related code indicates reading firmware out of storage.
The file path prefix alone also cannot identify CoMi's actual boot medium.
[Header/IDs][vendor-header]; [file operations][vendor-file]; [complete dispatcher][vendor-dispatch].

There is no harmless identity command in this public table to try against F5F0.
Its parser is not a specification for the observed CoMi F5F0 stream, nor for
CoMi's separate working Boyi E5E0 protocol. Existing Boyi `GET_DEVICE_INFO`
provides firmware version/capacity/status; recording downloads do not cover the
firmware image. See [Boyi protocol](protocol.md).

## OTA API reads an image from host; subscription can start OTA state

The independent OTA backend is not called by the vendor app's three handlers.
Its incoming dispatch table accepts upgrade request `01`, negotiation `02`,
negotiation result `09`, image data `04`, and image data with CRC `0b`.
No storage-dump command appears in that table. [OTA dispatch][ota-dispatch].

The OTA backend API's `.read = ota_backend_bt_read` is from the **device updater's**
perspective: it sends `OTA_CMD_D2H_REQUIRE_IMAGE_DATA=03` carrying offset and length,
then receives image bytes from the host into `ctx->read_buf`. Offsets refer to the
candidate upgrade image held by the host, not existing device flash.
[Image request/receive][ota-image]; [backend read][ota-read].

This SDK's foreground OTA entry is state-changing even before image programming:

```text
host enables OTA TX notifications (nonzero CCC write)
  → stream_ble_rx_write_state sets BLE_CONNECT_TYPE and invokes connect_cb(true)
  → sppble_connect_cb invokes backend callback(OTA_BACKEND_UPGRADE_STATE, 1)
  → ota_app_backend_callback attaches backend and calls ota_app_start()
  → flash_write_protection_set(flash_device, false); app switch/lock
```

With filesystem recovery configuration, the callback may additionally open the
OTA file with `FA_READ | FA_WRITE | FA_OPEN_ALWAYS` and bind it to storage.
The public code contains guards and configuration-dependent branches; this is not
a claim that every generic BLE connection starts OTA or that flash array contents
change merely from a CCC write. It shows that subscribing to **this OTA service**
is not a passive identity check. No such subscription was performed here.
[CCC activation][ota-ccc]; [backend callback][ota-connect];
[foreground attach/file/start][ota-start].

## Remaining useful investigation

1. Use already-observed CoMi thread entry addresses as anchors for bounded,
   independently reread code/literal analysis. Establish actual receive dispatcher
   and service UUID references before mapping `vendor_read` to a transport.
2. Trace F5F0 in an actual compatible app artifact or recovered device code;
   determine framing and an implemented non-mutating identity operation first.
   Similar write/notify topology does not establish vendor or OTA compatibility.
3. Continue existing logsrv mapped-code path and official-image acquisition;
   this source audit adds no validated backup or flash command for CoMi.

[vendor-gatt]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/vendor/vendor_app.c#L55-L82
[vendor-header]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/vendor/vendor_app.h#L10-L67
[vendor-file]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/vendor/vendor_app.c#L253-L370
[vendor-dispatch]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/vendor/vendor_app.c#L454-L545
[ota-gatt]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/ota/ota_app_foreground.c#L258-L281
[ota-dispatch]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/ota_backend_bt.c#L689-L697
[ota-image]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/ota_backend_bt.c#L526-L622
[ota-read]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/ota_backend_bt.c#L818-L865
[ota-ccc]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/bluetooth/bt_manager/bt_manager_sppble_stream.c#L327-L350
[ota-connect]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/ota_backend_bt.c#L1115-L1170
[ota-start]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/ota/ota_app_foreground.c#L89-L210
