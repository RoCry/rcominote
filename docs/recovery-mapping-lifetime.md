# Recovery 映射存活期：不能沿用 boot 地址直接读取

2026-10-13后续：[完整本机recovery与应用交接](recovery-complete.md)已取得并通过头/正文校验，补齐此前缺失尾部。下文保留阶段证据；缺字节/未绑定实际交接的限制以新报告为准，运行与整机恢复仍未验证。

2026-10-12。只读离线复核；没有设备 I/O、MMIO、映射修改或新 NOR 读取。

**结论：应用运行时 `11000000` 仍指向 recovery，尚未证明。参考 SDK 明确存在成功交接时覆盖该映射的路径；实际应用另有启用总线错误异常的代码。当前不将此地址加入默认读回集。**

## Boot 曾经映射，不代表应用仍然映射

[已验证实际 boot](actual-boot-flow.md) 在 `010103c0..d0` 将 NOR `4000` 映射至 CPU `11000000`，使用 slot 0（寄存器 `40010300/304`），随后跳入 recovery。这是交接之前的事实。

固定 SDK `26f51e584940d5b141cd1d09d2629d69b595f579` 提供一个具体的映射失效机制：

- [soc_boot_priv.c:19–20](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/boot/soc_boot_priv.c#L19)：`APP_RUN_ADDR=10000000`，`BOOT_RUN_ADDR=11000000`。
- [cache0_map:119–123](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/boot/soc_boot_priv.c#L119)：直接改指定 slot，再 invalidates cache。
- [boot_nor_ram:368–395](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/boot/soc_boot_priv.c#L368)：先保存 slot 0，再以 `cache0_map(0, APP_RUN_ADDR|0xf, offset)` 覆盖；只有镜像校验失败时恢复旧 slot。成功则 `run_app`，没有恢复旧映射。

因此，“应用没有找到清除 recovery 的函数”不足以证明它存活：覆盖可以发生在 recovery 交接应用时。上述机制是固定参考源码，**尚未绑定到实际 recovery 的已验证指令，不能宣布本机已经清除**。这里的 cache invalidate 与取消映射是两种操作；只 invalidate 也不能反过来证明地址失效。

## 实际应用：两个候选已缩小，均未证明 mapping entries

输入为已完整校验的 mapped-system，927632 B，base `10000000`，SHA256 `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。沿 [mapping audit](mapping-candidate-audit.md) 的既有三个 `40010000` literal 做局部 PC-relative 引用核对；没有用整镜像线性反汇编证明函数。

| 真实地址 / bytes | 本次确认 | 边界 |
|---|---|---|
| `1003c430` `644b6548196863f0a6fd` | 从 literal `1003c5c4` 取 `40010000`，读取首 word，调用 `1009ff86`；r0 从 `1003c5c8` 取 `100cd546`，字符串 `MEMORYCTL 0x%x \n` | 是寄存器诊断输出，不写 `+300/+304` |
| `1003e9b2` `0b4a0b49136844f4580043f008031360` | 从 literal `1003e9e0` 取 `40010000`，将首 word OR `8` 后写回 | 是 MEMORYCTL bit 3，不是 mapping slot |
| `1003e9e4` `8bdf0c10` | 指向 `100cdf8b`：`mpu init end\n`；所属函数入口 `1003e968`；`100b9f08` 存函数指针 `1003e969` | 初始化表引用，不等于本次读到了运行时 MMIO 状态 |
| `100bfd08` `00000140` | 本次在该 literal 之前 4096 B 内，逐半字候选解码，未找到直接 PC-relative LDR 引用 | 可能通过表间接使用；未建立用途，不能排除相关操作 |

固定 SDK [mpu_acts.c:209–223](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/mpu/mpu_acts.c#L209) 的同名日志和同样寄存器操作处于 `CONFIG_MPU_EXCEPTION_DRIVEN`，`SYS_INIT(... APPLICATION,20)`；[soc_memctrl.h:80](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/soc_memctrl.h#L80) 将 bit 3 命名为 `MEMORYCTL_BUSERROR_BIT`。这为实际操作提供源码解释，但没有尝试触发异常。

因此，一次未经映射确认的 `fread 11000000` 不能被视为一定无副作用的读操作；缺映射时可能进入异常处理。本文没有证明本机必然触发异常，也没有运行探测。

## 已有部分 recovery 的证据边界

同轮离线复验已有 94 个 512 B 原始块，恢复连续 48128 B 前缀；没有新增读回。[provenance](evidence/recovery-prefix-provenance-2026-10-12.json) 的 reset-32 解码 SHA256 为 `cff7225f49d502a3e6cf52a8d2df12cbee44625cc2120c3c7a03a96d77e577b7`，**完整正文 checksum 未验证，以下只属候选解码**。

[选定启动指令及 literal](evidence/recovery-prefix-startup-2026-10-12.json) 显示向量入口 `110023d5`，经 `11001ff8` 到初始化 `11008aac`；传入 ROM 表间接调用的源区包括 `1100e098`（长度 `1508`）和 `1100f5a0`（目标 `18001508..180016a0`）。两源区均超过已取得的前缀结束地址 `1100bc00`。`1100999a` 从 ROM 表 `688c` 加载函数指针再 BX，ROM 函数本体未取得；参数形状与 SDK data/RAM 函数初始化一致，尚未将其升级为已验证 memcpy。

因此，执行于 RAM 的实际交接/映射改写代码可能位于尚缺的数据区；只检查前缀中的 Flash 指令，无法排除 SDK 所示 slot 0 覆盖。完整校验及实际交接链仍缺，不能靠候选 Thumb 指令宣布 recovery 存活或已被移除。

## 当前最短的证明路径

1. 从已有 recovery 原始证据恢复、校验实际执行的交接函数，确认 slot 0 的最终设置；优先离线已有数据。部分解码正文未通过全镜像 checksum 时，任何指令结论须标为候选。
2. 或者通过一个已确认安全的寄存器读取路径，取得应用运行时所有 mapping slots，按实际 boot 指令与厂商 ABI 解释；读取 MMIO 本身不在本次执行范围。
3. 在 mapping 存活、范围、CRC/解码语义得到证据之前，不新增 `11000000` 镜像导出，不用参考 SDK 地址公式代替实际状态，也不恢复已归档的慢速全量 NOR 路线。

反例源码已足以否定“boot 映射自然永久保留”的假设；它尚不足以确定实际 recovery 最终状态。

后续[入口候选审计](recovery-entry-candidate.md)已从现有前缀定位第二阶段入口及升级标志清除分支；仍属未完成正文校验的候选，未解决交接映射或恢复验收。

入口候选审计进一步定位交接的间接调用为RAM `18000451`；按启动复制形状，对应缺失镜像偏移地址`1100e4e8`。这说明映射改写的关键函数可能位于缺失尾部，不能以已有Flash前缀没有相关写入来排除它。
