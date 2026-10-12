# TLV文本分支到shell执行入口：实机证据

2026-10-12，C261CF0430 / FW010004。接续[协议入口](shell-service-readback.md)。当前`shell-code`两次独立读取777 B一致，较前轮新增432 B；累计4661不同映射字节。仅固定地址`dbg mdb`+`help`，未执行新的shell命令、文件操作、Flash操作或复位。

## 实际路径

| 地址 | 读回行为 |
|---|---|
| `1000c19c..c1c6` | service剩余长度非零→读取3B TLV头；成功→`1000c1f4` |
| `1000c1f4..c222` | type进入r7，little-endian长度进入r4；正文接收长度最多64；≤64成功路径→`1000c256` |
| `1000c256..c25a` | type0进入code分支；type1→`1000c2cc`文本分支 |
| `1000c2cc..c2da` | `buf[min(len,63)]=0` |
| `1000c2ea` | BL `100242b0`，参数callback/context；此callee最终`STRD r0,r1,[r3,#14]` |
| `1000c2ee` | BL `100242a8`；getter为`LDR r0,[PC]; BX LR`，literal=`100ba644` |
| `1000c2f4` | BL `100a0e1a`，r0=backend、r1=text buffer |
| `1000c2fc` | 以两个零再次调用`100242b0`，解除输出callback |
| `1000c302` | BL已知日志发送callee`1000bc18`；随后回TLV循环 |
| `100a0e1a..e38` | 检查text/backend非空与长度≤255；复制命令到ctx+42 |
| `100a0e3a..e70` | 保存长度到ctx+3c/+3e；ctx+2f4锁调用；BL `10023020`；解锁；清空命令和长度；返回 |
| `10023020..305e` | 内部执行入口：准备cmd buffer、光标相关调用、清空ctx+8的20B active-command对象、继续命令处理 |

SDK固定版本及源码链接见[引用路线](partition-reference-route.md)。参数、缓冲区处理、加锁→内部execute→解锁→清空的实际结构支持`100a0e1a`为`shell_execute_cmd`的对应实现；没有从源码符号臆测地址。`10023020`是否完全匹配SDK的`execute`仍需后续代码确认；当前只取得其64B前缀。

Getter返回后的`100242ac`独立标为4B数据，不能反汇编为指令。32位BL跨transport行`1000c2dc/c2ec`，必须拼接相邻代码后解码。每阶段先核验实际父分支/BL字节，变化则拒绝跟随旧地址。

## 后续边界

下一步从`10023060`连续代码追命令查找；通过实际BL定位`z_shell_find_cmd`/registry候选后，确认表边界、stride和descriptor。尚未获取root表、`dbg`/`sdfs` descriptor、partition getter或ACPT表。不执行动态command callback，不把backend对象当root表。

当前仍无完整固件备份、刷写/恢复证明。777 B是映射代码/常量，不是Flash镜像。

## 保存证据

[首次](evidence/shell-text-first-2026-10-12.json)、[重读](evidence/shell-text-second-2026-10-12.json)、[逐指令分析](evidence/shell-text-analysis-2026-10-12.json)、[结束状态](evidence/shell-text-final-state-2026-10-12.json)。CLI命令同前篇，当前profile已扩展。测试覆盖真实type1分支、跨行BL、getter数据边界、改变execute目标后的拒绝行为。

后续：[shell registry与dbg静态表](shell-registry-readback.md)已定位实际root表和dbg子命令数组；本文777 B为历史阶段，当前profile1535 B。
