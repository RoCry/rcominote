# 实机SD/MMC驱动状态追踪

2026-10-12；C261CF0430/FW010004。接续[磁盘registry](disk-registry-readback.md)，只读固定代码/引用，不调用init/read/write/ioctl，不读取MMIO。

## 已确认的控制器配置

`MMC_1` device.config=`100bc3bc`，首16 B：`00800540 a74f0a10 dd7c0c10 02020006`。按公开config前缀，对应base常量`40058000`、IRQ配置函数候选`100a4fa7`、DMA设备名候选`100c7cdd`，后四字节保留原值。base与固定SDK [SD1_REG_BASE](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_regs.h#L62)相同；没有访问这个寄存器地址。不能单独据此确定精确SoC或板级引脚。

## 与公开wrapper的差异

实机API read指针`100a4ef5`，函数20 B `100a4ef4..100a4f07`：把四寄存器参数重新排列，r1置0、旧r3放栈，BL `100335e0`，随后返回。没有offset/length右移9。

公开[Zephyr wrapper](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L1465-L1479)用u64字节offset/len并右移9；同仓库[bootloader wrapper](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/drivers/mmc/sd.c#L1353-L1368)虽使用32位参数，也右移9。实机不能套任一公开wrapper ABI；单靠调用形状不证明其参数单位。相邻`100a4f08`是另一函数，不归入该wrapper。

## 实机disk ioctl分发

`10025a14..10025a83`共112 B代码，后接40 B绝对Thumb地址表 `10025a84..10025aab`、8 B literal pool。范围检查cmd−1≤9，基址由ADDW取得，`LDR pc,[ip,index,LSL#2]`分发；表必须作为数据排除出Thumb解码。

| cmd | 表内目标 | 实际分支 |
|---|---|---|
| 1 | `10025a2d` | node+14缓存count非零则写输出；否则转storage ioctl |
| 2,4 | `10025a43` | 原cmd转storage ioctl |
| 3,6,7,8,9 | `10025a71` | 返回-22 |
| 5 | `10025a33` | 返回0 |
| 10 | `10025a47` | 调storage ioctl；结果可能清空全局device指针，不能当无副作用getter调用 |

实际storage ioctl目标`10033a20`，由`10025a3e`尾调用和`10025a4a` BL独立引用。literal `10025aac`为已知全局`1800c3f0`，`10025ab0`为已知`sd`名字地址`100caef3`。表内保存Thumb位，实际代码地址为目标清最低位。

## storage ioctl与实际字段偏移

`10033a20`从device+10取得driver data，检查data+171的initialized字节。cmd减1、检查≤11，`10033a40`为`TBH [pc,r1,LSL#1]`。其后`10033a44..10033a5b`为十二个u16偏移，不是代码：

`000c 0014 00e3 0017 000f 00e3 00e3 00e3 00e3 001a 006b 0097`

目标为`10033a44 + 2×offset`。cmd1→`10033a5c`读取data+17c的count；cmd2→`10033a6c`读取data+180的sector_size；cmd4→`10033a72`返回512；cmd5→`10033a62`返回0；cmd10→`10033a78`检查force_plug_out。其他分支未完整读取，不声称完整反编译或执行结果。

common transfer `100335e0`经device+10取得data。已读指令检查+171、用+17c做offset+count边界比较；低功耗路径读取+173、+170。类型为1才到`100336b2`，检查+184是否>2再调用`10032ab8`，否则直接走select-card路径。该callee未读取/执行；分支形状和偏移关系对应SDK的MMC类型与EXT_CSD rev≥3判断。后续+178为0才把地址左移9。

这比SDK sizeof猜测更强：实际指令确定位置，固定源码给结构语义；没有原厂符号，类型命名仍为交叉推断。[结构与枚举](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L53-L109)、[低功耗类型判断](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L556-L558)、[sector接口](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mmc/sd.c#L833-L890)。

## 缓存状态与能支持的结论

父指针data=`18005be8`；读取+170的16 B为`00010001 01000000 01030100 00b04707`；+180的4 B为`00020000`。两次独立读取一致：

| 字段 | 值 | 依据/边界 |
|---|---|---|
| type +170 | 0 | SDK枚举SD=0、MMC=1；实际类型分支交叉对应 |
| initialized +171 | 1 | ioctl/common-transfer实读检查 |
| force_plug_out +172 | 0 | ioctl检测分支 |
| low_power +173 | 1 | common-transfer读取并清零的字段；本工具未执行该函数 |
| RCA +174 | 1 | select-card调用参数加载 |
| CCS +178 | 1 | 实际地址移位分支；块寻址 |
| sector_count +17c | 122138624 | 与独立disk_info节点相同 |
| sector_size +180 | 512 B | 与独立disk_info节点相同 |

结论：**当前录音存储的驱动状态支持SD协议类别**，不再只是从名字`MMC_1`猜测。不能推出可拔插microSD、封装、厂商或精确型号，也不能推出启动固件位于这块介质。逻辑容量62,534,975,488 B不等于可恢复的固件镜像大小。

## 复现、工具与后续

`uv run comi diag capture card-code --out NEW`；两份结果经`diag compare-references FIRST SECOND --card --out REPORT`核对。固定2031 B，较disk-code新增544 B；累计2916不同映射字节。每层先核对当前指针/指令，再读取既定后继地址；没有任意地址接口。离线输出增加`card_metadata`；两个跳转表均排除出代码解码。

[首次](evidence/card-first-2026-10-12.json)、[重读](evidence/card-second-2026-10-12.json)、[分析](evidence/card-analysis-2026-10-12.json)。RAM是非原子的时间点样本；一致性不保证重启后仍适用。[结束状态](evidence/card-final-state-2026-10-12.json)另行查询。REA provider不可用，本轮实际使用仓库Capstone解码器和本地固定SDK源码，未声称REA反编译。

后续优先区分录音介质与启动介质，沿有证据的启动分区表引用查布局；其次定位实际SD初始化/CID处理以识别厂商。不要调用现有init/read/ioctl函数或扩大为盲扫。Android登录按用户要求暂缓，不阻塞这些工作。完整固件提取、烧录及独立恢复仍未实现。
