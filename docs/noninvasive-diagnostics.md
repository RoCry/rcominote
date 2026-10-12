# 不拆机：日志与只读诊断候选

2026-10-12；源码核查，**本轮没有连接设备、执行 shell 或采集日志流**。
固定参考：[Actions SDK `26f51e584940d5b141cd1d09d2629d69b595f579`][sdk]。
SDK 行为不等于 CoMi 原厂固件行为；具体 SoC、引脚和安全启动状态仍不能据此确定。

## 已知与下一步

| 路径 | 已有证据 | 不拆机可增加的证据 | 边界 |
|---|---|---|---|
| Boyi 状态/文件 | [协议与工具](protocol.md)已有实测 | 记录固件版本、容量、状态；下载原厂录音作格式与音频基线 | 文件下载是用户数据备份，不是固件备份 |
| Actions log | [固定 PREPARE/ACK](usb-log-probe.md)实测成功 | 限时接收默认实时日志，观察启动/模块/存储驱动名称 | START/STOP 改日志会话；尚未实测 |
| 固定只读 shell 命令 | SDK 有下表处理器 | OS 版本、启动时长、已编译设备名 | 原厂是否编译 shell/backend/命令仍未知；ACK 不证明执行 |
| Linux SDK 编译 | [Ubuntu 构建已通过](ubuntu-build.md) | 延伸自己的应用，分析 ELF/map/分区 | 编译成功不证明样例适配 CoMi 或可刷入 |

最低侵入的新增设备实验：实现独立的**限时默认实时日志采集**，固定
PREPARE → DEFAULT_START (`0x20`) → 接收最多 15 秒 → STOP (`0x21`) → 断开；
保存原始通知、时间、ACK/F0/F1 帧，不发送文本命令或 dump 请求。
SDK 默认日志分支只注册用户输出 backend、启用 10 ms 定时发送；STOP/断开注销 backend、清队列。
连接还可能持有 `PARTIAL_WAKE_LOCK`；因此它是有临时运行状态影响的观察，不是完全被动监听。
[模式切换][modes] [连接/清理][connection]

判定：收到真实日志文本才证明日志可读；只收到 ACK 表示解析路径成功。
无 F0 数据不能证明日志关闭，另有下面的短缓冲陷阱。

## 可限定为白名单的命令

以下仅描述固定 SDK 的处理器；**尚未在 CoMi 执行**。不要因此开放任意命令输入。

| 完整命令 | 处理器行为 | 价值与限制 | 固定源码 |
|---|---|---|---|
| `kernel version` | `sys_kernel_version_get()`，打印三段版本 | 识别 RTOS vendor fork；不能识别芯片 | [handler][kernel], [注册][kernel-registration] |
| `kernel uptime` | `k_uptime_get_32()`，打印毫秒 | 确认来自实时设备、判断是否重启；32 位计时会回绕 | [handler][kernel] |
| `kernel cycles` | `k_cycle_get_32()`，打印计数 | 额外实时性证据；不直接给 CPU 型号/频率 | [handler][kernel] |
| `device levels` | 遍历静态设备表、`device_is_ready()`，打印初始化阶段和名字 | 可能暴露 flash、LCD、音频设备名；只是编译标签 | [handler][device-levels], [注册][device-registration] |
| `device list` | 遍历静态设备表；可选 `pm_device_state_get()`；打印依赖关系 | 可能帮助定位 BSP 驱动；不提供板级引脚或芯片丝印 | [handler][device-list], [注册][device-registration] |

`kernel`/`device` 模块分别受 `CONFIG_KERNEL_SHELL`、`CONFIG_DEVICE_SHELL` 控制。
日志文本执行又要求 serial 或 RTT shell backend；仅有 dummy/Telnet backend 不走该分支。
[模块编译][module-build] [日志文本分支][text]

当前未找到可直接返回精确板号/SoC 型号的同级固定命令。`device list` 中的名字是线索，
应与驱动源码/原厂包交叉核对。不要把 `dbg` 全命令集当作只读：它包含写内存、存储测试、
复位、RAM 写入 flash 等操作。[dbg 注册表][dbg]

## ACK 与短输出陷阱

1. `_logsrv_proc_tlv_cmd()` 忽略 `_logsrv_proc_console_text()` 的返回值；顶层成功解析后发送固定
   ACK。即使 shell 命令不存在、执行失败，甚至没有 shell backend，仍可能收到 ACK。
   [TLV 分发/ACK][dispatch]
2. 有 8 个缓冲，每个有效载荷 `512 − 5 − 3 = 504` 字节。`_logsrv_save_log()` 只有缓冲满
   或数据类型切换时推进 `wr_idx`。`_logsrv_send_log()` 外层先要求 `rd_idx != wr_idx`；
   初始缓冲不足 504 字节、类型未变时，完全不会进入发送循环。
   [尺寸][sizes] [保存/发送][buffer]
3. 发送函数内部确有“推进剩余短缓冲”逻辑，但只能在至少发送一个已排队缓冲后执行。
   单独的 `kernel version` 输出很短；**没有文本响应不能作为 shell 不可用的否定证据**。
   默认日志定时器调用同一发送函数，等 15 秒也不保证短缓冲发出。[buffer][buffer]
4. STOP/断开清队列，不强制刷新短缓冲。采集报告需明确“ACK/数据字节数/结束帧/超时”，
   保留“执行状态不明”，不要把超时改写成“命令未执行”。[模式切换][modes]

若以后测试固定 shell 白名单，先设计并限定能跨过缓冲阈值的观测序列；不通过增加写命令或
打开 dump 强迫输出。单条命令 ACK 仅作协议证据，不作为执行成功 oracle。

## dump 不属于最小观察

console code `0x10/0x11/0x12/0x13` 分别选择 syslog/coredump/runtime/ramdump，随后走
`_logsrv_actlog_send_syslog()`。该函数在 `CONFIG_TASK_WDT` 下调用 `task_wdt_stop()`，
函数内未见对应 restart；STOP 和断连清理也未重启 task watchdog。
这证明参考实现有额外运行状态影响；不能把“读取 dump”概括为无副作用。
本轮建议先做默认实时日志，dump 另行核对 CoMi 实现和恢复方式。[dump][dump] [清理][connection]

[sdk]: https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579
[sizes]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L41-L80
[buffer]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L446-L541
[modes]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L603-L683
[connection]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L853-L887
[text]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L685-L708
[dispatch]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L710-L787
[dump]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L572-L594
[kernel]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/kernel_service.c#L18-L51
[kernel-registration]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/kernel_service.c#L249-L264
[device-levels]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/device_service.c#L15-L108
[device-list]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/device_service.c#L110-L170
[device-registration]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/device_service.c#L174-L180
[module-build]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/CMakeLists.txt#L1-L18
[dbg]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L2430-L2601
