# LARK 芯片层：从现有调试信息恢复部分定义

2026-10-13，host-only。**恢复12组外设寄存器布局、47个IRQ常量，形成自包含C头文件；无需另一个项目即可使用这份参考定义。**
不是完整 `lark.h`、匹配CoMi的BSP或可运行固件。没有设备I/O、MMIO访问、上传或执行候选代码。

## 实际取得什么

来源是[已固定身份的两个M4 loader ELF](platform-source-followup.md#follow-up-two-elf-symboltype-inventories)，并非从M33参考板抄写。
[提取记录](evidence/lark-register-layouts-2026-10-13.json)保存原文件SHA/固定源码链接、全部选定类型、DIE/CU、声明文件/行、字段位移、整数宽度、限定符、数组长度。
编译单元使用DWARF4，行表版本3；外设typedef声明来自 `lark.h`，核心类型来自 `core_cm4.h`。
const/volatile仅恢复参考源码声明，不证明寄存器的实硅读写副作用。

| 恢复组 | 来源struct大小；字节 | 价值 |
|---|---|---|
| CMUA / CMUD | 36 / 280 | 模拟/数字时钟寄存器布局，含SPI、I2C、timer、memory时钟数组 |
| GPIO | 784 | CTL[78]、输入/输出/置位/清零数组、WIOCTL；布局不证明实体引脚数量或接线 |
| MEM | 784 | 两组cache映射/entry字段；slot0位移300/304与此前本机启动代码相符 |
| PMU | 288 | 电源门控、SVCC控制/唤醒/8Hz计数器布局；字段名不等于位操作合同 |
| RMU / RTC | 8 / 36 | 复位字、watchdog字段的存放位置 |
| SPI0 / SPI1 | 24 / 60 | 控制、数据、状态及SPI1 DDR字段 |
| SPI0CACHE / SPI1CACHE | 56 / 68 | cache控制与统计字段布局 |
| UART | 16384 | 控制/收发/状态/波特率及原reserved数组；不是UART FIFO大小 |

Flash ELF保留全部12组；SD ELF保留其中6组。另核对SCB、NVIC、IRQn，共9类跨ELF定义一致，包含每个成员宽度、位移、const/volatile和数组长度。
这两个产物可能共享原头文件；一致性检查不是两份独立硅片规格。
IRQ保留47个明确名称/数值：包含10个负异常号、37个非连续外设号，最大63；未填补空号。
来源IRQ枚举为1 B（loader采用short-enums）；生成文件只提供常量，**不重建枚举ABI typedef**。

## 入库材料与复验

- [部分头文件](../firmware/reference/lark_registers.h)：`rc_lark_`结构、`RC_LARK_`中断常量，不声明MMIO地址。
- [编译布局断言](../firmware/reference/lark_layout_assertions.c)：12个sizeof、130个offsetof，与来源DWARF逐项核对；只编译，不链接或运行。
- [提取工具](../tools/recover_lark_registers.py)：精确双文件SHA守卫；跨CU/跨ELF冲突立即失败；不支持的类型、位域、隐式padding立即失败，绝不猜reserved字段。
- [验证记录](evidence/lark-register-validation-2026-10-13.json)：重复提取、M4编译、输入损坏拒绝及输出保留检查。

从固定SDK取得两个ELF后，在仓库根运行；`out`必须不存在：

```sh
uv run tools/recover_lark_registers.py /path/to/lark_flash.elf /path/to/lark_sd.elf artifacts/lark-layout-new
just check-lark /path/to/gcc-arm-none-eabi-10.3-2021.10
```

生成目录的 `.h` / `.c` 对应已入库参考文件，`layouts.json`对应提取记录。
Ubuntu现有GNU Arm10.3.1，Cortex-M4/Thumb/soft-float、C11、`-Wall -Wextra -Werror -pedantic -fsyntax-only`通过；这证明C布局可表达，不证明外设能工作。
另由Astra用LLVM dwarfdump独立核对CMUD/GPIO数组、PMU/UART限定符、IRQ符号/空号；不把生成器自身输出作为唯一oracle。

## 仍缺什么；何时继续

没有恢复寄存器base宏、bit语义、clock/reset编号、完整IRQ向量绑定、startup/system实现、ROM总长度或本机板级配置。原头文件中未被编译器保留的内容不会因生成C文件而出现。
未把任何定义接入[自建M4镜像](minimal-firmware-image.md)，也未替换原厂驱动。CoMi固件版本/结构存在已知差异；本机代码与实读证据优先。

这些定义今后可用于对照匹配BSP、解释实际指令的寄存器位移；只有具体bring-up或平台兼容性问题需要时才补base/bit，不逐字段开启研究。
[正式DFP索引核查](platform-next-route-review.md)未取得整包；下一步仍需匹配startup/时钟/板级材料或明确加载/退出入口。
