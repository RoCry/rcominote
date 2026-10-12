# SD 后端元数据与启动分区候选路线

2026-10-12；**源码审计，无设备 I/O、无函数调用、无实际 RAM 捕获分析**。来源固定为公开 SDK commit `26f51e584940d5b141cd1d09d2629d69b595f579`。下列结构是该源码的 32 位、自然对齐 ABI 候选；必须先由实机指令、literal 和结构访问交叉验证，不能直接套用地址或完整布局。实机证据另见 [disk registry readback](disk-registry-readback.md)。

## 从逻辑磁盘到控制器

公开 SD disk driver 使用全局 `sd_disk`：`sd_disk_status()` 仅检查它是否非空；`sd_disk_initialize()` 通过 `device_get_binding("sd")` 设置它。`disk_sd_mass.dev` 没有初始化，因此不能假设 `disk_info.dev` 指向存储设备。`status` 函数体引用的实际 global literal 是更有价值的下一跳。[SD disk][sd-disk]

| 对象 | 稳定前缀，32 位字节 offset | 可识别什么 |
|---|---|---|
| `struct device` | name `0`; config `4`; api `8`; state `0c`; data `10`; handles `14` | name/config/API 区分驱动实例；data 是运行时状态 |
| SD device `data` → `sd_card_data` | `mmc_dev` 指针 `0` | 已绑定的 MMC **控制器 device** |
| SD device `config` → `sd_acts_config` | `mmc_dev_name` 指针 `0`; detect GPIO `4`; power GPIO `5`; flags byte `6` | 编译时绑定目标名与 GPIO 配置 |
| MMC controller device `config` → `acts_mmc_config` | MMIO base **指针值** `0`; IRQ config function `4`; DMA device name pointer `8`; clock/reset/clock-select/DMA-id/DMA-channel bytes `0c..10` | 控制器实例、时钟/复位/DMA 配置；不是存储厂商/型号 |

[device ABI][device]；[SD data/config][sd-struct]；[controller config][mmc-config]。尾部 kernel/PM 字段不影响上述前缀。不要解引用 controller MMIO base；读 config 中保存的地址值即可区分实例候选。

`sd_card_init()` 确实以 config 中的名字查找控制器并写入 `sd->mmc_dev`。SD device 的静态 data/config/API 在 `DEVICE_DEFINE(sd_storage_0, ...)` 绑定；MMC 的实例由 `MMC_ACTS_DEVICE_INIT(0/1)` 建立，base 来自 `SD0/1_REG_BASE`，名字来自对应 `CONFIG_MMC_n_NAME`。[SD binding][sd-binding]；[SD instance][sd-instance]；[MMC instances][mmc-instance]

建议证据链：实际 disk status 指令 → 实际 `sd_disk` global → SD device 前缀 → 实际 SD data 首指针 → MMC device name/config/API。每一跳都先确认源地址与区间属于已证明的映射；源码静态名字不是实机兼容性证明。

## 卡信息：保留了什么，没有保留什么

`sd_card_data` 保存 `card_type`、`card_initialized`、RCA、解码后的 CSD/EXT_CSD 和可复用 `mmc_cmd`。但是 `mmc_dev` 后面先有 `k_sem`，还可能有 `CONFIG_PM_DEVICE` 工作队列、工作项、timer 等；**card_type/CSD 的绝对 offset 不能在未知固件配置下给出**。[SD data][sd-struct]

| 已定位子结构后的相对 offset | 字段 / 意义 |
|---|---|
| `mmc_csd +0/+1/+2` | OCR CCS、高版本 SD spec、CMD23 支持 |
| `mmc_csd +4/+8`；size `0c` | decoded `sector_count` / `sector_size`，均 u32 |
| `mmc_ext_csd +0/+1/+4`；size `8` | EXT_CSD revision / MMC version / erase size（sector 数） |

枚举为 `CARD_TYPE_SD=0`、`CARD_TYPE_MMC=1`。初始化先写 SD 默认值；扫描先尝试 SD ACMD41，失败再尝试 MMC，成功后才改为 MMC。因此默认0、名字 `"sd"` 或 SD/MMC 控制器本身都不能证明介质为可拆 SD 卡；应结合初始化完成标志和实际控制流。[types][sd-struct]；[card scan][sd-scan]

**该源码没有长期保存原始 CID 或原始 CSD。** `sd_scan_host()` 的栈上 `cid_csd[4]` 先接收 CID，随后被 CSD 覆盖并解码；`sd->cmd` 的 response 被后续命令复用，不能把当前 response 当作 CID。EXT_CSD 也是临时 buffer，只保留结构中的少量解码字段。这条源码路线可以支持介质类型和逻辑几何调查，不能保证找出制造商、序列号或完整型号。[card scan][sd-scan]；[decode][sd-decode]

## “容量查询”不是无条件只读

这里只读源码；以下边界不授权调用设备函数：

- `sd_disk_status()` 源码仅读 global 指针。`sd_disk_ioctl(GET_SECTOR_COUNT)` 优先返回 disk partition 的缓存 count；否则底层返回缓存 CSD count。SIZE 同样来自 CSD；ERASE_BLOCK_SZ 固定返回512，不能当真实擦除块大小。上述 getter 分支没有卡命令，但初始化未完成可能报错。[SD disk][sd-disk]；[disk ioctl][disk-ioctl]；[card ioctl][card-ioctl]
- `HW_DETECT` 另行调用检测路径，且 disk wrapper 可以清空 `sd_disk`；initialize 会启动卡初始化。不能将它们当成缓存 getter。[disk ioctl][disk-ioctl]；[card scan][sd-scan]
- FatFs `f_getfree()` 只有在已挂载、`disk_status` 认可且 free-cluster 缓存有效时才走缓存返回。否则可能初始化磁盘或扫描 FAT；扫描 `move_window()` 可先将原有 dirty window 写回，随后更新 RAM `free_clst/fsi_flag`。之后 `sync_fs()` 还可能写 FSInfo。即使上层 API 名字是 statvfs / getfree，也没有端到端无写保证。[mount branch][fat-mount]；[free branch][fat-free]；[window writeback][fat-window]；[FSInfo writeback][fat-sync]

源码候选中最小扰动路线是分析实际代码和已经存在的 RAM/config 值；新增函数调用必须另做实机调用链审计。

## 启动分区表：独立于 `/SD:` 文件系统容量

两个名称接近的 init 不能混淆：`disk_operations.init = sd_disk_initialize()`；**启动时** `SYS_INIT(sd_disk_init, ...)` 才调用 `partition_get_stf_part(STORAGE_ID_SD=1, PARTITION_FILE_ID_UDISK=40)`，并把 entry 的 offset/size 转成 disk geometry。flag bit3 表示原值已经是 sector，否则两值右移9。这个 geometry 可以只覆盖 UDISK 分区，不等于整卡容量。[SD init][sd-init]；[partition IDs/layout][part-layout]

最短源码链分成两段：

1. 启动配置：`sd_disk_init()` → `partition_get_stf_part()` → global `g_part_table` → `parts[i]`。查找固定扫描30项，匹配 storage_id（也接受 `STORAGE_ID_MAX=5`）与 file_id；不调用 boot getter。[partition lookup][part-find]
2. 更早的表指针来源：`partition_init()` → `soc_boot_get_part_tbl_addr()` → `soc_boot_get_info()->param_save_addr` → boot-info。表初始化检查 magic 与 CRC。`soc_boot_get_info()` 的固定地址来自 `CONFIG_SRAM_BASE_ADDRESS - 0x400`；实机地址必须从实际 getter/literal 导出，不能直接使用公开 SDK 的 SRAM 配置。[table init][part-init]；[boot getter][boot-get]；[boot ABI][boot-abi]

| 对象 | 源码 32 位布局 |
|---|---|
| `partition_table` | magic `0`（`0x54504341`，LE `ACPT`）; version u16 `4`; table_size u16 `6`; part_cnt u16 `8`; part_entry_size u16 `0a`; reserved `0c..0f`; parts `10`; 30×24 B entries；reserved `2e0..2e3`; CRC u32 `2e4`; size `2e8` |
| packed `partition_entry` | name[8] `0`; type `8`; file_id `9`; mirror/storage nibbles `0a`; flag `0b`; offset u32 `0c`; size u32 `10`; file_offset u32 `14`; size `18` |
| `boot_info_t` prefix | mbrec_phy_addr `0`; param_save_addr `4`（已映射/保存的 PARAM 地址）; system_phy_addr `8`; reboot_reason `0c`; nand_id_offs `10`; nand_id_len `14`; flags `18`; reserved `1c/20`; param_phy_addr `24`（物理 PARAM 地址）; nor_offset `28`; code_len `2c` |

[table layout][part-table]；[entry layout][part-layout]；[boot ABI][boot-abi]。nibble 次序还需实机位提取指令确认。`param_save_addr` 与 `param_phy_addr` 不同；`nand_id_*` 字段存在不证明实际 NAND 后端。源码可以引导验证表与当前启动镜像位置，尚不能证明读出完整固件、识别烧录接口或保证官方恢复。

[sd-disk]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/disk/disk_access_sd.c#L37-L80
[device]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/device.h#L370-L395
[sd-struct]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L53-L125
[mmc-config]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/mmc_acts.c#L126-L143
[sd-binding]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L1611-L1623
[sd-instance]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L1775-L1786
[mmc-instance]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/mmc_acts.c#L1107-L1144
[sd-scan]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L983-L1058
[sd-decode]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L175-L323
[disk-ioctl]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/disk/disk_access_sd.c#L157-L205
[card-ioctl]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L1543-L1599
[fat-mount]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/fs/fatfs/ff.c#L3071-L3095
[fat-free]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/fs/fatfs/ff.c#L4722-L4780
[fat-window]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/fs/fatfs/ff.c#L897-L930
[fat-sync]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/fs/fatfs/ff.c#L956-L973
[sd-init]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/disk/disk_access_sd.c#L207-L246
[part-layout]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/partition/partition.h#L15-L83
[part-find]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/partition/partition.c#L248-L265
[part-init]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/partition/partition.c#L319-L336
[boot-get]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_boot.c#L26-L39
[boot-abi]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_boot.h#L14-L47
[part-table]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/partition/partition.c#L13-L28
