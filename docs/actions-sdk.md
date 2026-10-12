# Actions SDK 与 CoMi Note 自写固件可行性

2026-10-12。本文 SDK 核查为主机侧源码阅读；未编译 SDK、未发送 BLE log/OTA 命令、未刷机。
同轮设备调查另做了 BLE GATT 枚举，结果见[本地证据](evidence/gatt-2026-10-12.json)，未操作应用特征。
本文把原 rlcdv 调研中与本设备相关的线索重新核对到公开源码；阅读本文不需要 rlcdv。

**结论：已有可用的 Actions 308x 开发入口，但尚不能挑一个参考板固件直接刷 CoMi。**
阻塞点是实际 SoC/板级连接、原厂镜像与分区、启动签名策略、可恢复的下载入口。
尤其需要修正交接中的两处过度推断：AOTA 容器只有 CRC 不代表启动链无签名；log service UUID 存在不代表本机开放了 shell。

## 证据边界

| 结论 | 证据状态 | 对 CoMi 的含义 |
|---|---|---|
| Actions SDK 与 CoMi 暴露相同 `e49a3001/3002/3003` BLE log UUID | 公开源码已核对 [log GATT][log-gatt]；[同轮 CoMi GATT 枚举](evidence/gatt-2026-10-12.json)独立复核 | Actions 软件栈血缘的强证据；不能确定 ATS3085S、ATS3089P 或 ZS308B |
| `LEOPARD` 是 Cortex-M33，带 DSP 指令、FPU、DWT、MPU | SDK Kconfig 已核对 [CPU][cpu] | 是候选 SDK 的架构；实际 CoMi 型号仍未知 |
| SDK 内的 Zephyr 版本字段为 2.7.0 | 已核对 [VERSION][version] | 自写固件可以从此 vendor fork 入手；不代表 CoMi 原厂使用完全相同版本 |
| log 文本 TLV 可进入 `shell_execute_cmd` | SDK 条件路径已核对 [shell dispatch][log-shell] | 需启用 serial 或 RTT shell 后端；后续已验证本机版本/帮助命令；完整命令行为与连接安全策略未验证 |
| OTA GATT/TLV/AOTA/recovery 实现存在 | 公开源码已核对，见下文；同轮 GATT 枚举未见 OTA 服务 | CoMi 当前正常模式未发现同一 OTA 服务；入口与兼容性未知 |
| 正常 USB 仅见充电，录音 MP3 16 kHz mono 32 kbps，容量约 58 GiB | 交接中已有设备观察；本轮未重测 | 均不能单独确定启动存储、USB 引脚是否接出或 SoC 型号 |

本轮实际可读的是 LVGL 组织公开仓库 `lvgl/lv_port_actions_technology`，固定提交
`26f51e584940d5b141cd1d09d2629d69b595f579`。它自称 Beta SDK，含 `hello_world` 与 Actions SDK。
交接提到的非公开 `actions-sdk-research` 目录在本轮环境不存在，因此不把其独有内容作为已复核事实。

## 可复现获取与构建路径

仓库外获取源码，固定提交；本仓库不复制整套 SDK 或非公开 SDK：

```sh
git clone https://github.com/lvgl/lv_port_actions_technology.git ~/w/_tmp/lv_port_actions_technology
git -C ~/w/_tmp/lv_port_actions_technology checkout --detach 26f51e584940d5b141cd1d09d2629d69b595f579
```

已存在目录则核对 `git rev-parse HEAD`，不要覆盖已有改动。
SDK 自带 `zephyr/` 与 `bootloader/` 两棵 OS 树；构建自写应用先按公开仓库的 `hello_world` 流程，
而不是以最新上游 Zephyr 替换 vendor fork。[开发入口][readme]

- **上游说明支持 Linux/Windows 构建和下载**；SoC 配置、初始 blob/文件系统打包依赖 Windows 配置工具。
  工具已附在公开仓库 `tools/config_tool.rar`，J-Link 设备描述在 `tools/JLinkDevices/Actions/LEOPARD/Devices.xml`。
  macOS 构建/完整打包未获此说明支持，推荐先在隔离的 Linux 构建环境复现，Windows 负责原厂工具。[host 与工具][readme]
- 构建入口在 `action_technology_sdk/zephyr/`，先 source `zephyr-env.sh`；脚本提供 `build.sh -n`
  选择板卡和应用。默认 GCC 路径实际调用 `west build -p auto -b BOARD -d OUT APP`；`-k` 才选择 Keil。
  `-p` 仅打包，`-m` menuconfig。[build.py][build]
- 编译器选择通过 `ZEPHYR_TOOLCHAIN_VARIANT`。Zephyr SDK 路径由 `ZEPHYR_SDK_INSTALL_DIR` 指定；
  CMake 写的是**最低版本 0.11.1**，不是经过测试的最佳版本。另有 GNU Arm Embedded 路径：
  `ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb`、`GNUARMEMB_TOOLCHAIN_PATH`、`arm-none-eabi-*`。
  当前公开说明只要求安装 Zephyr SDK，并提醒现代版本可能遇到 warnings-as-errors。
  **没有从这份树确认唯一精确 GCC/Zephyr SDK 版本，也未完成 ABI/链接验证。** [SDK 检测][toolchain] [gnuarmemb][gnuarm]
- 脚本还调用 `python` 执行 packer；按本仓库约定，未来应在 `uv` 管理的隔离环境中运行，
  先核对 SDK Python requirements、CMake、Ninja、west。这里没有伪装成已验证的一键构建配方。
- 产物不同：`zephyr.elf/.hex/.bin` 是应用编译结果；`_firmware/*.fw` 是配置/下载工具产物；
  `AOTA` 是 OTA 容器。不能按扩展名把三者互换。[产物与下载流程][readme]

公开说明的 EVK 示例是 `ats3089p_dev_watch_sdnand_8b`。
**该板只是构建工具链的验证目标，不能据此选作 CoMi 的硬件目标。**

## 板级配置与分区：从哪些文件恢复实际硬件

SDK 板目录位于 `action_technology_sdk/zephyr/boards/arm/BOARD/`；应用可在 `APP/boards/` 覆盖。
`build.py` 会从板/应用目录拼装固件布局和资源，不能只阅读板级 `firmware.xml`。[打包路径][pack]

| 候选参考 | 已核对用途 | 需要抄取的知识，非直接抄用配置 |
|---|---|---|
| `ats3089p_dev_watch_sdnand_8b` | 公开 hello_world 示例；MMC SD、SD 文件系统、32 MiB PSRAM、UART0 115200 | `*_defconfig` 的内存/驱动选择；`board_cfg.h` 引脚和供电；`board.c` 初始化 [defconfig][p-def] |
| `ats3085s_watch_bootemmc` | 明确 `CONFIG_BOARD_EMMCBOOT=y`，有 MMC/SD 存储配置 | eMMC 启动与普通 NOR+SD 数据板的差别；不能由 64 GB 用户容量推定使用此方案 [eMMC 配置][emmc-def] |
| `ats3085s_dev_watch_sign` | bootloader 板配置定义 `CONFIG_SOC_SIGN_ENABLE`；应用板附带 `sign-img/` | 必须调查签名启动链；应用打包时可能用预签名 blob 替换新编译结果 [签名板][sign-board] [覆盖逻辑][pack] |

布局示例差别非常大：

- `hello_world/boards/ats3089p_dev_watch_sdnand_8b/firmware.xml`：声明 16 MiB，
  BOOT `0x0`、SYS_PARAM `0x1000`，另有镜像 BOOT/PARAM，RECOVERY `0x4000`、SYSTEM `0x24000`；
  SYSTEM OTA 开，BOOT/RECOVERY OTA 关；有 factory/user NVRAM 与 log/coredump 区。[P 示例布局][p-layout]
- `ats3085s_watch_bootemmc/firmware.xml`：声明 128 MiB；BOOT `0x0` 与 `0x20000`、
  PARAM `0x40000`/`0x60000`、RECOVERY `0x80000` 使用 storage_id 4，
  SYSTEM `0x1a0000` 使用 storage_id 0；包含不同存储目标。[eMMC 布局][emmc-layout]

这些是参考板打包地址，不是 CoMi 分区表。后续需要原厂更新包或完整存储读回，
识别 `mbrec.bin/param.bin/recovery.bin/app.bin/sdfs.bin/nvram.bin`、存储介质/ID、实际地址、
校准/身份/NVRAM 区域后，才能起草 CoMi 板目录。屏幕、触摸、按键、麦克风接线、充电器与电池保护同样需要实际证据。

## OTA：格式已知，CoMi 可用性未知

SDK 的 Actions OTA 服务为 `e49a25f8-f69a-11e8-8eb2-f2801f1b9fd1`；
RX `e49a25e0-…` Write/WriteWithoutResponse，TX `e49a28e1-…` Notify。[OTA GATT][ota-gatt]
控制协议 service ID `0x09`，请求/协商/设备拉取数据/发送数据/验证/状态等命令，支持单位数据 CRC；
源码推荐 BLE unit 230 B、SPP 650 B，并非测得的 CoMi 吞吐或 MTU。[OTA transport][ota-bt]

公开 bt_watch 默认前台 OTA、Bluetooth/SD backend、recovery、temp partition；
SD NAND 应用板把临时存储指向 `sd`。这是**配置选择**，不是所有 SDK 产品固有行为。[默认 OTA][ota-conf] [SD temp][ota-sd]
前台实现设置 `flag_use_recovery=1`，结束时给 main 发重启事件；
独立 ota_app 外层虽写失败转 ADFU、成功正常重启，但实际 `ota_main()` 是无限循环占位实现，不能视为恢复保证；详见 [恢复评估](flash-recovery-assessment.md)。[前台路径][ota-fg] [ota_app][ota-main]

`AOTA` 容器在本提交的关键结构：

| 字段/区域 | 公开 packer 行为 |
|---|---|
| magic/version | ASCII `AOTA`；version `0x0100` |
| header/directory/data | header size `0x400`；directory `0x200`，entry 32 B；data `0x400` |
| entry | 12 B 文件名、offset、length、CRC32，剩余保留；文件按 512 B 填充 |
| `data_size` | packer 写入文件数据最终结束 offset，包含整个头的偏移与尾部 padding；不应直接理解为 payload 长度 |
| 校验 | header CRC32 覆盖 `[8:0x400]`；data CRC32 覆盖 `[data_offset:data_size]`；另有单文件 CRC32 |

[打包实现][ota-pack]；设备读取与 CRC 逻辑见 [ota_image.c][ota-image]。
packer 强制包含 `ota.xml`；LZMA 支持默认开，差分实现有 hpatch，
但 CoMi 支持哪些模式以及外层是否另有封装仍未知。[LZMA][ota-kconfig] [hpatch][hpatch]

**不要把 CRC 校验等价成未签名启动。** AOTA 读取层未看到公钥签名校验；
另一层的 bootloader `CONFIG_SOC_SIGN_ENABLE` 路径会寻找 RSA-2048 签名 TLV，加载 boot image 公钥并验证。
关闭时该检查返回 0；这只能证明 SDK 支持两种配置。签名 TLV 宏名含 `PSS`，但 `soc_rsa.c`
实现注释称 PKCS1.5，因此此处只称 RSA-2048，不据宏名断言填充算法。[启动验证][boot-sign] [RSA 实现][rsa]
构建脚本检测 `sign-img/` 并覆盖 app/recovery/ota_app；加密打包另走 `encrypt.bin`/`E_CHECK.FW`。
CoMi 是否签名、是否熔丝约束、原厂密钥与 ROM 级策略均未确认。[打包][pack]

额外格式陷阱：`ota_image.c` 声明的 `ota_fw_ver` 与 Python packer 当前版本串布局不一致：
C 为 96 B、`board_name[32]`；Python 为 `<32s24s4xIxI`。
做离线解析应保留版本区域原始字节，并以 `ota.xml` 为版本/板名依据；不要照搬 C struct 给任意包标版本。[C 声明][ota-image] [packer][ota-pack]

## Log service 与恢复入口

SDK logsrv GATT 权限没有 `WRITE_ENCRYPT`/`WRITE_AUTHEN`；文本 TLV type `0x01` 经解析器送到
`_logsrv_proc_console_text()`，然后仅在 `CONFIG_SHELL_BACKEND_SERIAL` 或 RTT 下执行 shell。
64 B 临时 TLV buffer、日志/握手状态机也在此文件中；它不是普通终端裸文本特征。
**后续实机已执行 `kernel version`、`help` 与 `dbg`，返回 Zephyr 2.7.0 和命令清单；见 [诊断记录](device-diagnostics.md)。这不验证任意命令或所有安全策略。** [GATT][log-gatt] [解析/执行][log-shell]

源码中有准确命令 `dbg reboot adfu`：`shell_dbg.c` 的 `SHELL_STATIC_SUBCMD_SET_CREATE(sub_dbg, …)`
注册 reboot 子命令，参数 `adfu` 调 `sys_pm_reboot(REBOOT_TYPE_GOTO_ADFU)`。
本机帮助已列出该命令，**不是本轮已测试的 CoMi 恢复方法；本轮未发送**。[处理器][adfu-shell]

硬件入口也有 SDK 依据：recovery 支持按配置检查 TX/RX 或 GPIO key 进入 ADFU；
公开 EVK 教程是断电→按住 ADFU 键→上电→Windows 工具选 ADFU0。
EVK UART0 RX/TX 还能复用 SWDIO/SWDCLK，J-Link 有专用设备支持。
上述针脚、键和 USB 数据连通性都必须在 CoMi 板上重新确认，不能把 EVK 操作直接套到整机。[recovery 检查][recovery] [EVK 下载][readme]

## 对自写录音固件最有用的现成模块

- 第一条录音纵切可从 `application/app_demo/audio_demo` 入手：8 KiB PCM ring buffer、
  4 KiB 文件缓存，定时读流写文件，demo 30 s 截止。比直接接完整 bt_watch 更容易验证音频→存储链路。[audio_demo][audio-demo]
- 板级 `board_audio_input_map[]` 明确模拟 MIC0、双模拟 MIC2、双 DMIC 映射；
  双麦能力是 SDK 参考配置，CoMi 实际麦克风数量/接法需拆机。[音频映射][audio-map]
- MP3/Opus encoder Kconfig 与 `aeRECORD.dsp` 配置已存在；public tree 的模块选择不能证明配套 DSP blob 齐全或能独立构建。
  CoMi 原厂 MP3 不意味着自写固件一定要复用该 codec。[encoder 配置][codec]

公开 SDK 仍有二进制边界：仓库跟踪 `libbt_stack.a`、`libmedia.a`、`libboot.a` 等库；
CMake 会导入预编译库，不能把“有公开 SDK”理解为所有底层均可重编译。
本提交没有跟踪 `aeRECORD.dsp`，使用对应 encoder 路径还需补齐实际 blob。[媒体库导入][media-lib] [BT 库导入][bt-lib]
后续发布自写固件时需逐项确认所用 blob/代码授权；本轮未复制 SDK 库或镜像进本仓库。

## 下一轮需要补齐的证据

1. 拆机记录主 IC 完整丝印、PCB 版号，启动 NOR/NAND/eMMC/SD 芯片与容量；屏/触摸/音频/电源器件丝印。
2. 原厂升级文件与来源、SHA-256；离线识别是否 AOTA，提取 `ota.xml`、board name、image/分区/签名 TLV；尚无本机升级镜像。
3. 在不刷写前提下定位 UART/SWD/USB D+/D−、ADFU 键或测试点；取得启动日志；记录恢复入口和身份。
4. 验证启动签名策略与备份范围。现有 BLE 录音文件下载不是固件备份；自写 app 还需匹配 bootloader、资源与校准区。
5. 在匹配芯片的 EVK/可恢复目标先证明固定提交能编译、打包、下载；记录编译器精确版本、所缺 binary、最小修改。
6. 得到实际板配置后再做最小 bring-up：启动日志→安全供电/充电→存储读写→PCM→屏幕→BLE。

## 固定源码索引

以下均来自上述公开固定提交；链接可离开本机及 rlcdv 阅读。

[readme]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/README.md#L1-L283
[cpu]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/Kconfig.series#L4-L14
[version]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/VERSION#L1-L5
[build]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/build.py#L623-L665
[toolchain]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/cmake/toolchain/zephyr/host-tools.cmake#L1-L55
[gnuarm]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/cmake/toolchain/gnuarmemb/generic.cmake#L1-L32
[pack]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/build.py#L470-L610
[p-def]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3089p_dev_watch_sdnand_8b/ats3089p_dev_watch_sdnand_8b_defconfig#L58-L165
[emmc-def]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3085s_watch_bootemmc/ats3085s_watch_bootemmc_defconfig#L9-L160
[sign-board]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/boards/arm/ats3085s_dev_watch_sign/board_cfg.h#L15-L16
[p-layout]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/hello_world/boards/ats3089p_dev_watch_sdnand_8b/firmware.xml#L1-L235
[emmc-layout]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3085s_watch_bootemmc/firmware.xml#L1-L179
[ota-gatt]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/ota/ota_app_background.c#L211-L250
[ota-bt]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/ota_backend_bt.c#L22-L56
[ota-conf]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/prj.conf#L268-L279
[ota-sd]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/boards/ats3089p_dev_watch_sdnand_8b.conf#L24
[ota-fg]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/ota/ota_app_foreground.c#L325-L450
[ota-main]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/application/ota_app/src/main.c#L47-L82
[ota-pack]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_ota_image.py#L147-L403
[ota-image]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_image.c#L22-L362
[ota-kconfig]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/Kconfig#L9-L21
[hpatch]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/hpatch.c
[boot-sign]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/soc_boot.c#L79-L168
[rsa]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/soc_rsa.c#L546-L549
[log-gatt]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L154-L193
[log-shell]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L685-L737
[adfu-shell]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L1212-L1235
[recovery]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/application/recovery/src/main.c#L21-L87
[audio-demo]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/app_demo/audio_demo/src/audio_app/audio_app.c#L17-L93
[audio-map]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3085s_watch_bootemmc/board.c#L386-L414
[codec]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/media/codec_config.c#L270-L302
[media-lib]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/media/CMakeLists.txt#L28-L35
[bt-lib]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/bluetooth/bt_stack/CMakeLists.txt#L19-L23
