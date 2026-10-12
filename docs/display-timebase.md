# 屏幕等待参数：tick与名义毫秒

2026-10-12；C261CF0430 / FW010004。完整校验镜像离线分析，无设备I/O。[证据JSON](evidence/display-timebase-analysis-2026-10-12.json)保留14个代码/literal窗口，七个完整函数解码。

**实际代码支持每tick 32,000个计数周期；结合busy-wait的32 MHz配置常数，支持名义1 ms/tick。** 因此屏幕resume参数10、120可解释为名义10 ms、120 ms等待；这不是实测GPIO间隔或精确唤醒保证。

## 证据链

| 实际入口 | 观察 |
|---|---|
| sys_clock initializer `10029974..100299d2` | 实际init表已定位；初次compare目标为当前counter加`7d00` |
| timeout driver `100299ec..10029a64` | 输入tick乘`7d00=32000`，扣除尚未announce的周期，再设置compare；另有最小`140=320`周期限制 |
| elapsed `10029b08..10029b40` | 周期差经明确UDIV除以`7d00`，返回完整tick数 |
| uptime `1009c4a8..1009c4d8` | 调用elapsed，将返回tick加到64bit累计值，无毫秒换算 |
| enqueue `1009c2c0..1009c3c4` | 普通正timeout路径保留输入量，加1及elapsed后插入delta队列；必要时调用上述timeout driver |
| busy-wait `1009c4dc..1009c504` | 输入乘literal `01e84800=32000000`，以literal `000f4240=1000000`及64bit形状helper换算，再比较cycle差 |
| cycle read `10029b50..10029b5e` | 读取counter，加另一个helper返回值；不是墙钟测量 |

屏幕调用`1009c02c`、睡眠实现`1009bf94`的参数10/120原样进入timeout链，前篇[GPIO报告](display-gpio-polarity.md)已保留该路径。这里只补齐单位解释，没有改变原始等待参数。

固定SDK [acts_timer.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/timer/acts_timer.c#L15-L17)定义cycles-per-tick为硬件cycles-per-second除以ticks-per-second；其timeout/elapsed路径与实际乘除相符。[timeout.c busy-wait](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/kernel/timeout.c#L359-L385)把微秒乘硬件频率再除1,000,000，与实际常数、UMULL及cycle差循环一致。故32 MHz是对实际固件配置的强推断，不只是引用参考板默认值；64bit算术helper本轮未独立解码，仍保留此证据边界。

## 对复位时序的影响

正常初始化后：GPIO24逻辑assert→GPIO25逻辑enable→等待10tick→GPIO24逻辑release→等待120tick→发送初始化表。以配置时间基准折算，等待请求名义为10 ms与120 ms。

timeout排队含tick取整/额外边界处理，调度、抢占、低功耗及实际时钟偏差也可能延长或改变实际间隔。不能把上述参数标为示波器测得的10.000/120.000 ms；亦未验证晶振实物或运行时频率。

下一步显示BSP仍缺I2C pinmux/速率、physical pad与电源测量，以及实际屏幕验证。时间单位已有可复核的静态解释，不再需要把它完全列为未知。
