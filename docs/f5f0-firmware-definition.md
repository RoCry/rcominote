# F5F0: actual firmware Bluetooth OTA backend

2026-10-12. Offline mapped-system reads and Capstone 5.0.6 analysis; no
subscription, BLE write, memory read, reset, or Flash operation on device.

**F5F0/F5F1/F5F2 belongs to this image's Bluetooth OTA backend.** Actual
parameter references, backend initialization, dynamically installed callbacks
and application notification establish this attribution. The earlier
[app-artifact literal search](f5f0-artifact-search.md) remains a bounded negative
result for those app artifacts; the device image now supplies positive evidence.

This identifies an existing upgrade transport. It does not establish a firmware
backup command, accepted custom-image format, successful programming, or recovery
when the main application fails. Enabling F5F2 notifications has an application
state-change path; it is not established as passive observation.

## Input and evidence

Mapped system: 927,632 B at `10000000`; SHA-256
`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`.
This is the validated mapped application image, not a raw Flash backup.

Exact bytes, region hashes, instruction addresses and literal pools:

- [Definition and initializer](evidence/f5f0-firmware-definition-2026-10-12.json).
- [Stream registration and callbacks](evidence/f5f0-firmware-callbacks-2026-10-12.json).

Code regions exclude literal pools. Functions marked complete include all local
branches to return/tail calls; called functions remain separate analysis scope.
Application callback excerpt is explicitly partial. No emulation or hardware
execution was performed for this report.

## Service and initialization

[Startup copy evidence](startup-memory-readback.md) maps the first two initialized
regions by `RAM = image − 100dd500 + 18000000`. GATT initializers therefore use
RAM pointers, explaining why a search only for pointers to image UUID addresses
misses this connection.

| Initializer image / RAM address | Value and role |
|---|---|
| `100dfa30` / `18002530` | UUID16 F5F0 service |
| `100dfa3c`, `100dfa40` / `1800253c`, `18002540` | UUID16 F5F1 declaration/value |
| `100dfa48`, `100dfa4c` / `18002548`, `1800254c` | UUID16 F5F2 declaration/value |
| `100deba0` / `180016a0` | Six attributes, 20 B each |
| `100deb90` / `18001690` | F5F1 characteristic: properties `0c` = write and write without response |
| `100deb98` / `18001698` | F5F2 characteristic: property `10` = notify |

Attribute order: primary service, F5F1 declaration, F5F1 value, F5F2 declaration,
F5F2 value, CCC. F5F1's initialized write pointer is NULL; stream initialization
installs its callback later. The structure matches pinned SDK
[`bt_gatt_attr`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/bluetooth/gatt.h#L104-L147).

The 36 B object at `100ba914` matches
[`ota_backend_bt_init_param`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/include/ota_backend_bt.h#L30-L43):

| Field | Actual value |
|---|---|
| SPP UUID pointer | `100c11bc`; little-endian bytes `fb349b5f800000800010000066660000`, UUID `00006666-0000-1000-8000-00805f9b34fb` |
| GATT attributes / count | `180016a0` / 6 |
| TX declaration / value / CCC | `180016dc` / `180016f0` / `18001704` |
| RX value | `180016c8` |
| Read / write timeout | 60,000 / −1 |

Complete application initializer `10004a30..10004a6e` loads this object and
callback `10004855`, calls `10064698` at `10004a50`, returns −19 on NULL or 0 on
success. Complete callee `10064698..10064754`:

- Uses log identity string **`ota_backend_bt_init`** at `100d373c`.
- Allocates/clears a 68 B backend; copies service pointers into a stream init
  object; installs connect callback `100638e5`; sets receive buffer size `1004`
  hex = 4,100 B; invokes stream creator `1006cd44`.
- Allocates 128 B send buffer; sets unit size 256, protocol state 0, global
  backend pointer `18019d14`, backend type 2, API pointer `18001cac`, application
  callback `10004855`.

This sequence matches fixed SDK
[`ota_backend_bt_init`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/ota_backend_bt.c#L1184-L1239).
SDK Bluetooth backend type is 2. SDK example BLE UUIDs differ from CoMi; source
matching rests on actual parameter/control flow, not assuming UUID equality.

## Dynamic handlers and notification side effect

Stream creator `1006cd44..1006cd4c` passes ops `100bd7f8` to generic creator
`100513d4`; ops[0] is `1006c9c9`. Complete stream initializer
`1006c9c8..1006cb52` copies pointers and registers these callbacks:

| Actual store | Installed function / target |
|---|---|
| `1006cb20` | F5F1 attribute +8 write pointer ← `1006c83d` |
| `1006cb2a` | CCC userdata +`2c` cfg_changed ← `1006c5b9` |
| `1006cb30` | CCC userdata +`30` cfg_write ← `1006c7b9` |
| `1006cb34` | Stream link callback ← `1006c915` |
| `1006cb38` | Registers BLE service via `1006bf78` |

The RX callback `1006c83c..1006c904` finds a stream by attribute, requires
connection type 2, opens stream mode 3, then appends incoming bytes to its
receive buffer and signals the reader. It returns incoming length. This is a
transport buffer path; no Flash read command is established by this callback.
Registration/receiver shapes match SDK
[`sppble_register` and RX callbacks](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/bluetooth/bt_manager/bt_manager_sppble_stream.c#L276-L415).

The CCC changed callback stores notification-enable state. More significantly,
complete CCC write callback `1006c7b8..1006c828`, given a non-NULL connection,
matching stream, nonzero CCC value and previous connection type 0, changes
connection type to 2 and invokes `connect_cb(1,2)`. Complete backend connect
callback `100638e4..10063972` handles that event and invokes application callback
with `(backend, 1, 1)` when installed.

Application callback excerpt `100048ba..10004952` tests command 1/state 1,
calls backend attach `1006696c`, and follows its success branch through log
**`ota app start`** and application/message helpers. An earlier guard can reject
the `btcall` case. This report does not fully audit those helpers or claim that
CCC enable alone erases/programs Flash. It does establish an application upgrade
state-change route, so subscribing is not a proven read-only diagnostic.

## Remaining boundary

No F5F0 traffic sent. Follow-up [actual wire dispatcher](ota-wire-contract.md)
establishes device-pull image input, not a Flash readback command table;
[actual version policy](ota-version-policy.md) traces no-version-control
initialization and the independent board-name gate. Remaining package validation,
Flash write path, interruption handling and independent recovery are unverified.
The identified backend operates inside the main firmware; its existence alone
cannot demonstrate recovery after that firmware stops booting. Firmware backup
still requires an independently established content-export path.
