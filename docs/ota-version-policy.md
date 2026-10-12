# Actual OTA initialization disables the ordinary version gate

2026-10-12. Static analysis of SHA-verified mapped-system FW010004, not an OTA
attempt. No F5F0 subscription, package transfer, Flash write, reset or downgrade.
[Exact instructions/literals](evidence/ota-version-policy-2026-10-12.json).

## Decision-changing finding

The inspected CoMi application initializer explicitly requests **no version
control**. Therefore the reference SDK's default same/older-version rejection
cannot be presented as CoMi's configured policy. This removes one assumed
obstacle; it does not establish that an original image can be restored.

| Actual instructions | Data/control flow |
|---|---|
| `10004ae8..10004b54` | Builds OTA initialization argument on stack. Storage string from `10004ba0` is `spi_flash`. |
| `10004b2e..10004b36` | Clears word at SP+0c, then stores byte `0d` there. |
| `10004b4a..10004b4c` | Passes SP to initializer `100669f8`. |
| `10066a18..10066a20` | Clears364 hex B of OTA state. |
| `10066a24..10066a3a` | Tests caller byte+0c bit2; when set, logs `enable no version control`, ORs4 into internal flags at state+8. |
| `10066548..1006655a` | Tests internal bit2. When set, skips current/new version comparison. Otherwise current at+4 >= candidate at state+2c goes to `ota image is same or older, skip ota`. |

The shifts `LSLS #29` followed by `BMI/BPL` test original bit2. Literal0d sets
bits0,2,3 and clears bit1. Pinned SDK names these `use_recovery`,
`use_no_version_control`, `erase_part_for_upg`; these names interpret the observed
bits, not proof of every downstream path. The version bit's effect is established
by actual initializer **and** actual decision branch, not the SDK name alone.

## Board check remains separate

`100664c2` calls current firmware-version getter `10027798`; saved return is r6.
`1006652e..10066546` compares strings at current+50 and OTA state+78 via actual
bytewise string comparator `10000cc8..10000cda`. Nonzero result logs
`unmatched board name, skip ota` and follows rejection before the version gate.

Consequently, disabling version comparison does not disable the board-name
check in this path. Follow-up [two-session parameter readback](firmware-board-identity.md) establishes
firmware board name `ats3085l_dvb_watch_ext_nor_max`. Knowing this matching name
does not prove electrical/board compatibility.

## Limits for own firmware and official recovery

- This is an initialization request and its conditional consumer. No runtime
  flags snapshot or accepted same/older image was observed; other callers or
  later state changes are outside this narrow audit.
- Header/container checks, per-file checksums, partition choice, encryption,
  signatures, patch compatibility and recovery-side acceptance remain separate.
- Neither no-version-control nor board-name acceptance is an authentication or
  safe-boot guarantee. A valid transfer can still install nonworking firmware.
- Application BLE OTA depends on the application running. It cannot itself
  prove recovery from an unbootable replacement application.
- The complete current official production/OTA package and independent restore
  path remain missing. Do not test this finding by flashing an arbitrary image.

## Reproduction and source context

```sh
uv run tools/inspect_ota_version.py artifacts/mapped-system/mapped-system.bin
```

Script SHA-binds the complete checksum-verified927632 B image, rejects partial
instruction decoding, and emits bounded code ranges plus PC-relative literals.
Selected ranges end before literal pools. Compare output against committed JSON.

Pinned SDK source context:
[flags and consumer](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_upgrade.c#L57),
[initialization ABI](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/include/ota_upgrade.h#L31),
[board/version decision](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_upgrade.c#L1308).
