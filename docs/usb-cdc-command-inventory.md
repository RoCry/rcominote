# CDC完整工作线程：备份价值与协议边界

2026-10-12；FW010004，SHA `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。离线分析，无USB连接、配置写入或命令发送。[可复现证据](evidence/usb-cdc-command-inventory-2026-10-12.json)。

**结论：实际CDC测试线程没有提供任意内存、NOR或文件内容读取命令。为加速固件备份而启用它，当前缺乏依据。** 已覆盖整个worker的代码区间、三张分发表、IRQ/发送helper和timer callback；其公开读取结果均为固定配置/状态、小回复。该结论不覆盖异步消息接收者内部、其他USB类、ROM ADFU或别的固件。

## 完整分派及副作用

[已有命令表](usb-cdc-command-map.md)保留逐项入口与身份键。此次实际字节解码重新验证02..12的17项绝对地址表、81..83的3项TBH、0c子命令0..7的8项TBH，结果全部相符。显式比较另外覆盖28、80、90、a0、b0、f0、ff；其余命令均落默认组。

| 分组 | 命令（十六进制） | 本轮追踪结果 |
|---|---|---|
| 固定读取 | 12/a0/b0/f0/ff | SD容量单byte、版本字段、电量单byte、固定信息字段、TEST_ITEM及状态；无调用方可指定地址/长度/路径 |
| 固定键读取 | 0c子0/2/4/6 | PCBA_SN、SN_NUM、BT_MAC、BT_NAME；正文10/10/12/最多32 B |
| 身份写入 | 0c子1/3/5/7 | 固定NVRAM键写入；回复成功帧在setter之前发送，不足以确认写入成功 |
| 测试状态 | 默认组、02/08/0a/11 | 更新测试位、timer或板级状态；部分参数写TEST_ITEM |
| 控制/退出 | 28/80/81/82/90 | 异步main消息、BQB属性+重启、ADFU重启、退出CDC属性+重启、停止测试并发送main消息 |
| 格式化 | 83 | timer回调进入SD格式化；既有结论不变 |

默认组包括00/01和03..07、09、0b、0d..10，不是只读拒绝路径。不能用命令穷举验证“哪些编号有效”。

新增展开的28：`1000c93e..1000c946`传`(0x0d,0,0,0)`给`1005280c`。完整helper `1005280c..1005287c`清零20 B消息，写type/command至byte2/3，调用`1004fe28("main", &message)`；无额外payload时跳过分配/复制分支。与固定SDK [sys_event_send_message_new](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/system/sys_event.c#L43)的参数、消息形状、分支及main投递相符。实际main接收者未继续展开，因此保留“可能改变应用状态”的边界；这不是从CDC请求地址并回传内容的入口。

## 接收边界：没有worker层帧校验

`1000c838..1000c866`通过device API+18读取最多40 B到固定buffer=`1800b9b0`；只要返回值大于0，就直接读取buffer+2的命令并分派。完整worker未发现：

- 检查实际返回长度至少3/4 B；
- 检查输入byte0的aa、byte1长度或尾部加和；
- 保存半帧、拼接完整帧或遍历合并帧。

这些是**此worker代码的缺失检查**，不证明任意畸形USB数据必然产生同样实机结果。SDK [CDC FIFO实现](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/cdc_acm.c#L480)返回可用字节数，与worker的FIFO调用方式相符；USB串口数据流不能据此视为可靠的应用帧边界。将来写客户端需做响应缓冲/校验及受控实机验证，不能把一次read等同一帧。

## 回复正文范围

`1000c3e4..1000c452`发送调用者给出的固定RAM buffer和长度，按API+14的实际写入量推进指针；它不从请求解析内存地址、文件名或flash offset。IRQ callback `1000c3a0..1000c3da`只通过device API更新TX/RX状态旗标。SDK [CDC API表](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/cdc_acm.c#L824)对应FIFO读写/IRQ/line-control结构。

| 回复 | 字节数 / 格式（均为静态构造，未现场捕获） |
|---|---|
| 启动通知 | 5：`aa 02 f1 00 f1` |
| 普通结果 | 5：`aa 02 cmd value (cmd+value)&ff`；81使用旧checksum byte参与计算，不能概括所有分支完全一致 |
| a0版本 | 9：`aa 06 a0` +版本对象10..12+`.`+对象13+加和byte |
| f0固定信息 | 12：`aa 09 f0 02 02 08 01 0a 00 11 00 18` |
| ff测试位 | 8：`aa 05 ff` +4 B高位优先bitmask+加和byte |
| 0c子0/2 | 15：`aa 0c 0c sub` +10 B正文+加和byte |
| 0c子4 | 17：`aa 0e 0c 04` +12 B正文+加和byte |
| 0c子6 | N+5，N≤32：`aa (N+2) 0c 06` +N B名称+加和byte |

普通帧的加和从byte2到正文末尾，模256；不含aa和长度。timer的08失败回复有独立6 B构造；不将其错误帧当通用5 B帧。容量/电量/版本是固定格式的小结果，身份读取最长37 B；没有在此worker找到分块序号、offset/length、任意路径或大块正文循环。

timer callback=`1000c508..1000c696`覆盖02/12/a0/b0/0c相关板级状态、08录音测试、0a测试helper、11板级bit与83格式化；正在运行的timer读取当前命令，状态读取可能改变其分支选择。08调用`1000dca8`/`1000dd70`；入口检查录音状态，并使用固定`/SD:/RECORDER`路径启动/停止测试。底层录音文件实现未穷尽，但worker既无文件选择/读取参数，也无把录音正文接到CDC发送helper的路径。`1002dd74`完整函数操作固定MMIO位，无读取正文并返回的代码。ff额外状态helper=`100a5f9e`只查询两个索引、写两个word输出，worker最终仍只回传4 B bitmask。

## 研究决策与复现

CDC应归入“生产测试/配置客户端候选”，从固件批量备份候选主线移出；保留本证据供将来实现有限的状态读取，不需要为本结论启用测试模式。优先寻找SDK已有文件/内存传输协议和实际固件对应入口。此结论不能用于否定USB MSC、OTA或ROM工具能力。

```sh
uv run tools/inspect_usb_cdc_commands.py artifacts/mapped-system/mapped-system.bin
```

脚本锁定镜像SHA，按已审计代码边界反汇编；TBH、绝对地址表与literal pools不当代码解码。输出所有已覆盖区间SHA、调用、literal及关键指令。它是静态提取器，未执行ARM指令或硬件I/O；输出不是协议实机验收。
