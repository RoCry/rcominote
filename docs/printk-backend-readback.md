# 实机printk backend：DMA分派与动态字符hook

2026-10-12；C261CF0430 / FW010004。接续[fread实际输出分流](raw-read-handler-followup.md)，仅离线分析完整mapped-system镜像中的五个小函数；无设备I/O、MMIO访问、函数执行或修改。

**fread正文确实进入独立的printk分派：DMA缓冲路径或动态字符hook路径。** 它们与已确认的shell→BLE日志回调不是同一入口。实际指令强力支持既有输出路由解释，但缺当前RAM flags/hook，仍不能宣布正文一定去了某个UART，或把每次丢正文归因于DMA满。

## 完整输入验收

`artifacts/mapped-system/mapped-system.bin`经`inspect_image()`重新验证：927632 B、固定头SHA、正文u32 additive checksum全部通过。

- 完整SHA256：`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。
- 正文sum=`b18576b5`，加存储字段`4e7a894a`后为`ffffffff`。
- [每段bytes、SHA、file offset、literal与完整反汇编](evidence/printk-backend-analysis-2026-10-12.json)。Capstone 5.0.6，ARM Thumb+MCLASS little-endian；每段代码完整解码，literal单列。

这证明完整mapped-system artifact的内部校验，不证明physical Flash等价、整机备份或恢复。

| 已分析函数 | 代码长度 | 实际作用 |
|---|---:|---|
| `10026e6c..10026ece` | 98 B | printk分派，检查init/panic，选择两条输出链 |
| `10020644..1002065c` | 24 B | fallback：准备字符callback/context，调用格式引擎 |
| `10020628..10020634` | 12 B | fallback字符callback：计数后跳转RAM hook |
| `100a1f56..100a1f8a` | 52 B | DMA格式化callback：62 B阈值flush、LF前插CR |
| `10026d4c..10026daa` | 94 B | DMA cbuf writer：空余量判断、写入或计drop |

末地址均不含。源码名称由完整小函数行为与固定SDK对应，未取得原厂符号；没有展开格式引擎、UART/DMA driver、模式切换或init函数。

## 实际分派与两条链

`10026ed0`的literal=`1800e004`，为独立context；`+18`即`1800e01c`为init候选byte，`+19`即`1800e01d`为panic候选byte。分支、字段和后续行为与SDK [printk_dma.c vprintk](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/trace/printk_dma.c#L393-L425)对应：

| 静态条件 | 已确定控制流 |
|---|---|
| init=0 | `10026e7a` BL `10020644(fmt,va_list)` |
| init≠0、panic≠0 | 调`10026e30`、以`186a0`传`1009c4dc`、r0=0调用`10026c70`、清init，再转fallback；drain/wait/切CPU为源码对应，helper未展开 |
| init≠0、panic=0 | callback=`100a1f57`、临时count=0、fmt/va_list→`100a038e`；剩余bytes经`10026d4c`flush；最后调用`100a1e42(context)` |

实际98 B入口没有公开源码前置的`soc_in_sleep_mode()`调用；不能称逐字节同一实现，也不能推广为全固件没有sleep处理。

fallback `10020644`准备callback=`10020629`、count context、fmt、va_list调用同一`100a038e`，对应`cbvprintf`参数形状。实际callback在`10020628`递增count，随后：

`1002062e 014b`取literal `180018c8` → `10020630 1b68`读取该RAM word → `10020632 1847 BX r3`。字符仍在r0。故**最终目标是运行时RAM函数指针，不是镜像代码中一个固定BL目标**。这与SDK [printk字符hook](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/lib/os/printk.c#L51-L78)对应。

DMA callback `100a1f56`在count≥62时调用`10026d4c`并清count；遇LF先追加CR，再追加原字符，最后返回0。与SDK [buf_char_out](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/trace/printk_dma.c#L226-L251)吻合。

## DMA缓冲：有实际drop分支，未测运行时占用

`10026d4c`先取锁，按`context[10]−context[c]`计算space候选；`10026d60 CMP r4,r3`、`10026d64 BLO 10026d96`仅在**length<space**时接受。接受路径以context+4、buffer、length调用`100a1da6`，恢复BASEPRI、ISB，返回length。

space≤length时，向context+1c累加请求长度，通常返回0；累计>65536还检查`100a449a(context[0])`及context+24，可能调`10026d24`后重试。与SDK [cbuf_output的FULL_LOST分支](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/trace/printk_dma.c#L179-L223)逐项对应。

这些是明确的静态丢弃条件，不是这次fread运行时命中它们的证据。`1800e004`这套cbuf与已分析的[BLE logsrv](log-buffer-wrap.md)不同；后者`1800a9b0`是8×512B slot数组base，8×504B正文由saver=`1000bcec`管理，不能把数组base当context。两种drop机制不可混淆。

## 初始化载荷不等于当前指针

根据[启动复制](startup-memory-readback.md)已确认的source=`100de7c8`、destination=`180012c8`、length=`29d8`，RAM hook slot `180018c8`相对offset=`600`，对应镜像载荷`100dedc8`。该4 B=`ab420a10`，初始Thumb pointer=`100a42ab`，code=`100a42aa`。本轮未展开该target，不能给它强加UART函数名。

这仅恢复**启动复制的初值**。SDK允许[安装字符hook](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/lib/os/printk.c#L62-L65)，镜像初值不能代替当前RAM读取。类似地，context=`1800e004`落在已有清零调用参数`[18003ca0,18045250)`内；正常执行该初始化时初始为零，后续DMA init/switch可改变flags、device和ring。公开[DMA初始化](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/trace/printk_dma.c#L562-L593)绑定console device并配置DMA，但本轮未验证实际init函数或当前结果。

## 当前结论与下一处缺口

这五个函数已确定printk使用独立context、动态hook/DMA cbuf，以及明确的缓冲丢弃门控；没有看到调用shell输出注册或已知BLE saver/sender。与固定Actions UART/DMA实现高度吻合，说明只注册shell BLE callback不足以保证取得fread正文。尚未独立观察物理UART输出，也未排除运行时hook被其他代码改写。

最小真实缺口是当前RAM：`1800e01c/1d`两flags、`1800e004`的device pointer、`180018c8`的hook word。它们决定实际走哪条链；本轮没有读取。另一条纯离线后续是限定展开DMA start `100a1e42`和其初始化引用，确认device/发送callee；当前止于这两个边界，不扩大分析。

下轮固定profile建议仅10 B；先核对设备身份、已知头和下面引用指令，再读取固定范围，地址变化即拒绝旧profile：

| RAM范围 | 字节数 | 来源/目的 |
|---|---:|---|
| `1800e004..1800e008` | 4 | `10026ed0` literal给context，`10026d7c` LDR `[ctx]`；取得device pointer候选 |
| `1800e01c..1800e01e` | 2 | `10026e70`、`10026e82` LDRB `[ctx,#18/#19]`；选择init/panic分支 |
| `180018c8..180018cc` | 4 | `10020634` literal及`10020630`间接load；取得当前字符hook Thumb pointer |

这里只建议快照，不自动跟随任何返回pointer；RAM样本非原子，不等同历史fread执行时状态。

没有证明NOR read成功、发现可直接启用的BLE重定向开关、建立raw Flash备份或恢复路径。
