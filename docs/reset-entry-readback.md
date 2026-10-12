# 实机reset入口与C启动边界

2026-10-12；C261CF0430 / FW010004。只分析已保存映射镜像chunk；无设备I/O、MMIO访问、复位或执行。

**实机入口与公开Zephyr Cortex-M启动序列高度吻合。** 已验证入口、临时PSP、SRAM向量目标、FPU设置与64项IRQ优先级循环；尚未覆盖后续内存初始化/kernel入口，不能据此证明烧录、恢复或精确芯片型号。

## 输入与边界

[逐字节、SHA、完整反汇编及源文件SHA](evidence/reset-entry-analysis-2026-10-12.json)。`ImageStore`验证已知512 B头、全部已提交chunk的范围/长度/bytes SHA，再从确定存在的字节拼接。取样时正文已有249856 B，连续覆盖`10000200..1003d200`，末地址不含；导出继续增长，此处是固定分析快照。完整正文checksum尚未验证。

头SHA256=`911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5`。向量前8 B=`402b000119d80210`：初始MSP=`01002b40`，reset Thumb指针=`1002d819`，实际代码入口=`1002d818`；与ACTH头entry字段一致。代码按Capstone 5.0.6 ARM Thumb+MCLASS little-endian解码，literal pool单独保留，未当指令。

| 已读region | 长度 | 身份依据 |
|---|---:|---|
| `1002d818..1002d84c` | 52 B | 头/向量直接指定入口；BASEPRI、栈填充参数、PSP切换、直接BL |
| `1002d0c4..1002d11e` | 90 B | reset直接调用；向量/FPU初始化及四个后续直接调用 |
| `1002d800..1002d814` | 20 B | 上述callee直接调用；64次优先级byte写入循环，BX LR |
| `1002d120`、`1002d814`、`1002d84c` | 12+4+4 B | 指令PC-relative引用的literal pool |

区间末地址均不含。原厂符号表未取得；下文源码函数名是行为对照推断，地址与指令是实机字节事实。

## 入口：中断屏蔽与临时栈

| 地址 | bytes | 实际指令/常量 |
|---|---|---|
| `1002d818` | `202080f31188` | `movs r0,#20; msr basepri,r0` |
| `1002d81e..d828` | `0b484ff0aa014ff400628bf04eff` | r0取literal=`01001b40`，r1=`aa`，r2=`800`，BL `100b96c8` |
| `1002d82c..d834` | `07484ff40061401880f30988` | PSP=`01001b40+800=01002340` |
| `1002d838..d844` | `eff314800221084380f31488bff36f8f` | 保留原CONTROL其余位，OR 2后写回，ISB |
| `1002d848` | `fff73cfc` | 直接BL `1002d0c4` |
| `1002d84c` | `401b0001` | literal数据：`01001b40` |

该序列对应SDK [reset.S的BASEPRI路径与INIT_STACKS](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/core/aarch32/cortex_m/reset.S#L100-L154)：`memset`候选参数为填充2048 B的`aa`，随后用该区域顶端作为启动PSP。`100b96c8`正文未保存，填充语义来自源码匹配，未独立验证callee。

已确认常量仅说明这段代码将使用的地址；没有测量当前栈。向量初始MSP `01002b40`与临时PSP `01002340`不同，不能合并。此入口没有先清CONTROL、重设MSP或调用平台init；这不排除更早的bootloader已做相关操作，也不证明直接上电即进入此函数。

## C准备：向量重定位与FPU

`1002d0c4`准备r0=`01001a00`、r1=`10000200`、r2=`140`，在`1002d0d0` BL `100b9652`；随后在`1002d0d6`把`01001a00`写到`e000ed08`，DSB/ISB。三个literal来自`1002d120`的12 B：`001a00010002001000ed00e0`，分别为目标、源、SCB base=`e000ed00`。

这对应SDK [SRAM向量重定位](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/core/aarch32/prep_c.c#L45-L64)：先复制320 B向量，再把VTOR指向SRAM。`memcpy`候选`100b9652`正文未保存，复制语义为推断；实际参数与后续VTOR store已确定。这里解析的是代码中的寄存器访问，未访问这些MMIO地址。

独立核对保存的前320 B向量：16个core slot后，64个external slot均为Thumb指针`1002d2a9`。320 B复制长度与这80项吻合，也与下述64项优先级循环吻合；未分析共享handler正文，不据此推断物理IRQ数量或芯片身份。

后续已保存指令确定：

- `1002d0e0..d0f4`：CPACR `e000ed88`清`00f00000`，再OR `00500000`；对应CP10/11 privileged access。
- `1002d0f8..d0fc`：写`c0000000`到FPCCR `e000ef34`；对应automatic/lazy preservation。
- `1002d100..d10a`：DSB、ISB，FPSCR置0。

操作顺序、位值与SDK [FPU准备](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/core/aarch32/prep_c.c#L88-L175)吻合。不能由此唯一还原所有CONFIG值或确定CPU精确型号。

## 直接调用边界

| call site → target | 已读body | SDK对照；结论强度 |
|---|---|---|
| `1002d10e → 1009aa24` | 否 | `z_bss_zero`候选，仅调用顺序匹配 |
| `1002d112 → 1009c1d0` | 否 | `z_data_copy`候选，仅调用顺序匹配 |
| `1002d116 → 1002d800` | 是 | `z_arm_interrupt_init`候选，完整循环行为匹配 |
| `1002d11a → 1009aa54` | 否 | `z_cstart`候选，仅最终调用位置匹配 |

顺序来自SDK [z_arm_prep_c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/core/aarch32/prep_c.c#L188-L202)。没有反汇编未保存目标，也没有确定.bss/.data范围、复制来源、kernel/main流程。

`1002d800`从literal `1002d814`的`00e100e0`取得NVIC base=`e000e100`。r3从0开始；每次向`base+300+旧r3`写byte `20`，r3递增至`40`，`BNE 1002d806`回环，最后`BX LR`。故静态效果为向`e000e400..e000e43f`写64个优先级byte，与SDK [IRQ初始化循环](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/core/aarch32/cortex_m/irq_init.c#L27-L34)对应；64是该循环上限，不证明硅片全部IRQ的实际实现数量。literal的两个halfword不是branch指令。

## 能支持的后续

已把“类似Actions SDK”推进为三个实机启动函数的具体对应，得到可复核RAM与向量常量。后续可在顺序导出覆盖后沿上述直接调用分析内存初始化与kernel入口。当前证据不能回答启动介质布局、ROM下载入口、签名校验、刷机接口或恢复路径；公开reset源码[明确允许硬件reset和chainload](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/core/aarch32/cortex_m/reset.S#L35-L63)，当前artifact无法区分实际启动路线。

这是部分mapped-system镜像分析，尚非raw Flash备份；未写入固件、未验证可独立恢复。
