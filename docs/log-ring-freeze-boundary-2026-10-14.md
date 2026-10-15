# Printk ring：CPU/DMA 切换不是稳定快照锁

2026-10-14；固定 CoMi FW010004 镜像离线审计。**不执行 `dbg dbgsw cpu` / `dma`：实际代码缺少有界等待、可靠恢复结果及独占冻结合同。** 该结论不等于设备已经发生挂死；本轮无设备操作、无模式切换测试。

输入为已保存完整 system 镜像，927632 B，SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。[静态证据](evidence/log-ring-freeze-boundary-2026-10-14.json)仅含必要镜像字节、地址、摘要及 Thumb 反汇编；无运行日志。函数名为分析标签，地址与指令是直接证据。

## 为什么需要冻结

拟议读取 `1803ee09..1803fe09` 的 4096 B printk ring：拆为八个 512 B SD 文件，再分别完整下载。八片长度、顺序、SHA 均正确，仍只构成不同时刻的 RAM 组合；不能证明曾存在对应的完整快照。每条命令及后台输出也可能继续改变 ring。

现有 [`sector_from_ring`](../src/rcominote/experiments/sd_bridge.py) 验收 status、32 条连续数据行、producer echo、后置 dump nonce。后置 nonce 不能单独排除旧圈正文与新尾部组合。非原子 baseline 的“无旧行”也不能证明 producer 前某一时刻整个 ring 无旧行。与已知 boot0 oracle 相等证明提取字节正确，不能自行证明来自本轮 fread。

## 实际调用与等待

| 实际地址 | 指令事实 | 对合同的影响 |
|---|---|---|
| `10024c40..10024c88` | handler 要求 argc=2；与字符串 `cpu` 比较。相等传 0，其余字符串传 1 给 `10026f10`；返回不检查切换结果 | 不是严格 `cpu/dma` 双值验证；ACK 不能证明切换成功 |
| `10026f34..10026f4c` | CPU 分支先打印，再调 `10026e30`，等待参数 1000，调用低层 `10026c70(0)`，最后清 `1800e01c` 的 init byte | 打印、排空、硬件切换均发生在 init 清零之前 |
| `100a1e30..100a1e40` | 保存 BASEPRI，设 `BASEPRI_MAX=0x20` | 排空期间提高中断屏蔽阈值，不应表述为屏蔽所有中断 |
| `10026e3a..10026e42` | 反复调用 DMA 完成检查 `100a449a`，为零则回跳；无计数器或超时 | DMA 不完成时此循环无软件时间上界 |
| `10026e54..10026e5c` | 继续启动/排空，返回非零再回跳；BASEPRI 至 `10026e5e` 才恢复 | 后续固定等待不能给前面的循环补上时间界限 |
| `1002fbe2..1002fbee` | FIFO 切换反复调用 device API +`30`，返回零继续；无超时 | 切换还有另一条不受主机超时约束的等待 |

上层 `10026f10` 实际只先检查 UART device 非空；没有引入公开 SDK 中 `soc_in_sleep_mode()` 的额外门控。不能用相似源码替代本机分支。

## CPU 输出与恢复

CPU fallback `10020628` 间接调用 RAM hook `180018c8`。镜像启动初值为 `100a42ab`，正文 `100a42aa` 调 `1002dca8` 输出字符；换行前另输出 CR。`1002dcaa..1002dcae` 持续读取 UART status bit 6，等待退出后才向 UART +8 写字符，**无超时**。该 hook 初值不代表当前 live RAM 指针；本轮没有读取 live hook，也未证明 UART clock/FIFO 在整个 CPU 模式期间持续可用。

DMA 恢复 `10026f1c..10026f30` 清 staging count，打印消息，调用 `10026c70(1)`，随后无条件设置 `init=1`。低层可能返回 -1，上层仍设置该标志。更下层配置调用 `1002fd00` 的返回值也未在该返回路径检查。因此，恢复 ACK、`init=1` 或单次前后 info 相同均不足以证明 DMA 已正常恢复。

主机 Actions 超时或发送 STOP 不能证明能解除这些目标端轮询，更不能保证阻塞中的 shell 仍能处理恢复命令。故本轮不安排“先小试一次再恢复”的实机实验。

## 保留正文不等于停止所有写入

- 已审计切换函数不直接清零 4096 B body，也不重新调用 ring 初始化；`100a1e14` 的初始化修改描述符而非 memset 正文。这支持“可能保留正文”，不是跨全部间接硬件路径的完整保留证明。
- 排空可以调用 drop-report helper；`100a1f2c..100a1f3c` 将 8 B 标记送入 `100a1da6`。切换过程自身可能追加内容。
- 格式化入口 `10026e6c`、raw 入口 `10026edc`、stdout 入口 `10026db4` 检查 init。init=0 时，前两者走 CPU fallback，stdout 返回；这是正常新调用的门控。
- **实际直接 writer `10026d4c` 不检查 init**；剩余空间足够即调用 `100a1da6` 写 ring。已通过入口检查、随后被抢占的调用及在途 callback 是否全部结束，没有已验证的静止屏障。这里只指出未证明，不宣称竞态已经发生。
- 初始记录 `180019c8` 含 `100a1f91` / `100a1f8b`，初始化路径 `10026cf6..10026cfa` 注册该记录。对应 wrapper 分别传 0/1 调 `10026f10`，与 SDK PM entry/exit 一致。退出回调可重新启用 DMA；手动 CPU 命令没有独占冻结租约。具体 PM 事件是否会在拟议读取期间发生，尚未测定。

因此不能从一次 `init=0` 推出“后续八片来自稳定 body”，也不能从恢复时 `init=1` 推出“所有资源恢复”。CPU/DMA 切换暂不能跨越分段 ring 的新鲜度与完整性门槛。重新考虑需先建立有效、可恢复的硬件等待条件，以及覆盖整个采样期间的 writer 静止与自动重启控制；不以更多同类字节比较替代这些合同。

## 复验与边界

```sh
uv run tools/verify_log_ring_freeze.py
```

脚本校验固定证据 SHA、完整镜像 SHA、每段字节与摘要、全部所列 Thumb 反汇编及关键回跳/恢复指令。它不执行目标代码，不读取设备，也不把静态轮询提升为实际挂死结论。

公开源码仅用于解释算法：[固定 SDK `printk_dma.c`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/trace/printk_dma.c)，commit `26f51e584940d5b141cd1d09d2629d69b595f579`；排空/切换约 134–175、502–527 行，PM callback 530–559 行。最终判断以本机指令为准。关联：[printk backend](printk-backend-readback.md)、[另一套 BLE logsrv ring](log-buffer-wrap.md)；勿将 printk body `1803ee09` 与 logsrv slot 数组 `1800a9b0` 混同。
