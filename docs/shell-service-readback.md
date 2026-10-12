# 日志服务回调与协议入口：实机读回

2026-10-12，C261CF0430 / FW010004。`uv run comi diag capture shell-code`：限定 `dbg mdb` + `help`，只读已见分支、literal、连续代码；未调用 shell handler、文件操作、NOR操作或刷写入口。无需 Android 登录。

两次独立读取345 B一致；其中276 B新增，累计4229不同映射字节。地址属于运行时映射，不等于物理Flash offset。

## 已确认链

| 实机位置 | 指令/数据证据 | 边界 |
|---|---|---|
| `1000bf3c` | allocation结果非零→`1000bf58` | 不沿失败日志猜成功路径 |
| `1000bf6e` | stream结果非零→`1000bf82` | stream实现未分析 |
| `1000bf8a..bf98` | literal `1000c0cc`加载callback，r2=context、r0=context+20，BL `1009c8cc` | callback word=`1000c0e9`，Thumb入口`1000c0e8` |
| `1009c8cc..c8f4` | 保存r1/r2到r6/r5；`STRD r6,r5,[r4,#14]`；返回 | 实际注册代码支持callback/context解释 |
| `1000c0e8..c108` | 检查context+4低位、stream可读长度、准备5B header，BL `1000bb0c` | 后者只定位，未另行执行 |
| `1000c116` | header读取成功→`1000c138` | 失败路径回到回调收尾 |
| `1000c138..c166` | header字节检查service=`1d`、type=`81`、command=`10` | 与已捕获的日志协议吻合 |
| `1000c16a..c18c` | 从header offset3/4组装little-endian长度 | 处理正文的后续尚未读取 |

相邻transport行合并后解码，保留末尾不完整Thumb指令；未将缺失字节猜成完整指令。每一阶段读取前验证父分支/参数代码；固件地址或指令变化即拒绝沿旧地址读取。

## 仍待确认

`1000c18e`起正文处理、TLV text分支、shell命令表、`sdfs` handler、partition getter。此轮未取得分区表、完整固件或恢复镜像；[源码候选路线](partition-reference-route.md)仍不能当作已确认调用链。后续从实际连续代码和BL/literal推进，不扫描猜测地址。

## 重现与证据

```sh
uv run comi diag capture shell-code --out artifacts/shell-a.json
uv run comi diag capture shell-code --out artifacts/shell-b.json
uv run comi diag compare-references artifacts/shell-a.json artifacts/shell-b.json --shell --out artifacts/shell-compare.json
```

[首次](evidence/shell-first-2026-10-12.json)、[重读](evidence/shell-second-2026-10-12.json)、[逐指令分析](evidence/shell-analysis-2026-10-12.json)、[结束状态](evidence/shell-final-state-2026-10-12.json)。回归测试以实际STRD、条件跳转和修改父分支后的拒绝行为为oracle。

后续：[TLV文本到shell执行入口](shell-text-readback.md)已推进这条路线；本文345 B为当轮历史证据，当前profile扩展到777 B。
