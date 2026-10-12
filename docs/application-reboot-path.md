# 应用侧ADFU重启路径：存在但不等于独立恢复

2026-10-12，FW010004完整映射镜像离线分析。[实际字节](evidence/application-reboot-path-2026-10-12.json)。未执行重启、MMIO访问、ADFU切换或helper上传。

**实际`dbg reboot adfu`调用应用内重启函数，写入ADFU模式标记，再触发watchdog。** 这证明应用包含软件入口；尚不证明boot/ROM实际接纳该标记、USB恢复模式可用或应用损坏后能独立进入。

## 实际命令分支

[dbg命令表](actual-dbg-command-inventory.md)的reboot handler为`10024dcc`。完整函数至`10024e44`：

| 输入分支 | 实际调用 |
|---|---|
| argc2，argv[1]匹配`adfu` | `10021388(0x100)` |
| argc2，匹配`poweroff` | `10021408()`；本轮未展开 |
| argc2，匹配`jtag` | `10021388(0x600)` |
| 其他参数/无参数 | 等待helper后调用`10021388(0)` |

所以未知参数不是只打印帮助：它也会落到普通重启。此表是静态行为说明，不是待执行实验清单。

## 实际重启函数

完整`10021388..100213ec`包含若干准备helper，未逐一审计。模式600特殊分支读改写`4000c038`的bit0，并把模式归零；不能将jtag参数理解为只读调试查询。

共用末段：

- 将type截为u16，组合`0x42520000 | type`，写地址`4000c03c`。
- 调用等待helper，参数500；本轮不为其独立声明时间单位。
- 向`4000c020`写`0x5f`，随后在`100213ea`无限循环。

ADFU分支由此写入`0x42520100`。固定SDK的[sys_pm_reboot](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_pm.c#L334-L360)与[寄存器定义](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_regs.h#L367-L372)分别对应重启标记、RTC_REMAIN3和WD_CTL。这里仅解码指令，没有读取/写入这些硬件地址。

## 恢复验收仍缺什么

1. 应用无法运行时仍可触发的入口：实际按键/引脚或ROM条件；应用shell不满足此条件。
2. CoMi恢复态USB/UART身份及退出方法；普通USB插拔未确认接口，不能用SDK默认PID代替。
3. 匹配原厂镜像、设备独有配置与可靠备份；system映射导出不覆盖全部分区。
4. 经过审计的加载/刷写工具和恢复实测；公开helper的初始化可能擦写，不能当无损连接测试。

原厂/host侧线索见[恢复传输研究](recovery-transport.md)。本轮没有把软件重启命令加入CLI，也不把它作为目前可推荐的“试一下”操作。
