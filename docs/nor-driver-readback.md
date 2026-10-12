# 实机NOR读取路径与缓存芯片标识

2026-10-12；C261CF0430/FW010004。接续[Flash设备对象](boot-storage-device-readback.md)。只读固定映射代码/既存数据，不调用Flash API、模式切换或JEDEC命令。

## 底层函数表

实际RAM wrapper `1800006c`从literal `180000ac`取得`100bc294`，通过table+14读出函数指针并BLX。表首24 B实读：

`00000000 00000000 dd0b0018 c30a0018 b70b0018 110d0018`

即前两slot为0，+8=`18000bdd`、+c=`18000ac3`、+10=`18000bb7`、+14=`18000d11`。实际read目标`18000d10`；其他slot角色依据固定SDK API结构推断，并未调用。

[API结构](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spi_flash.h#L63-L85)及[扩展NOR表](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spinor/spinor.c#L844-L874)对应首两槽留空的形状。不能把位于应用映射区的表当成ROM API地址。

## read入口与调查边界

实际`18000d10`保存四参数；`18000d1c`先BL `18001290`，随后比较offset+len与`0x1000000`（16 MiB）。这与固定SDK的非XIP `spinor_ram_read`分支吻合，而不是先检查`xip_nor_offset`的路径。不能用公开XIP公式将本机`0x100xxxxx`直接换算成物理Flash偏移。[两种实现](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spinor/spinor.c#L561-L627)。

源码模式helper检查cached chipid；若匹配特定ID，退出4字节地址模式时会发write-enable及扩展地址寄存器写入。只有实际load/compare指令能定位本机缓存字段；不能直接照搬SDK结构尺寸。[helper](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spinor/spinor.c#L526-L544)。

API的`read_chipid`候选是发送硬件9F的路径，不是缓存getter；本轮不调用。[源码实现](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/spinor/spinor.c#L454-L464)。芯片标识、启动分区与原厂恢复仍需各自证据，不能由read函数存在代替。

## 实际mode helper及缓存值

read函数完整76 B，结束于`18000d58`的POP，`d5c`是下一函数。`d30`/`d4c`分别带r1=1/0调用`18000c48`；`d3c`调用`18000cf8`执行底层读取，后者未读/调用。本轮仅分析这些代码，没有触发模式切换。

`18000c48`实际从sni+24取flags；进入时置bit1，退出时清bit1，再从sni+20取chipid，与literal `18000c68`比较。literal实值`85201900`，即`0x192085`。匹配则分支到`18000c2e`，该26 B函数调用`18000a20`，然后以r1=`c5`、r2=0、r3=1尾调用`180009ca`。与公开write-enable/扩展地址寄存器写路径相符；callee未读，不把源码语义当实际执行记录。

已确认device.data=`18001a7c`，因此指令推导缓存地址为`18001a9c`。独立两次读到：

| 字段 | 原始字节 / 值 |
|---|---|
| chipid +20 | `5e401600` → `0x16405e` |
| flags +24 | `00000000` → 0 |
| helper例外ID | `85201900` → `0x192085`，与当前chipid不同 |

没有发送9F/SFDP命令、调用init或解引用MMIO。缓存不是新鲜总线测量；精确型号/封装仍需其他证据。

## 容量线索：4 MiB，不是配置的32 MiB

固定SDK的[延时表](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/flash/flash_delaytran_table.c#L82-L92)将`0x16405e`标作`ZB25VQ32DSJG`。独立原厂资料核对：

- [Zbit产品页](https://zbitsemi.com/en/m/display.php?id=17)列ZB25VQ32B/D为32 Mbit。
- [原厂B版手册](https://zbitsemi.com/upload/file/20240319/20240319153145_95803.pdf)，p32 Table7.4：SPI ID=`5e 40 16`，与缓存字节顺序一致；p4为32 Mbit／4M-Byte。4 MiB=4,194,304 B。
- [原厂D_DTR手册](https://zbitsemi.com/upload/file/20240319/20240319153157_94471.pdf)，p34 Table7.4的ID却为`5e 80 16`。SDK注释与当前D_DTR文档有版本差异，不能据ID宣称本机必为B版、D版或DSJG封装。

**证据支持Zbit ZB25VQ32系列、4 MiB容量候选。** 这与driver配置的32 MiB相差8倍；说明编译时page layout不能代替物理芯片几何。不读取32 MiB来试探容量，也不把缓存ID等同完整原厂镜像。64 GB级SD逻辑录音存储与此NOR对象是不同后端；是否由NOR启动、映射物理偏移及具体分区仍未证明。

原厂PDF来源/哈希与关键页见[来源记录](evidence/zbit-id-sources-2026-10-12.json)。pdf2md native被高风险token完整性检查拒绝，未采用失败转换；实际以Poppler文本定位，再渲染B版p32逐项核对。PDF/页面图保留于忽略的artifacts，不把整本手册复制进仓库。

## 复现与后续

`uv run comi diag capture nor-code --out NEW`；`diag compare-references FIRST SECOND --nor --out REPORT`。profile3101读取字节、3068不同映射字节；本轮新增170 B，累计3953不同映射字节。输出`nor_state`只报告缓存原值，不把候选型号硬编码为已确认硬件。

[首次](evidence/nor-first-2026-10-12.json)、[重读](evidence/nor-second-2026-10-12.json)、[分析](evidence/nor-analysis-2026-10-12.json)、[结束状态](evidence/nor-final-state-2026-10-12.json)。设备仍FW010004、idle、容量59634/59632、noise9。实际解码为Capstone；未新增REA provider结果。

下一步转向[分区引用路线](partition-reference-route.md)：已有logsrv指令`1000bf3c CBNZ`明确指向`1000bf58`，可从初始化成功分支寻找timer callback，再到console parser/shell descriptor。不要继续追分配器。原厂固件完整备份、烧录和独立恢复仍未建立。
