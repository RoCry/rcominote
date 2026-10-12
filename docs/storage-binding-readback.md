# 实机文件系统与存储绑定追踪

2026-10-12；C261CF0430 / FW010004。沿[容量 getter](device-info-fields.md)实际 BL 继续；不调用新的文件系统函数，只通过既有固定 mdb 读取代码/引用。公开 SDK 是交叉解释依据，不是原厂符号表。

## 完整函数证据

- `100546fc..10054737`：60 B。r6 从 literal `10054738` 取表地址；每项4 B、最多5项，与输入路径比较。匹配后从 literal `1005473c` 取另一表基址，索引乘8，检查 byte+4 的 bits0/1，任一未置位返回-22。吻合 `fs_manager_get_volume()` 的 allocated/mounted 检查。
- 两个实际 literal：`100bce24`（名字指针表）、`18017bb0`（RAM volume 表）。名字表第五项 `100bce34` 为 `100c1243`，该地址已读字符串 `/SD:`；故该卷 RAM 条目地址为 `18017bb0 + 4×8 = 18017bd0`。此地址来自实机指令/常量/索引，不是 SDK 配置猜测。
- `1002f24c..1002f2db`：144 B。拒绝空指针、长度≤1、首字节非 `/` 的路径，调用 `1002e8e8(&mp,path,NULL)`。成功后加载 `[mp+1c]`，再加载 `[vtable+44]`，非空则 `BLX r3(mp,path,stat)`。与 `fs_statvfs()` 源码及32位ABI吻合；间接 callback 才决定具体文件系统。
- `1002e8e8` 函数体尚未读取，`fs_get_mnt_point` 身份仍为调用结构推断。长度与比较 helper 亦未单独命名证明。

## 源码对应及限制

固定源码 `26f51e584940d5b141cd1d09d2629d69b595f579`：

| 结构/路径 | 32位 ABI / 证据 |
|---|---|
| `fat_fs_volume` | mp指针+0、flags字节+4、stride8；实机stride/flags已验证 |
| `fs_mount_t` | type+8、mnt_point+c、fs_data+10、storage_dev+14、mountp_len+18、fs/vtable+1c；实机只验证vtable偏移 |
| `fs_file_system_t` | statvfs callback+44；实机已验证 |

源码：[volume查找](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/fs_manager/fs_manager.c#L94-L118)、[VFS分发](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/fs/fs.c#L705-L729)、[mount结构](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/fs/fs.h#L85-L95)、[函数表](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/fs/fs_sys.h#L42-L76)。

不能直接跟随 `mp+14` 猜 `struct device *`：FAT manager 没有赋值该字段，FAT mount 使用 `fs_data` 与卷名。若 mount/vtable 证实后续 callback，才继续追 FATFS/disk registry；不得套配置敏感 FATFS 全结构。[FAT mount](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/fs/fat_fs.c#L428-L453)。

这些地址属于CPU映射，不是物理Flash偏移。尚无JEDEC ID、启动分区表、固件镜像长度或恢复保证。

## 已读到的挂载对象

`18017bd0` 返回 `640a0118 03000000`：候选 mp=`18010a64`、flags=3，与 allocated/mounted 均置位吻合。再读取该对象32 B：

| 偏移 | 实际值 | 与候选ABI的对应 |
|---|---|---|
| +00/+04 | `18010ce4` / `1800f7f8` | 链表指针候选，未跟随 |
| +08 | 0 | SDK FS_FATFS枚举值；仍需 callback 证实 |
| +0c | `100c1243` | 正是已读 `/SD:` 常量 |
| +10 | `18010a8c` | fs_data候选，未读取 |
| +14 | 0 | storage_dev为空；不能用此字段找芯片 |
| +18 | 4 | `/SD:` 字符串长度 |
| +1c | `100bc09c` | 与实机VFS取函数表的偏移吻合 |

因此下一次固定读取 `100bc09c + 44 = 100bc0e0`，获取实机statvfs callback。每次会话先重读并核对父指针/flags/对象身份，变化即停止，绝不自动跟随新地址。RAM只是时间点快照，不是原子冻结，也不保证重启后地址稳定。

## 实际 callback 与 FAT 对应

函数表word `100bc0e0` 实际为 `100a42d7`，Thumb入口 `100a42d6`。捕获48 B `100a42d6..100a4305`，成功路径完整；错误路径目前只读到置r0=-5，其后的返回分支未读，不能声称整函数已读全。

| 指令位置 | 实际行为 | FAT源码对应 |
|---|---|---|
| 42d8..42e4 | 从mount+0c取路径并+1；r1=stat+0c，r2=&local；BL `100a794e` | `f_getfree(&mnt_point[1], &f_bfree, &fs)`调用形状 |
| 42e8 | 非零返回跳4302错误分支 | `res != FR_OK` |
| 42ec..42f0 | stat+0写512 | `f_bsize = _MIN_SS`，实机配置512 |
| 42f2..42f6 | 取fs+0a的u16，左移9，写stat+4 | `f_frsize = csize × 512` |
| 42f8..42fc | 取fs+34的u32，减2，写stat+8 | `f_blocks = n_fatent − 2` |
| 42fe..4300 | 恢复栈并返回，成功时r0保持0 | 成功返回 |
| 4302 | r0=-5 | `-EIO` |

[固定SDK FAT statvfs](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/fs/fat_fs.c#L403-L425)与实机完整成功分支逐项吻合，结合mount type0，强力支持实际卷采用FAT路径。`100a794e`仍是未读的`f_getfree`候选；未见原厂符号，未证明底层介质型号。

实机代码已经给出fs结构的csize+0a/n_fatent+34，不必再凭SDK编译选项猜这两个字段。后续应先验证getter返回的fs与mount->fs_data的关系，再沿实际磁盘号/registry定位底层驱动。512是**逻辑扇区大小**，不是物理NAND页/擦除块大小；录音卷与启动固件可处于不同介质。

## 可复现证据

最终937 B固定读集已两次独立采集一致：[首次](evidence/storage-first-2026-10-12.json)、[重读](evidence/storage-second-2026-10-12.json)、[解码](evidence/storage-analysis-2026-10-12.json)。其中601 B为此前校验链，336 B新增，包括40 B RAM元数据。`uv run comi diag capture storage-code --out NEW`；两份捕获用`diag compare-references FIRST SECOND --storage --out REPORT`离线验证。
