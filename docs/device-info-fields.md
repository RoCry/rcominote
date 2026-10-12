# 实机设备信息字段来源

2026-10-12；自有 C261CF0430 / FW `010004`。只分析主调查进程保存的[第一次捕获](evidence/device-info-first-2026-10-12.json)、[第二次捕获](evidence/device-info-second-2026-10-12.json)与[离线分析](evidence/device-info-analysis-2026-10-12.json)，没有发送设备命令。601 B非连续字节两次相同，包含完整容量 getter 代码；原始帧与完整性校验保留于这些文件。

**容量查询使用 `/SD:` 文件系统卷名；不能凭 59634/59632 识别 NAND 型号、物理 Flash 容量或启动分区布局。** 固件版本 `010004` 与 `xink_test` 来自代码引用的常量区。下述 getter 的源码对应仍为推断；实际函数地址来自实机 BL。

## 已证实的构造流程

命令分发表 `0x05` 分支调用 `0x1000aad0`，见 [分发证据](vendor-dispatch-followup.md)。连续 276 B `1000aad0..1000abe3` 包含全部已见控制流、返回以及尾部其他分支；16 B literal pool `1000abe4..1000abf3` 两次相同。

函数使用 `sp+4` 为回复 payload 起点；`1000abba` 调 `1000a888(r0=5, r1=sp+4, r2=0x34)`，即构造 **52 B** 回复。`1000aaee` 调用 `(sp+4, 0, 52)` 的 helper，很像清零；尚未读 helper，名称不是实机符号。官方 App / 当前解析器只要求至少 44 B，不能据解析器长度声称固件只返回 44 B。

容量：

1. `1000aaf4` → `100549c0`，r0 = literal `100c1243`；结果保留 r4。
2. `1000aafc` → `10054a28`，r0 = 同一 literal；结果保留 r0。
3. `1000ab00/02` 对两结果 `REV`，`1000ab04` 以 `STRD` 写到 `sp+4`。故第二 getter 返回值占 payload 0..3，第一占 4..7；小端 CPU 存储反转后的 word，形成协议 u32 BE。
4. `100c1243` 实际 8 B `2f53443a002f5553`，C 字符串到 NUL 为 **`/SD:`**。后面的 `/US` 是相邻数据，不属于卷名。

现有官方 JS 与捕获帧将 payload 0..3 解释为 total，4..7 为 free；这一语义来自独立协议证据，结合上述调用即可定位 total/free getter，而不是按函数地址猜顺序。

## Getter 算术已读全；与 SDK 的对应程度

已读完整代码：free `100549c0..10054a17`，total `10054a28..10054a7f`，分别以 POP 返回，包含所有已见分支。二者均：保存传入路径 → 调同一 `100546fc` → 负结果返回0 → 以 `r0=path, r1=sp` 调 `1002f24c` → 非零结果打印错误并返回0 → 算术成功分支。顺序吻合公开 `fs_manager_get_free_capacity()` / `fs_manager_get_total_capacity()`：检查已挂载卷 → `fs_statvfs(path, &stat)` → 容量计算及日志。[getter source][capacity]；[volume check][volume]

| 实机地址 | 指令序列 | ABI 对应 |
|---|---|---|
| `100549f6..10054a00` | `LDR r4,[sp+4]; LSR r2,r4,#10; LDR r4,[sp+12]; MULS r4,r2,r4; LSR r4,r4,#10` | free 用 allocation-unit size 与 free-block count |
| `10054a5e..10054a68` | 同上，但第二次 `LDR [sp+8]` | total 用 allocation-unit size 与 total-block count |

独立 Zephyr `struct fs_statvfs` 的四个32位字段为 `f_bsize / f_frsize / f_blocks / f_bfree`，与两处读取位置吻合。实机算术**已证明**为 `(((word_at_sp4 >> 10) × count) mod 2^32) >> 10`；结合此 ABI，数值单位为整数 **MiB**。59634 对应约58.24 GiB 的该卷容量报告值。[ABI][stat-layout]；[unit API][capacity-api]

这里尚有两条边界：`100546fc` / `1002f24c` 的身份未通过读取函数体确认，fs-manager/statvfs 对应属于有实际指令和独立 ABI 支持的推断；公开 littlefs manager 有相似结构，不能据此证明底层一定 FAT。[littlefs][littlefs]

此外，实机成功分支只有上述 `>>10 → 32位乘 → >>10`，**没有**公开 SDK 的 `frsize < 1024 || count < 1024` 替代分支。这证明不能直接给原厂代码套公开源码。先截断 frsize、再截断结果，乘法还会保留低32位；frsize小于1024时会报0，大数也可能溢出。未捕获实际 stat 四个字段，因此不能由容量整数反推出精确总字节数或文件系统 cluster geometry。

公开 FAT statvfs 用 `f_getfree()` 得空闲 cluster；`f_frsize = csize × sector_size`，`f_blocks = n_fatent − 2`。它没有报告 JEDEC ID、坏块储备、boot/resource/calibration partition 或整个介质大小。[FAT statvfs][fat-stat]

下一步若继续追容量底层，应沿共同 helper `100546fc` / `1002f24c` 确认卷查找/statvfs，或找到真实 storage device 绑定；继续读取同一已知容量输出不会给出芯片型号。只沿实际 BL、条件分支和 literal 推导白名单，不探测未知地址。

## 字段/常量与尚未知的状态结构

| Payload offset | 实机构造证据 | 解释边界 |
|---|---|---|
| 0..3 / 4..7 | 第二 / 第一容量 getter 的 REV 结果 | total/free 语义由官方协议支持；实际缩放已读全，fs-stat ABI 支持整数MiB解释 |
| 8 | 两个 `100adbc4` / `100adbbe` helper 的真假组合，写 0/1/2 | 协议解析器视非零 charging；helper 身份未知 |
| 9 | `100adbb2()` 的低字节 | 协议解释为电量；未读该 getter |
| 10 | `1000d2c8()`：返回 3→0，1→2，其他→1 | 与 idle/paused/recording 解码兼容；实际状态枚举身份未证实 |
| 11..13 | `100ba780` 读取 3 B，再按原字节顺序放入回复 | 实际常量 `01 00 04`，与 FW 1.0.4 一致；该常量不是板号 |
| 14 / 15 / 16 | RAM base literal `1800ba00` + `45e` / `470` / `45f` | 已有协议解释为 USB / mode / indicator；只证明字段读取，未读取整个 RAM context |
| 17 起 | literal `100c21e8` → helper `10000cdc` → `100b966e`，目标 `sp+15` | 实际常量 `xink_test\0`；helper 调用形状像 strlen/copy，名称未验证；原始回复确实出现该串，不能推定产品/芯片厂商 |
| 38 | RAM base +3 | 现有 parser 未解释；不能和 byte15 擅自合并 |
| 39 | RAM base +0c | 现有协议解释为降噪档位 |
| 40 | 固定 `ff` | 当前固件回复此字段为未知；不代表硬件绝对不支持语音触发 |
| 41 | RAM base +19 | 现有协议解释为分段档位 |
| 42 | RAM base +2 是否等于5，转为布尔 | 现有协议解释为背光；状态5具体含义未知 |
| 43 | `100546d8()` 低字节 | 未读、未命名该 helper |
| 44 | 固定0 | 未命名 |
| 45..47 | 初始 `1000a1b0()` 返回 context +171..173 | 未读、未命名；不是从常量版本复制 |
| 48..51 | 本函数未见后续覆盖，前述清零 helper 若成立则为0 | 历史52B原始回复尾4B为0；不单靠 helper 猜测未来固件格式 |

结论范围：证实了常量和数据来源，缩小下一次只读代码调查范围。没有获得原始 flash 映射、物理存储型号、完整固件或回刷路径。

[capacity]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/fs_manager/fs_manager.c#L248-L295
[volume]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/fs_manager/fs_manager.c#L94-L118
[littlefs]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/fs_manager/littlefs_manager.c#L121-L168
[capacity-api]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/include/fs_manager.h#L64-L83
[fat-stat]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/fs/fat_fs.c#L403-L425
[stat-layout]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/fs/fs.h#L118-L131
