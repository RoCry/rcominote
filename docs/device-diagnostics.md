# CoMi 实机日志与只读诊断

2026-10-12；自有 C261CF0430 / FW 1.0.4，macOS BLE。实际命令、原始 notification 与重组文本保存在证据 JSON；公开 SDK 仅用于事前审计，不能等同原厂全部实现。

## 已得到的实机证据

| 会话 | 固定操作 | 观察 |
|---|---|---|
| [默认日志](evidence/log-default-2026-10-12.json) | PREPARE / DEFAULT START，15 秒，STOP | 3 ACK + F1，正文 0 B；不能推定日志不可用 |
| [系统版本](evidence/log-device-info-2026-10-12.json) | `kernel version`；`device levels` 两次 | `Zephyr version 2.7.0`；两次 `device: command not found`；543 B 正文、6 ACK + F1 |
| [命令帮助](evidence/log-commands-2026-10-12.json) | `help`；裸 `dbg` | 2837 B 正文、5 ACK + F1；列出 flash 读取与 ADFU 重启命令 |

首次用命令正文证实 shell 执行，超越此前的 PREPARE/ACK 证据。仍未识别精确 SoC、板号或存储布局。

根命令包括 `actlog/app/bt/coredump/dbg/devmem/kernel/system` 等。`dbg` 帮助列出 `fread/snandr/snandw`、内存读写、`snort`、`reboot [adfu]` 等。**帮助存在不证明命令可用，也不证明刷写后能恢复。** 没有执行重启、写存储、擦除、看门狗停止、任意内存或完整 dump。

## 固定 NOR 头读取

精确命令 `dbg fread spi_flash 0` 对应公开源码的 512 B 读取：设备不存在/分配失败直接返回；已核查的 NOR read 路径没有 erase/write。地址零不跨 16 MiB，避免高地址模式切换。实际 CoMi 编译/ROM 分支内部仍未知；该工具不开放任意地址。

读取失败时 shell handler 仍可能返回 0，所以 ACK/会话 `ok` 仅表示传输完整，必须检查正文和完整字节数。首次请求仅收到 4 ACK + F1，没有正文；追加固定 `help` 的第二轮用于越过日志缓冲阈值。[首次记录](evidence/log-flash-header-2026-10-12.json)保留空输出；[追加帮助的记录](evidence/log-flash-header-flushed-2026-10-12.json)共 1305 B 正文、5 ACK + F1，包含 `fread 512b: offset=0x0, buf=0x1804fe68`，未见 binding/read failure，但**没有 512 B 十六进制正文**。只能确认进入处理流程，不能确认读回或备份成功。

源码 `print_buf()` 使用 `printk`，而命令执行时注册的是 shell UART/RTT 输出 callback；这是数据未进入 BLE 正文的候选解释，尚未确认本机 printk 路由。见 [print_buf](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L289-L309) 与 [shell callback](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L685-L707)。没有为绕过输出缺失而读取未知内存地址。

结束后 `just comi info` 成功：serial C261CF0430，unbound，FW 010004，idle，total/free 59634/59632，battery 100，charging/usb_mode true；没有验证新的录音或重启。

`fread sd/spinand` 的帮助与源码 byte/sector 约定不匹配；`snandr` 缺少缓冲长度上界；`snort` 包含写速度测试。没有尝试这些命令。精确依据及备份覆盖要求见 [恢复评估](flash-recovery-assessment.md)。

## 工具与复现

```sh
just log-capture --out artifacts/default.json
just log-capture --device-info --out artifacts/version.json
just log-capture --commands --out artifacts/commands.json
just log-capture --flash-header --out artifacts/header.json
```

默认只启动有界实时日志，1–30 秒；显式选项只发送固定查询，`--flash-header` 后自动发送 `help` 促进短缓冲输出。每条请求等待精确 ACK，最后 STOP，等待 F1 后退出。按广告序列号选设备；官方 App 先断开。

`Stream` 按长度重组 BLE notification；真实 504 B 文本块跨多次通知，不能把单个 notification 当完整协议帧。离线测试回放真实版本采集及断流，检查已观察到的版本/错误正文、ACK/F1 和未完成帧。

SDK 首个不足 504 B 的日志块可能没有立即发送；默认日志空白、某命令 ACK 或 STOP 成功，都不单独证明查询执行结果。源码分析见 [诊断设计](noninvasive-diagnostics.md)。

## 后续：配置读取已验证

[platform-info 实测](evidence/log-platform-info-2026-10-12.json)：固定 `app`、`system`、`dbg nvram FW_VERION`、`dbg nvram BT_LE_NAME`、`help`；8 ACK/F1，1937 B 正文，完整结束。

- `app` 仅列 set_config/input/btinfo；`system` 列 dumpmem/set_config/set_voice_effect/set_music_effect/wlock，没有新发现的芯片/分区 getter。
- `FW_VERION`（SDK 原拼写）读取失败，不能据此否定其他版本存储位置。
- `BT_LE_NAME` 返回14字节 `43 6f 4d 69 20 4e 6f 74 65 20 32 46 30 31`，即 `CoMi Note 2F01`。
- 证明现有配置 getter 的数据正文能经 shell/BLE 返回；不证明 NOR 原始数据可导出，更不是完整备份。

复现：`just log-capture --platform-info --out artifacts/platform.json`。仅两个固定键，不接收写值或任意键名；源码 getter 上限63 B。最终 Boyi info 查询再次成功，版本/容量/idle 未变。输出路由和源码依据见 [读取通路](readback-routes.md)。

## 后续：已读回实机程序字节

[映射代码读回](mapped-code-readback.md)记录kernel帮助/线程/栈元数据、当前logsrv入口的两次16字节读取与Thumb解码。原始flash fread仍无正文；新增mdb路径能够传回限定映射字节。
