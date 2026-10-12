# 实机早期pinmux表与I2C0候选引脚

2026-10-12；C261CF0430 / FW010004。完整校验镜像离线分析，无设备I/O。[证据JSON](evidence/board-pinmux-analysis-2026-10-12.json)保留完整三张表、三个完整函数、init entry和literal，共九个窗口。

**GPIO14、15被实机早期代码配置为3808，功能号8与SDK I2C0定义一致。** 因此它们是I2C0总线强候选；目前不能分配SCL/SDA身份，也没有physical pad或排线连通性证据。

## 定位与写入

实际init entry `100b9d28={1002dd9d,0}`，位于已证实启动调用的level0范围。函数`1002dd9c..1002dde0`先连续调用三次`100a086e`，参数分别是19、3、3项的表。

完整表helper `100a086e..100a088e`按8 B `{u32 pin,u32 mode}`读取，逐项调用`100219f8`。完整setter `100219f8..10021a34`拒绝pin>77，正常路径：

```text
address = (0x1001a001 + pin) << 2 = 0x40068004 + 4*pin
new_value = (old_value & ~0x7f3f) | mode
write32(address, new_value)
```

操作包在中断优先级锁内；这里记录指令，未访问寄存器。helper忽略setter返回值；本表pin均≤77，不触发其越界分支。

## 三张表，按实际调用顺序

| 表地址 / 项数 | pin:mode（均为GPIO逻辑编号；mode十六进制） |
|---|---|
| `100bbf2c` /19 | 28:4125, 29:4125, 16:4126, 17:4126, 0:3021, 1:3021, 2:3021, 3:3021, 6:3821, 7:3821, **14:3808, 15:3808**, 35:3103, 34:3103, 33:3103, 49:3240, 50:3040, 10:0080, 9:3040 |
| `100bbf14` /3 | 18:580a, 19:300a, 20:580a |
| `100bbefc` /3 | **14:3808, 15:3808**, 25:3000 |

25项不等于25根不同引脚；14/15重复。setter对GPIO14/15访问的地址分别为`4006803c`、`40068040`。第三张表随后将GPIO25设为3000；更晚的[panel initializer](display-gpio-polarity.md)再将其配置为power输出，因此不能把早期表值当成当前状态。

三次表调用之后还有两个未展开helper、其他调用和直接寄存器写入。本轮没有证明后续所有路径均保留14/15配置，也未将这张表解释为完整板级BSP。

## I2C0解释依据与边界

固定SDK [pinctrl_leopard.h](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/cfg_drv/pinctrl_leopard.h#L43-L47)定义MFP0_I2C=8。实际3808的低6bit为8；结合本机[注册I2C_0与屏幕绑定](display-i2c-config.md)，支持14/15为其候选pinmux。不是直接套参考板的GPIO57/58配置。

尚缺相应SoC精确pin-function矩阵、SCL/SDA方向身份、后续重配置排除、实物引脚和电压测量。本轮对SDK cfg_drv目录的限定文本搜索没有找到14/15与SCL/SDA的独立映射；该未命中不证明资料或映射不存在。其他表项暂只保留数值，不按功能号猜测麦克风、存储或按键。

## 后续helper补查：该initializer结束前的覆盖

[补充字节证据](evidence/board-pinmux-overrides-2026-10-12.json)完整展开本initializer此前未审计的四个直接helper，另存三个literal窗口。与前篇原始initializer合并后，其所有直接调用目标都有代码依据：三次表helper、两次批量覆盖、一次pin9控制、pin62 setter及最终控制寄存器helper。

按三张表之后的执行顺序：

| 入口/操作 | 实际行为 |
|---|---|
| `100a426c..100a4290` | 依次调用setter，pin35、34、33各写mode1000 |
| `100a4290..100a42aa` | pin16、17各写mode1000 |
| `1002dd74..1002dd96`，参数0 | `40068028 ← 7040`，对应pin9 control；对`40068200`读改写，清bit9 |
| initializer直接setter | pin62写mode303c，即control地址400680fc |
| initializer直接STR | `40068304 ← 5880`；不擅自命名寄存器用途 |
| `100219cc..100219f2`，参数1 | `40001000`读改写bits8..9为1，保留其他位；用途未独立核对 |

因此在这个initializer内，pin16/17最终mode来源是1000，pin33/34/35亦为1000，pin9 control最终是7040；不能再仅引用第一张表的4126、3103、3040作为最终配置。setter仍保留mode掩码之外的原寄存器位，mode1000不等于完整寄存器值1000。

这些后续操作没有命中pin14/15 control地址`4006803c/40068040`。所以已排除**这个initializer的后续直接调用路径**覆盖14/15的可能；没有排除其他initializer、应用或低功耗路径在稍后重新配置。静态执行路径亦不等于当前RAM/MMIO状态。

SDK整个树中限定C/header/XML/DTS/text/JSON文件的GPIO14/15与SCL/SDA同一行文本搜索仍未找到独立方向映射。此类搜索不覆盖压缩文档、图片、间接表或别名命名，不能据此断言资料不存在。下一步可沿相关板级函数的调用者寻找运行期切换，或查精确SoC pin-function资料；不应猜SCL/SDA方向。
