# 启动存储调查：实机device表与Flash对象

2026-10-12；C261CF0430/FW010004。接续[SD状态](card-state-readback.md)。仅经现有日志通道读固定代码/数据；没有调用device binding、Flash API、初始化或MMIO。

## 从实际调用到表边界

SD disk ioctl的`10025a62` BL目标`1009a81c`。已读后者88 B代码、12 B literal：空名字返回NULL，先比较名字指针，失败再比较字符串；每条路径均先调用`100b890a`检测ready。实际两处迭代为`adds r4,#0x20`，故device条目步长32，不能从其他SDK配置猜成24。

literal `1009a874`为end=`100ba320`，`1009a878`为start=`100b9f40`，共31项。读取各项name指针，再按当次指针核对读取最多16 B字符串；第一个NUL后内容不归入名字。已读过的`sd`与`MMC_1`前缀复用既有profile，避免重复输出同地址破坏行唯一性。

实机函数与固定[device_get_binding](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/kernel/device.c#L102-L134)的两阶段查找对应；[device结构](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/device.h#L370-L397)的PM尾部可解释32 B，但具体编译开关仍不是独立读出的配置。

## 31个设备名字

按地址顺序：`UART_1 UART_0 WIO GPIOC GPIOB GPIOA spi_flash sys_clock hrtimer PMUDAC_0 sim_flash keyearphone DMA_0 I2C_0 MMC_1 DAC_0 ADC_0 sd BTC audio_out de_acts lcdc_acts audio_in DSP onoffkey batadc RTC_0 ALARM8HZ_0 lcd_panel SPI_2 CDC_ACM`。

名字表不是硬件BOM，也不是ready设备列表。`CDC_ACM`只证明原厂镜像注册了此对象，不能否定既往普通模式USB不枚举的实测，更不能证明ROM恢复接口。`lcd_panel`等名字也不能给出具体屏幕控制器型号。

## Flash对象前缀

| 对象 | config | API | state | data |
|---|---|---|---|---|
| `spi_flash` @ `100ba000` | `100bc258` | `18001aa4` | `18002e70` | `18001a7c` |
| `sim_flash` @ `100ba080` | 0 | `100bc268` | `18002ed8` | 0 |

`sim_flash`的NULL config/data与公开[RAM模拟Flash注册](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/flash_sim_acts.c#L441-L451)相符；名称和空指针不足以证明其实机read实现，仍需实际callback代码。

`spi_flash`与SD后端是不同device实例；仅凭注册名不能宣称其容量、厂商或正在承载启动固件。下一层由实读config/API/data指针确定，避免盲扫或读取猜测的启动头。

## 实读配置与就绪状态

config16 B为`00200000 00100000 00000002 00100000`。API第6指针为`100a4a07`；实际callback10 B从device+4取config，存入layout输出，再将layout数量设为1后返回。这与[page-layout回调](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spi_flash_acts.c#L532-L539)一致：8192页×4096 B=32 MiB。config后两word也与SDK的chip_size=32 MiB/page_size=4096一致，但**这是配置容量，不是JEDEC ID或物理容量检测**。

API第5指针`10031441`的实际函数只有4 B（LDR literal、BX LR）；紧随4 B literal为`100bc250`，不能解码成指令。该地址实读`00100000 ff000000`，对应公开参数的write_block_size=4096、erase_value=ff。[配置和注册](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spi_flash_acts.c#L624-L671)、[参数](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spi_flash_acts.c#L593-L603)。

实机ready helper `100b890a..100b891d`：非NULL device取state半字、保留低9位、与`0x100`做减法/进位计算，只有等于`0x100`时返回1。Flash state实读`0001`（LE=0x100），支持初始化成功。未调用该helper；这是对读取到的状态按实际指令离线求值。

data首16 B为`00800240 05000000 0000040b 00000000`；首word常量`40028000`与固定[SDK SPI0_REG_BASE](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_regs.h#L44)一致。结合结构/回调，支持独立SPI NOR后端；仍未读MMIO、chip ID或启动分区。

## RAM中的实际Flash read wrapper

API首指针`1800006d`。`1800006c..180000ab`共64 B代码，从device+10取得data，将请求拆成最大`0x8000`字节块，经函数表+14间接调用，再推进offset/buffer并减少remaining。结束直接返回最近结果；不等同于已执行读取。相邻literal `180000ac`实读`100bc294`，是下一轮可追踪的函数表地址。

该结构与[公开NOR read wrapper](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spi_flash_acts.c#L78-L112)对应，代码位于映射RAM。仍未知底层函数表是否ROM或扩展实现；没有调用它，也不能据wrapper形式保证下层读无初始化/模式切换副作用。当前工具保持固定mdb读取，无新Flash操作入口。

## 分区表仍未找到

device数组不包含`SYS_INIT`函数指针。不能向数组前面倒扫、或借SDK linker排列猜init表位置。独立[源码路线](partition-reference-route.md)已找到shell→SDFS→partition getter候选链；实机帮助确实含sdfs，但尚未定位其handler。这条路线只计划分析代码，不执行sdfs、升级或初始化命令。

## 证据与复现

`uv run comi diag capture boot-code --out NEW`继承card-code的父引用检查，新增device/Flash固定引用；`diag compare-references FIRST SECOND --boot --out REPORT`离线核对，输出`device_names`和`flash_configuration`。profile共2931读取字节；新读取900 B中有33 B字符串重叠，故新增867不同映射字节、累计3783 B。不能把传输字节总数当独立覆盖量。

[首次](evidence/boot-first-2026-10-12.json)、[重读](evidence/boot-second-2026-10-12.json)、[分析](evidence/boot-analysis-2026-10-12.json)、[结束状态](evidence/boot-final-state-2026-10-12.json)。RAM非原子快照；重新启动/布局变化即需重新定位。使用实际Capstone解码及本地固定SDK源码，不声称REA provider结果。完整固件备份、烧录和独立恢复均未实现。

后续[缓存ID实读](nor-driver-readback.md)匹配Zbit 32 Mbit／4 MiB系列，与本页32 MiB编译配置不一致。不要将配置容量用作实际备份范围。
