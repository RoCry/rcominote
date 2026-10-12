# USB / ADFU 恢复与独立下载可行性

2026-10-12。主机侧源码研究；未连接设备、未启动下载器、未发送恢复命令。
SDK 固定于 `lvgl/lv_port_actions_technology@26f51e584940d5b141cd1d09d2629d69b595f579`。

**已找到 RAM helper→存储烧写的分层，以及可研究的旧版开源 ADFU host；尚未找到已验证适用于 ATS308x / CoMi 的独立 USB 备份工具。**
原厂资料中的“Linux 下载”不能解释为已有原生 Linux USB ADFU 工具：完整下载步骤明确使用 Windows 配置工具/虚拟机；原生 Linux 快速下载走 J-Link。[SDK 下载说明][sdk-download]

## 三种入口不能混为一谈

| 入口 | 源码事实 | CoMi 未知 |
|---|---|---|
| ROM ADFU | BROM API 表 `0x188` 暴露 `p_adfu_launcher`、UART launcher、存储读取和签名接口；此文件只给函数指针，未给 USB wire protocol/描述符 [BROM 接口][brom] | ROM VID/PID、接口类、鉴权、是否能加载任意 RAM 程序 |
| SDK framework USB DFU | 默认 `10d6:b018`；device class `0`，interface `fe/01/02`，无 bulk endpoints，功能描述符宣称上传/下载 [Kconfig][dfu-config] [描述符][dfu-desc] [class 定义][dfu-class] [协议定义][dfu-protocol] | 本机是否编入/启用；这个 PID **不能当作 ROM ADFU PID** |
| J-Link / SWD | LEOPARD Cortex-M33 设备条目；work RAM `0x2ff68000+0x1c000`；SPI flash bank 映射到 `0x10000000`、`0x11000000`、raw `0x20000000` [设备定义][jlink] | SWD 焊盘、pinmux、读保护、实际存储与映射是否匹配 |

framework 的 `usb_dfu_dev.c` 请求处理函数仅打日志后返回，未实现 DFU 下载、上传、状态机或 flash 操作。
因此 `CAN_UPLOAD` 描述符位不构成“能备份”的证据，也不足以推荐 `dfu-util`。[处理函数][dfu-handler]

## RAM 下载与烧写分层：有线索，没有现成 CoMi 配方

LEOPARD `fw_product.cfg` 写明：USB 生产前先切换 ADFU 协议，`adfus.bin` / `adfus_u.bin`
下载地址 `0x2ff70000`、运行地址 `0x2ff70001`；另把 `nand_id.bin` 放 `0x2ff88000`、storage type `2`。
奇数运行地址符合 Cortex-M Thumb 入口约定，这是配置含义推断；**未执行验证**。[生产配置][product]

这至少区分两层：ROM/初始传输负责接收并运行 helper，helper 再处理目标存储。
配置不能证明 helper 只写 RAM、不会初始化/修改 flash；也没有给 ROM 传输格式。
`adfus*.bin` 是公开仓库中的预编译 blob，本仓库只保留来源，不复制或假装有源码可审计。[生产配置][product]

另一路打包器生成的升级脚本明确包含 `adfu_switch`、波特率、`payload=32768`，按 storage ID 排序，
调用 `renew_flash_id`、`sinit`，BOOT 用 `serase`，其他分区用 `swrite`。
这是一条**会擦写存储**的升级路径，不能拿生成脚本做只读连接测试；它也不是已公开的 USB packet 协议。[脚本生成器][upgrade-script]

SDK README 的 EVK 初次下载步骤还明确要求 factory settings 的 storage erase=YES。
它适合参考板初始化，不是保留 CoMi 原厂固件、NVRAM/校准和录音的研究流程。[SDK 下载说明][sdk-download]

## 已找到的 Linux/Python ADFU host：只作协议参考

公开项目 `nfd/atj2127decrypt`，核查提交 `a4454cb205ff3f38061040394d78b0ad5b0235bd`。
项目目标是 ATJ2127 / Sandisk Clip Sport，不能据名字相同宣称 ATS308x 兼容。[项目范围][old-readme]

其 `adfu.py` 使用 PyUSB，ADFU ID `10d6:10d6`，bulk OUT `02` / IN `81`；采用 MSC CBW/CSW 包装，
vendor CDB `cd`，子命令：RAM 写 `13`、storage 写 `10`、切换 helper `20`、执行 `21`、读取结果区 `23`。
`23` 接口没有任意读地址参数，**不是通用 flash readback**。[host 实现][old-host]

旧 helper 地址是 `0xbfc18000`，与 LEOPARD 配置不同。该工具的 `--no-write` 只替换最终 flash-write 回调，
仍会上传/执行 helper，且 `bEraseFlag` 来自默认为真的 `erase_flash`；**不能把这个选项当作 CoMi 无损探测模式**。
本轮仅阅读源码。[旧升级路径][old-upgrade] [默认配置][old-config]

未从本次核查获得 ATS308x ROM 命令号、端点或认证握手与旧协议一致的证据。
独立 host 值得研究，但应先拿对应 ROM/原厂下载器的静态证据或匹配 EVK trace 做逐字节核对，不能先改 PID 再试。

## 恢复触发的准确边界

- SDK recovery 只有启用 `CONFIG_TXRX_ADFU` / `CONFIG_GPIO_ADFU` 才检查相应入口；成功后设置 JTAG 状态并重启至 ADFU。[recovery main][recovery]
- TX/RX 路径实际是 **GPIO loopback 检查**：输出 `0x55aa55aa` 的 32 个 bit，每 bit 等 500 µs 后读输入，完全相等才成功；不是 UART 波特率握手。[检测实现][trigger]
- GPIO key 路径临时切 input，10 µs 后低电平触发，再恢复配置。公共默认 `bootloader.ini` 的 `adfu_txrx=1` / `adfu_gpio=21` 是打包参数；不能推成 CoMi GPIO21 或某颗外部按键。[检测实现][trigger] [默认 boot 参数][boot-ini]
- 软件 reboot 把 magic 与 type 写入 `RTC_REMAIN3`，再触发 watchdog；`dbg reboot adfu` 因而是改变设备状态的命令，不是读取身份。[重启实现][reboot]
- J-Link 附带 ADFU 脚本同样写寄存器并 reset/run；不能当作只读 SWD attach。[脚本][jlink-adfu]

补充：分区无效 / `GOTO_OTA` 分支先于 GPIO 检查；本公开树的 `ota_main()` 是无限循环占位代码，不能由外层分支推定自动救援。详见 [恢复评估](flash-recovery-assessment.md)。

## 签名与备份：下一步应取得什么

BROM API 包含签名验证、SHA-256 和带 `digital_sign` 参数的镜像检查；应用 bootloader 的条件签名实现已核对。
它们证明 SDK 有安全启动能力，**不证明 CoMi 开启，也不证明 ROM ADFU 会接受未签名 RAM helper**。
读接口、RAM 执行权限、flash 写权限、应用启动验签应分别调查。[BROM 接口][brom] [启动验签][sign]

| 可推进工作 | 产物 / 成功标准 |
|---|---|
| 正常与恢复 USB 身份记录 | 完整 device/config/interface/endpoint 描述符、VID/PID、strings、主机日志；分清本机实测与 SDK 默认 |
| 原厂包/下载器离线分析 | SHA-256、helper/flash-ID blob、storage ID、load/run 地址、鉴权条件；先确定工具行为 |
| 对应芯片 EVK 原厂下载 trace | ROM→helper 两阶段分界、重枚举、CBW/CDB 或其他协议、校验/签名；用作未来 host 实现 oracle |
| SWD 或匹配只读 helper 的备份方案 | 首先确认读保护和存储映射；列出所有 boot/系统/NVRAM/校准区域，重复读 hash 一致；有恢复验证后才称完整备份 |

当前不能声称：CoMi ADFU 键已定位、USB 数据必定接通、可无签名启动、存在完整备份或可恢复自写固件。
本轮形成的是后续取证边界和 host 协议研究入口；未把未经验证的下载器收入仓库的可执行路径。

## 固定源码索引

[sdk-download]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/README.md#L196-L237
[brom]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/brom_interface.h#L23-L48
[dfu-config]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/dfu/Kconfig#L4-L50
[dfu-desc]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/dfu/usb_dfu_descriptor.h#L26-L80
[dfu-class]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/include/usb/usb_common.h#L120
[dfu-protocol]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/include/usb/class/usb_dfu.h#L45-L52
[dfu-handler]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/dfu/usb_dfu_dev.c#L61-L96
[jlink]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/tools/JLinkDevices/Actions/LEOPARD/Devices.xml#L5-L9
[product]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/fw_product.cfg#L3-L13
[upgrade-script]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_firmware.py#L1026-L1069
[old-readme]: https://github.com/nfd/atj2127decrypt/blob/a4454cb205ff3f38061040394d78b0ad5b0235bd/README.md#L1-L6
[old-host]: https://github.com/nfd/atj2127decrypt/blob/a4454cb205ff3f38061040394d78b0ad5b0235bd/dfu/adfu.py#L24-L134
[old-config]: https://github.com/nfd/atj2127decrypt/blob/a4454cb205ff3f38061040394d78b0ad5b0235bd/dfu/actions_adfu_upgrade.py#L26-L37
[old-upgrade]: https://github.com/nfd/atj2127decrypt/blob/a4454cb205ff3f38061040394d78b0ad5b0235bd/dfu/actions_adfu_upgrade.py#L570-L640
[recovery]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/application/recovery/src/main.c#L21-L58
[trigger]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/soc.c#L51-L108
[boot-ini]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/bootloader.ini#L10-L12
[reboot]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/soc_pm.c#L263-L288
[jlink-adfu]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/jlink_script/jlink/jlink_adfu.txt#L1-L5
[sign]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/soc_boot.c#L79-L168
