# 从 shell 引用追启动分区表：源码候选

后续实测：[ACPT完整缓存表](partition-readback.md)已取得；实际SDFS仅接受NOR storage分支，最终经NOR显式分区getter到达表，以下SD/NAND路线保留为历史候选。

2026-10-12。仅审计固定 SDK `26f51e584940d5b141cd1d09d2629d69b595f579` 与已保存帮助；**没有新增设备 I/O、执行命令或调用函数**。这是下一次限定代码读取的候选链，不是已经完成的实机调用链。

## 已保存帮助确认 `sdfs` 存在

[log-commands-2026-10-12.json](evidence/log-commands-2026-10-12.json)，采集时间 `02:53:48.974749 UTC`，固定命令仅 `help` / 裸 `dbg`；`ok=true`、2837 B 正文、5 ACK、收到 F1。离线查看 command=`0xf0` 的 frame text：

```text
  sdfs        :sdfs name size
  nvdump      :nvram dump
  nvram       :nvram name (val)
```

因此 `dbg sdfs` 是实机帮助列出的入口；**未执行该子命令，也未验证 handler 地址或实现**。帮助不能证明它匹配公开 SDK。现有 [输出路径审计](readback-routes.md)还指出源码 `print_buf()` 的 printk 路径可能无法通过 BLE 回传正文，执行它也不是获取分区表的必要步骤。

## 最短候选：只读代码和 descriptor

```text
已知 logsrv 代码
→ 实际 _logsrv_proc_console_text 的 BL
→ shell_execute_cmd → execute → z_shell_find_cmd → z_shell_cmd_get
→ root table 的实际 literal / bounds
→ "dbg" descriptor.subcmd → 静态 subcommand array
→ "sdfs" descriptor.handler
→ sd_fopen → nand_sd_find_dir
→ partition_get_stf_part → g_part_table 的实际 literal
→ table pointer → ACPT header / entries
```

源码依据：logsrv 同步 console 路径注册 transport callback 后调用 `shell_execute_cmd()`；后者调用 `execute()`，命令查找进入静态 root/subcommand 结构。[logsrv][logsrv]；[execute][execute]；[command matching][matching]；[root/subcommand access][registry]

`shell_sdfs_dump()` 第一个文件调用就是 `sd_fopen(argv[1])`。`sd_fopen()` 按 storage ID 选择 NOR/data-NOR/SD-NAND 路径；SD/NAND 的 `nand_sd_find_dir()` 调用 `partition_get_stf_part(stor_id, part+10)`，随后才读目录。只需定位实际 BL 和 literal，即可在代码分析中到达 getter；不需要有效 filename，也不需要真的读文件。[handler][handler]；[open][open]；[SD/NAND lookup][lookup]

公开 `partition_get_stf_part()` 直接读取 global `g_part_table` 并固定扫描30项，匹配 storage/file ID。初始化时 `partition_init()` 从 boot-info 的 PARAM 保存地址设置此 global；runtime lookup 本身不调用 boot getter。表布局/初始化边界见 [SD 元数据候选](sd-metadata-candidates.md)。[partition lookup][partition]

## 仅作为验证模板的32位 ABI

| 源码结构 | 字节 offset / size |
|---|---|
| `shell_cmd_entry` | dynamic bool `0`; union pointer `4`; size8 |
| `shell_static_entry` | syntax `0`; help `4`; subcmd `8`; handler `0c`; mandatory/optional `10/11`; size20 |

[definitions][abi]。先从实际 load/stride 证明 ABI，再沿 table 边界和 syntax=NULL 哨兵读取。静态 subcommand 由 `.is_dynamic=false`、`.u.entry=array` 构造；dynamic descriptor 的 union 是函数指针，不可当作静态数组，更不能为了枚举而执行 callback。[static construction][static]

当前只知道实机 logsrv entry，尚未读全 console/shell 调用链；所有箭头仍需实机指令逐步确认。不要用源码函数相邻位置猜地址，也不把任意映射范围当作扫描区间。若实现/布局不同，停止该分支，保留已确认的证据边界。

## Device 数组不等于 SYS_INIT 表

`device_get_binding()` 只遍历 `__device_start..__device_end`；device 对象没有 init function 字段。已知实机 device 数组和 SD disk operations.init 不能直接提供 `partition_init` 或启动 `sd_disk_init` 地址。[device lookup][devices]

`device levels/list` 的公开实现列设备名字/状态，不列独立 `SYS_INIT` 服务；实机 [两次 device levels](device-diagnostics.md)均报 command not found。`SYS_INIT` 的 `init_entry` 另存 `{init_function, dev_pointer}`，源码32位 stride8；`z_sys_init_run_level()` 引用独立 level boundaries。只有未来从实际代码边得到这些 table literals，才能据此遍历；不能从 device array 向前倒扫或照搬 linker 邻接关系。[device shell][device-shell]；[init ABI][init-abi]；[init traversal][init-traversal]

本次没有找到可直接输出完整 boot/partition/init-entry 表的已确认只读 shell 命令。源码 `partition_dump()` 仅由初始化调用，走 printk；启动输出是否留存未证实。`nvram get/nvdump` 访问已初始化 region，未保留 partition-table backpointer，也不是 runtime partition getter 的短链。OTA 路径会涉及升级准备，不能用执行 OTA init 来查询分区。

[logsrv]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L685-L707
[execute]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell.c#L1578-L1613
[matching]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell.c#L621-L725
[registry]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_utils.c#L224-L274
[handler]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L1044-L1071
[open]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/sdfs/sdfs.c#L239-L277
[lookup]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/sdfs/sdfs_nand_sd.c#L361-L381
[partition]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/partition/partition.c#L248-L265
[abi]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/shell/shell.h#L94-L169
[static]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/shell/shell.h#L280-L287
[devices]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/kernel/device.c#L102-L134
[device-shell]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/modules/device_service.c#L15-L107
[init-abi]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/init.h#L38-L55
[init-traversal]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/kernel/device.c#L56-L99
