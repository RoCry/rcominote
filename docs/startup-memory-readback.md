# 实机启动内存范围与kernel入口

2026-10-12；C261CF0430 / FW010004。接续[reset入口](reset-entry-readback.md)，离线分析三个直接callee；无设备I/O、MMIO访问、复位或执行。

**已确定两段清零调用参数、三段复制调用参数，以及紧接着的kernel启动调用顺序。** 复制源连续到已知映射镜像末端；RAM目标与已知向量/栈区域可形成具体地址关系。原厂符号和link map仍未取得；不能把这些地址直接命名为物理RAM型号或可恢复Flash分区。

## 输入与代码身份

[准确bytes、SHA、literal pool与完整反汇编](evidence/startup-memory-analysis-2026-10-12.json)。`ImageStore`验证固定头SHA、已提交chunk范围/长度/bytes SHA；每个解码字节必须已保存。Capstone 5.0.6，ARM Thumb+MCLASS little-endian；literal pool不作代码解码。

固定分析快照：正文724992 B，连续覆盖`10000200..100b1200`，末地址不含。导出继续增长；本报告不借用快照以后的字节，也不声称已完成正文checksum。头SHA仍为`911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5`。

| 来源/已读函数 | 代码长度 | 实际链接 |
|---|---:|---|
| `1002d10e..1002d11e` | 16 B片段 | prep依次BL `1009aa24`、`1009c1d0`、已知IRQ init `1002d800`、`1009aa54` |
| `1009aa24..1009aa42` | 30 B | 两次调用同一`100b96c8`；第二次恢复LR后tail call |
| `1009c1d0..1009c1f6` | 38 B | 三次调用同一`100b9652`；第三次恢复LR后tail call |
| `1009aa54..1009ab0a` | 182 B | MSP/异常寄存器设置、十次直接调用；无本地return |

末地址均不含；三段函数均为直线控制流，未展开callee或间接driver init。填充callee `100b96c8`、复制callee `100b9652`在此快照未覆盖；`memset/memcpy`语义由先前栈/向量调用和固定SDK行为共同识别，尚未独立反汇编其实现。下列**寄存器参数、范围运算、跳转目标已确认**；并非观测到启动执行或RAM被修改。

## 两段清零调用

`1009aa44`的16 B literal：`a03c0018505204185052041850600418`。函数分别取起止地址，执行`r2=end−r0`，r1置0。

| call site | r0目标范围，末地址不含 | r1 | r2长度 | 目标 |
|---|---|---:|---:|---|
| `1009aa2e` BL | `[18003ca0,18045250)` | 0 | `415b0` =267696 B | `100b96c8` |
| `1009aa3e` B.W | `[18045250,18046050)` | 0 | `e00` =3584 B | `100b96c8` |

两段相邻，无重叠。与SDK [z_bss_zero](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/kernel/init.c#L112-L152)的多区域清零一致。该源码允许PSRAM/SRAM、sensor及其他区域组合；没有原厂link map，不能只凭两次调用唯一确定各自section名称或物理内存类型。

## 三段复制调用

literal位于`1009c1f8..1009c21c`，36 B，准确值见JSON。第一次r2由两个目标地址相减，后两次直接取长度literal；r0/r1/r2符合复制参数顺序。

| 调用顺序/call site | r1源范围 | r0目标范围 | r2长度 |
|---|---|---|---:|
| 1 / `1009c1da` BL | `[100de7c8,100e11a0)` | `[180012c8,18003ca0)` | `29d8` =10712 B |
| 2 / `1009c1e4` BL | `[100dd500,100de7c8)` | `[18000000,180012c8)` | `12c8` =4808 B |
| 3 / `1009c1f2` B.W | `[100e11a0,100e2790)` | `[01000400,010019f0)` | `15f0` =5616 B |

三个调用均指向`100b9652`。顺序与SDK [z_data_copy](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/kernel/xip.c#L26-L39)的data→ramfunc→sleep-data对应；这些section名称是源码顺序推断，不是恢复出的原厂符号。实际复制源payload在该快照尚未保存，未检查内容。

按地址重排，源区连续为`[100dd500,100e2790)`，共21136 B；末端正好等于固定头所界定的mapped-body end。目标`[18000000,18003ca0)`连续，随后接上两段清零参数直到`18046050`。这是实机启动代码的内存初始化布局证据，不能把mapped源地址当作已证明的物理Flash地址。

另一组已知区间关系：

| 范围 | 依据 |
|---|---|
| `[01000400,010019f0)` | 本轮第三段复制目标 |
| `[010019f0,01001a00)` | 16 B间隙，未确定用途 |
| `[01001a00,01001b40)` | 先前320 B向量复制目标 |
| `[01001b40,01002340)` | 先前2048 B、`aa`栈填充调用目标 |

仅记录地址及邻接；不为间隙或未记录区域发明名称，也未据此确定main stack边界。

## kernel入口的实际顺序

`1009aa5a` bytes=`87f30888`：`MSR MSP,r7`；r7从`1009ab0c`的`40230001`取得`01002340`。这解析了先前MSP/PSP的不同阶段：向量初始MSP为`01002b40`；reset把临时PSP设为`01002340`；此处随后把MSP也设为`01002340`。没有读当前CPU寄存器。

同一函数以SCB base=`e000ed00`执行CCR OR `200`、PendSV priority byte=`e0`、SVC/fault/debug/SysTick priority byte清零、SHCSR OR `70000`，随后CFSR/HFSR各写`ffffffff`。这些静态指令与SDK [arch_kernel_init](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/include/aarch32/kernel_arch_func.h#L39-L55)、[stack setup](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/include/aarch32/cortex_m/stack.h#L41-L64)、[exception setup/clear](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/arch/arm/include/aarch32/cortex_m/exc.h#L99-L183)吻合；没有实际访问MMIO。

| call site → target | 已确认参数或位置 | 源码名称候选；未在本报告展开body |
|---|---|---|
| `1009aa8a → 1002d7dc` | 异常设置后 | `z_arm_fault_init` |
| `1009aa8e → 1002cf38` | 紧接上一调用 | `z_arm_cpu_idle_init` |
| `1009aaaa → 100b8908` | dummy-thread形状的栈/全局写入后 | `z_device_state_init`；目标尚未覆盖 |
| `1009aab0 → 1009a7ac` | r0=0 | `z_sys_init_run_level(PRE_KERNEL_1)` |
| `1009aab8 → 1009a7ac` | r0=1 | `z_sys_init_run_level(PRE_KERNEL_2)` |
| `1009aabc → 1009befc` | 两次level调用后 | `z_sched_init` |
| `1009aadc → 1009ae70` | r0=`1800a588`、r1=`01002340`、r2=`800`、r3=`1009a9f1` | `z_setup_new_thread` |
| `1009aaec → 100b8ff2` | r0=`1800a588` | `z_ready_thread`；目标尚未覆盖 |
| `1009aaf2 → 1009a984` | r0=0 | `init_idle_thread(0)` |
| `1009ab06 → 1002d260` | r0=`1800a588`、r1=setup返回值、r2=`1009a9f1` | `arch_switch_to_main_thread` |

实际调用地址/参数已确认；候选名称来自SDK [z_cstart](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/kernel/init.c#L450-L490)、[prepare/switch](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/kernel/init.c#L322-L375)及[init level定义](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/init.h#L24-L25)的组合对应。并未证明每个helper完整语义，未读取init entry表或展开driver初始化。`1009a9f1`是带Thumb位的入口参数，不能直接当作已定位的应用main。

## 结论边界

先前仅按prep调用顺序猜测的三个名字，现已获得各自完整小函数和具体内存参数支持；原厂符号身份仍为高可信行为匹配。未验证libc实现、加载payload、实际RAM内容、线程切换或应用main。没有新增精确SoC/板型、启动介质、签名、烧录或恢复能力证明；仍是partial mapped-system分析，非可恢复的raw Flash备份。
