# Console运行时状态：固定10 B两次读回

2026-10-12；C261CF0430/FW010004。依据[实际backend](printk-backend-readback.md)读固定RAM，不调用Flash API、不改hook、不切换console模式。

## 命令及前置核对

```sh
uv run comi diag capture printk-state --duration 1 --out artifacts/console-first.json
uv run comi diag capture printk-state --duration 1 --out artifacts/console-second.json
uv run comi diag inspect-printk artifacts/console-first.json
```

同一会话先核对owned serial、logsrv线程入口及代码引用、512 B已知镜像头SHA。随后逐次读取并flush三段代码/literal：`10020628`16 B、`10026ed0`4 B、`10026e6c`16 B；准确bytes必须匹配实机镜像证据，才允许固定RAM读取。任何行不完整、重复或指令改变均终止，不跟随新地址。

| RAM读取 | 实际指令依据 | 两次值 |
|---|---|---|
| `1800e004` /4 B | 分派器literal `10026ed0`；ctx首word | `60 9f 0b 10` → `100b9f60` |
| `1800e01c` /2 B | 分派器从ctx+18/+19取byte | `01 00` → init=1、panic=0 |
| `180018c8` /4 B | 字符callback `10020628`的literal/load/BX链 | `c9 78 02 10` → Thumb hook `100278c9` |

每次RAM总10 B；前置代码与头读取另计。所有mdb后help刷新、逐行确认、命令帧范围隔离；最终ACK40、F1、readback_complete均通过。两次原始帧：[第一次](evidence/printk-state-first-2026-10-12.json)、[第二次](evidence/printk-state-second-2026-10-12.json)。证据保留命令及完整frame，去掉重复的底层notifications/writes，保留原文件SHA。

## 能确认什么

两次flags均为1/0；按实际已解码分支，对应DMA缓冲路径。字符hook当前值不同于启动复制载荷`100a42ab`，证明仅查看初始化镜像不足以确定当前hook。返回指针只报告，不自动解引用或执行；映射镜像内的目标可另行离线分析。

这不是跨字段的原子快照，也不证明flags在下一条命令时仍不变；没有在同一捕获中执行fread。不能据此宣称Flash读取成功、UART物理引脚有信号、DMA无丢弃，或原始备份已完成。实际RAM字段提供当前路径证据，仍须结合设备对象/发送实现判断输出终点。

## 验证

离线测试使用实读frame oracle，检查已知字段/分支；移除实际hook读取声明时拒绝旧结果并删除旧console_state；改变已读literal时拒绝状态。现有全套测试及包构建仍需通过，实机采集与离线单元验证各自覆盖不同边界。

后续[设备描述符与发送入口分析](console-target-followup.md)已把DMA context中的`100b9f60`关联到`UART_0`。当前字符hook使用另一个尚未实读的设备global；两条路径不可直接等同。UART名称和发送代码不证明已观察到物理引脚波形。
