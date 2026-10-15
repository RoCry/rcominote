# CoMi：设备、固件与 SDK 总览

更新至2026-10-14。面向自写固件的知识地图；链接指向已有证据，历史报告的“下一步”不作为执行计划。

**主线已收敛到 ATS3085L / Cortex-M4 与 LARK 工具谱系。尚缺可构建的匹配 BSP、匹配量产下载链、整机原厂恢复包。** [本机recovery已完整取得](recovery-complete.md)，不等于整机恢复包。单个函数的解释不能替代这三项。

## 设备是什么

| 层次 | 已知；证据类型 | 对自写固件的意义 / 未知 |
|---|---|---|
| 身份 | 自有 C261CF0430；FW010004；固件板名 `ats3085l_dvb_watch_ext_nor_max`、版本 `1.04_2602030950`；[两次实读](firmware-board-identity.md) | 强 ATS3085L 线索；实体 SoC 丝印、PCB 版本仍未确认 |
| CPU | CPUID `410fc241`；[两次实读 Cortex-M4 r0p1](cpu-identity.md) | 已排除直接使用现有 M33 参考构建作为本机固件；CPUID 不确认具体 SoC 或 FPU 配置 |
| 芯片家族 | [炬芯原厂 ATS3085L 表](ats3085l-primary-sources.md)：M4F128 MHz、DSP192 MHz、481 KB SRAM、4 MB PSRAM、外置 NOR、QFN68 | 家族规格；本机时钟、RAM/PSRAM 容量与封装未实测 |
| 固件存储 | [ACPT 实读 CRC 通过](partition-readback.md)：18项连续覆盖4 MiB；[缓存 JEDEC ID](nor-driver-readback.md) `16405e` 对应 Zbit32 Mbit 系列 | NOR 与用户录音存储分离；具体型号、接线及完整物理读回待确认 |
| 录音存储 | [实际驱动与状态](card-state-readback.md)：SD 协议、MMC_1、122138624×512 B = 62,534,975,488 B | 不把“64 GB”当固件 Flash 或 eMMC 身份；实体存储封装仍未知 |
| 系统 | [实机 shell](device-diagnostics.md)返回 Zephyr2.7.0；[初始化表](init-audio-board-evidence.md)已定位 | 与 Actions SDK 有共同接口/格式；不是可重建的完整源代码 |
| 音频 | [实际录音配置](recorder-media-config.md)：16 kHz、16-bit、单声道、MP3/32 kbps；[codec 分派](recorder-codec-dispatch.md)用 `mp3e` / `aeRECORD.dsp`；[说明书](manual-2026-10-13.md)记载模拟硅麦+骨传导麦；[模式核对](note-call-audio-2026-10-13.md)定位相反GPIOB18请求、36.5/40.5 dB增益及不同ADC字段 | 软件模式和静态配置已区分；现场GPIO/ADC读回因日志帧失败暂挂。精确麦数量、外部接线、实际切换、供电与 DMA/时钟配方仍缺 |
| 屏幕 | [实际驱动](display-board-evidence.md)：CH1115标签、72×40、I2C_0/0x3c、GPIOA24/25；[pinmux](board-pinmux-evidence.md)：GPIO14/15为总线候选 | 可约束移植；物理控制器、SCL/SDA方向、电压未确认 |
| 通信 | [BLE 客户端](cli-capabilities.md)可查状态、录音、下载；[实际DEFAULT→FAST RAM控制](archive/startup-ram-default-live-2026-10-14.md)两次4096独立oracle及全HCI/身份/正常断连通过；[USB 插拔对照](usb-log-probe.md)未归属到 CoMi 枚举 | DEFAULT/FAST为不同已审参数分支，下载仅在host6/0/500窗口内验收；控制不增NOR覆盖或证明唯一触发源。普通模式未枚举不证明无USB数据通路；ROM下载模式尚未实测 |
| UART引脚配置 | [GPIO28 CTRL首次实读](archive/gpio28-word-live-2026-10-14.md)`00001805`，低5位为UART0功能5；与早期4125不同，匹配实际后续1805表 | 软件配置读回，不证明物理触点、输出电压/波形/波特率或具体写入历史；GPIO29仍未现场读取 |
| 当前系统映射 | [slot0两个独立配置word](archive/map0-entry-live-2026-10-14.md)`40010300=1000000f`、`40010304=00024000` | 支持系统起点24000/CRC属性bit31清零；非原子快照，不证明窗口范围、raw alias或物理字节表示 |
| 系统原始页与转换观察 | [物理24200独立双读](archive/system24200-live-2026-10-14.md)512B逐字相等；同文件两覆盖/三下载/九事务、全状态/HCI通过 | 新增raw512B；后验固定32B reset解码全512匹配mapped向量页，SP01002b40/reset1002d819。另有24400至24e00完整pair；[完整raw首4KiB](archive/system-first4k-raw-live-2026-10-14.md)fixed32解码也全匹配mapped首4096；累计raw系统首4096B，支持这些页转换关系，不证明efuse key、全system物理表示或刷写恢复 |
| 连续原始读回 | [单连接boot0→4200](archive/dual-known-nor-live-2026-10-14.md)各512B匹配独立oracle；未知[2200](archive/dual-unknown2200-2026-10-14.md)、[2400](archive/window-nor2400-composer-2026-10-14.md)、[2600](archive/window-boot-tail-live-2026-10-14.md)、[新2800](archive/status-boot-tail-live-2026-10-14.md)、[新2a/2c](archive/startup-boot-tail-live-2026-10-14.md)各有独立双读/严格新鲜度/真实barrier | [独立最后2e双读](archive/final-boot-sector-live-2026-10-14.md)后boot1完整4096B已验证、全FF；未知块无独立字节oracle，旧失败保持。规模化可靠性/整片覆盖未完成 |

## 固件由哪些部分组成

按[本机分区表](partition-readback.md)，不是按参考板猜测：

| NOR 范围；末端不含 | 内容 | 当前理解 |
|---|---|---|
| `000000..004000` | boot / param，各有两个槽 | boot0完整原始4KiB与明文3672B；[boot转换512B](boot-complete.md)。[两个param完整原始各4KiB](param-slots.md)：主槽元数据32B转换/双CRC匹配缓存，备用槽全FF、没有有效副本；[boot1完整原始4KiB](archive/final-boot-sector-live-2026-10-14.md)全FF，没有有效备用boot代码；不能据此声称可靠恢复 |
| `004000..024000` | recovery | [原始/明文63,288 B完整校验](recovery-complete.md)；应用映射、加法验收、PSP/BX交接已静态解释，未执行新镜像；公开image外另200B实际旧pair尾已保存，来源分层见库存 |
| `024000..1c9000` | system | 完整927632 B映射镜像已校验；旧header/24200及[24400](archive/paired-nor24400-live-2026-10-14.md)/[24600与24800](archive/paired-nor-system4-live-2026-10-14.md)各有原来源，另有[首4KiB全部来源](archive/system-first4k-raw-live-2026-10-14.md)，raw连续4096B`[24000,25000)`；其余system raw未完整备份，非完整system原始备份，不可直接当恢复包 |
| `1c9000..200000` | user_rw / SDFS / factory与user NVRAM / 日志 / coredump | [factory-RW历史8KiB私有备份记录](factory-rw-backup.md)记载12条CRC通过；当前raw/producer输入缺失待重采，不能计可组装覆盖；其余区域未完整备份 |
| `200000..2f0000` | res_a / sdfs_k | 录音DSP raw110148B保留/全文件checksum通过；仅前3块原producer来源可重放，其余tierB，末块额外444B缺失；整个资源分区未备份 |
| `2f0000..400000` | OTA TEMP / runtime log | 临时区不是第二套system；当前无完整 A/B 回滚证据 |

启动代码、系统、DSP和用户录音是不同对象。完整system + DSP足够支撑大量离线研究，**不足以恢复整机**；还需boot/param/recovery/资源/个体配置及匹配写入方式。

## SDK 与工具，哪些能复用

固定公开SDK：[`lv_port_actions_technology@26f51e5`](https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579)。[源码核查](actions-sdk.md) · [L系列对照](ats3085l-reference-comparison.md)。

| 材料 | 可复用价值 | 不能据此宣称 |
|---|---|---|
| LEOPARD / ATS3089、ATS3085S参考源码 | Zephyr接口、分区/容器、工具脚本、驱动结构；[Ubuntu构建](ubuntu-build.md)证明工具链可用 | 内核为M33，地址/内存/显示/存储配置不同；不是 CoMi BSP |
| [LARK保留材料](lark-helper-candidate.md) | M4工程模板、boot/helper二进制、生产配置，加载地址01010000更接近本机 | 缺完整 `soc/arm/actions/lark` 源码；不可构建本机固件 |
| [官方ATS3085C测试盒包/板资料](actions-official-tester-2026-10-13.md) | 实际type100包、完整recovery/生产脚本、不同helper/host；原生PADS和BOM；参数CRC确认16 MiB/21项板型 | 非CoMi 4 MiB/18项板型；helper仍保留状态写路径；同页DUT helper为MIPS；无本机数据线/退出/恢复证明 |
| [LARK外设源码与构建缺口](platform-source-followup.md#rebuildability-peripheral-source-survives-platform-closure-does-not) | 音频ADC/DAC/I2S、PMU ADC、电池、USB、IPMSG源码；部分已有LARK构建选择 | 缺SoC/板级闭环，IPMSG父目录未接入LARK；外设名与参考充电芯片不等于本机配置 |
| [DWARF恢复的部分芯片定义](lark-register-recovery.md) | 自包含12组寄存器结构、47个IRQ常量；9类跨ELF一致，M4编译布局检查通过 | 不是完整lark.h/BSP；缺base/bit、clock/reset编号、startup和CoMi接线；不代表实际外设兼容 |
| [媒体/蓝牙静态库属性](evidence/lark-library-attributes-2026-10-13.json) | 已按archive member核对：媒体23项、蓝牙24项均声明v8-M/FPv5；LARK ATP测试库1项为v7E-M/VFPv4 | 不能仅改CPU/板名就移植完整应用；还需匹配M4库或替代实现；ATP库不替代媒体/蓝牙栈 |
| [Vela官方移植指南](platform-source-followup.md#public-history-and-vela-provenance-bounded-acquisition-result) | 含ATS3085X宏、ARMv7-M与内存地址示例；芯片层可由独立vendor包提供 | 不指明L型号或CoMi；未取得Actions vendor包，不采用示例长度/入口，不改变本机Zephyr事实 |
| [LARK调试loader与ATT源码](platform-source-followup.md#nor-comparison-host-selector-cache-window-and-initialization) | ELF给出 `BAREMETAL_CMSIS/lark_sdk`、NOR/SD接口与类型；两种存储接口已对照，另有M4编译配方、时钟/蓝牙源码 | NOR读依赖重建缓存映射、初始化改变硬件/NOR模式；SD固定SD0而本机用SD1，且wrapper吞读错；原样不能作可靠备份 |
| LARK `adfus.bin` / `adfus_u.bin` | 前者UART、后者USB；有真正的内存/存储读取handler | [初始化会写NOR状态寄存器](lark-nor-init-side-effects.md)，未经修改不可作为只读备份；同名不同版本不能混用 |
| [LARK `boot_recovery.app`](flash-recovery-assessment.md#启动授权问题缺的材料与不能替代它的产物) | 已核对6792 B参考stub：依赖文件末尾追加压缩块，执行NOR擦写、param复制及复位请求 | 不是本机63288 B recovery，不是完整独立恢复包；本机交接现已由完整实读镜像独立解释 |
| [SDK生产包生成链](production-package-contract.md) | 外层ACTTEST0、内层maker两种封装、raw、AOTA已区分；ATF离线验证；随包FAT/XOR恢复43文件 | 样例2 MiB/11项布局与CoMi不符；芯片/USB选择表为空，helper与既有参考相同；DB转换未实现，未生成CoMi生产包 |
| [量产工具DLL/INF](host-selection-followup.md) | WinUSB/API/驱动ID；恢复样例USBDevice＋指定DLL可追到family0/CClassical和31 B上传/切换包头 | 入口接收既有transport，未找到CoMi选择链；函数内不校验13 B状态；无本机ROM验收/备份/恢复证明 |
| 本机system / boot / DSP | 实际ABI、驱动、启动、安全/OTA约束；本机代码强于不匹配参考默认值 | 反汇编不等于源码；DSP提取不证明可在自写固件中加载执行或再分发 |
| [自建M4 ELF / ACTH与实际checker oracle](minimal-firmware-image.md) | 948 B自建镜像可重复构建，通过原厂recovery实际指令的离线局部准入检查；原厂正/损坏负例校准 | 仅镜像fixture；缺BSP/原始表示/早期授权/可恢复入口，未执行候选代码或证明RAM可用 |
| [原厂RAM→SD→Boyi通道](sd-file-bridge.md) | 固定4KiB RAM与单次boot0 ring导出均匹配独立原始字节，绕过数百次mdb小读 | [recovery缺失30扇区均双读一致且完整校验](recovery-complete.md)；留SD测试文件，流程仍不适合整片备份；直接XIP源失败原因暂存 |
| [当前小文件与logsrv槽通道](archive/logsrv-slot-live-2026-10-14.md) | known-mdb16→槽→新SD512、[RAM4096窗口对照](archive/download-window-live-2026-10-14.md)与[2400新窗口双读](archive/window-nor2400-composer-2026-10-14.md)通过；后者六参数事务/完整日志/新鲜度/真实barrier全验收 | [同一专用文件boot0新内容只读确认](archive/scratch-postmortem-live-2026-10-14.md)、[随后4200覆盖/读回](archive/scratch-4200-live-2026-10-14.md)通过，零新文件；旧两cover试验仍失败。已改善有界连续下载及未知块双读；规模化效率、整片备份仍未证明。仅指定gap允许一条精确composer日志，非一般printk冻结或worker退出证明 |
| [常驻coredump导出静态链](archive/resident-export-command-inventory-2026-10-14.md) | 实际shell目录/固定4096B常驻NOR读取消费者已闭合，28段bytes/3来源复验 | 无用户可选地址/长度，文本输出且可恢复固定backtrace RAM；不是安全通用binary出口，无live测试 |
| [已知ROM→SD两次导出](rom-sd-bridge.md) | `1900..1a50`共336 B均匹配旧独立oracle；该源可用文件通道 | 未建立ROM总范围、任意地址可读性或批量吞吐；扩展语料需可信边界 |
| [正常态RAM入口盘点](normal-ram-entry-inventory.md) | 完整静态命令树及候选直接路径区分日志控制、内存写入和执行 | 已检查接口没有受支持的RAM执行合同；不代表全固件无隐藏入口，不以控制流破坏补缺 |

## 固件主线的三个缺口

以下是完成条件，不表示当前均可执行；实际优先级、封存路线和可选有界任务见[当前路线](archive/research-routes.md)。

1. **匹配平台资料包**：ATS3085L/LARK M4 BSP、寄存器/引脚资料、开发板材料、生产配置和host。现有SDK保留实质外设源码，但缺SoC/板级闭环及匹配M4媒体/蓝牙库；[可重建性清单](platform-source-followup.md#rebuildability-peripheral-source-survives-platform-closure-does-not)已区分。另定位 `BAREMETAL_CMSIS/lark_sdk` / LarkHal / Flashloader，NOR/SD接口对照完成；精确公共检索未取得源包，有新入口再继续。不重复泛搜或已完成的接口分析。
2. **固件与恢复全景**：原厂包获取线索、镜像依赖/布局、安全约束、ROM→helper→NOR路径。先回答哪种路径值得验证，再决定是否一次性采集有界ROM语料；不逐callee新增实机实验。
3. **可承担的首次运行实验**：评估独立reset/断电退出与RAM加载可能性；目标、入口、初始化影响、退出方式明确后再制定具体实验。ROM枚举、helper执行、写Flash是不同阶段，不能相互冒充验收。

判断工作价值：**结果会改变芯片/BSP选择、取得关键产物，或决定备份/恢复/首次运行路径吗？** 若不会，先归入下表；不以函数数、脚本数或提交数衡量进度。

## 暂存问题：有新依据再继续

| 问题 | 已保留什么 | 重新推进条件 |
|---|---|---|
| ROM计数单位、回绕、调用者返回 | [固定代码与两次读回](actual-rom-exit-condition.md)；没有“超时会回到App”的保证 | 决定具体模式实验且无独立reset退出；或取得完整ROM/匹配文档后批量离线分析 |
| system启动验收与最终映射 | [完整recovery局部契约](recovery-complete.md)已补齐：slot0替换、加法校验、PSP/BX；晚期失败有映射局部别名风险 | 更早ROM/boot授权、运行态与独立恢复仍缺；不以局部无验签分支推断全链无签名 |
| SCL/SDA、屏幕等待、单个寄存器语义 | 板级专题证据 | 匹配SoC资料或进入屏幕bring-up |
| 长窗口实时流、cancel竞态、云端API | 客户端能力表与真实失败记录 | 独立客户端成为当前交付重点；不阻塞芯片/SDK研究 |
| 后台JAR获取 | [致远部署手册](seeyon-backend-reference.md)，包域名曾解析到私网 | 新的外部下载入口；目前无固件分发证据，不作为固件主线依赖 |
| 完整NOR日志导出 | 有效部分数据、[效率审计](archive/nor-efficiency.md)、归档代码 | 有界v2已有3新增页，但24a原prefix失败；新v3已完成system首4KiB；原known17失败/W0成功保持，新v3/STATUS4均失败；genericCONTENT通信role+完整formattermask待独立review，不恢复旧长任务 |

不删除有效证据。错误结论、错误产物和淘汰方案以[路线淘汰表](archive/research-routes.md)为准；历史报告只作溯源。
