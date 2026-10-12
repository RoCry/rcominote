# 从shell执行入口到dbg静态命令表

2026-10-12，C261CF0430 / FW010004。接续[文本分支](shell-text-readback.md)。当前`shell-code`两次独立读取1535 B一致，新增758 B，累计5419不同映射字节。仅固定`dbg mdb`+`help`；没有执行新handler、动态枚举callback、文件操作或Flash操作。

## 实际引用链

| 地址 | 实际指令/结果 |
|---|---|
| `1002307e..309e` | 解析循环条件；初始root层经`100231ec`回到tokenizer参数设置 |
| `100230a0..30d2` | tokenizer BL `10023bd8`；root层跳过help路径→`10023128` |
| `1002312e..3134` | r1=argvp[0]，r2=sp+1c，r0=parent；BL `100a0f94` |
| `100a0f94..0fea` | parent非空复制20 B；循环调用`10023d50(parent,idx++,dloc)`；比较syntax，匹配或NULL则返回 |
| `10023d50..3d6c` | root分支：加载start/end，比较`idx < (end-start)>>3`，取`start+idx*8+4` |
| `10023d6e..3d92` | 非root取parent+8；dynamic标志为0时按20 B stride取descriptor并检查syntax；非0调用callback |
| `10023d94` | start=`100ba674`，end=`100ba6dc`，104 B / 8 = 13项 |
| `100ba69c` | 第5索引entry：dynamic=0，descriptor=`100bb8c0` |
| `100bb8c0` | syntax=`100c69dd`，help=`100c69e1`，subcmd=`100bbba4`，handler=NULL |
| `100c69dd` | `64 62 67 00`=`dbg\0`，完整名字 |
| `100bbba4` | `00 00 00 00 d4 b8 0b 10`：静态，array=`100bb8d4` |

函数名称与固定SDK的`execute`→`z_shell_find_cmd`→`z_shell_cmd_get`结构吻合；地址来自实际BL/literal，而非源码位置推测。[源码链接与ABI候选](partition-reference-route.md)。本轮以实机加载和步长确认root entry为8 B、static descriptor为20 B，区分两种数组。

## root syntax前缀

按表索引0–12，只读每个syntax指针的4 B：`actl`、`app\0`、`bt\0U`、`clea`、`core`、`dbg\0`、`devm`、`help`、`hist`、`kern`、`resi`、`shel`、`syst`。仅`app`、`bt`、`dbg`见到NUL，其他为前缀；`bt`后的U属于后续字节。不能仅据此前缀宣称完整命令名或能力。

## 下一步与限制

沿`100bb8d4`静态数组查syntax，定位`sdfs`的实际handler；再从handler追`sd_fopen`和partition getter。动态callback不执行。子命令数组尚未读取，长度和终止descriptor未确认；不能把与相邻对象的距离当作数组边界。

仍无ACPT表、Flash物理offset映射、完整备份或刷写恢复证据。映射代码/表不等于固件镜像。

## 证据与验证

[首次](evidence/shell-registry-first-2026-10-12.json)、[重读](evidence/shell-registry-second-2026-10-12.json)、[逐指令分析](evidence/shell-registry-analysis-2026-10-12.json)、[结束状态](evidence/shell-registry-final-state-2026-10-12.json)。结束idle、FW010004，total59634/free59632。

每阶段跟随前验证已捕获父指令/表项；root边界或pointer变化立即拒绝。回归测试核对实际bounds、stride指令、`dbg\0`、静态数组指针，以及修改root边界后不读旧表。72项测试、24项子测试及wheel/sdist通过。

重现仍用`uv run comi diag capture shell-code --out ...`和`uv run comi diag compare-references A B --shell --out ...`；当前profile为1535 B，旧777 B记录保留为历史证据。

后续：[ACPT完整缓存表](partition-readback.md)已从dbg/sdfs/NOR路径取得；本文1535 B为历史阶段。
