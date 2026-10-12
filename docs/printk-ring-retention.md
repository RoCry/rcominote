# printk静态ring：DMA消费后正文保留

2026-10-12，FW010004。完整mapped-system SHA/头/正文checksum重验通过。[实际指令证据](evidence/printk-ring-retention-2026-10-12.json)、[Unicorn结果](evidence/printk-ring-emulation-2026-10-12.json)。未设备I/O、修改hook、调用Flash或执行USB模式切换。

**实际printk使用4096 B静态RAM ring；cbuf DMA消费只更新索引与占用，不擦除正文。** 这提出一条可以验证的新出口：通过既有shell memory-read取得ring中的printk文本。它不同于[fread返回前释放的heap buffer](raw-read-handler-followup.md)，但尚未证明实机采样能赶在后台日志覆盖前完成，不能视为已有raw NOR备份。

## 实际初始化与布局

完整`10026cac..10026d00`与固定SDK [printk_dma_init](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/trace/printk_dma.c#L562-L593)对应：绑定UART名字，存context首word；成功分支以context+4、literal buffer、容量调用cbuf初始化，然后配置DMA。失败分支可提前返回；静态代码不能替代当前初始化成功的实测。

- context=`1800e004`，cbuf=`1800e008`。
- `10026cd4`加载literal `10026d14`，其word=`1803ee09`。
- `10026cd6`明确r2=`1000`；`10026cdc BL 100a1e14`。
- 因此buffer范围为`[1803ee09,1803fe09)`，4096 B；不要求起点4 B对齐。

完整cbuf init `100a1e14..100a1e30`写以下五字段。实际字段布局与固定SDK [cbuf](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/trace/cbuf.c)一致：

| cbuf offset | context offset / RAM | 含义 |
|---|---|---|
| +0 | +4 / `1800e008` | read index |
| +4 | +8 / `1800e00c` | write index |
| +8 | +c / `1800e010` | used bytes |
| +c | +10 / `1800e014` | capacity=`1000` |
| +10 | +14 / `1800e018` | buffer=`1803ee09` |

这里保存的是实际代码中的初始参数；当前RAM值仍需重新读取核对，不能直接跟随未经验证的运行时pointer。旧[printk状态快照](console-target-followup.md)只证明当时init=1、panic=0与UART_0，未读取cbuf字段或正文。

## 写入、发送与消费

- 完整write `100a1da6..100a1e14`检查capacity/used，复制到buffer+write index；跨尾时拆成两次复制。已占用空间不够则返回0。
- 完整DMA read `100a1d58..100a1d8a`检查used，read index达到capacity时先归零；输出连续段pointer/length。本函数返回请求长度，**不一定等于连续段长度**，消费者须使用DMA结构+4。
- 完整consume `100a1d8a..100a1da6`只增加read index、减少used，未擦除payload。
- 完整DMA stop `100a1e8a..100a1ec2`核对source范围，调用consume，清context+24的DMA length，再调用driver stop。UART/DMA底层未完整审计或模拟；不能把这一层无擦除推成任何时刻内容必然保留。

ring是循环复用存储，used=0不意味着payload为零，也不证明残留属于最近一次命令。背景printk、下一次写入和环绕都可能覆盖内容。当前脚本不模拟并发、ISR、UART DMA硬件或BLE采样延迟。

## 离线验证与独立oracle

```sh
uv run tools/verify_printk_ring.py artifacts/mapped-system/mapped-system.bin
```

脚本SHA绑定完整原镜像；只执行实际cbuf init/write/DMA read/consume及BASEPRI lock/unlock，拦截libc memcpy。每次函数调用最多1000条指令，未知执行地址立即失败。使用实际4096 B容量和buffer地址；初始payload全部`?`，输入为手工六字节`ABCDEF`。

| 手工fixture | 实际结果 |
|---|---|
| 空ring、索引0，写6 B | write index6、used6；DMA段`ABCDEF`，长6；consume后read6、used0，正文逐字节未变 |
| 空ring、read/write4094，写6 B | 尾部`AB`、头部`CDEF`；write4、used6 |
| 上述跨尾ring，先请求6 B | DMA段只有`AB`、长2，但返回6；consume后read4096、used4 |
| 随后请求4 B | read归零，DMA段`CDEF`；consume后read4、used0；整个4096 B正文仍逐字节未变 |

普通序列103条、跨尾序列155条指令。expected索引、分段长度与字符串均为手算值，未从被测代码公式生成。该测试证明原始ARM cbuf函数行为；没有证明真实printk正文已进入ring、NOR读取成功、或BLE回读一致性。

后续[实机RAM读取](printk-ring-capture.md)已成功，但读命令自身会覆盖ring；下列边界仍适用于可靠正文导出。

## 下一步验收边界

固定RAM profile可先读20 B cbuf字段及init/panic flags，严格核对已知buffer/capacity与合法索引范围；read/write可暂等于4096，不能误判为越界。随后读有界ring片段，保留前后元数据，拒绝把非原子或被覆盖的采样拼成完整结果。新profile应绑定本机已验证入口和初始化literal，不开放任意地址读取。

先以短小可识别printk文本验证正文出口，再考虑固定NOR sector。`fread`512 B的hex文本约1920 B，小于ring容量；这只是容量预算，并未测量后台覆盖速度。未来任何导出仍需完整长度、偏移归属、重复一致性与独立内容校验；ACK、used变化、旧残留或正确魔数均不能单独验收。DSP/原始NOR与独立恢复仍是未完成目标。
