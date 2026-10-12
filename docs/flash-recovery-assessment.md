# CoMi 烧录、失败恢复与现有固件提取评估

2026-10-12。源码与有界实机诊断；本轮未发送烧录、擦除、重启或下载 helper 命令。
SDK 固定为 `lvgl/lv_port_actions_technology@26f51e584940d5b141cd1d09d2629d69b595f579`。
设备实测见 [USB/log 记录](usb-log-probe.md) 与 [本轮诊断](device-diagnostics.md)；SDK 分支不能当作 CoMi 实际配置。

**理论上存在自写固件与恢复路径；当前还没有 CoMi 可烧录、可完整备份、失败后可恢复的实证。**
编译成功只满足第一环。闭环还需匹配板配置、实际写入入口、启动授权、完整原厂资料及独立恢复入口。

## 四个问题的直接答案

| 问题 | 已确认事实 | 条件推断 | CoMi 未知 |
|---|---|---|---|
| 能烧录自己的固件吗？ | SDK 有 OTA 写入/校验、ADFU 生产配置及 J-Link 存储支持；启动层有条件签名路径。[OTA 写入][ota-write] [传输研究](recovery-transport.md) [签名][sign] | 能找到本机入口、匹配芯片/存储/板级配置且获得启动授权，才可能运行自写固件 | 型号、分区、接口、签名/加密策略；尚无可直接使用的 CoMi 配方 |
| 烧进去之后会怎样？ | SDK 会检查镜像头、入口地址、长度与 checksum；通过后跳入应用。[镜像检查][image-check] [跳转][nor-boot] | 包可能被拒绝；镜像可能写入但启动检查失败；也可能进入应用后黑屏、失去 BLE、重启或无法录音 | 参考板固件行为不可预测；尚未在 CoMi 写入/启动 |
| 失败后能恢复官方吗？ | SDK 有独立 recovery、临时升级区、ADFU 入口；但本公开 recovery 的 `ota_main()` 是无限循环占位实现。[启动流程][recovery-main] [占位实现][ota-stub] | 保留有效 boot/recovery，且应用死掉仍可进入已验证恢复入口，并有正确原厂包/备份，才有恢复基础 | 当前没有验证恢复入口、原厂完整包或回刷；不能承诺“随便刷，刷坏再救” |
| 能提取正在运行的固件吗？ | CoMi 已实测执行 shell 并返回 `Zephyr version 2.7.0`；SDK 有条件编译的 flash/内存读取命令，但部分处理器有单位/长度问题。[实测](evidence/log-device-info-2026-10-12.json) [命令与开关][shell-reg] [读取处理器][shell-read] | 本机帮助已列读取命令，固定 NOR 头读取进入 handler 但未传回数据；需先解决读取输出，再评估分区级备份；SWD/匹配只读 helper 是其他候选 | 后续已重读16字节映射代码，见[代码读回](mapped-code-readback.md)；没有完整物理flash备份 |

## 新证据：recovery 不等于自动回滚

固定参考板 `ats3089p_dev_watch_sdnand_8b` 的实际启动调用链：

1. recovery `main()` 检查分区表；无效或收到 `GOTO_OTA` 时进入 `ota_main()`。[入口][recovery-main]
2. 检查配置的 GPIO/TXRX ADFU 入口；成功才设置标志并重启到 ADFU。[入口][recovery-main]
3. 只有 pstore OTA 标志或 NVRAM `REC_OTA_FLAG=yes` 才运行暂存包的 recovery；不是每次应用崩溃都会触发。[许可判断][recovery-allowed]
4. `board.c:boot_to_application()` 固定调用 `boot_to_app(0, BOOT_FLASH_ID_NOR)`，并未根据试启动结果切换 SYSTEM A/B。[板级启动][board-boot]
5. NOR 路径执行镜像检查；失败会恢复 boot 映射并返回，成功才跳转应用。调用返回后 recovery 请求 `GOTO_OTA` 重启。[NOR 路径][nor-boot] [入口][recovery-main]
6. 下一次的 `ota_main()` **实际只有无限日志/睡眠循环**。外层虽写了“OTA 失败→ADFU，成功→正常重启”，这个 callee 不返回，不能把注释/外层分支当作可用修复功能。独立 `ota_app` 目录的同名实现也如此。[recovery 占位][ota-stub] [ota_app 占位][ota-app-stub]

镜像检查发生在跳转前；“checksum 正确，但应用立即死循环/访问错误外设”不属于该检查的能力。
因此，黑屏/看门狗重启不能据此推成自动回滚。看门狗可能重启到同一个坏应用；这是上述控制流的推断，未在 CoMi 验证。
`mbrec.bin`/ROM 的更早启动与故障处理不由这条应用源码调用链完整覆盖，也不能据此否定本机可能存在其他恢复功能。

参考 XML 确实有 `fw0_boot/fw1_boot`、`fw0_param/fw1_param`，但只有一个 SYSTEM `fw0_sys`；
SYSTEM 的 `ota_embed=TEMP` 指向临时升级路径。临时区放在 `storage_id=1`，不能把 boot/param 双副本或 TEMP 理解为保留整套旧应用。[启动分区][layout-boot] [临时区][layout-temp]

OTA 实际提交链也不包含“新应用运行健康后才确认”：

- 先找同一 file ID 的 mirror 分区；缺失时，recovery 模式允许写非当前执行分区的原分区。这可以覆盖唯一 SYSTEM。[目标选择][ota-write]
- 写完及文件校验通过后更新 firmware version，保存 `UPGRADE_DONE`，再向 backend 报告成功；这个时点尚未运行新应用。[提交顺序][ota-commit]
- breakpoint 记录写入状态/偏移并 sync 存储，`DONE/PENDING` 清除文件状态；这是升级续传/写入完成机制，不能等同运行失败回滚。[断点保存][breakpoint]
- 本树 `OTA_FULL_UPGRADE=1` 路径可把 boot/param 写到 mirror 后**擦除当前副本**；布局/manifest 是否提供这些文件决定是否走此路径。[开关][full-flag] [最后写 boot/param][ota-write]
- 版本检查默认拒绝同版/旧版，patch 还要求匹配旧版本。即使持有原厂 OTA，也需确认本机允许回装原版，不能假设通用 OTA 会降级。[版本检查][version-check]

## “刷坏”分别意味着什么

| 失败层 | 可能表现（推断） | 恢复所需条件 |
|---|---|---|
| 升级包/板名/版本被拒绝，未进入写入 | 仍运行官方系统 | 先确认准确拒绝点与是否已经产生部分写入；不能仅凭 App 报错推定原样保留 |
| 应用区镜像损坏/不符合启动格式 | 无法跳入应用、停在 recovery 或重启 | boot/recovery 仍有效；独立入口与正确应用/资源包已验证 |
| 镜像合法但板级配置或应用错误 | 黑屏、BLE 消失、死循环、频繁重启；可能无法从 App 发升级命令 | 不依赖应用正常运行的恢复入口；应用内 BLE OTA 不能充当独立救援方式 |
| boot/param/recovery/flash-ID 配置损坏 | 连 recovery 都无法启动，或找不到存储 | 实际 ROM 下载入口、匹配 RAM helper/存储驱动与原厂完整内容；或可用 SWD/编程器 |
| 设备身份/校准/NVRAM 被覆盖 | 系统能启动仍可能丢失配置或无线校准 | 该设备原始数据；通用升级包不保证包含每台设备独有内容 |
| 错误供电、充电或 GPIO 初始化 | 外设异常，可能出现电气风险 | 先恢复正确板级行为；软件回刷无法保证修复已发生的物理损伤 |

上述是失败分类，**不是已观察到的 CoMi 故障**。板级风险有具体源码依据：参考板启动会配置串口、存储、LCD pinmux，
条件路径还会切换电源输出模式、关闭内部充电器并配置唤醒源；这些操作在应用 `main()` 前执行。[早期初始化][board-init]
即使打算写“最简单 hello world”，链接了参考板初始化也不是只执行自己的几行代码。

## 读取现有固件：精确到处理器的限制

| 候选路径 | 固定源码实际行为 | 研究边界 |
|---|---|---|
| `dbg fread spi_flash <offset>` | `CONFIG_CMD_SPINOR` 控制；精确名称 `spi_flash` 才传长度 512，`offset` 用 base 0 解析；NOR 驱动按 byte 读取。[处理器][shell-read] [NOR 驱动][nor-read] | 候选 NOR 512 B 读取；实机 offset 0 已返回 fread 状态行，无 512 B 正文；容量/区域与完整输出仍待确认，见 [实测](device-diagnostics.md) |
| `dbg fread sd/spinand <offset>` | 同一处理器传 `size=1`，注释称 sector；但 SD 驱动把 byte len 右移 9 得零，SPI NAND 驱动要求 offset/len 为 512 B 倍数，因此命令与驱动不匹配。[处理器][shell-read] [SD 驱动][sd-read] [NAND 驱动][nand-read] | **不能按帮助文本把它作为 SD/NAND 备份工具**；失败处理器仍可能返回 0，必须判正文与收到的字节 |
| `dbg snandr <offset> <size>` | `CONFIG_CMD_SPINAND` 控制；固定分配 2048 B，直接使用用户 size，缺少上界；驱动要求 byte 对齐且不超过逻辑容量。[处理器][shell-read] [注册][shell-reg] [驱动][nand-read] | 若未来验证可用，只能受控对齐分块；逻辑 NAND read 不保证含 OOB、坏块表和隐藏启动区域 |
| `dbg mdb/mdh/mdw` | `CONFIG_CMD_MEMORY` 控制；地址/数量按十六进制解析，直接解引用；没有“仅 flash 地址”检查。[处理器][mem-read] [注册][shell-reg] | 读取未知地址可能 fault 或访问 MMIO；XIP 读出的映射内容也不等于完整物理存储 |
| ROM helper / SWD | 有地址与工具配置线索；没有匹配 CoMi 的只读读回验证 | 见 [独立传输研究](recovery-transport.md)；先区分读权限、RAM 执行权限与写入权限 |

相邻 `dbg snort` 名字像测试，实际依次调用读速度与**写速度**测试；`snandw`、`dumpbuf`、`ramdump` 等也不是原始存储只读命令。[NOR 测试][shell-read]
当前不发布“固件提取脚本”：没有已验证的真实读回传输与地址范围，先写批量 dump 只会放大这些未知。

## 什么才能称为“足够恢复”的备份

原厂 OTA 文件、录音导出、内存 dump 和原始存储备份覆盖范围不同。应逐区域记录：

1. **存储清单**：主控型号、全部启动/数据介质、容量、接口与 storage ID；确认是否另有 NOR、SD/eMMC boot 区、NAND 隐藏区。
2. **启动必需内容**：boot/mbrec、分区表/param、recovery、应用、依赖的 SDFS/资源/DSP，全部 mirror 副本；映射读与原始读的 CRC/加密转换区别。
3. **设备独有内容**：factory RO/RW、user NVRAM、身份/无线校准（具体存放位置待确认）；另存所有录音。SDK 配置确有 factory/user 分区，OTA 关闭；并非 app.bin 的一部分。[布局][layout-nvram]
4. **不可普通回刷内容**：OTP/eFuse、芯片 UID、ROM 与保护位需单独记状态；不假设可读、可复制或可逆。签名私钥不会由普通固件备份自动获得。
5. **证据清单**：设备与固件版本、来源、每块起始地址/长度/单位、原始文件、SHA-256、两次独立读一致；动态 NVRAM 区变化需解释，不能悄悄忽略。
6. **恢复闭环**：独立入口可反复进入/退出，写回工具与范围经过核查，官方完整包或可写回备份与本机匹配；最终需实际恢复启动、录音、BLE 与身份校准验收，才称“恢复已验证”。

以上是后续备份验收要求，不是目前已具备的能力。下一步最有价值的是取得原厂更新包、在已确认可执行的 BLE shell 上解决读取数据的输出通路、
读出本机板名/分区/存储信息；在完整恢复证据形成前，现有 EVK 固件不能直接用作 CoMi 烧录实验。

## 固定源码索引

[sign]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/soc_boot.c#L79-L168
[image-check]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/boot/soc_boot_priv.c#L188-L257
[nor-boot]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/boot/soc_boot_priv.c#L368-L405
[recovery-main]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/application/recovery/src/main.c#L21-L89
[recovery-allowed]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/application/recovery/src/ota_recovery/recovery_main.c#L256-L272
[ota-stub]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/application/recovery/src/ota_recovery/recovery_main.c#L274-L282
[ota-app-stub]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/application/ota_app/src/ota_recovery/recovery_main.c#L264-L272
[board-boot]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/boards/arm/ats3089p_dev_watch_sdnand_8b/board.c#L21-L29
[layout-boot]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/hello_world/boards/ats3089p_dev_watch_sdnand_8b/firmware.xml#L14-L111
[layout-temp]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/hello_world/boards/ats3089p_dev_watch_sdnand_8b/firmware.xml#L321-L335
[layout-nvram]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/hello_world/boards/ats3089p_dev_watch_sdnand_8b/firmware.xml#L131-L174
[ota-write]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_upgrade.c#L1193-L1305
[ota-commit]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_upgrade.c#L1578-L1613
[breakpoint]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_breakpoint.c#L164-L234
[full-flag]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_upgrade.c#L39-L41
[version-check]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/ota/libota/ota_upgrade.c#L1344-L1387
[board-init]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3089p_dev_watch_sdnand_8b/board.c#L332-L358
[shell-read]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L414-L515
[shell-reg]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L2426-L2454
[nor-read]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spi_flash_acts.c#L78-L111
[sd-read]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L1465-L1471
[nand-read]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/spinand/spinand_acts.c#L157-L205
[mem-read]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L138-L179
