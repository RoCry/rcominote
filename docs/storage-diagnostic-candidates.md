# 存储诊断候选：日志、coredump 与 geometry 查询

2026-10-12；源码审计，未访问硬件。SDK 固定 `26f51e584940d5b141cd1d09d2629d69b595f579`。实机已知输出见 [诊断记录](device-diagnostics.md)、[读取通路](readback-routes.md)。公开 SDK 与 CoMi 的编译选项、底层驱动及地址布局仍不能等同。

**没有找到可直接加入白名单、同时能证明存储型号/完整分区布局的新 getter。** 可以先获取 `actlog` / `coredump` 裸命令帮助；`coredump error get` 只读已有错误码。其余看似查询的路径需要额外条件，部分明确包含写入。

## 可建议的固定查询

| 命令 | 公开实现 | 价值与限制 |
|---|---|---|
| `actlog` | 根 handler NULL，列子命令 | 确认原厂是否有新增 getter；不选择任何文件 ID。注册见 [actlog shell][act-shell]。 |
| `coredump` | 根 handler NULL，列子命令 | 确认是否与公开实现相同；不是 dump。注册见 [coredump shell][cd-shell]。 |
| `coredump error get` | 只检查 `backend_ctx.error`，`shell_print` 输出 `No error.` / `Error: N` | 无 partition open/read、flush、erase、初始化或重启；只说明已有 backend 错误状态，不能识别存储。[handler][cd-get] |

先采帮助再考虑 `error get`；原厂同名命令实现尚未读取。短输出沿用固定 `help` 排空方法；ACK 不是执行结果。这里没有执行或新增 CLI 命令。

## `actlog find` 并非无条件安全

`actlog find HEX_ID` → `act_log_backend_get_used_size()` → binary backend → `flash_buffer_get()` → `ef_log_get_used_size()`。已审计路径仅用现存 RAM context 的 start/end/base/size 算已用字节；**不调用初始化、flush 或 flash_read**。[shell query][act-find]；[backend][act-backend]；[context selection][act-context]；[size getter][ef-size]

但 `act_log_output_binary_get_used_size()` 的判断是 `if (ctx)`，其中 `ctx = &flash_log` 恒非空；并未判断 `buffer_ctx`。ID 不支持、对应编译选项关闭或初始化失败时，`buffer_ctx` 可为 NULL；`ef_log_get_used_size()` 的 `init_ok` 宏直接解引用 `ctx->init_flag`。因此**不能盲试 `find 0/1/2/3`**。[defective guard][act-size]；[macros][ef-macros]

公开 ID：0 normal、1 runtime、2 event、3 saved；它们不是分区编号。只有证实实际编译启用了对应 buffer、且初始化成功，才能把对应查询作为小范围候选；返回已用大小依然不能推出全 flash 容量。[IDs][act-ids]

## 读取历史日志的输出和副作用

- `actlog print HEX_ID` 遍历已有 buffer，无显式 flush/init；正文 callback 调 `act_log_output_flow_write()`，后者走 UART DMA 或 `k_str_out()`，不会因此走 shell callback。头尾及统计用 `shell_print`；很可能再次出现“有状态、无正文”，不应反复试它绕过 `printk` 缺失。末尾还调用上述有 NULL context 风险的 used-size getter。[shell traversal][act-print]；[flow][act-flow]
- BLE console `0x10/0x11/0x12/0x13` 的 syslog/coredump/runtime/ramdump 选择，都走 `_logsrv_actlog_send_syslog()`；已知条件性停止 task watchdog。新增审计：inline `actlog_bt_transfer()` 把 syslog/runtime 转给 `actlog_syslog_transfer()`，后者在遍历前调用 `act_log_backend_flush()`；binary flush 启用落盘并调用 `flash_buffer_sync()` → `ef_log_write()`。因此 syslog/runtime 还有**可能写存储**的路径；不能当作被动提取历史启动日志。coredump/ramdump 分发到各自 transfer，不能把该 flush 结论套给它们。[BLE dispatch][ble-log]；[inline dispatch][act-inline]；[transfer flush][act-transfer]；[binary flush][act-flush]；[storage sync][act-sync]
- 正常 `partition_init()` 调 `partition_dump()`；输出名称、offset、type、file_id 等，**没有 size**，使用 `printk`。SPI NOR chip ID、NAND chip name / sector count 也有启动打印；NAND 源码的 `LOG` 宏就是 `printk`。现有 Actions binary 日志不自动收集全部 printk，尚无这些启动文本已持久化的证据。[partition initialization][partition-init]；[partition format][partition-dump]；[NAND print macro][nand-log]

## `coredump find/verify/print`：逻辑只读，但不是小查询

`find` 和 `verify` 都调用同一个 `process_stored_dump()`：打开固定 flash area、读 header、按 header 的 size 遍历全部存储 dump 求 checksum；并非只检查一个标志。`print` 先完整校验，再遍历第二次，正文经 `shell_print` 转 hex，所以与 `actlog print` 路由不同。[process][cd-process]；[shell print][cd-print]

已审计公共调用链没有 erase/write/flush，`flash_area_open()` 只是选常量表；`flash_area_read()` 绑定设备后调用其 `flash_read()`。但具体 flash driver 与其可能的恢复/初始化副作用仍取决于实际编译；不能凭这层接口证明 CoMi NAND 物理上不写。[flash map][flash-map]

额外边界：`process_stored_dump()` 的 header signature 使用 `&&`，只拒绝 C、D 两个字符均不匹配的情况；header read 返回值未先检查；未在此层把 `hdr.size` 限制到 area size。底层 `flash_area_read()` 有单次范围检查，但流程并非可靠有界小查询。`data_read()` 的结束 callback 还可能覆盖前面的 read error。故未建议盲执行 find/verify/print；不制造 crash，也不清除/擦除已有 dump。

## 几何查询中的隐式 flush

`dbg snand_ioctrl` 在 `CONFIG_CMD_SPINAND && CONFIG_SPINAND_TEST_FRAMEWORKS` 下注册。依次获取 sector size/count、erase-block size、hardware detection，**最后无条件请求 `DISK_IOCTL_CTRL_SYNC`**。驱动将该请求转为 `spinand_acts_flush(dev, 1)`；ioctl 前还可能执行 resume initialization。不能把它作为只读 geometry getter。[registration][nand-register]；[handler][nand-ioctrl]；[driver][nand-driver]

该驱动的 `GET_ERASE_BLOCK_SZ` 返回 `SECTOR_SIZE = 512`，并非物理 NAND block 几何证明。`snand_hardware_params` / `snand_software_params` 只找到 shell wrapper 与 extern 声明；未找到被调用函数源码，不能凭 `print` 名称证明无副作用。[wrappers][nand-params]

## 更值得继续的只读证据链

若通过**已证实映射的实机代码调用/常量**找到 boot-info getter，SDK 有更直接的只读结构线索：`soc_boot_get_part_tbl_addr()` 返回 `boot_info.param_save_addr`，固件版本地址为其 + `0x2e8`；boot info 包含 system/param 物理地址、NAND ID 表位置和长度、NOR mapping offset、code length。[getters][boot-get]；[structure][boot-struct]

`BOOT_INFO_SRAM_ADDR = CONFIG_SRAM_BASE_ADDRESS - 0x400`；这取决于实际配置。源码注释里的 `0x1000000` 不是实机地址证明，NAND ID 表也可能是支持型号表。只保存为后续代码追踪线索；不据此读取固定未知地址、MMIO 或整段 RAM。

[act-shell]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_shell.c#L283-L315
[cd-shell]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/debug/coredump/coredump_backend_flash_partition.c#L797-L823
[cd-get]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/debug/coredump/coredump_backend_flash_partition.c#L546-L559
[act-find]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_shell.c#L173-L192
[act-backend]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_output_backend.c#L116-L136
[act-context]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_output_binary.c#L34-L61
[ef-size]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/easyflash/ef_log.c#L408-L424
[act-size]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_output_binary.c#L366-L377
[ef-macros]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/easyflash/ef_log.c#L85-L88
[act-ids]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/logging/act_log.h#L39-L42
[act-print]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_shell.c#L83-L147
[act-flow]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_output_flow.c#L9-L20
[ble-log]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/application/bt_watch/src/bt_log/log_service.c#L572-L594
[act-inline]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/logging/act_log.h#L90-L106
[act-transfer]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log.c#L839-L858
[act-flush]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_output_binary.c#L442-L464
[act-sync]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/act_log/act_log_flash_buffer.c#L185-L225
[partition-init]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/partition/partition.c#L319-L336
[partition-dump]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/partition/partition.c#L30-L52
[nand-log]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/spinand/spinand_acts.c#L43-L49
[cd-process]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/debug/coredump/coredump_backend_flash_partition.c#L154-L273
[cd-print]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/debug/coredump/coredump_backend_flash_partition.c#L716-L766
[flash-map]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/storage/flash_map/flash_map.c#L58-L78
[nand-register]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L2451-L2462
[nand-ioctrl]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L578-L629
[nand-driver]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/spinand/spinand_acts.c#L467-L524
[nand-params]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L687-L712
[boot-get]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_boot.c#L26-L45
[boot-struct]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_boot.h#L14-L47
