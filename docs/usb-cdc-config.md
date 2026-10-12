# 实际CDC配置：10d6:b00a与串口端点

2026-10-12；FW010004离线分析。[字节/descriptor证据](evidence/usb-cdc-config-2026-10-12.json)、[指令模拟](evidence/usb-cdc-init-emulation-2026-10-12.json)。未切换USB模式、修改配置或运行设备代码。

**镜像内有实际CDC初始化函数及相互引用的FS/HS描述符：VID/PID=`10d6:b00a`，两个interface，CDC控制和数据类。** 这比孤立字符串更强，但不是实机USB枚举结果，也不能解释为ADFU或NOR导出接口。

## 已解析描述符

`100dcd4a`与`100dcda7`各93 B：18 B device +75 B configuration。逐descriptor按bLength遍历，正好到边界。

| 项 | 实际值 |
|---|---|
| device class / VID / PID | 02 / 10d6 / b00a |
| interface0 | class02/subclass02/protocol01；CDC ACM |
| interface1 | class0a；数据接口 |
| control endpoint | 81 IN interrupt，最大16 B；FS interval10、HS interval6 |
| data endpoints | 84 IN bulk、03 OUT bulk；FS最大64 B、HS最大512 B |
| 配置 | 1个配置、2个interface，bmAttributes80、bMaxPower50 |

端点表属于此CDC描述符，不作为ROM/ADFU默认值。`mass_storage`日志模块字符串也存在，但不能用它把CDC endpoints认成磁盘接口；MSC实际配置/后端尚未建立关联。

## 注册与初始化

完整`1009a5e0..1009a6f2`准备device私有状态，依次注册索引1的`Actions`、索引2的`CDC-ACM-DEV`。串号尝试读取`BT_MAC`，失败使用`0123456789A`；未读取本机实际配置值。

`1009a676..1009a67a`将FS/HS指针传给`1009a200`；该完整小函数把指针存到USB全局对象+20/+24。随后以config=`100bf968`调用配置/enable函数`1009a2d0`、`1009a324`，错误时退出。这与固定SDK的[CDC初始化结构](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/cdc_acm.c)对应，具体值来自本机镜像。

```sh
uv run tools/verify_usb_cdc_init.py artifacts/mapped-system/mapped-system.bin
```

模拟从实际函数入口执行初始化及字符串注册，手工oracle为索引1/2/3及上述描述符顺序；模拟缺失BT_MAC、外部USB调用成功。实际返回0，按顺序到达config/enable桩。未执行USB/MMIO，不证明真实enable成功。

校验过程曾发现从`1009a620`开始的片段落在32位指令中间，误解码出索引24；完整入口解码和模拟排除了该误判。实际索引为1，**没有据此认定CDC初始化存在索引错误**。证据JSON仅保存完整函数边界。

## 独立模式检查线索

完整`1002dec0..1002def8`对应字符串`board_check_enter_usbcdc_mode`，读取key=`USBCDC_TEST_MODE`的1 B值；返回长度恰为1且该字节为ASCII `1`才返回真，否则返回假。这是属性检查，不能将函数名解释成已知外部按键入口。尚未把其caller与上述CDC初始化连成完整启动链；不设置该属性进行试验。它也不同于前篇[USB_COPY](usb-copy-setting.md)。

本轮只读主机IORegistry：16个USB节点中未见VID10d6。没有重新做受控插拔，不能据此确认CoMi当前连接状态或排除其他VID。下一步有价值的证据是模式checker的实际caller、CDC协议处理及MSC后端，而非仅根据嵌入描述符发送命令。
