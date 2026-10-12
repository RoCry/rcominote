# 实机ACPT分区表：首次完整读回

2026-10-12，C261CF0430 / FW010004。通过日志→shell→dbg→sdfs→NOR分区getter，取得启动SRAM内的完整744 B ACPT缓存；两次独立一致，CRC通过。当前固定读取链2987 B，较前轮新增1452 B，累计6871不同映射字节。

**这是实际运行时分区配置，不是原始Flash备份，也不是恢复流程证明。** 所有新设备操作仍仅固定`dbg mdb`+`help`；未调用sdfs、flash read、分区helper、动态callback或复位。

## 从实际指令到表

| 位置 | 证据 |
|---|---|
| `100bb8d4`起256 B | 静态dbg表前缀；20 B descriptor，第11索引为`100bb9b0` |
| `100bb9b0` | syntax=`100c6c2a`，help=`100c6c2f`，handler=`10025415` |
| strings | 完整`sdfs\0`、`sdfs name size\0` |
| `10025414` | argc必须3；argv[1]→BL `10026614`；符合sdfs handler开头 |
| `10026614` | filename解析→storage/part byte；storage非0直接走失败返回，未走SDK候选SD/NAND路径 |
| `10026654..66b6` | NOR默认资源区与显式分区分支；part=`ff`表示无显式分区 |
| `100266b8..66c0` | r0=0，r1=uint8(part+10)，BL `10027720` |
| `10027720..7786` | global pointer load；30次循环；entry stride24；storage高半字节/file ID匹配；返回base+10+index*24 |
| `10027788` | literal=`1800ecb4` |
| `1800ecb4` | 实际table pointer=`01000040` |
| `01000040` | `ACPT`、version0101、table_size02e8、part_cnt18、entry_size24 |

公开SDK的SD/NAND候选路线不适用于这里的实际storage分支；NOR分支仍到达分区getter。录音exFAT/SD后端证据不受此影响，两条文件访问路径不同。

## 完整表与CRC

- 范围：SRAM `01000040..01000328`，744 B。
- 存储CRC：`703f5674`；按固定SDK `utils_crc32(0, first740B)`，与Python zlib CRC32一致。
- SHA256：`a071b0cdafad355eb05a71e96fc2cb6a5348ec8b5e11d0ac4dfe54d83671a144`。
- 18有效项；剩余12项全零。所有storage_id=0；按SDK枚举为NOR。
- 下表名字为8字节字段，可能截断；offset/size是表中配置值，尚未通过实际Flash总线读取验证。

| # | name | offset | size | file ID | mirror | flags |
|---|---|---|---|---|---|---|
| 0 | fw0_boot | `0x0` | `0x1000` | 1 | 0 | 2 |
| 1 | fw0_para | `0x1000` | `0x1000` | 2 | 0 | 2 |
| 2 | fw1_boot | `0x2000` | `0x1000` | 1 | 1 | 0 |
| 3 | fw1_para | `0x3000` | `0x1000` | 2 | 1 | 0 |
| 4 | fw0_rec | `0x4000` | `0x20000` | 3 | 0 | 2 |
| 5 | fw0_sys | `0x24000` | `0x1a5000` | 4 | 0 | 2 |
| 6 | user_rw | `0x1c9000` | `0x12000` | 9 | 0 | 0 |
| 7 | fw0_sdfs | `0x1db000` | `0x10000` | 5 | 0 | 2 |
| 8 | nvram_fa | `0x1eb000` | `0x1000` | 6 | 15 | 0 |
| 9 | nvram_fa | `0x1ec000` | `0x2000` | 7 | 15 | 0 |
| 10 | nvram_us | `0x1ee000` | `0x2000` | 8 | 15 | 0 |
| 11 | logbuf | `0x1f0000` | `0x4000` | 251 | 0 | 0 |
| 12 | evtbuf | `0x1f4000` | `0x2000` | 252 | 0 | 0 |
| 13 | coredump | `0x1f6000` | `0xa000` | 253 | 0 | 0 |
| 14 | res_a | `0x200000` | `0x40000` | 10 | 0 | 0 |
| 15 | sdfs_k | `0x240000` | `0xb0000` | 20 | 0 | 0 |
| 16 | fw0_temp | `0x2f0000` | `0x100000` | 254 | 0 | 0 |
| 17 | runtimel | `0x3f0000` | `0x10000` | 250 | 0 | 0 |

所有18项按offset连续，覆盖`0..400000`，与[NOR缓存ID的4 MiB系列线索](nor-driver-readback.md)吻合；不能因此证明芯片所有范围均可读写。

## 对备份、烧录、恢复的含义

- `fw0_rec`配置128 KiB recovery区，`fw0_sys`配置系统区；目前没读其内容，不能证明recovery有效、入口可达或能恢复自定义固件。
- boot/param各有mirror0/1条目；没有`fw1_sys`，不能称完整A/B系统或自动回滚。
- boot0/param0/recovery/system/fw0_sdfs的flags=2。SDK定义bit1为`PARTITION_FLAG_ENABLE_ENCRYPTION`；这是加密处理线索，不是已验证的实际密码算法、密钥位置或原始镜像可移植性。
- NVRAM factory/RW/user区均有配置；备份应最终覆盖设备个体配置。此轮只读表，无NVRAM内容。
- `fw0_temp`为1 MiB、file ID254，与SDK OTA_TEMP常量对应；不等于已确认升级包格式、写入权限或恢复路径。
- 可以定位后续研究的具体区域；**CLI仍没有整片备份或烧录能力**，不得将2987 B映射读回称为固件导出。

下一步：追实际启动信息引用，核对镜像选择、param/system物理位置与映射；审计加密标志消费路径和ROM/NOR读取实现。先证明读回与原始镜像之间关系，再考虑备份。恢复仍需独立证明。

## CLI与证据

`uv run comi diag capture shell-code --out ...`；两次记录用`uv run comi diag compare-references A B --shell --out ...`。离线报告增加`partition_table`，严格校验长度、表头和CRC；损坏立即报错。

[首次](evidence/partition-first-2026-10-12.json)、[重读](evidence/partition-second-2026-10-12.json)、[分析及表](evidence/partition-analysis-2026-10-12.json)、[结束状态](evidence/partition-final-state-2026-10-12.json)。结束idle/FW010004。76项测试、24项子测试、wheel/sdist通过；测试oracle是实机存储CRC、手读entry字段及指针变化拒绝行为。

固定SDK `26f51e584940d5b141cd1d09d2629d69b595f579`，源码作为解释模板，实际地址由读回证明：

- [NOR SDFS路径](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/sdfs/sdfs.c#L101-L189)
- [分区布局和初始化CRC](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/partition/partition.c#L13-L28)
- [分区字段和flags](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/partition/partition.h#L15-L82)
- [CRC实现](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/lib/crc/crc.c#L42-L59)
- [启动SRAM源码说明](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_boot.c#L18-L29)

后续：[flags、签名与恢复源码审计](boot-security-source-audit.md)确认三种标志不可混用，打包工具存在声明加密但该阶段未加密的允许路径；未证明CoMi采用该路径。
