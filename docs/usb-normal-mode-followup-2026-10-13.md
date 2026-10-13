# 普通模式 USB：实际固件后续核对

2026-10-13；仅本地完整 system 静态分析，无设备读取、模式切换、USB 命令或 ROM 入口实验。方法：固定镜像字节检索、Capstone Thumb/M-class 解码、分发表与 literal 分开解释。不是运行时路径证明。

**新增结果：USB_COPY 仍只证明属性/状态；正常 USB 事件转给 launcher 后，对应消息落默认分支，没有找到该路径启动 MSC 的专用处理。不能据四触点或已开启 USB_COPY 宣称原厂固件提供 U 盘；也不能据本轮有限搜索断言 USB 数据脚未连接或所有 MSC 路径不存在。**

## 输入与复验位置

实际镜像：[原厂 system gzip](evidence/minimal-image-2026-10-13/original-system.bin.gz)，解压后 927632 B，SHA-256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`，映射基址 `10000000`。本文地址均十六进制；范围为半开区间。给定地址减基址即可复验下列原始字节。

参考 SDK 固定于 [`lvgl/lv_port_actions_technology@26f51e584940d5b141cd1d09d2629d69b595f579`](https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579)。其完整 SoC 平台为 M33，与本机 M4 不同；用于源语义对照，不当作本机编译配置。

## USB_COPY：新增一处配置重设，没有新增启动消费者

既有链：[setter/init/status 与属性持久化边界](usb-copy-setting.md)。实际字段为 `1800ba00+45e`；setter `1000ada8` 写字段、保存 `USB_COPY`、请求 flush，未直接启动 USB。

本轮在 `[10000000,100b9d08)` 按半字边界检索并解码直接 Thumb `#0x45e` 内存操作，共六处：

| 指令地址 | 操作 | 含义/边界 |
|---|---|---|
| `1000ab3e` | `ldrb.w r3,[r4,#45e]` | 设备 info 字段 |
| `1000aca4` | `ldrb.w r2,[r3,#45e]` | 已知状态事件 |
| `1000adb4` / `1000adce` | 写 / 读字段 | 已知 setter |
| `1000d19e` | `strb.w r0,[r4,#45e]` | 属性初始化 |
| `1000d4f2` | `strb.w r5,[r4,#45e]` | 新确认：整组配置重设片段，`r5=1` |

最后一处 `[1000d4ee,1000d500)` 原始字节：`2946214884f85e5442f06dfd1f489ff0a2ff`。它将 `r5` 传入 `1004ffd4`，再调用 `100ad444`；literal `1000d578=100c2219` 指向 `USB_COPY`。周围还重设其他配置字段，未据此给上层操作命名为“恢复出厂”。

完整镜像中 `USB_COPY` 字符串地址 `100c2219` 的逐字节小端 word 引用仅 `1000ae10`、`1000d288`、`1000d578`，分别对应 setter、初始化、上述重设片段。此搜索不覆盖寄存器索引、拆分偏移、指针运算、间接表或动态构造；“六处”不是完整数据流证明。

## 正常 USB 事件：可闭合的一条实际分发链

1. `1000180c` 接收消息到 `sp+8`，`1000185a` 读取 byte `sp+0a`（消息 type）。`10001866` TBH 按 `type−1` 分派；type 11 的表项 `1000187e=009a`，落 `1000199e`，调用 `10001f2c`。调用片段 `[1000199e,100019a6)`：`02a800f0c4faaee7`。
2. `10001f2c` 读取消息 byte+3（cmd），TBB 将 cmd 3 分到 `10001f60`。这两个数字与固定 SDK 的 `MSG_HOTPLUG_EVENT=11`、`HOTPLUG_USB_DEVICE=3` 一致；命名由源对照支持，实际数值路径由机器码独立确定。[消息枚举](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/base/include/core/msg_manager.h#L23-L39)、[热插拔枚举](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/include/hotplug_manager.h#L36-L49)。
3. `10001f60` 调用测试标志 getter `1002df08`。标志为 0 时走 `10001fa6`：检查当前应用名等于 `launcher` 才转交原消息；不等则返回测试标志检查并退出本分支。正常转交路径未检查 `USB_COPY`，也未直接初始化 USB 类。`[10001fa6,10001fc2)`：`4df023fa2a49fef78cfe0028e6d14df01cfa2146bde838404df033bf`；`10002054=100c2d25` 为 `launcher` literal。
4. 实际应用描述符 `[10000400,10000420)`：`252d0c10a03c001800080a12000000000000000000000000418f001000000000`，首 word 指向 `launcher`，entry 为 `10008f41`。其接收循环以 byte `sp+6`（消息基址 `sp+4` 的 type）分派。type 4..21 使用 `10009090` 起的绝对地址表；**type 11 对应 `100090ac=1000903f`，落默认处理**，并非 USB 专用 arm。
5. 默认处理 `[1000903e,10009042)` 为 `00246de0`，置 `r4=0` 后到 `1000911e`；那里可调用消息自带 callback，然后继续接收。没有在该默认 arm 找到 MSC 初始化/存储后端选择。未展开通用 callback 或所有间接调用，故不将其扩大为“任何运行状态均不能启动 MSC”。

非零测试标志分支仍是已审计的 [CDC 测试启动链](usb-cdc-startup.md)，另有消息 value/helper 条件；不是将普通 USB_COPY 开关打开便进入 CDC，也不作为只读导出服务。[完整 CDC 命令边界](usb-cdc-command-inventory.md)。

## 存储类与后端：实际证据仍少于参考 SDK

实际镜像存在 `usb msc ejected` 日志及 `1009a40c` 状态 getter（读取 `18045244` 的 bit 2），但它们未连到本机 MSC 初始化/块设备。既有描述符扫描只找到两套 CDC 描述符，直接 descriptor-register 调用搜索也只连到 CDC；检索不覆盖分离/动态描述符或所有间接路径，本轮不重复扩大搜索。[既有 MSC 审计及严格限制](usb-msc-followup.md)、[实际 CDC 描述符](usb-cdc-config.md)。`/USB:` 字符串也不能单独证明 USB device MSC；它可能描述 USB host 文件系统。

参考 SDK 确有完整 MSC 实现：`card_reader_init()` 先卸载应用文件系统，再做 USB disable/PHY/init/MSC 初始化；退出先停止 MSC 再检查并重新挂载文件系统。类实现包含 descriptor/config/enable 和 `disk_initialize/read/write` 后端。**这是可借用的源实现与存储所有权约束，不是本机已启用该类的证据。** [card_reader_main.c:131–174](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/card_reader/card_reader_main.c#L131-L174)、[mass_storage.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/mass_storage.c)。

## 对文件传输与烧录决策的影响

- **原厂普通固件文件传输**：当前仍缺可归属本机的实际 USB 枚举/接口，以及该接口到 SD 文件/块后端的正链。四触点和“磁吸充电”均不能决定数据接线；充电成功也不等于 USB 枚举成功。[说明书原始证据](manual-2026-10-13.md)。本轮不能把 USB_COPY=true 转成“U 盘已可用”。
- **未来自写固件**：参考 MSC 源能提供类/后端设计，但仍须匹配 M4 USB 控制器/PHY/BSP、真实接线与可恢复启动路径。需要处理 SD 文件系统独占；不能让本机录音文件系统与电脑同时直接修改同一块卷。
- **烧录/独立恢复**：即便将来确认导出 SD 的 MSC，也只证明相应块设备；不自动证明 NOR 写入、ROM 下载或固件损坏后的恢复。正常应用 CDC 与 ROM ADFU 同样分开。[独立退出边界](actual-rom-exit-condition.md)。

本轮到此停止静态扩展。可改变下一步决策的是正常条件下可归属本机的 USB 描述符/接口，或原厂线缆数据接线证据；无此新输入不继续用更多日志字符串或通用参考驱动充当本机能力证明。
