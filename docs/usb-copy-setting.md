# USB模式命令：USB_COPY配置，不是枚举证明

2026-10-12，FW010004离线分析。[实际字节](evidence/usb-copy-setting-2026-10-12.json)。未发送SET_USB_MODE、写配置、重启或切换USB模式。

**0x13 handler更新RAM中的USB_COPY、设置属性并调用flush；其自身没有直接的USB控制器/重枚举调用。** 返回状态取自属性设置结果。尚未追完全部配置消费者，不能据此断言配置永不影响USB，也不能据ACK或usb_mode=true断言数据接口可用。

## 实际setter

[dispatcher](vendor-dispatch-followup.md)把0x13传到完整函数`1000ada8..1000adfe`。参数P指向command byte，P+2为payload首字节：

1. 读取P+2，直接写`1800ba00+45e`；该函数没有将任意输入限定为0/1，也没有在写入前检查payload长度。正常CLI仅发送已定义的布尔值。
2. 日志literal为`usb_copy = %d data[2] = %d`；以key=`USB_COPY`、该byte调用`1004ffd4`。
3. 保存上述返回值，然后无条件以同一key调用`100ad444`。
4. 第一项返回0则回复status0，否则status1；flush结果不参与判断。未见设置失败后恢复旧RAM值的代码。

## 属性与flush边界

完整`1004ffd4..1005002a`将整数格式化为字符串，调用`10050100`属性缓存setter；返回0则成功，非零打印日志并返回−13。与固定SDK [property_set_int](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/base/property/property_manager.c#L74-L89)结构相符，但**源码该版本对返回值的条件与实际分支不同**，本报告以实际指令为准。

完整wrapper `100ad444..100ad44e`调用`10050240`后总返回0。完整cache flush `10050240..100502d4`扫描15条、每条12 B缓存，匹配key后调用`10036a10`，成功才清理对应状态；结束也返回0。未完整展开持久化callee，因此不称已实测NVRAM成功，但足以说明命令ACK不携带逐项flush失败结果。

## 配置读回与接口状态不同

初始化片段`1000d192..1000d1a2`以默认1读取USB_COPY并存到同一+45e字段。事件状态片段`1000ac9e..1000acb2`从该字段读取并归一化为0/1，放入状态包；已有设备信息字段也使用这一配置值。

因此读到true可以来自保存的配置或默认值，不是USB枚举状态。此前[配对插拔观察](usb-log-probe.md)仍未确认CoMi USB节点；不能靠“开关已经开了”消除这项缺口。

下一步若继续USB功能分析，应找实际连接事件与USB_COPY消费者，再核对class/端点及存储后端；不能仅由命令名推断它导出原始NOR、恢复接口或录音盘。本轮没有理由把开关切换作为固件备份试验。
