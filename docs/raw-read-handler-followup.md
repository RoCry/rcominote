# 实机fread处理器：身份、门控与输出分流

2026-10-12；C261CF0430 / FW010004。仅离线分析已保存mapped chunks，无设备I/O、Flash操作、MMIO访问或复位。

**实机确有fread读取分支，但尚无经BLE完整返回原始NOR字节的已验证路径。** 本轮把既有[输出路由源码解释](readback-routes.md)推进为实际handler/输出调用证据：状态与十六进制正文使用不同formatter。最终printk backend及实际Flash read效果未证明，不能把该分流直接宣布为全部丢正文的动态原因。

## 表项身份：先排除snort

[准确bytes、SHA、完整反汇编与来源记录](evidence/raw-read-handler-followup-2026-10-12.json)。`ImageStore`验证固定头及chunk范围/长度/bytes SHA；分析固定在823296 B正文快照，末地址`100c9200`不含。三个函数按Capstone 5.0.6 ARM Thumb+MCLASS little-endian完整解码；literal pool单列。

入口沿[已确认dbg静态数组](shell-registry-readback.md) `100bb8d4`，20 B stride取得；没有根据SDK命令顺序猜入口：

| index / descriptor | 实读syntax及完整NUL名字 | handler指针 → code |
|---|---|---|
| 6 / `100bb94c` | `100c6b3f` → `snort\0` | `100257d5` → `100257d4` |
| 7 / `100bb960` | `100c6b63` → `fread\0` | `10025349` → `10025348` |

fread descriptor准确20 B：`636b0c10696b0c10000000004953021000000000`；help=`flash read : fread dev[sd/spi_flash/spinand] offset`。**相邻index6是snort，不能当作fread。** 仅按名字长度或源码排列推测会选错handler；没有执行任一handler。公开[注册表](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L2447-L2450)仅作对照。

## 实际handler与门控

`10025348..100253fa`完整178 B；SHA256=`f8d5f427e0c2268d6c6858ea4bece33054a3d63d74dd8d81c8346f03f379134e`。行为与SDK [shell_flash_read](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L439-L472)吻合；函数名仍为源码行为对应，未取得原厂符号。

| 检查/步骤 | 实际指令事实 |
|---|---|
| 参数 | argc必须3；否则usage、返回−1 |
| device | argv[1]→已知binding函数`1009a81c`；NULL则报错、返回+22 |
| 长度 | argv[1]与实读`spi_flash\0`比较；相等取512，否则取1 |
| offset | argv[2]调用`1009d48c`，base参数0；handler未验证返回的endpointer |
| buffer | 向`100b959c`传512；NULL则报malloc failure、返回−1 |
| 状态 | 在read调用前，经`100a0dd6`输出offset/buffer状态行 |
| read | 从device+8取API，取API首word；`100253d2` BLX该指针；参数device、offset、buffer、length |
| 结果 | signed ret≥0才进入dump；ret<0输出read failure |
| dump/释放 | 成功分支固定dump512 B；两分支均调用`100b958e`释放buffer，随后返回0 |

`100253c4..d2` bytes=`b3682246d3f80090394643463046c847`确定间接API调用。没有在这178 B中发现命令级offset容量检查、数据重读比较或认证分支；下层API可有额外条件。512 B状态行在read之前，不能证明read成功；read失败后也返回0，ACK/handler返回0不能当作数据验收。

实际非`spi_flash`分支只请求length=1，却仍dump512 B；没有展开其他device API的单位约定，不能将其认作有效SD/NAND备份入口。buffer在返回前释放，打印出的heap地址不能用作持久的原始读接口。

## 实际输出分流

成功分支`100253f4` BL `100252e4`，参数shell、buffer、512。该82 B函数保存pointer/len，按16 B一行遍历，LDRB取每个byte：

| call site | 实际目标/参数 |
|---|---|
| `100252fa` | `100a0dd6`，shell、color0、format=`100d13f4` |
| `1002531a` | `1009ff86`，format=`%8x: `、index |
| `10025322` | `1009ff86`，format=`%2x `、读到的byte |
| `1002532e`、`10025306` | `1009ff86`，format=`100d13f5`，行末/结束位置 |

两个hex format的NUL字符串已保存并校验；`100d13f4/100d13f5`在固定快照之外，未猜测其字节。首次输出使用与状态行相同的shell formatter，hex正文全部使用另一个format-first API。公开[print_buf](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L289-L307)连首次输出也使用printk，故本机实现并非该文件逐字节照搬；共同的关键行为是hex正文不走shell formatter。

`1009ff86..1009ffa0`完整26 B为变参wrapper：保存r0–r3，构造va_list，`1009ff92` BL `10026e6c`后返回。结合print_buf完整循环和format-first ABI，可识别为`printk`候选；[公开printk](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/lib/os/printk.c#L218-L229)可选择log_printk或vprintk。本轮止于该调用边界，不继续展开backend；没有证明当前走UART、DMA、日志重定向、disabled输出或某个具体console hook。

因此，**实际调用分流已确认，最终数据丢失位置仍未完全确认。** 这加强了源码输出路由解释，但没有观察到Flash读后的buffer，也不能以“未见read failure”推出已读到512 B。既有[状态行实测](device-diagnostics.md)仍只证明进入处理流程，没有完整字节正文。

## raw只读能力仍缺什么

handler直接选择的是read形状的API首slot，没有显式erase/program选择；这不构成完整下层无写副作用证明。既有[NOR驱动报告](nor-driver-readback.md)已确认RAM wrapper、16 MiB边界和可能的地址模式切换；该RAM API是另一份运行时快照，本轮没有重新读取或调用，更没有完整追完底层总线实现。

本轮没有发现新的BLE输出门控开关，也没有安装/执行任何重定向。仍缺：formatter backend与当前输出hook的实际对应、Flash调用成功后的完整字节、下层无erase/program及必要模式变更的完整证明、物理镜像与mapped镜像关系。接下来的最小离线缺口是`10026e6c`的backend分支；原始NOR读取、可恢复备份及烧录仍需各自验收。已实现的固定mdb映射镜像导出属于另一能力，不能替代raw Flash备份。
