# 自建 M4 镜像：构建与本机检查代码接通

2026-10-13。Ubuntu编译、Mac离线仿真；无设备I/O。**自建948 B ACTH镜像通过本机recovery的实际检查机器码。** 这是工具链→链接→封装→局部准入的实证，不是硬件启动、完整BSP或可恢复烧录。

## 产物与依据

源代码：[startup.S](../firmware/minimal/startup.S)、[main.c](../firmware/minimal/main.c)、[linker.ld](../firmware/minimal/linker.ld)；[构建工具](../tools/build_minimal_firmware.py)。不用不匹配的M33 SDK、媒体/BLE库、ROM调用或硬件驱动。

| 项目 | 实际结果 / 边界 |
|---|---|
| 编译 | 既有GNU Arm Embedded10.3.1；Cortex-M4 / Thumb / soft-float / freestanding / nostdlib；[ELF属性](evidence/minimal-image-2026-10-13/attributes.txt)为ARMv7E-M，无VFP寄存器调用约定 |
| 链接 | 正文 `10000200` 起436 B，80项向量占320 B，ELF入口 `10000341`；[ELF](evidence/minimal-image-2026-10-13/minimal.elf)、[反汇编](evidence/minimal-image-2026-10-13/disassembly.txt) |
| 包装 | 普通512 B ACTH头＋正文；向量SP `01002b40`，头entry与向量entry对应ELF；加法校验，无签名/TLV/物理NOR转换/OTA封装 |
| 自建镜像 | [minimal-acth.bin](evidence/minimal-image-2026-10-13/minimal-acth.bin)，948 B，SHA256 `487b3873d9b62a32afde64305e99d7b6940fcc67b9740fcd769a9e2cf96c685b` |
| 重复构建 | 两个新目录的ELF/正文/ACTH哈希相同；远端ELF与ACTH逐字节比较一致。[记录](evidence/minimal-image-2026-10-13/reproducibility.json)；显式assembler `.file`消除随机 `cc*.o` 符号，未靠strip掩盖差异 |

startup只屏蔽IRQ、设置CONTROL/MSP、复制.data、清.bss、进入写RAM标记的C函数再循环。它没有设置VTOR、初始化时钟/看门狗/存储/屏幕/音频/BLE或建立异常恢复。
RAM数据 `01001b40..01002340` 和SP `01002b40` 来自[原厂启动常量](reset-entry-readback.md)，**只是本轮链接fixture，不证明这些地址在当前运行系统空闲，也不证明入口权限/栈/映射状态满足要求**。不能把这个文件上传为RAM helper或直接当原始NOR镜像刷入。

## Oracle 是实际机器码

[完整recovery](recovery-complete.md)中 `180000e8..1800020c` 的sum/checker及 `20c..218` literal直接载入[离线工具](../tools/check_recovery_image.py)，没有重写验收算法。完整recovery SHA固定；CPU模型为Unicorn2.1.4 ARM Thumb MCLASS，按静态复制解释放入RAM。只允许这些代码执行、输入精确范围只读、256 B模型栈和两个4 B输出读写。

唯一拦截 `18000078`：记录r0并返回LR。实际helper具有 `0x`＋八个nibble＋换行的诊断输出形状；不执行其字符输出、不模拟UART。其他越界执行、缺字节、未知内存/MMIO均报模型错误，不补零、不假造返回码。指令数和时间均有上限。模型栈位于合成地址，和本机RAM布局无关。

[真实执行结果](evidence/minimal-image-2026-10-13/gate-results.json)：

| 输入 | 实际返回 | entry_out；意义 |
|---|---:|---|
| 原厂完整927632 B system | 0 | `1002d819`；正oracle，记录SP `01002b40` |
| 原厂正文末字节xor1 | −15 | `1002d819`；正文拒绝前已覆盖输出 |
| 原厂头 `+10` 字节xor1 | −14 | `1002d819`；头校验拒绝前已覆盖输出 |
| 原厂向量entry清Thumb位 | −12 | 保持模型初值 `1100000f`；早期拒绝未覆盖 |
| 自建M4镜像 | 0 | `10000341`；局部checker接受 |
| 原厂文件缺最后1 B | 无返回结论 | 实际读越过文件精确末端，模型错误；没有用页尾零补出结果 |

原厂正oracle是此前已完整校验的[映射system](offline-system-analysis.md)，本轮以[确定性gzip](evidence/minimal-image-2026-10-13/original-system.bin.gz)入库；[长度、哈希及旧验收来源](evidence/minimal-image-2026-10-13/original-system.json)保留。它不是原始NOR或原厂恢复包。

这将此前[晚期失败的entry_out别名](recovery-complete.md)从静态解释推进到真实checker的有限仿真复现，仍未执行handoff的映射恢复路径。接受也只覆盖这个checker：未模拟复制helper、准备/映射、ROM/更早授权、候选入口执行或硬件状态。

## 重现

Linux上用已验证工具链构建；输出必须新目录：

```sh
uv run tools/build_minimal_firmware.py \
  "$HOME/.cache/rcominote/gcc-arm-none-eabi-10.3-2021.10" artifacts/minimal-NEW
```

任意支持Unicorn的主机验证CPU可见的明文字节；拒绝exit1，模型/输入错误exit2，接受exit0并输出JSON：

```sh
uv run tools/check_recovery_image.py \
  docs/evidence/recovery-complete-2026-10-13/recovery-decoded.bin \
  docs/evidence/minimal-image-2026-10-13/minimal-acth.bin
just check  # 包含实际原厂正/负oracle、精确读取边界和自建编译产物验收
```

本轮在这些产物处收尾；不扩成OS/外设移植或新增刷写入口。下一道门槛依旧是匹配平台初始化与内存配置、更早启动授权和原始表示、独立可退出的加载路径。详情以[研究路线](archive/research-routes.md)为准。
