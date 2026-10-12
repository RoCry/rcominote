# 映射镜像到物理NOR：当前证据缺口

2026-10-12。完整实机mapped-system镜像离线复验通过；无设备I/O、MMIO访问、地址探测或映射修改。[搜索方法、命中位置、bytes及SHA](evidence/mapping-candidate-audit-2026-10-12.json)。

## 已有联系仍不足以导出raw地址

- 实际ACPT：fw0_sys.file_offset=`24000`；18项逻辑NOR分区覆盖4 MiB。
- boot-info候选：system/nor offset同为`24000`；param物理字段不匹配仍保留。未独立恢复完整厂商ABI。
- 当前执行视图：`10000000..100e2790`，927632 B完整镜像checksum通过。
- 实际NOR read wrapper符合非XIP分支；没有观察到SDK `spinor_xip_read`公式在本机read路径中执行，见[NOR读路径](nor-driver-readback.md)。

这些关系支持来源关联，不能证明raw NOR与mapped字节一一相同。CRC展开、硬件解码和偏移配置仍缺实际映射状态/原始对照。即使system映射确认，也不自动暴露boot/recovery/NVRAM等其他分区。

## 本次限定搜索

固定SDK [soc_memctrl.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_memctrl.c)的mapping诊断文字作为候选特征。

在完整已校验artifact中精确ASCII搜索：`invalid nor phy addr`、`invalid cpu addr`、`cannot found slot`、`xip_nor_offset`、`slot=%d  to map`均无命中。4 B对齐LE word搜索：`40010300`、`40010304`、`13800000`、`14000000`均无命中。

这些只是特定字节特征不存在；不能推成mapping功能不存在。它可能被优化、合成immediate、厂商改写，或位于未取得的boot/recovery/ROM。未以全镜像线性反汇编的数据误识别结果证明函数存在。

找到的两个相关片段：

- `1003e9b2`从literal=`40010000`取得base，读base首word、OR8并写回；没有访问mapping entry offsets。仅描述静态指令，未执行。
- `10031448..10031470`按参数5/6修改`40014000`的bits5–6；没有提供系统物理偏移或raw读取指针。

其余`40010000`对齐word位于`1003c5c4`、`100bfd08`，本次未建立它们到mapping操作的调用/访问链，不据其出现升级结论。完整命中清单见JSON。

## 原始备份仍需的新证据

最低有用增量是实际mapping配置及含义，或同一已知镜像头的独立raw读取对照。仅把boot-info候选offset代入SDK公式、不验证地址语义就读uncached窗口，不能建立可靠备份。当前不新增映射窗口读命令，也不修改cache映射。

[fread运行时输出](console-target-followup.md)已定位到UART_0 DMA链；[完整dbg目录](actual-dbg-command-inventory.md)用于检查另一条可返回字节的路径。官方包路线仍受[用户暂不登录](android-runtime-followup.md)边界约束。这些限制分别属于数据返回、物理映射和原厂资料，不能以某一项进展替代恢复验收。
