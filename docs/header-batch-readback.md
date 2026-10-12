# 单命令多行读取：64/256/512 B实测

2026-10-12，C261CF0430 / FW010004。目标是为有界映射镜像导出验证传输单元。仅重读已独立确认的ACTH头部，无新增内存覆盖；累计已核对范围仍7455不同映射字节。未读取新正文、Flash、外设寄存器，未复位或刷写。

## 实测

| 单条mdb请求 | 数据行 | 次数 | 结果 |
|---|---|---|---|
| `dbg mdb 10000000 40` | 4 | 1 | 与此前4个独立16 B行一致 |
| `dbg mdb 10000000 100` | 16 | 1 | 与此前16个独立行一致 |
| `dbg mdb 10000000 200` | 32 | 2 | 两次一致，匹配既有512 B头部及其校验 |

数量参数按hex；最后200即512 B。每轮先检查当前logsrv入口并读固定base引用，随后只发一个header范围请求和help刷新输出，最终STOP并等F1。512 B SHA256=`911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5`。

通知时域约9.7/10.8/11.7/10.8秒，包含发现、握手、固定检查、help和末尾等待，**不是payload吞吐率**。不能据此推算927 KB导出耗时或连续块可靠性。

## CLI与完整性

```sh
uv run comi diag capture header-batch --out artifacts/header-batch.json
```

当前固定profile重读512 B，无地址/长度自由输入；只允许既定设备。`read_range`拆成16 B输出行，要求每个预期地址恰好一行、字节数完整；尾行按余数验证。缺行/重复/截断立即判失败，不能靠ACK/F1掩盖。512 B头部还必须匹配已独立验证的FW010004 SHA256。

读取验证从log_capture提取为独立模块，保持采集文件小于500行；既有固定行验证不变。85项测试、24项子测试及wheel/sdist通过。新测试以实际多行capture对照旧单行证据，并模拟已知风险：ACK齐全但丢尾行、重复、截断、内容变更。

## 下一步

- 连续几个512 B正文块：每块help后等待其完整行，再发下一块；测真实payload耗时/丢包。
- 把数据和范围/hash落盘，断点恢复前重验身份、头部和边界；不得用缺失块补零。
- 完整声明正文到齐后才计算image checksum，并与头部4e7a894a对照。

当前尚未实现这些导出能力。即使映射正文导出成功，也不覆盖其他分区、不证明与原始Flash字节等价。[镜像头边界](image-header-readback.md)。

## 证据

[64 B](evidence/header-batch64-first-2026-10-12.json)、[256 B](evidence/header-batch256-first-2026-10-12.json)、[512 B首次](evidence/header-batch512-first-2026-10-12.json)、[512 B重读](evidence/header-batch512-second-2026-10-12.json)、[对照与hash](evidence/header-batch-analysis-2026-10-12.json)、[结束状态](evidence/header-batch-final-state-2026-10-12.json)。结束idle/FW010004。
