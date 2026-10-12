# 实际dbg静态命令表：35项与终止证据

2026-10-12；C261CF0430 / FW010004。完整checksum镜像离线分析，未执行任何handler、设备命令、RAM pointer跟随或MMIO访问。

**dbg静态表共35项，没有发现新的、已证明只读且能返回原始NOR字节的导出路径。** 本轮补齐全部名字/help/handler和明确终止；仅新解码一个直接相关的小handler `snandr`，实际指令补充了公开源码未体现的长度单位差异与缓冲风险。

## 完整表与输入

[证据JSON](evidence/actual-dbg-command-inventory-2026-10-12.json)保留完整720 B表、每项descriptor、完整NUL名字/help、逐段SHA、literal及snandr全部反汇编。完整mapped image经`inspect_image()`重验927632 B、固定头和正文checksum通过；SHA256=`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。该校验不证明physical Flash等价或恢复能力。

入口沿[实际shell registry](shell-registry-readback.md)取得：`dbg` descriptor=`100bb8c0`，subcmd=`100bbba4`，静态array=`100bb8d4`，stride20 B。此次逐项读取syntax直至index35=`100bbb90`；此项**20 B全零**，不是按相邻对象距离猜终止。index0–34的subcmd均NULL；handler均为Thumb pointer，下表去掉bit0显示code地址。末word均零，未强加额外ABI含义。

| # | name | handler code | 完整help |
|---:|---|---|---|
| 0 | `mdw` | `100a18ee` | display memory by word: mdw address [,count] |
| 1 | `mdh` | `100a18e4` | display memory by half-word: mdh address [,count] |
| 2 | `mdb` | `100a18da` | display memory by byte: mdb address [,count] |
| 3 | `mww` | `100a1862` | memory write (fill) by word: mww address value [,count] |
| 4 | `mwh` | `100a185c` | memory write (fill) by half-word: mwh address value [,count] |
| 5 | `mwb` | `100a1856` | memory write (fill) by byte: mwb address value [,count] |
| 6 | `snort` | `100257d4` | nor test : snort address size |
| 7 | `fread` | `10025348` | flash read : fread dev[sd/spi_flash/spinand] offset |
| 8 | `snandr` | `1002549c` | nand logic read: offset start address; size read len; |
| 9 | `snandw` | `1002502c` | nand logic write: offset start address; size read len; |
| 10 | `dma_dump` | `100a17ea` | dma info |
| 11 | `sdfs` | `10025414` | sdfs name size |
| 12 | `nvdump` | `100a17e0` | nvram dump |
| 13 | `nvram` | `10025240` | nvram name (val) |
| 14 | `de_dump` | `100a17d6` | de dump |
| 15 | `lcd_dump` | `100a17c8` | lcdc dump |
| 16 | `bb-reg` | `10024bd4` | read/write btc bb ctl |
| 17 | `rf-reg` | `10024b68` | read/write btc rf ctl |
| 18 | `sleep` | `10024d38` | sleep |
| 19 | `show_stack` | `100a17be` | show kernel stack |
| 20 | `reboot` | `10024dcc` | reboot [adfu] |
| 21 | `kheap` | `10024c9c` | kheap [addr] |
| 22 | `uimem` | `100a1868` | uimem dump [0&#124;1&#124;2], where 0-FB, 1-LVGL, 2-RES |
| 23 | `uiview` | `100a17a8` | view dump |
| 24 | `cpuload` | `10024abc` | show cpu load statistic preriodically |
| 25 | `dumpbuf` | `10024a28` | dump buffer to file system: dumpbuf addr len path |
| 26 | `dumpmsg` | `100a179e` | dump message: dumpmsg |
| 27 | `dumprbuf` | `10024a18` | dump rbuf in share ram |
| 28 | `dbgsw` | `10024c40` | dbgsw cpu[dma] |
| 29 | `resman` | `100a1790` | resource dump |
| 30 | `wksrct` | `100249c0` | wksrct  ms |
| 31 | `rtc` | `10024ee0` | rtc get/set current time |
| 32 | `alarm8hz` | `10024e60` | alarm8hz set alarm time |
| 33 | `dvfs` | `1002495c` | dvfs set/unset level |
| 34 | `mpu_set` | `100248ec` | mpu_set mem_base size ro[no/rw/ro] |

## 唯一新增handler审计：snandr

index8 descriptor=`100bb974`，完整syntax=`snandr\0`、help=`nand logic read: offset start address; size read len;`，handler Thumb=`1002549d`。新解码范围`1002549c..1002554a`，174 B，末地址不含；其后nop不计代码，`1002554c..10025564`为六个literal。Capstone 5.0.6 Thumb+MCLASS完整解码；SHA256=`ccd008109efec0da17f40de229e4c6d222cc8b85c22a8297fe1377ef2d86a4a5`。未展开任何callee或driver。

| 步骤 | 实际指令事实 |
|---|---|
| binding | literal指向`spinand\0`；`100254a8` BL已知binding函数`1009a81c`，NULL报错并返回+22；名字不证明设备存在 |
| allocation | `100254c2`固定r0=`800`即2048 B，BL `1009cab4`；NULL返回−1 |
| argc | 分配之后才检查argc=3；错误路径打印后返回−1，未见释放已分配buffer |
| parsing | argv[1] offset、argv[2] size分别BL `1009d48c`，base=0；未检查endpointer |
| 长度分流 | `100254fc 4fea4029 LSL.W sb,r0,#9`计算dump/status长度；r8保留未shift的size。未见size、shift结果与2048的比较 |
| status | `1002550e`经shell formatter `100a0dd6`打印read长度、offset、buffer；在API调用之前 |
| read形状 | 从device+8 API取首slot；`10025520 BLX sl`传device、offset、buffer、**未shift的size** |
| dump | signed ret≥0时`10025544 BL 100252e4(shell,buffer,size<<9)`，使用已解码的[print_buf](raw-read-handler-followup.md#实际输出分流)；hex正文仍走printk |
| result | ret<0只打印失败；read成功/失败两支均free后返回0，返回值不能验收字节 |

手算例子：size=1时API长度参数1、dump512 B；size=4时dump2048 B；size=5时dump2560 B，已比2048 B固定buffer多512 B。这里说的是实际参数值；下层API单位没有本轮证明。若API按sector理解，超过4可能连读取也溢出；若按byte理解，dump可能包含未初始化内容。无论哪种解释，不能据命令名把它升级为已验证安全导出。

与固定SDK [shell_nand_read](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L483-L524)相比，本机status/dump新增`<<9`，read参数仍未shift；公开源码使用未shift的size。此前[恢复评估](flash-recovery-assessment.md)仅有源码级固定2048 B/缺上界警告，此次补为实际handler证据，并明确单位差异。不能照搬公开源码参数约定。

## 对只读返回路径的判断

- `mdw/mdh/mdb`：已知memory display家族；没有增加物理Flash映射证明。现有固定mdb镜像导出仍有效，不自动授权任意RAM/MMIO读。
- `fread`：实际handler和printk正文路由已审计；本表没有第二个NOR dump入口的确证。`snandr`新增审计不能解决单位、buffer、设备可用性或BLE输出问题。
- `sdfs`：既有[分区/SDFS路径](partition-readback.md)已追踪；不是通用原始Flash备份，本轮未展开完整handler。
- `nvdump/nvram`：实际名字/help确有NVRAM入口，但完整handler、输出和副作用未审计；`nvram name (val)`本身提示混合操作，不能当已证明只读的一般存储导出。
- `dumpbuf`：实际help明确“dump buffer to file system”；固定SDK [实现](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L1437-L1468)创建并写目标文件。本轮没有解码实际handler，不将它作为只读路径或执行候选。
- `dumprbuf/kheap/uimem`及其他dump：诊断名字/help不能证明其返回任意Flash/file字节或无副作用。`dbgsw`的固定SDK对应[切CPU/DMA模式](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/subsys/shell/shell_dbg.c#L1720-L1740)，不是新增数据返回接口；本轮未展开。

表内没有显式USB导出命令名/help；这仅限当前35项dbg静态表，不能推断其他root/dynamic命令或全固件没有USB能力。余下write/test/control/mixed命令没有因名字被认定安全，也未执行。

本轮关闭“dbg表是否漏枚举”的缺口；没有新增已证明只读的raw NOR返回路径。后续应围绕实际物理映射/driver单位/数据校验补证，不能把表项存在、状态行或handler返回0当作备份成功。
