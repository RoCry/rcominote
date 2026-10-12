# CoMi 烧录、失败恢复与现有固件提取评估

更新2026-10-13。综合源码、保留镜像与既有实机证据；本次更新仅离线分析，未烧录、擦除、重启或执行 helper。
SDK 固定为 `lvgl/lv_port_actions_technology@26f51e584940d5b141cd1d09d2629d69b595f579`。
设备实测见 [USB/log 记录](usb-log-probe.md) 与 [本轮诊断](device-diagnostics.md)；SDK 分支不能当作 CoMi 实际配置。

**理论上存在自写固件与恢复路径；当前还没有 CoMi 可烧录、可完整备份、失败后可恢复的实证。**
编译成功只满足第一环。闭环还需匹配板配置、实际写入入口、启动授权、完整原厂资料及独立恢复入口。

当前实证：Cortex-M4 r0p1；固件板名`ats3085l_dvb_watch_ext_nor_max`；ACPT覆盖4 MiB NOR，录音另走SD。完整system927632 B、boot3672 B、录音DSP110148 B已校验；[recovery原始/明文63,288 B完整校验](recovery-complete.md)，应用交接已静态解释。仍无整片原始备份、匹配官方恢复包、烧录或独立恢复验收。优先级以[研究路线](research-routes.md)为准。

## 四个问题的直接答案

| 问题 | 已确认事实 | 条件推断 | CoMi 未知 |
|---|---|---|---|
| 能烧录自己的固件吗？ | [实际OTA写入/提交链](ota-write-commit.md)、[boot→ROM入口](actual-boot-flow.md)已定位；本机为M4，公开完整参考BSP为M33 | 匹配传输、板级初始化、镜像格式与启动授权后才可能运行 | 更早启动授权、交接运行态、ROM加载权限、匹配M4 BSP/库、独立恢复仍未闭合；没有可直接使用的CoMi烧录配方 |
| 烧进去之后会怎样？ | [实际boot](actual-boot-flow.md)加载recovery；[完整recovery](recovery-complete.md)揭示slot0映射、加法验收与PSP/BX，晚期失败不能保证旧映射恢复 | 包可能被拒绝；已写入镜像也可能不能启动；错误外设初始化可能使BLE/显示/录音失效 | 尚无自写镜像的实机写入/启动，不能用参考板编译或OTA CRC通过预测结果 |
| 失败后能恢复官方吗？ | 实际分区只有一个system；boot/param有镜像，另有recovery/TEMP；[成功通知早于新固件启动](ota-write-commit.md) | 有应用之外的入口、匹配完整内容与可验证写回方式，才有恢复基础 | 独立入口/退出与官方回刷未验证；boot/param双槽不是整套系统回滚 |
| 能提取正在运行的固件吗？ | system、boot、DSP和ACPT已取得；system映射字节不是整片物理NOR；recovery完整校验；[factory-RW8KiB私有备份](factory-rw-backup.md)完成 | 可靠bulk读回与逐区完整性验收可以进一步形成可恢复备份 | factory-RO/user NVRAM、其余资源、分区副本仍未齐；[慢速日志NOR批量导出已退役](nor-efficiency.md)，不继续盲目长跑 |

## 启动授权问题：缺的材料与不能替代它的产物

此前缺失的镜像`1100e4e8`现已包含于[完整校验recovery](recovery-complete.md)，静态对应RAM `18000450`。局部checker只做向量/尺寸/加法检查，未见参考验签分支；这不证明更早ROM/boot无授权。slot0写入与PSP/BX已解释，复制和执行仍未实测；晚期校验失败存在旧映射局部被entry覆盖的问题。保留独立恢复门槛，不把OTA CRC当作启动验签。
固定SDK的应用构建在`CONFIG_FLASH_LOAD_OFFSET==0`时取消`CONFIG_SOC_SIGN_ENABLE`（[审计](boot-security-source-audit.md)）；即便找到应用中的同源成功stub，也不能推成recovery接受未签名镜像。

另一个已取得产物是SDK [`boot_recovery.app`][lark-recovery-blob]，不能按文件名当作CoMi recovery。
6792 B，SHA256=`00f30f32e754e1b33110b0f98a2b9387ffc4808ccf049ea260e2e326a1cd39f1`。
仅由bootloader树LARK `fw_product.cfg:13`以`RECOVERY_IM`引用；没有本机使用它的证据。
[原始指令与literal](evidence/lark-recovery-writer-2026-10-13.json)保留两个完整code区间，排除尾部数据；root与Astra独立核对。其直接流程：

| 参考程序观察 | 对恢复路线的意义 |
|---|---|
| 原始向量SP=`01004000`，entry=`10000009`；无ELF/ACTH头 | 与实际63288 B recovery不同；没有CPU/FPU属性，也未建立CoMi加载契约 |
| main`1000173c`读取`10001a88`起的块数/块长，正好在文件末尾之外 | 必须另有追加载荷；单独文件不是完整可运行的恢复包 |
| 查询`fw0_sys`，复制压缩输入并调用decoder；随后经ROM表`1a4` slots`1c/18`请求erase/write，未检查这些调用返回 | 是写入型程序；5B属性解析具有LZMA特征，未完整审计decoder；不能执行来“只读识别” |
| 后段读取`fw1_para`的4096 B并擦写`fw0_para`；decoder失败也可到达该段 | 不提供已证明的事务恢复或全机配置保留保证 |
| 最后写`4000c020=5f`并永久循环 | 观察到复位请求形状，未验证实际复位效果或独立退出 |

主流程不是普通system校验后跳转的替代模块；追加载荷与外层生成/调用契约仍缺。
停止这份stub的callee扩展：保留为LARK恢复打包、ROM NOR接口参考，**不作为CoMi救砖镜像，不替代已完整实读的本机recovery，不证明未签名镜像可启动**。

## 参考 SDK：recovery 不等于自动回滚

固定参考板 `ats3089p_dev_watch_sdnand_8b` 的实际启动调用链：

1. recovery `main()` 检查分区表；无效或收到 `GOTO_OTA` 时进入 `ota_main()`。[入口][recovery-main]
2. 检查配置的 GPIO/TXRX ADFU 入口；成功才设置标志并重启到 ADFU。[入口][recovery-main]
3. 只有 pstore OTA 标志或 NVRAM `REC_OTA_FLAG=yes` 才运行暂存包的 recovery；不是每次应用崩溃都会触发。[许可判断][recovery-allowed]
4. `board.c:boot_to_application()` 固定调用 `boot_to_app(0, BOOT_FLASH_ID_NOR)`，并未根据试启动结果切换 SYSTEM A/B。[板级启动][board-boot]
5. NOR 路径执行镜像检查；失败路径尝试恢复 boot 映射并返回，成功才跳转应用；但saved map/entry_out别名使晚期校验失败不保证恢复原值，见[实际完整交接复核](recovery-complete.md)。调用返回后 recovery 请求 `GOTO_OTA` 重启。[NOR 路径][nor-boot] [入口][recovery-main]
6. 下一次的 `ota_main()` **实际只有无限日志/睡眠循环**。外层虽写了“OTA 失败→ADFU，成功→正常重启”，这个 callee 不返回，不能把注释/外层分支当作可用修复功能。独立 `ota_app` 目录的同名实现也如此。[recovery 占位][ota-stub] [ota_app 占位][ota-app-stub]

镜像检查发生在跳转前；“checksum 正确，但应用立即死循环/访问错误外设”不属于该检查的能力。

后续[实际OTA初始化副作用](ota-initialization-side-effects.md)已把准备函数追到NOR擦除接口及`OTA_BP`持久化：这些条件路径发生在镜像对象初始化、包头校验之前。实际启动初始化与蓝牙连接回调不同；不能推断每次订阅都会重新初始化，也不能把拒收包当作绝对无写入的试验。
因此，黑屏/看门狗重启不能据此推成自动回滚。看门狗可能重启到同一个坏应用；这是上述控制流的推断，未在 CoMi 验证。
`mbrec.bin`/ROM 的更早启动与故障处理不由这条应用源码调用链完整覆盖，也不能据此否定本机可能存在其他恢复功能。

参考 XML 确实有 `fw0_boot/fw1_boot`、`fw0_param/fw1_param`，但只有一个 SYSTEM `fw0_sys`；
SYSTEM 的 `ota_embed=TEMP` 指向临时升级路径。临时区放在 `storage_id=1`，不能把 boot/param 双副本或 TEMP 理解为保留整套旧应用。[启动分区][layout-boot] [临时区][layout-temp]

参考 SDK 的 OTA 提交链不包含“新应用运行健康后才确认”（下列源码链接均指 SDK）：

- 先找同一 file ID 的 mirror 分区；缺失时，recovery 模式允许写非当前执行分区的原分区。这可以覆盖唯一 SYSTEM。[目标选择][ota-write]
- 写完及文件校验通过后更新 firmware version，保存 `UPGRADE_DONE`，再向 backend 报告成功；这个时点尚未运行新应用。[提交顺序][ota-commit]
- breakpoint 记录写入状态/偏移并 sync 存储，`DONE/PENDING` 清除文件状态；这是升级续传/写入完成机制，不能等同运行失败回滚。[断点保存][breakpoint]
- 本树 `OTA_FULL_UPGRADE=1` 路径可把 boot/param 写到 mirror 后**擦除当前副本**；布局/manifest 是否提供这些文件决定是否走此路径。[开关][full-flag] [最后写 boot/param][ota-write]
- 参考SDK版本检查默认拒绝同版/旧版，patch 还要求匹配旧版本。[版本检查][version-check] **后续实际固件修正：CoMi初始化显式设置no-version-control，并有实际跳过版本比较的分支**，见[版本策略](ota-version-policy.md)。这推翻“默认拒绝必然适用本机”的假设，仍未验证原厂包回装或恢复成功。

## 实际 CoMi 写入与成功通知：新增证据

[FW010004 指令审计](ota-write-commit.md)确认：应用写入、文件读回 CRC、
保存 PENDING/DONE、backend 成功通知、应用 DONE 回调依次发生；成功通知早于新固件启动。
当前配置选择 recovery 暂存分支，但 payload 选择循环并非硬编码只允许 TEMP：
它依 manifest file ID 找 mirror，再有条件回退原分区。尚无原厂包证明实际文件组合。
存储写入返回值被检查；CRC 读回循环丢弃读取返回值，整体断点保存也不传播失败。
这些是实际代码的条件行为，未执行 OTA、制造故障或验证掉电恢复。

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
| `dbg fread spi_flash <offset>` | `CONFIG_CMD_SPINOR` 控制；精确名称 `spi_flash` 才传长度 512，`offset` 用 base 0 解析；NOR 驱动按 byte 读取。[处理器][shell-read] [NOR 驱动][nor-read] | 早期正文不回问题后由printk ring读回取得boot/部分recovery；[吞吐与失败率审计](nor-efficiency.md)使其退出默认批量备份路线；不能把handler返回0当完整数据 |
| `dbg fread sd/spinand <offset>` | 同一处理器传 `size=1`，注释称 sector；但 SD 驱动把 byte len 右移 9 得零，SPI NAND 驱动要求 offset/len 为 512 B 倍数，因此命令与驱动不匹配。[处理器][shell-read] [SD 驱动][sd-read] [NAND 驱动][nand-read] | **不能按帮助文本把它作为 SD/NAND 备份工具**；失败处理器仍可能返回 0，必须判正文与收到的字节 |
| `dbg snandr <offset> <size>` | `CONFIG_CMD_SPINAND` 控制；固定分配 2048 B，直接使用用户 size，缺少上界；驱动要求 byte 对齐且不超过逻辑容量。[处理器][shell-read] [注册][shell-reg] [驱动][nand-read] | 若未来验证可用，只能受控对齐分块；逻辑 NAND read 不保证含 OOB、坏块表和隐藏启动区域 |
| `dbg mdb/mdh/mdw` | `CONFIG_CMD_MEMORY` 控制；地址/数量按十六进制解析，直接解引用；没有“仅 flash 地址”检查。[处理器][mem-read] [注册][shell-reg] | 读取未知地址可能 fault 或访问 MMIO；XIP 读出的映射内容也不等于完整物理存储 |
| ROM helper / SWD | 有地址与工具配置线索；没有匹配 CoMi 的只读读回验证 | 见 [独立传输研究](recovery-transport.md)；先区分读权限、RAM 执行权限与写入权限 |

相邻 `dbg snort` 名字像测试，实际依次调用读速度与**写速度**测试；`snandw`、`dumpbuf`、`ramdump` 等也不是原始存储只读命令。[NOR 测试][shell-read]
当前已发布固定系统映射镜像导出与校验CLI；没有原始Flash批量dump/烧录接口。映射镜像的已证实范围不能推广为原始存储地址范围。

## 什么才能称为“足够恢复”的备份

原厂 OTA 文件、录音导出、内存 dump 和原始存储备份覆盖范围不同。应逐区域记录：

1. **存储清单**：主控型号、全部启动/数据介质、容量、接口与 storage ID；确认是否另有 NOR、SD/eMMC boot 区、NAND 隐藏区。
2. **启动必需内容**：boot/mbrec、分区表/param、recovery、应用、依赖的 SDFS/资源/DSP，全部 mirror 副本；映射读与原始读的 CRC/加密转换区别。
3. **设备独有内容**：factory RO/RW、user NVRAM、身份/无线校准（具体存放位置待确认）；另存所有录音。SDK 配置确有 factory/user 分区，OTA 关闭；并非 app.bin 的一部分。[布局][layout-nvram]
4. **不可普通回刷内容**：OTP/eFuse、芯片 UID、ROM 与保护位需单独记状态；不假设可读、可复制或可逆。签名私钥不会由普通固件备份自动获得。
5. **证据清单**：设备与固件版本、来源、每块起始地址/长度/单位、原始文件、SHA-256、两次独立读一致；动态 NVRAM 区变化需解释，不能悄悄忽略。
6. **恢复闭环**：独立入口可反复进入/退出，写回工具与范围经过核查，官方完整包或可写回备份与本机匹配；最终需实际恢复启动、录音、BLE 与身份校准验收，才称“恢复已验证”。

以上是备份验收要求，不是已具备的恢复能力。板名/分区/存储与部分镜像已取得；后续优先匹配平台/生产资料、官方镜像和高效读回路线，以[研究路线](research-routes.md)为准。现有EVK固件不能直接用于CoMi烧录实验。

## 固定源码索引

[lark-recovery-blob]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/tools/prebuilt/lark/common/bin/boot_recovery.app
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
