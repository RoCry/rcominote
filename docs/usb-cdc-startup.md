# CDC启动门与自定义测试协议

后续已完成[工作线程与回复范围审计](usb-cdc-command-inventory.md)：此测试接口移出批量备份候选。以下保留初次启动链分析，不再按末尾旧“下一步”重复枚举命令。

2026-10-12；FW010004完整映射镜像离线分析。[字节与分发表证据](evidence/usb-cdc-startup-2026-10-12.json)。未设置测试模式、连接CDC串口、设置DTR或发送任何命令。

**已将测试标志、事件分支、CDC初始化和工作线程连起来；该线程处理自定义测试命令，至少部分命令写入配置，不是已证明只读的shell或固件导出服务。** 尚未取得完整命令语义，不能据此断言不存在可用读取命令。

## 启动与事件条件

- 启动片段`10001b32`调用前篇[模式checker](usb-cdc-config.md) `1002dec0`。它读取USBCDC_TEST_MODE并更新global=`1804062e`；此call的返回值随后被覆盖，但global保留。
- 完整getter `1002df08..1002df0e`读取同一global。
- 事件handler `10001f2c`以消息byte+3做TBB分派；实际表将值3路由到`10001f60`。这只是数值类型，未在本轮赋予“USB插入”等符号名。
- 该分支处理若干当前应用条件后，在`10001f82`再次检查mode getter；非零、消息word+8为1、helper `10027950`返回非零时，`10001fa2`尾调用`1000cf90`。

因此设置标志不等于立即出现CDC。事件来源、helper条件与实际硬件连接仍未验收；普通USB_COPY与该global不是同一字段。

还须区分checker返回值与global：checker对ASCII `1`返回真，但读取1 B后会把byte减30并保存；启动调用忽略返回值，后续getter只检查global是否非零。因此不能把整条启动链概括为“严格只接受ASCII 1”；异常属性值未测试，也不建议通过它试探模式。

## CDC启动器

完整`1000cf90..1000d036`：已有active标志时返回；否则绑定`CDC_ACM`，找不到返回−19。调用[实际CDC init](usb-cdc-config.md) `1009a5e0`，失败直接返回其错误；成功置active，并创建entry=`1000c6d9`、stack大小400（十六进制）的线程，名字`cdc_acm`。

前篇模拟只覆盖CDC init及注册，尚未执行这个启动器或真实线程。

## 线程并非通用命令行

线程入口`1000c6d8`绑定同一CDC device；`1000c72c..1000c746`通过device API+50查询参数4，将结果写到stack，再等结果非零。实际日志为`Wait for DTR`、`DTR set, start test`，支持DTR等待含义；UART API及外部枚举仍未现场观测。

接收分支`1000c838..1000c846`通过API+18最多读40 B到buffer，随后用buffer+2 byte作为命令值。这里没有把该buffer当NUL文本交给shell parser；不能对它发送已有BLE shell字符串并预期相同处理。

已审计的命令0/1路径：

1. 构造5 B回复，开头halfword02aa即磁盘/线性内存字节`aa 02`，后接命令、输入byte3和两者相加的byte。
2. 以命令号作为bit index更新context+3c bitmask。
3. 通过`100369e0(TEST_ITEM, &bitmask, 4)`进入已知NVRAM setter路径。

因此即便编号很小、回复简短，也不是无副作用握手的证明。完整worker含TBH与绝对地址表，本轮分别保存为数据，未对表内容线性反汇编；其他命令尚未完整审计。

## 下一步边界

有价值的后续是离线枚举实际command表，并逐个识别与存储/身份相关的处理器。只有确认接口可达、协议长度/校验、命令副作用和正文返回方式后，才能设计受控读取；当前不增加CDC运行命令或修改测试属性。应用CDC仍不等于ROM ADFU，也不满足应用损坏后的独立恢复要求。
