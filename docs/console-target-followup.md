# printk当前目标：UART_0与独立字符hook

2026-10-12；C261CF0430 / FW010004。接续[printk backend](printk-backend-readback.md)和[两次运行时快照](printk-runtime-state.md)。本轮仅离线展开两个小函数和mapped descriptor/config常量；无设备I/O、RAM pointer跟随或MMIO访问。

**两次快照中的DMA context均指向名字为`UART_0`的设备，flags选择DMA缓冲分支。** 实际DMA start把该context的device/buffer/length传给一个独立发送callee；当前字符hook则是逐字符console输出形状。结合既有分派，printk正文有明确的独立UART输出链，仍未证明物理引脚输出、DMA完成或NOR read成功。

## 输入与验收

完整`artifacts/mapped-system/mapped-system.bin`再次经`inspect_image()`通过固定头、927632 B长度和正文checksum；SHA256=`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。正文sum=`b18576b5`，加字段`4e7a894a`为`ffffffff`。这验证mapped artifact，不证明physical Flash等价、整机备份或恢复。

[证据JSON](evidence/console-target-followup-2026-10-12.json)保留每段原始bytes、SHA、file offset、Capstone 5.0.6 Thumb+MCLASS反汇编、固定SDK链接、两次capture SHA和验收状态。两份既有capture分别为07:55:47、07:56:17 UTC，`ok/transport_ok/readback_complete/end_received`全部true，无pending bytes。三个独立RAM读均为：

| RAM地址 | bytes | 含义 |
|---|---|---|
| `1800e004` | `60 9f 0b 10` | DMA context device=`100b9f60` |
| `1800e01c` | `01 00` | init=1、panic=0；按已验证分派选择DMA分支 |
| `180018c8` | `c9 78 02 10` | 当前字符hook Thumb=`100278c9`，code=`100278c8` |

快照非原子；两次相同只证明两个采样窗口一致，不能替代历史fread执行时状态或保证下一次调用仍一致。

## device身份与配置边界

`100b9f60`的32 B descriptor布局沿用[已确认的设备表](boot-storage-device-readback.md)：name=`100c0e7f`，config=`100bc0f0`，API=`100bc128`。name实际7 B=`55 41 52 54 5f 30 00`，即`UART_0\0`。descriptor另含`18002b30`、`1800f824`、`18002b38`等RAM pointer，本轮均未跟随。

config pointer起28 B窗口如下；它不等同已证明的完整struct长度：

| offset | 实际值 | 有限解释 |
|---|---|---|
| `+00` | `00000000` | 未识别前缀 |
| `+04` | `40038000` | 与UART register base形状对应；未访问MMIO |
| `+08` | `100c7cdd` | mapped字符串`DMA_0\0`，6 B |
| `+0c` | bytes `01 ff 01 ff` | 与TX/RX DMA ID/channel排列对应的候选 |
| `+10` | bytes `18 18 03 00` | 与clock/reset/IRQ/flags排列对应的候选 |
| `+14` | `001e8480` | 十进制2000000；配置baud候选，非实测波特率 |
| `+18` | `100a441f` | IRQ配置函数Thumb pointer候选；未展开 |

固定SDK [acts_uart_config](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/serial/uart_acts.c#L28-L44)有上述字段顺序，**没有实际窗口的前导4 B**。因此只把后续对齐作为源码对应推断，不据此宣布实际ABI、flags位定义或物理UART配置。名字与DMA字符串是直接mapped bytes事实。

## 当前hook：console逐字符路径

`100278c8..100278ea`共34 B，末地址不含；literal `100278ec`的4 B=`38 ed 00 18`，即独立设备pointer slot=`1800ed38`。关键路径：

- 字符为LF时：读取该slot的device，取device+8的API pointer，再取API+4，`BLX`传CR。
- 所有字符：同样取API+4，`UXTB`后传原字符；最后返回原字符。

这与固定SDK [console_out / uart_poll_out](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/console/uart_console.c#L76-L95)吻合；源码名为推断，未取得原厂符号。34 B实际实现没有额外debug-server hook检查。

**该hook的device slot不是DMA context的device slot。** `1800ed38`未读取，不能把fallback也宣称为同一`UART_0`。当前init=1/panic=0按既有分派不会使用字符hook。当前Thumb pointer=`100278c9`与[启动载荷初值](printk-backend-readback.md#初始化载荷不等于当前指针)`100a42ab`不同，实证镜像初值不能代替运行时RAM。

## DMA start：已到发送调用边界

`100a1e42..100a1e8a`共72 B，对应固定SDK [dma_start_tx与内联_dma_start_tx](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/trace/printk_dma.c#L59-L89)：

1. `100a1e46`调用`100a1e30`，保存返回值；所有返回路径恢复BASEPRI并ISB。lock角色为源码对应，helper未展开。
2. `ctx+24`非零直接返回1；否则取`ctx+c`，≤0返回0，正数最多取`400`即1024 B。
3. `100a1e74`调用`100a1d58(ctx+4,ctx+20,size)`，与cbuf DMA read参数形状对应。随后重新读取`ctx+24`；为0返回0。
4. 非零时，`100a1e82 BL 100a446c`：r0=`[ctx]` device；r1=`[ctx+20]` buffer；r2=`[ctx+24]` length；随后返回1。发送callee与`uart_dma_send`对应，未展开，未检查其返回值。

如果context自快照起未变化，r0即`100b9f60`，名字`UART_0`。buffer/read_len、ring占用和driver runtime state均未读；这里的返回1表示已发送调用或已有read_len，不能解释为物理发送完成。

## 当前结论与未证实部分

既有printk分派、此次运行时flags/device、两个实际函数把正文独立输出链定位到UART_0 DMA发送调用边界；与shell→BLE回调是不同路径。这能解释为何BLE shell可见状态行而printk正文不可见，不能单凭静态链和快照认定每次缺正文的唯一原因。

下一处离线边界是`100a446c`驱动callee；当前没有展开。物理pin mux、引脚是否暴露、实际电气输出、有效波特率、DMA完成与NOR read结果仍未知。没有改hook、执行fread、访问MMIO、建立raw Flash备份或验证恢复路径。
