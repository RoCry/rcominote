# CoMi：设备、固件与 SDK 总览

2026-10-13。面向自写固件的知识地图；链接指向已有证据，历史报告的“下一步”不作为执行计划。

**主线已收敛到 ATS3085L / Cortex-M4 与 LARK 工具谱系。尚缺可构建的匹配 BSP、匹配量产下载链、完整原厂恢复内容。** 单个函数的解释不能替代这三项。

## 设备是什么

| 层次 | 已知；证据类型 | 对自写固件的意义 / 未知 |
|---|---|---|
| 身份 | 自有 C261CF0430；FW010004；固件板名 `ats3085l_dvb_watch_ext_nor_max`、版本 `1.04_2602030950`；[两次实读](firmware-board-identity.md) | 强 ATS3085L 线索；实体 SoC 丝印、PCB 版本仍未确认 |
| CPU | CPUID `410fc241`；[两次实读 Cortex-M4 r0p1](cpu-identity.md) | 已排除直接使用现有 M33 参考构建作为本机固件；CPUID 不确认具体 SoC 或 FPU 配置 |
| 芯片家族 | [炬芯原厂 ATS3085L 表](ats3085l-primary-sources.md)：M4F128 MHz、DSP192 MHz、481 KB SRAM、4 MB PSRAM、外置 NOR、QFN68 | 家族规格；本机时钟、RAM/PSRAM 容量与封装未实测 |
| 固件存储 | [ACPT 实读 CRC 通过](partition-readback.md)：18项连续覆盖4 MiB；[缓存 JEDEC ID](nor-driver-readback.md) `16405e` 对应 Zbit32 Mbit 系列 | NOR 与用户录音存储分离；具体型号、接线及完整物理读回待确认 |
| 录音存储 | [实际驱动与状态](card-state-readback.md)：SD 协议、MMC_1、122138624×512 B = 62,534,975,488 B | 不把“64 GB”当固件 Flash 或 eMMC 身份；实体存储封装仍未知 |
| 系统 | [实机 shell](device-diagnostics.md)返回 Zephyr2.7.0；[初始化表](init-audio-board-evidence.md)已定位 | 与 Actions SDK 有共同接口/格式；不是可重建的完整源代码 |
| 音频 | [实际录音配置](recorder-media-config.md)：16 kHz、16-bit、单声道、MP3/32 kbps；[codec 分派](recorder-codec-dispatch.md)用 `mp3e` / `aeRECORD.dsp`；离线文件也已实测 | 依赖 DSP 资源；麦克风类型、数量、供电与 DMA/时钟配方仍缺 |
| 屏幕 | [实际驱动](display-board-evidence.md)：CH1115标签、72×40、I2C_0/0x3c、GPIOA24/25；[pinmux](board-pinmux-evidence.md)：GPIO14/15为总线候选 | 可约束移植；物理控制器、SCL/SDA方向、电压未确认 |
| 通信 | [BLE 客户端](cli-capabilities.md)可查状态、录音、下载；[USB 插拔对照](usb-log-probe.md)未归属到 CoMi 枚举 | 普通模式未枚举不证明无 USB 数据通路；ROM 下载模式尚未实测 |

## 固件由哪些部分组成

按[本机分区表](partition-readback.md)，不是按参考板猜测：

| NOR 范围；末端不含 | 内容 | 当前理解 |
|---|---|---|
| `000000..004000` | boot / param，各有两个槽 | boot0已有完整原始4 KiB与明文3672 B；[校验与512 B转换规则](boot-complete.md)已验证 |
| `004000..024000` | recovery | 已定位镜像；原始读取48128 / 声明63288 B，[尚未完整验收](recovery-export.md) |
| `024000..1c9000` | system | 完整927632 B映射镜像已校验；映射字节与物理NOR字节存在转换，不可直接当恢复包 |
| `1c9000..200000` | user_rw / SDFS / factory与user NVRAM / 日志 / coredump | 含个体配置与状态；尚无完整备份 |
| `200000..2f0000` | res_a / sdfs_k | 录音DSP完整110148 B已校验，整个资源分区未备份 |
| `2f0000..400000` | OTA TEMP / runtime log | 临时区不是第二套system；当前无完整 A/B 回滚证据 |

启动代码、系统、DSP和用户录音是不同对象。完整system + DSP足够支撑大量离线研究，**不足以恢复整机**；还需boot/param/recovery/资源/个体配置及匹配写入方式。

## SDK 与工具，哪些能复用

固定公开SDK：[`lv_port_actions_technology@26f51e5`](https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579)。[源码核查](actions-sdk.md) · [L系列对照](ats3085l-reference-comparison.md)。

| 材料 | 可复用价值 | 不能据此宣称 |
|---|---|---|
| LEOPARD / ATS3089、ATS3085S参考源码 | Zephyr接口、分区/容器、工具脚本、驱动结构；[Ubuntu构建](ubuntu-build.md)证明工具链可用 | 内核为M33，地址/内存/显示/存储配置不同；不是 CoMi BSP |
| [LARK保留材料](lark-helper-candidate.md) | M4工程模板、boot/helper二进制、生产配置，加载地址01010000更接近本机 | 缺完整 `soc/arm/actions/lark` 源码；不可构建本机固件 |
| [LARK调试loader与ATT源码](platform-source-followup.md#nor-comparison-host-selector-cache-window-and-initialization) | ELF给出 `BAREMETAL_CMSIS/lark_sdk`、NOR/SD接口与类型；两种存储接口已对照，另有M4编译配方、时钟/蓝牙源码 | NOR读依赖重建缓存映射、初始化改变硬件/NOR模式；SD固定SD0而本机用SD1，且wrapper吞读错；原样不能作可靠备份 |
| LARK `adfus.bin` / `adfus_u.bin` | 前者UART、后者USB；有真正的内存/存储读取handler | [初始化会写NOR状态寄存器](lark-nor-init-side-effects.md)，未经修改不可作为只读备份；同名不同版本不能混用 |
| [量产工具DLL/INF](host-selection-followup.md) | 有 WinUSB、ADFU API及驱动ID，可指导匹配host | 尚无本机芯片→host选择→ROM协议闭环；不能直接套旧ATJ包格式 |
| 本机system / boot / DSP | 实际ABI、驱动、启动、安全/OTA约束；本机代码强于不匹配参考默认值 | 反汇编不等于源码；DSP提取不证明可在自写固件中加载执行或再分发 |

## 下一阶段只抓三个交付物

1. **匹配平台资料包**：ATS3085L/LARK M4 BSP、寄存器/引脚资料、开发板材料、生产配置和host。已定位 `BAREMETAL_CMSIS/lark_sdk` / LarkHal / Flashloader，NOR/SD接口对照完成；精确公共检索未取得源包，有新入口再继续。[资料核查](platform-source-followup.md)。不重复泛搜或已完成的接口分析。
2. **固件与恢复全景**：原厂包获取线索、镜像依赖/布局、安全约束、ROM→helper→NOR路径。先回答哪种路径值得验证，再决定是否一次性采集有界ROM语料；不逐callee新增实机实验。
3. **可承担的首次运行实验**：评估独立reset/断电退出与RAM加载可能性；目标、入口、初始化影响、退出方式明确后再制定具体实验。ROM枚举、helper执行、写Flash是不同阶段，不能相互冒充验收。

判断工作价值：**结果会改变芯片/BSP选择、取得关键产物，或决定备份/恢复/首次运行路径吗？** 若不会，先归入下表；不以函数数、脚本数或提交数衡量进度。

## 暂存问题：有新依据再继续

| 问题 | 已保留什么 | 重新推进条件 |
|---|---|---|
| ROM计数单位、回绕、调用者返回 | [固定代码与两次读回](actual-rom-exit-condition.md)；没有“超时会回到App”的保证 | 决定具体模式实验且无独立reset退出；或取得完整ROM/匹配文档后批量离线分析 |
| SCL/SDA、屏幕等待、单个寄存器语义 | 板级专题证据 | 匹配SoC资料或进入屏幕bring-up |
| 长窗口实时流、cancel竞态、云端API | 客户端能力表与真实失败记录 | 独立客户端成为当前交付重点；不阻塞芯片/SDK研究 |
| 后台JAR获取 | [致远部署手册](seeyon-backend-reference.md)，包域名曾解析到私网 | 新的外部下载入口；目前无固件分发证据，不作为固件主线依赖 |
| 完整NOR日志导出 | 有效部分数据、[效率审计](nor-efficiency.md)、归档代码 | 新证据证明吞吐/可靠性有实质改善；不恢复旧长任务 |

不删除有效证据。错误结论、错误产物和淘汰方案以[路线淘汰表](research-routes.md)为准；历史报告只作溯源。
