# 屏幕I2C实际速率配置

2026-10-12；C261CF0430 / FW010004。完整校验系统映射镜像离线分析，无设备I/O。[原始证据](evidence/display-i2c-analysis-2026-10-12.json)含九个窗口、三个完整函数解码。

**屏幕init传入的14选择400 kHz目标配置；实际driver写divider=5。** I2C_0的设备初始化默认100 kHz、divider=20，屏幕init随后配置为fast。此处是执行路径的静态含义，尚无实际SCL频率或当前寄存器测量。

## Descriptor与入口

- 实际init entry `100b9df0={10030579,100ba0e0}`。
- I2C_0 descriptor=`100ba0e0`，config=`100bc190`，API=`100bc1a8`，data=`1800f85c`。
- config前24 B：base=`40048000`、callback=`100a453b`、后续配置bytes与默认速率word（+14）=`000186a0=100000`。
- API首slot configure=`1002ffc5`。对应完整函数`1002ffc4..10030052`。

## 参数14如何解释

实际configure先要求bit4置位，再拒绝bit0置位；取bits1..3作为速率索引，减1后查表。实际表`100bc17c`的五项为100000、400000、1000000、1500000、1500000。参数14满足bit4=1、bit0=0、速率索引2，因此取第二项400000。

固定SDK [I2C flags](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/i2c.h#L34-L59)对应MASTER、FAST；这里也保留实际查表结果，避免只用SDK名称代替行为证据。

实际分频计算：

```text
divider = low8((31999999 + target_hz * 16) / (target_hz * 16))
write32(base + 4, divider)
data[0x3c:u32] = target_hz
```

400000时divider=5，100000时divider=20。实际literal=`01e847ff=31999999`，与固定SDK [i2c_acts_set_clk](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/i2c/i2c_acts.c#L225-L240)的32 MHz源时钟、向上取整公式一致。不能由配置值排除实际时钟差异、clock stretching或电气问题。

## Pinmux尚不在这条路径中

I2C initializer `10030578..100305f8`执行clock/reset形状helper、配置默认divider、初始化同步和内部状态，最后调用config+4 callback。该callback `100a453a..100a4550`仅向已见IRQ配置/enable helper传IRQ编号18；没有pinmux表或GPIO配置。

完整configure也没有pinmux操作。因此不能把参考板上的I2C引脚直接套给CoMi；后续需从实际早期board initializer寻找pinmux表。此处只排除了这三个已展开函数中直接配置引脚的路径，不声称固件缺少pinmux。

显示驱动现有证据可串联为：[板级入口](display-board-evidence.md)→[命令表](display-command-sequence.md)→[像素转换](display-pixel-path.md)→[GPIO极性](display-gpio-polarity.md)→[时间基准](display-timebase.md)。仍缺SDA/SCL编号及电气连接、物理显示验证；烧录和恢复条件没有因此满足。
