# Host selection / USB identity follow-up

2026-10-12. Offline SDK/configuration and PE reads only. No DLL/executable loaded,
driver installed, hardware enumerated, protocol switch, helper download or flash.

**Result:** reference ATS3089p selects LEOPARD in the SDK, and its production
configuration requests an ADFU protocol switch. Neither that fact nor the
extracted host DLLs establishes which host transport implementation CoMi needs.

## What the SDK selects

Pinned upstream: `lvgl/lv_port_actions_technology`, commit
`26f51e584940d5b141cd1d09d2629d69b595f579`.

| Source | Confirmed selection | Limit |
|---|---|---|
| [ATS3089p 8-bit board defconfig][board] | `CONFIG_SOC_SERIES_LEOPARD=y`, `CONFIG_SOC_LEOPARD=y` | Reference board; not identification of owned CoMi |
| [Board packaging config][image] | `CHIP_NAME = "ATS3089"` | Packaging chip name; not a DLL transport enum |
| [LEOPARD product config][product] | `USB_ADFU_PROTOCOL_SWITCH = "YES"` | Comment requires switching protocol before USB production; switch opcode/implementation not provided here |
| Same product config | `adfus.bin` / `adfus_u.bin`: download `0x2ff70000`, run `0x2ff70001` | Helper RAM placement, not physical flash addresses |
| Same product config | `STORAGE_ID_FILE = "nand_id.bin", 0x2ff88000, 2` | Production configuration; does not identify CoMi storage or its partition map |

[build_firmware.py][builder] includes `fw_product.cfg` and available `fwimage.cfg`
in generated maker configuration. Separately, it parses `CHIP_NAME` and passes
it to `fw2x ... MakeEncryptBin Encrypt`. Thus treating `CHIP_NAME="ATS3089"` as
proof of a host USB protocol number would skip an unverified mapping.

[build.py][build] permits board overrides for helpers, `nand_id.bin`,
`bootloader.ini`, `recovery.bin`, and `fw_product.cfg`, followed by application
prebuild/config overrides. A generic family helper/config is not sufficient to
establish the configuration of a shipped recorder.

## Host artifact facts

Source: [SDK `tools/config_tool.rar`][tool], MSI members extracted by the parallel
helper investigation into ignored `artifacts/helper-static/`. PE32 i386 files;
no executable behavior observed.

| File | SHA-256 |
|---|---|
| `HardwareEx.dll` | `986582c243fb0f300c41c483cbc3100f6ff897057b4cace0d30510624a769aa3` |
| `Hardware_C.dll` | `541df654824561537be4e0a500ad7a7997ba9df848dfae4c9202a29dc65fcc5b` |
| `AdfuInstall.exe` | `342bbbc1db60f558b5f5bd272406b36c083784e89fc7dac9775796a1affe0f2f` |

- `Hardware_C.dll` exports `Py_EnumByType`, `Py_ADFU_EnumEx`, `Py_ADFU_OpenEP`,
  `Py_SwitchAdfuByType`, plus raw I/O wrappers. Imports delegate to
  `HardwareEx.dll` methods `CEnumUSB::EnumDevice`, `GetDeviceInfo`, `CCommUSB::Open`,
  `DoRawIO`, and `SwitchToAdfu`. These are host API surfaces, not an IC mapping table.
- `HardwareEx.dll` exports ADFU, raw I/O, SCSI-switch and user-command wrappers.
  Its `CCommUSB(int)` constructor at RVA `0xe910` dispatches numeric values
  `0..4`; no inspected configuration maps ATS3089/LEOPARD to those values.
- Its ASCII strings contain `WinUsb_Initialize`, `WinUsb_QueryInterfaceSettings`,
  `WinUsb_QueryPipe`, `WinUsb_ReadPipe`, and `WinUsb_WritePipe`, plus errors for
  these calls. This supports presence of a WinUSB implementation; it does not
  establish runtime endpoint values or the path chosen for CoMi.
- `AdfuInstall.exe` embeds INF text for **VID `10d6`, PIDs `10d6`, `ff76`, `fe02`**,
  each labeled Actions USB 2.0 (HS) WinUSB Device. First INF declarations at file
  offsets `0x120e7cb`, `0x120e811`, `0x120e857`; matching UTF-16 device-id literals
  at `0x120f7aa`, `0x120f758`, `0x120f706`. These are driver-supported identities,
  not observed CoMi descriptors or a per-chip PID assignment.
- MSI `support_list.txt` contains `ATS3003, ATS3005, ATS3009P`, `ATS3015`,
  `ATS3015P, ATS3019`, `ATS3025, ATS3085`; no ATS3089 line. `version.ini` declares
  `SOLUTION=US302A_V1.0`, `CFGVER=0x20002000`. Neither proves incompatibility, but
  neither supplies positive ATS3089 host-tool compatibility evidence.

Bounded ASCII + UTF-16LE string scans of the seven extracted host binaries
(`HardwareEx`, `Hardware_C`, `ActDbgUsb`, `ATDUsbComm`, `Generate`, `Script`,
`AdfuInstall`) found no `LEOPARD`, `LARK`, `3089`, or `3085` mapping literal.
Encoded/numeric tables and other installer members remain outside this claim.

## Remaining gap

Need chip-to-host selection code or matched vendor production configuration,
then observed descriptors/endpoints from the owned device's authorized download
mode. The driver IDs above can guide identification if such a device appears;
they do not justify sending older Actions MSC packets or assuming endpoint
`02/81` from unrelated implementations. See [transport distinctions](recovery-transport.md).

Reproduction: `objdump -p` for PE imports/exports; `objdump -d` for bounded wrapper
and constructor dispatch; format-aware ASCII/UTF-16LE string reads for embedded
INF declarations. `7z e -so artifacts/helper-static/MSI.CAB
_965C0C5DA76A4597A6FEBFA61B72FE3D` prints the mapped support-list member without
executing installer code.

[board]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3089p_dev_watch_sdnand_8b/ats3089p_dev_watch_sdnand_8b_defconfig#L10-L11
[image]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/hello_world/boards/ats3089p_dev_watch_sdnand_8b/fwimage.cfg
[product]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/fw_product.cfg
[builder]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_firmware.py#L590-L603
[build]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/build.py#L501-L515
[tool]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/tools/config_tool.rar

## Later actual firmware identity

[Two independent parameter reads](firmware-board-identity.md) establish firmware board name `ats3085l_dvb_watch_ext_nor_max`; prioritize matching ATS3085L production artifacts. This supersedes the broad search priority, not the reference ATS3089 facts above. Firmware metadata alone does not prove chip marking or map host enum0..4 to this device.

Follow-up: [LARK retained M4 artifacts](lark-helper-candidate.md) select01010000 and include a different in-image NOR driver. UART/USB initialization comparisons are complete within their static scope; unchanged init is not a read-only backup route. Do not restart that audit.

2026-10-13: [default production generation](production-package-contract.md) separates outer ACTTEST0, inner maker, raw and AOTA outputs. Default include selects fw_product rather than the legacy fw_maker_ext/mp_usb configuration; neither supplies a CoMi chip-to-host mapping. Prioritize the matching final production directory and effective configuration before another generic host/helper investigation.
