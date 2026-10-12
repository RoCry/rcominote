# 实际初始化表与音频入口

2026-10-12；C261CF0430 / FW010004。完整系统映射镜像离线分析，无设备I/O。**已把31个注册设备对应到具体initializer；音频输入初始化明确绑定ADC_0，但麦克风类型、数量与接线仍未知。**

## 输入与初始化表

[证据JSON](evidence/init-audio-analysis-2026-10-12.json)保留完整镜像校验结果、71项表记录、原始窗口及完整Thumb/MCLASS反汇编。927632 B镜像SHA256=`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`；checksum通过不等于raw NOR备份。

实际helper `1009a7ac..1009a7fc`从`100bf9f8`按level索引读取相邻边界，循环读取8 B `{function,device}`，在`1009a7d4`以device为r0调用function；非NULL device另记录init返回值及initialized标志。device descriptor本身的`+18`并非initializer。

| 观察到的索引 | 起点 | 终点，不含 | entries |
|---|---|---|---:|
| 0 | `100b9d08` | `100b9da8` | 20 |
| 1 | `100b9da8` | `100b9dd0` | 5 |
| 2 | `100b9dd0` | `100b9ef0` | 36 |
| 3 | `100b9ef0` | `100b9f40` | 10 |

共71项，31项device非NULL，均对齐到已证实的32 B设备表。启动入口独立证明调用索引0、1。固定SDK [device.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/kernel/device.c#L56-L105)循环布局吻合，但其边界列表另含POWER_MAX及条件SMP；不能把SDK全部level枚举直接套给实际五个边界。

## 音频descriptor与入口

| 设备 | descriptor | config pointer | API | data RAM | init entry → Thumb function |
|---|---|---|---|---|---|
| ADC_0 | `100ba140` | `100ba800` | `100bc648` | `180427f5` | `100b9e10` → `1003b1e9` |
| audio_in | `100ba200` | `18001be4` | `100bc590` | `1800fc40` | `100b9ea0` → `100384e1` |

audio_in config位于[启动复制](startup-memory-readback.md)目标：`100de7c8 → 180012c8`，偏移`91c`，故其初始载荷在`100df0e4`。前三word=`100cc3a8,0,0`；首pointer指向完整`ADC_0\0`。这是启动镜像初值，未读取当前RAM。

固定SDK [ain_config_data与初始化](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/audio/audio_in_acts.c#L1025-L1084)支持首字段为ADC设备名的解释。实际84 B initializer `100384e0..10038534`：

- 清零data的`38` B并调用初始化helper。
- 读取config首word，调用已证实的binding函数`1009a81c`；结果存data+1c。
- binding为NULL会记错误，仍继续并最终返回0。因此init成功返回不证明ADC可用。
- 对literal地址`4000011c`执行读、清bit4、写；对应SDK关闭音频LDO pulldown的代码形状。这里只观察指令，没有访问MMIO或确认当前电压。
- 完整函数内没有额外I2S/SPDIF binding；不能据此排除其他调用路径或判定麦克风模拟/数字类型。

ADC config首word=`4005c100`。实际54 B initializer `1003b1e8..1003b21e`取config+11的byte=`23`作为helper参数，清data首byte，然后把config+1c的byte=`10`之bits4–5写入寄存器base+48的bits10–11，最后打印并返回0。未独立审计helper/寄存器定义，不把这些数值翻译为引脚、采样率或增益；公开SDK更复杂的ADC配置解析也不能视作本机已执行。

## 对自写固件的价值与边界

初始化表提供了可靠的后续入口，避免把设备PM callback误认作init。音频路径可从ADC_0 API及实际open/config调用继续追踪；显示已有[单独板级证据](display-board-evidence.md)。

尚缺：实际音频open参数、DMA通道与buffer约束、ADC输入选择、analog/DMIC模式、麦克风数量/供电、采样时钟与引脚。下一步应沿录音调用及音频API确定配置，不能仅凭ADC_0名字写BSP。此次没有录音、修改状态、烧录或恢复操作。
