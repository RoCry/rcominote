# 屏幕GPIO极性与寄存器路径

2026-10-12；C261CF0430 / FW010004。完整校验镜像离线分析，无设备I/O。[字节证据](evidence/display-gpio-analysis-2026-10-12.json)。承接[初始化顺序](display-command-sequence.md)，补齐当时未知的逻辑反转来源。

## 初始化明确设置反转mask

panel init的实际片段：

- `10027fd4..10027fea`：取GPIOA device data首word，OR `01000000`并写回，再调用configure(pin24,flags601)。
- `10028002..10028018`：同一data首word清`02000000`，再调用configure(pin25,flagsa00)。

结合已完整解码的逻辑write helper `100a2012`，这证明正常init设定pin24为逻辑反转、pin25为逻辑不反转。不是仅凭SDK flags命名猜极性；仍不代表当前RAM未被其他代码重新配置。

## 实际GPIOA driver

GPIOA descriptor=`100b9fe0`、config=`100bc1e4`、API=`100bc1c0`、data=`1800f8f8`。config首12 B对应words `ffffffff,40068000,00000000`，driver读取config+4为base、+8 byte为port index，因此GPIOA走index0分支。

| API slot | 实际函数 | index0路径 |
|---|---|---|
| +0 | `100307e8` | 配置输出模式与初始set/reset |
| +c | `10030740` | mask写`40068210` |
| +10 | `10030794` | mask写`40068220` |

固定SDK [GPIO寄存器定义](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_gpio.h#L125-L140)将base+210/+220命名为BSR/BRR；[GPIO driver](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/gpio/gpio_acts.c#L100-L152)对应置位/清位。这是源码语义与实际寻址相互印证，不是本轮寄存器读取。

configure实际检查flags bit9输出、bit11初始set、bit10初始reset；对应flags601使pin24初始reset，a00使pin25初始set。随后将对应pin control寄存器低12bit替换为40（其他高位保留）：pin24=`40068064`，pin25=`40068068`。这些是GPIO编号对应的寄存器地址，不是封装pad编号。

## 可复核的reset/power顺序

假设这些初始化写入正常执行且之后未重新配置，resume callback的顺序可细化为：

| 步骤 | 逻辑调用 | driver寄存器操作 |
|---|---|---|
| reset assert | pin24=1 | `40068220 ← 01000000`，清位 |
| power enable | pin25=1 | `40068210 ← 02000000`，置位 |
| 等待 | 参数10,0 | 时间单位尚未确认 |
| reset release | pin24=0 | `40068210 ← 01000000`，置位 |
| 等待 | 参数120,0 | 时间单位尚未确认 |
| 初始化 | 28个命令 | 见前篇命令表 |

因此软件的reset为active-low、power为active-high语义已有依据。但外接反相器、电源开关、pad复用后效果、供电电压、物理连线均未测量；不宣称实物电平波形已验证。

## 等待单位仍未解决

完整`1009bf94..1009c020`显示等待参数被保留为两个word，交给timeout helper `1009c2c0`，并以`100b91f0`读数计算剩余量。当前路径未见单位换算，但这不能证明参数为毫秒：仍需timeout/timebase实现及实际时钟配置。保留原始10、120，不写成10 ms/120 ms。

后续：[时间基准分析](display-timebase.md)已取得32,000 cycles/tick及32 MHz配置证据，支持名义1 ms/tick；上述“单位尚未确认”保留本轮阶段边界，当前结论以前述后续报告为准。
