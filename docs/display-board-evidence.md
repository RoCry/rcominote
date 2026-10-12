# 显示板级证据：CH1115标签、72×40与I2C

2026-10-12；C261CF0430 / FW010004。完整校验镜像离线分析；只展开三个函数，无设备I/O、函数执行、RAM pointer跟随或MMIO访问。

**实际panel实现带`panel_ch1115`日志标签，固定输出函数给出72、40两个分辨率候选值；init绑定`I2C_0`，命令helper使用地址`3c`。** init还配置GPIOA pin24/25，错误标签分别称reset/power。这些已有实际代码依据，足以约束后续porting调研；尚非实物controller读ID、物理像素/引脚测量或完整bring-up配方。

## 输入与定位

`artifacts/mapped-system/mapped-system.bin`经`inspect_image()`重验927632 B、固定头与正文checksum通过。完整SHA256=`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。[证据JSON](evidence/display-board-analysis-2026-10-12.json)保留descriptor/API窗口、init entry、全部bytes/SHA、literal、字符串和Capstone 5.0.6 Thumb+MCLASS反汇编。校验mapped artifact不等于physical Flash备份或恢复证明。

沿[已证实设备表](boot-storage-device-readback.md)`100b9f40..100ba320`、stride32取得：

| 对象 | descriptor | config | API | data RAM | PM control Thumb |
|---|---|---|---|---|---|
| `lcd_panel` | `100ba2c0` | NULL | `100bbc2c` | `180056f0` | `10027bed` |
| `lcdc_acts` | `100ba1e0` | NULL | `100bc2e0` | `1800f9a8` | `100318c1` |

两个完整NUL名字均由descriptor的name pointer取得，非扫字符串猜设备。`+18`是PM control，**不是init**；布局与固定SDK [device](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/device.h#L369-L398)对应。

本轮父分析另确认kernel helper `1009a7ac`按8 B `fn/device`对逐项调用。实际init entry：`100b9ed0={10027f99,100ba2c0}`；LCDC另为`100b9e90={100a4b17,100ba1e0}`。因此panel initializer精确定位为`10027f98`；LCDC init未展开。API窗口分别保存48/36 B，仅记录pointer；不从相邻数据推断完整API长度。

## 三个函数与直接事实

| 范围，末地址不含 | 长度 | 本轮用途 |
|---|---:|---|
| `10027a38..10027a50` | 24 B | panel API+1c指向的固定输出函数 |
| `10027ad0..10027b1a` | 74 B | 构造并提交两字节命令消息 |
| `10027f98..100280b4` | 284 B | init表绑定的panel initializer |

所有代码完整解码；nop/相邻函数不算入，literal独立保存。未展开PM control、work callbacks、GPIO/I2C driver或像素传输。

### 控制器：直接driver标签，尚非硬件ID

日志module entry `100ba574`含name=`100c7b51`，实际字符串`panel_ch1115\0`。命令helper literal `10027b20`与init literal `100280bc`均直接指向该entry，日志调用还使用共同module-table base=`100ba36c`。因此该标签确实绑定这套panel实现，不是镜像中无关字符串命中。

这支持**原厂软件选择CH1115命名的panel driver**。未读controller ID、未取得实物丝印或panel完整料号；不能由标签唯一确定芯片revision、兼容替代件或屏幕制造商。固定公开SDK没有给出本机driver源码对照，未凭相似名称套其他panel初始化表。

### 分辨率：72×40配置线索，后续ABI不同

实际API slot `100bbc48`即API+1c=`10027a39`，去Thumb位后为24 B函数。它不读取device/RAM，只向r1目标写固定值：

| 输出offset | 写入 |
|---|---|
| `+00` /u32 | literal `00280048`，拆为u16 `0048=72`、`0028=40` |
| `+04` /u32 | 0 |
| `+08` /u32 | `10` |
| `+0c` /u32 | `20` |
| `+10` /u16 | `10` |
| `+12/+13` /u8 | 0、0 |

固定SDK [display_capabilities](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/display.h#L160-L177)首两个u16是x/y resolution；API成员身份和输出形状共同支持**配置分辨率72×40**。但公开SDK当前API有17个slot，后续capabilities字段顺序/大小也不能与这20 B输出直接等同。因此这里不把`10/20`擅自解释为pixel format、orientation、refresh或monochrome属性。

该函数未执行，分辨率非物理像素测量；屏幕有效显示区、偏移、旋转和地址窗口仍未知。

### 总线：I2C_0绑定、0x3c消息形状

init `10028028`加载完整`I2C_0\0`，`1002802a BL 1009a81c`取得binding，`1002802e`保存到panel data首word；NULL时用`Could not get LCD controller device`报错。随后通过device API首slot传configure参数`14`；失败字符串为`i2c_configure error`。未把该数值强套成已证明的频率/模式。

同一module的命令helper `10027ad0`接收device及command byte，在stack构造：buffer=`{00,low8(command)}`、len=2、flags=2。`10027af2 BLX`调用device API+4，参数为device、message pointer、num_messages=1、address=`3c`。返回非零则记录错误并返回−22；零则保留零返回。

该消息布局、slot与参数顺序对应固定SDK [i2c_msg](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/i2c.h#L145-L169)、[transfer API](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/i2c.h#L415-L429)；[WRITE|STOP](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/i2c.h#L104-L115)=2。因此存在具体I2C写命令代码，目标地址`0x3c`，不是SPI/LCDC总线名称猜测。

本轮没有展开helper调用者或数据写路径，未证明当前bus pointer、configure成功、transaction实际完成、I2C速率或SDA/SCL pinmux。`lcdc_acts`注册存在不等于这块panel采用其像素通道。

### reset/power：GPIOA 24/25参数

panel init两次binding同一`GPIOA\0` literal，结果分别存data+50/+54；经device API首slot配置：

| call site | pin参数 | flags参数 | 实际错误字符串 |
|---|---:|---|---|
| `10027fe8` | 24 | `601` | `Couldn't find reset pin` / `Couldn't configure reset pin` |
| `10028016` | 25 | `a00` | `Couldn't find power pin` / `Couldn't configure power pin` |

数字及reset/power标签来自实际指令/literal；未独立审计GPIO driver，未解析flags极性或初始电平，不据此推断physical pad、排线pin、电压或电源开关接法。init还安排了后续work/callback；本轮不跟随，尚缺真正panel命令初始化序列及复位时序。

## 初始化与当前状态边界

两个data RAM地址均落在[已证实启动清零](startup-memory-readback.md#两段清零调用)范围`[18003ca0,18045250)`内，不属于已证明的initialized-data复制目标；没有可从镜像payload直接恢复的当前bus/config状态。清零是reset正常执行后的初始预期，后续init才写device/flags/work；本轮没有RAM快照，也未把初值当当前值。

目前可用于新固件调研的具体约束：`panel_ch1115`原厂driver标签、配置72×40、I2C_0/0x3c命令形状、GPIOA24/25 reset/power候选。仍缺实物控制器身份、pixel format与地址窗口、完整init序列、SDA/SCL与pad映射、GPIO极性/电压、有效速率及物理显示验证。没有修改显示状态、烧录或恢复操作。
