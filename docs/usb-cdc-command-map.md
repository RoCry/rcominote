# CDC命令表：生产测试、身份字段与破坏性操作

2026-10-12，FW010004离线分析。[分发表、相关代码与literal](evidence/usb-cdc-command-map-2026-10-12.json)。没有连接CDC或发送协议帧。

**已枚举实际一级分派及身份子表；没有从这些直接分支获得任意NOR/文件读取接口。** 已确认模式切换、身份配置写入和SD格式化路径。部分callee/异步路径仍未展开，不能扩大为“整个CDC协议绝无备份能力”。

## 一级分派

线程以接收buffer+2 byte作为命令。`1000c8d8`的17项word表覆盖02..12；`1000c8c4`的3项TBH覆盖81..83；其他特殊值由显式比较分支处理。以下命令均为十六进制，地址为去Thumb位后的代码入口。

| 命令 | 入口 | 实际操作/范围 |
|---|---|---|
| 02 | 1000cad8 | 设置测试状态，启动timer并调用回复helper；非只读身份查询 |
| 08 | 1000cbfe | 设置参数并调度timer；callback调用录音相关helper |
| 0a | 1000cbcc | 设置参数并调度timer；参数ff还写TEST_ITEM |
| 0c | 1000cd2c | 固定身份字段子命令，见下表 |
| 11 | 1000cc18 | 按参数启动/停止timer及板级helper；ff还写TEST_ITEM |
| 12 | 1000cc6c | 以`/SD:`查容量，缩放后放入单byte回复；不是存储内容 |
| 28 | 1000c91c | 回复后调用1005280c，参数0d/0/0/0；callee未审计 |
| 80 | 1000cb42 | 回复、写`BT_BQB_MODE`为ASCII 1、普通重启 |
| 81 | 1000cb18 | 回复后`10021388(100)`，即应用侧ADFU重启 |
| 82 | 1000cc9c | 回复、写`USBCDC_TEST_MODE`为ASCII 0、普通重启 |
| 83 | 1000ccca | `start format udisk`日志、调度timer；对应callback格式化路径见下文 |
| 90 | 1000cb72 | 停止timer/录音相关helper、板级操作并发送消息；非纯查询 |
| a0 | 1000c9ce | 取版本对象+10..13，构造带点的版本回复 |
| b0 | 1000caf6 | 调电量getter，返回单byte；日志TEST_READ_BAT |
| f0 | 1000ca9e | 构造12 B固定字段回复；未解释为Flash身份 |
| ff | 1000ca2c | 读TEST_ITEM并结合另一helper结果调整回复bit31；不是资源导出 |
| 其他值 | 1000c880 | 5 B回复，更新测试bitmask并写TEST_ITEM；**不是无副作用拒绝** |

默认组包含00/01及word表中的03..07、09、0b、0d..10等。对超大命令值，移位结果依ARM规则；无论是否新增bit，仍会走属性写调用。不能用未知命令扫描当被动探测。

## 0c身份子表

buffer+3为子命令，0..7；大于7回接收循环。本机实际TBH表如下；读写key来自对应literal和NVRAM调用，而非日志猜测：

| 子命令 | 入口 | 内容 |
|---|---|---|
| 0 / 1 | 1000cd6e / 1000cd48 | 读取 / 写入PCBA_SN，10 B |
| 2 / 3 | 1000cde8 / 1000cd9c | 读取 / 写入SN_NUM；存储12 B，写入时加SN前缀 |
| 4 / 5 | 1000ce6a / 1000ce2e | 读取 / 写入BT_MAC，12 B配置表示 |
| 6 / 7 | 1000cedc / 1000ce9c | 读取 / 写入BT_NAME，最多32 B处理buffer |

这些固定键不提供任意filename或NOR offset；不能由“可读配置”推断可备份分区。没有通过CDC读取设备身份或修改以上字段。

## 83的格式化路径

前篇[工作线程](usb-cdc-startup.md)已定位timer callback=`1000c508`。它从相同context+39读取当前命令；`1000c648`比较83，匹配后：

1. 查询`/SD:`容量，按与b400（十六进制）的比较选flags0a/0c。
2. 传path=`SD:`、上述flags、allocation unit0、stack工作buffer、长度512到`10040290`。
3. 打印`format_ret:%d`，返回带83的结果帧。

callee入口与固定SDK [FatFs f_mkfs](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/fs/fatfs/ff.c)五参数形状一致：解析drive、清挂载状态、初始化磁盘。格式化语义同时有命令日志、path、参数和入口结构支持；未执行、未完整反汇编整个formatter。无论后续成功与否，都不应作为只读USB探测。

## 对备份工作的结论

这个接口带有读取配置/状态的能力，也包含不可混用的生产与破坏性命令。当前没有理由为了固件备份启用它：普通读取分支没有返回固件/DSP内容，模式入口依赖原应用和持久属性，且实际USB可达性/协议校验仍未知。ADFU和退出命令存在，只证明代码中的软件路径，不能代替独立恢复实验。
