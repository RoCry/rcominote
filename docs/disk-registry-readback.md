# 实机 FatFs 到磁盘 registry 的追踪

2026-10-12；C261CF0430/FW010004。接续[挂载与容量回调](storage-binding-readback.md)。只经现有日志shell读取已证实代码及引用，不执行新内部函数、不强制重新挂载。

## 已读调用链

1. 容量callback `100a42e4` BL `100a794e`；错误尾部 `100a4306` 实际为 `B 100a42fe`，补齐先前缺失的返回分支。
2. `100a794e` 接收path、输出free-count和输出fs-pointer；`100a7960` BL `1003f684(&path,&fs,0)`。成功后输出fs-pointer，读取fs+34、fs+1c，比较后者与前者减2；有效则直接写free-count。与FatFs `f_getfree()`缓存路径吻合，完整扫描分支未读。
3. `1003f684` 调 `1003eeec`（逻辑盘解析候选），用返回索引从literal `1003f864`→`1800fd4c`读取fs指针。检查/锁定后，取fs byte0；非零时取byte1，`1003f6be` BL `10040d9c`。若返回状态bit0为0，按访问模式/写保护位返回。吻合 `find_volume()`已挂载快速分支。
4. `10040d9c` 限定编号0..4，通过literal `10040dc0`→`100bc768`取名字指针，BL `100a1998`；返回经另一字节表翻译。这里编号范围已由实机比较/分支证实。
5. `100a1998` BL `10025870(name)`，非空结果经 `[disk+18]`→`[ops+4]`，最后 `BX r3` 尾调用；空指针返回-22。与 `disk_access_status()` → registry查找 → ops.status吻合。

函数边界：named-status从1998到19b3共28 B；32 B读取还含相邻函数push和一个未解码半指令，不能归入status。find_volume与f_getfree都只读了相关入口/快速分支，不能称为完整反编译。

## 固定源码交叉依据

- [FatFs f_getfree](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/fs/fatfs/ff.c#L4707-L4727)：缓存free-count及fs输出。
- [find_volume](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/fs/fatfs/ff.c#L3050-L3095)：索引表、锁、type/drive/status快速分支。
- [disk_status](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/fs/fatfs/diskio.c#L39-L49)：编号→名字→status。
- [registry与status分发](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/disk/disk_access.c#L26-L79)。

结构名称仍是固定源码与实机指令的对应推断；实际地址、偏移、分支和字节来自设备。没有原厂符号或完整镜像。

## 容量查询副作用边界

不能把所有 `info`/容量查询概括成物理上绝不写盘。公开 `f_getfree`缓存无效时可通过 `move_window`→`sync_window`刷出已有dirty sector，扫描后还置FSINFO dirty。`find_volume`卷失效会进入disk_initialize。是否在原厂实现中发生取决于实际路径/驱动，未通过本次代码读取证明或触发。用户正常查询行为与本次只读机器码采集应分开描述。[审计与后续识别路线](sd-metadata-candidates.md)。

## 活跃卷与缓存统计

实读FatFs指针表 `1800fd4c` 五项为 `[0,0,0,0,18010a8c]`；第五项与mount.fs_data一致。名字表第五项 `100bc778`→`100c6f54`，已读 **`SD\0`**。这将逻辑编号4、`/SD:`挂载对象和磁盘名SD连起来。

`18010a8c`首16 B：`04 04 01 00 01 00 01 00 00 00 00 01 68 fe 04 18`。实机find_volume已证实type在byte0、drv在byte1；callback已证实csize在u16+0a。因此type=4、drive=4、每簇256逻辑扇区（512 B/扇区），即128 KiB/簇。固定FatFs枚举4为exFAT，结合调用/字段吻合支持 **exFAT卷**，不是物理卡型号证明。[枚举](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/fs/fatfs/include/ff.h#L363-L367)。

实际缓存字段：

| 字段 | 地址/值 | 推导 |
|---|---|---|
| n_fatent | `18010ac0` = `0x74792` | 可用数据簇477072，即n_fatent−2 |
| free_clst | `18010aa8` = `0x74785` | 缓存空闲簇477061；≤477072，满足已读快速分支条件 |
| 数据簇总字节 | 477072×131072 | 62,530,781,184 B，恰为59634 MiB |
| 缓存空闲簇字节 | 477061×131072 | 62,529,339,392 B，整数MiB截断后59632 |

这些乘法解释了Boyi容量字段，数值来自时间点缓存；不是重新扫描磁盘的结果，也不是整块物理介质总大小。卷引导/位图/元数据、分区前后空间与其他介质固件均不包含在数据簇总字节中。

registry函数 `10025870..100258c3` 共84 B已读全：锁后遍历双链表，读取node+8名字，先比较长度再比较名字，返回匹配node。literal `100258c4`→`1800c3d4`为表头，`100258c8`→`1800c3dc`为mutex候选。下一步从实际表头定位命名为SD的disk_info，再读取ops.status的实际代码；不调用init或ioctl。

## 唯一注册磁盘节点

表头 `1800c3d4` 的next/prev均为`1800195c`；该node的next/prev均回到表头。node+8指向已读`SD\0`，因此本次快照registry只有一个命名为SD的节点。两份一致读取仍不是持锁原子快照。

| node字段 | 实际值 | 边界 |
|---|---|---|
| sector_size+0c | 512 | 逻辑扇区 |
| sector_offset+10 | 0 | 已注册逻辑磁盘偏移 |
| sector_count+14 | `0x747b000` = 122138624 | 驱动暴露的逻辑扇区数；不是物理原始NAND几何 |
| ops+18 | `1800197c` | 实机status分发已证实此偏移 |
| dev+1c | 0 | 不能由此直接取得硬件device |

sector_count×512为62,534,975,488 B；比数据簇总字节多4,194,304 B。差值可以来自文件系统布局/元数据等，不能据此命名隐藏固件分区；尤其不能把这些逻辑扇区当作原始Flash备份地址。

## 后端状态函数与设备指针

ops表 `1800197c` 五个Thumb指针依次为 `10025ab5`（init）、`10025951`（status）、`10025965`（read）、`100259a1`（write）、`10025a15`（ioctl）。这些函数均未通过本工具调用。

status实际16 B `10025950..1002595f`：从literal `10025960`取全局地址，读其word，为0返回2，否则返回0；BX LR后NOP。literal实际为`1800c3f0`，该word实际为`100ba160`。这与公开SD/NOR/NAND status检查全局设备指针的通用形状相符；仅凭这段短代码不能区分卡协议或芯片厂商。

后续读取`100ba160`的device候选固定前缀，需核对name/config/API/data是否符合实际driver结构；不读取配置指向的MMIO，也不调用init/ioctl。

## 已识别的device前缀

候选device `100ba160`前五word为：name=`100caef3`，config=`100bc398`，API=`100bc3a0`，state=`18003010`，data=`18005be8`。name实读 **`sd\0`**。config首8 B为`e9ae0c1000400c00`，首word指向控制器名称候选`100caee9`；GPIO/flag原始字节先保留，不未经实际代码验证就宣称板级引脚。

data首word实读`100ba100`，与固定SDK的`sd_card_data.mmc_dev`前缀相符。API前四word为`100a4ef5,100a4ee1,0,0`；尚未读取这些函数，不能按未核实ABI命名或调用。

控制器名引用 `100caee9`实读10 B `MMC_1\0mmc_`；到第一个NUL为 **`MMC_1`**，后面的`mmc_`是邻接数据。控制器对象`100ba100`的name也指向`100caee9`，与config字符串交叉一致；config=`100bc3bc`，API=`100bc3d4`，state=`18003078`，data=`1800f9d0`。尚未读取控制器config/API/data，不把这些值当作寄存器访问授权。

因此目前实机链为：**`/SD:` exFAT卷 → drive4 → 名字SD → 唯一disk_info → sd后端 → MMC_1控制器**。`MMC_1`是固件设备实例名，不能单独证明具体SoC、板级引脚、卡厂商或SD/eMMC类别。后续需实际驱动代码支持的卡类型/几何字段，或独立启动分区表链；不应继续靠卷容量猜固件大小。

## 最终证据与工具

[首次](evidence/disk-first-2026-10-12.json)、[重读](evidence/disk-second-2026-10-12.json)、[离线分析](evidence/disk-analysis-2026-10-12.json)：1487 B一致，含550 B新增；累计2372不同映射字节。运行期RAM只是时间点样本，尚无原子快照保证。

`uv run comi diag capture disk-code --out NEW`；`diag compare-references FIRST SECOND --disk --out REPORT`输出Thumb解码和`disk_metadata`，按实际指令缩放复算容量，拒绝无效/未知free-cluster缓存。独立[Boyi回复](evidence/disk-final-state-2026-10-12.json)仍为59634/59632，作为离线metadata测试oracle；设备idle、FW010004、noise9。
