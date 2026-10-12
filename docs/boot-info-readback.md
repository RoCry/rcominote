# 启动SRAM候选结构与实际ACPT交叉核对

2026-10-12，C261CF0430 / FW010004。两次64 B候选结构独立一致；当前shell-code链3051 B，累计6935不同映射字节。本次无复位、模式切换、MMIO读写、文件访问或Flash操作。

## 读取依据与证据等级

已由实际partition getter取得global→`01000040`→完整CRC正确ACPT。[分区证据](partition-readback.md)。固定SDK `soc_boot.c:18–38`把boot-info列在启动SRAM起点；`soc_boot.h:28–45`提供64 B结构。此次仅取ACPT之前相邻的`01000000..01000040`候选范围，先以实际global/table header校验当前设备和区域。

**这64 B的起点/字段布局来自SDK候选，不是已解码的实机boot-info getter。** 不同于此前逐条BL/literal推导，本次采用已证实区域中的限定结构假设，再以独立ACPT字段交叉核对；没有扫描任意地址或读取外设寄存器。候选结构相符不证明整个ABI、SoC型号或板级配置。

## 实际值及解释

| 候选字段 | 相对offset | 实读值 | 与独立证据关系 |
|---|---|---|---|
| mbrec_phy_addr | 00 | `0` | 对应fw0_boot起点，但不能仅凭零确定当前mirror |
| param_save_addr | 04 | `01000040` | 与实机partition global指针精确一致 |
| system_phy_addr | 08 | `00024000` | 精确匹配ACPT index5 fw0_sys.file_offset |
| reboot_reason | 0c | `0` | 未根据单次值解释重启原因 |
| nand_id_offs/len | 10/14 | `0/0` | 未据此否定其他介质 |
| boot_flags | 18 | `0` | SDK低位含watchdog/mirror等；实机字段访问未核对 |
| param_phy_addr | 24 | `0` | **不匹配**任何ACPT PARAM条目（1000/3000） |
| nor_offset | 28 | `00024000` | 与system字段相同 |
| code_len | 2c | `0` | 不解释为固件长度为0 |
| dvfs | 34 | `23085f0a` | 不据此推断精确芯片/电压 |

reserved字段保留在原始证据，不赋予含义。param物理字段不匹配可能来自厂商ABI变化、未填充字段或其他机制，尚无证据选择其中一个。禁止把它自动替换成1000；测试保留这一不一致。

## 能推进什么

`param_save_addr`与实际table pointer、`system_phy_addr/nor_offset`与ACPT系统区两组一致，提高了boot-info候选解释的可信度。当前系统物理偏移线索为24000；仍不能直接推出虚拟10000000对应其原始字节，也未取得镜像头、安全flags、CRC映射或解密行为。

下一步应核对实际boot-info getter/镜像头及映射关系；先解释一致和不一致字段，再扩展原始镜像备份。此前[加密/签名审计](boot-security-source-audit.md)的边界不变。

## 复现

`uv run comi diag capture shell-code --out ...`；两次记录用`uv run comi diag compare-references A B --shell --out ...`。报告新增`boot_info_candidate`，明确候选scope并保留system_matches与param_matches。

[首次](evidence/boot-info-first-2026-10-12.json)、[重读](evidence/boot-info-second-2026-10-12.json)、[分析](evidence/boot-info-analysis-2026-10-12.json)、[结束状态](evidence/boot-info-final-state-2026-10-12.json)。77项测试、24项子测试及wheel/sdist通过。设备结束idle/FW010004。

固定源码：[启动SRAM/getter](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_boot.c#L18-L38)、[结构](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_boot.h#L14-L45)。
