# 已读回实机映射代码：16 字节的边界

2026-10-12，C261CF0430 / FW 1.0.4。**两次独立 BLE 会话返回相同的16字节映射代码**；没有 flash 写入、重启或下载 helper。此前“尚未拿到程序字节”的状态已改变；完整固件、物理 flash 偏移、分区与恢复仍未解决。

## 实测链路

1. [kernel 帮助](evidence/log-kernel-help-2026-10-12.json)列出 threads/stacks；uptime 6,316,256 ms。
2. [线程查询](evidence/log-threads-2026-10-12.json)显示当前执行线程 logsrv 的 entry 为 `0x1000bf21`；其他代码入口同样多为奇数 `0x100xxxxx`。查询前后 uptime 6,357,822→6,358,610 ms。
3. [紧凑栈表](evidence/log-stacks-2026-10-12.json)返回25条线程记录及 IRQ 00，包括 `vendor_read/vendor/launcher/logsrv/diskio_cache/sd_workq/shell_uart/media/dspworkq/ui_service`。这是线程元数据，不是栈内存内容；名字不能单独识别芯片、介质或恢复支持。
4. 清除 Thumb 位，固定发送 `dbg mdb 1000bf20 10`。该处理器把地址和数量按16进制解析，mdb宽度1，因此只读 `0x1000bf20..0x1000bf2f`，共16 B。
5. [首次采集](evidence/log-code-sample-2026-10-12.json)、[独立重读](evidence/log-code-sample-repeat-2026-10-12.json)内容完全一致；第二次在同一会话先重新查询线程并验证 logsrv entry。每次收齐 ACK/F1。
6. 最后 Boyi info 再次成功：FW010004、idle、容量59634/59632、unbound、charging、USB mode true。没有新录音/重启验收。

```text
1000bf20: 2d e9 f0 47 61 49 62 4e 86 b0 50 20 a1 f0 ab fa
SHA-256: 3314944ac8ca0faa67e68af9cff62b0daa5959ae0a1f1d9b0ea00bbf689e1cef
```

[离线解码报告](evidence/code-sample-analysis-2026-10-12.json)：Capstone5.0.6，ARM Thumb little-endian，16 B全部解码为6条指令：push.w、两条PC-relative ldr、sub sp、movs、bl。与函数入口相符，是对代码解释的支持；解码没有执行代码，不能独立认证芯片型号。

## 为什么这次可以读

`fread` 十六进制正文走 printk；`mdb` 的 `print_buffer()` 走 shell_fprintf，所以可以进入 BLE shell callback。读取数据的地址来自本机当前线程，而非直接猜测 SDK flash 基址或使用已释放的 fread heap buffer。[mdb/格式化][mdb]

入口来源仍有一个必须保留的限制：SDK把 `thread->entry` 结构传给 `%p`，C语言层面类型不匹配；`__thread_entry` 的第一个字段为 pEntry。`shell_print`→普通变参 `shell_fprintf`，在32位ARM AAPCS参数布局下，格式化读取到结构首字，即pEntry。多条一致的奇数代码地址支持这一ABI解释，实际16字节读取进一步提供证据；不能推广为任意结构/平台都可这样打印。[线程输出][thread-print] [结构][entry] [宏][macro] [变参][varargs]

SDK SPI0 cache 基址与所见地址相符，但缓存映射会使用 bootinfo 中当前 system 的物理偏移。**虚拟/映射地址不等于物理 flash offset**。16字节读回不证明整个 `0x10000000` 区域可读，也不覆盖 boot、参数、资源或校准。[映射][mapping]

## 长输出确实会丢失

线程详细输出在 dspworkq 的 `usage 1156 / 2` 处被截断，但协议 ACK/F1、帧长度均完整。随后紧凑 `kernel stacks` 返回后续线程。公开 logsrv 只有8×504 B缓冲；满时丢弃，drop提示自身走 printk。此处观察到的截断与缓冲机制一致，未直接测量原厂缓冲配置。[队列][buffers]

因此 `capture.ok` 只代表会话传输完整，不代表 shell 正文完整。未来读取必须限制每次输出，并按明确地址、精确字节数与独立重读逐块验收；不能把大段日志当成可靠 dump。

## 可复现工具与下一步

```sh
just log-capture --kernel-info --out artifacts/kernel.json
just log-capture --threads --out artifacts/threads.json
just log-capture --stacks --out artifacts/stacks.json
just log-capture --code-sample --out artifacts/code-1.json
just log-capture --code-sample --out artifacts/code-2.json
uv run tools/code_sample.py artifacts/code-1.json artifacts/code-2.json --out artifacts/code-report.json
```

`--code-sample` 只允许该自有序列号；每次先获取当前 logsrv entry，必须仍为 `0x1000bf21`，变化或没收到时停止，绝不发送 mdb。没有地址/长度自由输入。首次采集使用事前人工核对，第二次起工具强制会话内检查。

下一目标是沿已证实的代码区做有界、可校验的函数分析，识别映射/镜像范围和读取处理器；不能直接扩成整片地址扫描。独立恢复入口与原厂包仍需另一条证据链。

[mdb]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L28-L185
[thread-print]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/kernel_service.c#L55-L155
[entry]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/kernel/thread.h#L34-L39
[macro]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/shell/shell.h#L930-L944
[varargs]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell.c#L1493-L1500
[mapping]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/spicache.c#L190-L244
[buffers]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L444-L521
