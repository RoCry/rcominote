# 现有固件读回：输出路由与下一步

2026-10-13更新：[RAM→SD→Boyi](sd-file-bridge.md)固定RAM与boot0环形日志导出已通过独立字节比较；是新的提取候选，不是完整备份能力。后续选择以[研究路线](archive/research-routes.md)为准。

2026-10-12；本文作者仅做源码审计；主调查进程新增了下述固定查询实测。固定 SDK `26f51e584940d5b141cd1d09d2629d69b595f579`；原厂固件行为以[实机记录](device-diagnostics.md)为准。

[本轮平台查询](evidence/log-platform-info-2026-10-12.json)确认：`app` 仅列出 `set_config/input/btinfo`；`system` 与参考命令一致；`FW_VERION` 读取失败；`BT_LE_NAME` 返回 14 字节 `CoMi Note 2F01`。这证明**NVRAM 单键内容可以经 BLE 读回**，没有证明原始 flash 或完整固件可读回。

后续已依据实时线程入口、ABI布局核对并成功读取16字节映射代码；此前“不能自动把线程entry当映射”的限制仍成立，新增证据与固定白名单见 [代码读回](mapped-code-readback.md)。完整flash与恢复尚未知。

## 为什么 NOR 读取只有状态行

参考实现存在两条独立输出链：

1. `shell_print/shell_fprintf` → shell UART/RTT transport → `_logsrv_actlog_backend_callback` → BLE F0。`_logsrv_proc_console_text()` 只在同步执行命令期间注册 shell transport callback。[注册与执行][console-text]；[UART callback][uart-write]
2. `printk` → `_char_out` → 平台 console hook。UART console 默认直接 `uart_poll_out`；USB/RTT console 另有 hook。它们没有因此进入 shell transport callback。[printk hook][printk]；[UART console][uart-console]

`shell_flash_read()` 状态及错误用 `shell_print`；成功后的 `print_buf()` 用 `printk` 输出十六进制。二者差异足以解释“收到 fread 状态行、没有 512 B 正文”。实际 CoMi 的 printk 配置仍未知；不能把源码解释当成已观测的串口输出。[fread][fread]；[print_buf][print-buf]

DEFAULT START 注册 Actions log USER backend，接收的是 Actions 格式化日志；该 backend 不是通用 printk hook。没有在已审计的日志协议/根命令中找到可只读地把 printk 重定向到 BLE 的开关。[Actions backend][act-backend]；[DEFAULT START][default-start]

`dbg dbgsw cpu/dma` 改 console 传输实现，不安装 BLE callback，不能据名称推断能解决问题。`actlog info` 自身也用 printk；默认 BLE 看不到输出不能证明没有执行。

## 当前可执行的固定查询

这些只描述公开处理器的边界；先查看原厂帮助，再决定是否执行对应子命令。短输出后追加固定 `help` 以越过已知 504 B 缓冲阈值。

| 固定文本 | 源码行为 | 可以回答什么 |
|---|---|---|
| `system` | 根 handler NULL，展示子命令帮助 | 原厂是否新增版本/存储查询；不执行 `set_config` 等子命令。[注册][system] |
| `app` | `argc == 1` 只 `shell_help` | 原厂应用特有 getter；不执行 input/monkey/set_config。[handler][app] |
| `kernel` | 根 handler NULL，展示帮助 | 是否编译线程查询。[注册][kernel-registration] |
| `kernel uptime` | `k_uptime_get_32()`，shell_print | 实时性、前后是否重启；不是芯片 ID。[handler][kernel] |
| `kernel threads` | 仅在对应配置下注册；遍历线程、读取栈使用量，shell_print | 录音/存储/应用线程名与运行状态；不是分区图。[handler][threads] |
| `dbg nvram FW_VERION` | `argc == 2` 调 getter，最多 63 B，`print_buffer` 经 shell_fprintf 输出 | 可比较厂商属性版本；键名包含原始拼写错误，可能不存在/过期。[keys][keys]；[handler][nvram-shell] |
| `dbg nvram BT_LE_NAME` | 同上，固定名字键 | 交叉验证 BLE 名称；无法识别板号。[keys][keys] |

NVRAM getter 查 user → factory RW → factory RO，执行 CRC 与只读 region access，无 set/erase/flush。传入第二个值会切换到写入分支；工具应固定完整命令，禁止追加值。[getter][nvram-get]；[region_get][region-get]

`kernel threads` 中 `entry: %p` 的实参实际是 `struct __thread_entry`；这不是可靠的映射证明，不能自动把输出数值当作可读取的函数地址。[线程结构][thread-struct]

## 暂时不能作为备份路径

- 不读 fread 打印的 `buf` 地址：handler 返回前 `k_free(buf)`，这是释放后的堆地址；读到内容不能证明来自 flash，也可能读其他任务数据。
- `dbg sdfs NAME SIZE` 仍使用同一 `print_buf()`，换文件系统不会解决 BLE 输出；它是具名资源文件读取，不是整个固件读取。[sdfs][sdfs]
- `dbg nvdump` 会遍历全部区域并输出配置值；既不能给出完整固件，又会扩大私人配置采集。优先固定单键 getter。
- `dbg fread sd/spinand` 的长度约定缺陷及 `snandr` 缓冲上界缺失已记录于[恢复评估](flash-recovery-assessment.md)，不作为盲试路径。
- SDK Leopard 定义 SPI0 cache `0x10000000..0x13ffffff` 与 uncached `0x14000000..0x17ffffff`；实际 CoMi 芯片、映射寄存器与 flash 地址对应关系未证明。`dbg mdb`/`devmem` 直接解引用，没有 fault 防护，不能只凭 SDK 常量读这片地址。[cache ranges][spicache]；[memory handler][memory]
- 已审计根命令中没有直接、固定的 chip ID、partition table、flash capacity getter。这个结论只覆盖固定 SDK 与当前保存的原厂根帮助，不能排除原厂 app 子命令。

## 推进条件

1. 先采集 `system/app/kernel` 帮助、固定版本属性、线程信息；新 getter 逐个审计。目标是实际板级/存储线索，避免反复发送已知丢正文的 fread。
2. 找到可返回内容的只读路径后，只取小块头，确认格式、地址单位、完整长度；成功 ACK 不替代字节正文。
3. 有真实布局后分段备份，保存长度、每块校验和与重读一致性；包括 boot、应用、资源、参数与校准。OTA 包和录音文件下载均不等同完整备份。
4. 若所有现有 BLE 命令都只能输出 printk，实际 UART/USB console 或官方升级包成为后续入口；当前没有证据表明它们可从这台设备直接取得。

[console-text]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L685-L707
[uart-write]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_uart.c#L305-L340
[printk]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/lib/os/printk.c#L51-L78
[uart-console]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/console/uart_console.c#L76-L95
[fread]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L439-L475
[print-buf]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L289-L308
[act-backend]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_output_backend.c#L74-L113
[default-start]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L603-L633
[system]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/sys_shell.c#L123-L138
[app]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/main/system_app_shell.c#L112-L124
[kernel-registration]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/kernel_service.c#L249-L264
[kernel]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/kernel_service.c#L18-L51
[threads]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/kernel_service.c#L55-L155
[keys]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/base/include/core/property_manager.h#L13-L35
[nvram-shell]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L1108-L1136
[nvram-get]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/nvram/nvram_config.c#L1323-L1350
[region-get]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/nvram/nvram_config.c#L993-L1031
[thread-struct]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/kernel/thread.h#L218-L223
[sdfs]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L1044-L1073
[spicache]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/spicache.h#L17-L26
[memory]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L128-L163
