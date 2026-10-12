# 原始NOR转换：system头匹配与recovery头校验通过

后续修正：[完整boot已取得并通过头/正文checksum](boot-complete.md)。boot采用512 B重置，本文早期32 B模式下的boot结果仅用于记录失败尝试，不能视为完整正确明文；system/recovery头结论不变。

2026-10-12。静态重建SDK工具算法，用实读system原始/映射头求有效初始状态，再验证未参与拟合的字节和另一分区。**已解释这台设备的system头存储转换，尚未验证完整system/boot/recovery正文，更不是恢复或刷写验收。**

## 实机交叉验证

- 只用system头首32 B已知明文/原始字节，建立256条GF(2)方程；秩32，唯一有效状态 `0x0a15a191`。
- 独立用offset64..95全零明文块求解，得到同一状态、秩32。
- 每32 B重置状态，完整512 B重新编码与原始字节逐字节相同；反向解码与已校验映射头逐字节相同。首块拟合之外还有480 B验证，不是只展示拟合数据。
- 同一状态解码recovery前512 B：magic=`ACTHHTCA`，name=`b`，load/entry=`0x110023d5`，正文长度字段=`0xf538`（62776 B），头长度512，头内128个LE u32之和=`0xffffffff`。**正文尚未读取，正文checksum未验收。**
- 同一状态解码boot前512 B：magic=`ACTHHTCA`，name=`mbrec`，load=`0x01010000`，entry=`0x01010039`，长度字段=`0xe20`。其512 B和为`0x1c3d4149`，不能套用system头校验规则；后续布局/代码仍待确认。

[system验证](evidence/raw-codec-2026-10-12/system-verification.json)、[跨分区报告](evidence/raw-codec-2026-10-12/cross-partition.json)、[recovery解码头](evidence/raw-codec-2026-10-12/recovery-decoded-header.bin)、[boot解码头](evidence/raw-codec-2026-10-12/boot-decoded-header.bin)。原始输入来自已独立双覆盖的[system](raw-header-block-pattern.md)、[boot](nor-sector-zero.md)、[recovery](boot-recovery-prefixes.md)。有效状态不是已经读取的efuse密钥，也不能推广为其他设备通用值。

## 静态算法来源

固定SDK提交 `26f51e584940d5b141cd1d09d2629d69b595f579`，`action_technology_sdk/zephyr/tools/prebuilt/leopard/common/bin/encrypt.bin`，4267536 B，SHA256 `c33c1882ee297968d5a4f51004adbacb440b7e42435aafb7fd4d713386e766f6`。它是Actions `100TMFWFSTCA` / `ACTS-FWT001` 容器；本次只读文件，没有执行其中二进制。

容器offset `0x32d010`起506368 B，各字节XOR `0x38`得到带符号的x86_64 ELF `EFUSEX~1.SO~`，SHA256 `6bb0d1f4394987792e5b8163ce605411f2a91e169ef5cf133407642105b1e26c`。**这里的XOR38只是工具文件包装，不是NOR转换。** ELF包含Cython `efuse.py`函数，保留静态反汇编：[seed函数](evidence/raw-codec-2026-10-12/seed-functions.asm.gz)、[encrypt](evidence/raw-codec-2026-10-12/encrypt.asm.gz)。

`gen_seed8`（ELF VA `0x2d1f8`）对state与以下8个mask的交集取奇偶校验，依次组成结果bit0..7：

```text
82108421 08411043 10802084 21004108
82008210 04000420 10001020 200021cc
```

mask载入位置分别为 `2d2a1,2d5a3,2da71,2df3f,2e40d,2e8d4,2eda2,2f270`。

`gen_seed32`（`0x2fee2`）更新：

```text
((state << 1) & fffffffc)
| (((state XOR popcount(plaintext_byte & 3c)) & 1) << 1)
| parity(state & 82608edb)
```

字节mask位置`2ff32..2ff4a`，bit1运算`301a5..3029a`，反馈mask/parity `30325..305e0`，左移mask `30630..30699`，组合`30724..30780`。encrypt在`32800..32813`将输入XOR `gen_seed8(state)`，在`32a77..32a89`以**原明文字节**更新状态；解码时必须先恢复明文再反馈。32 B重置与实机头全部字节相符，不从工具符号名称单独推导。

## 复现与后续

```sh
uv run tools/verify_raw_codec.py docs/evidence/system-raw-header-2026-10-12/raw.bin docs/evidence/system-raw-header-2026-10-12/mapped.bin
```

脚本SHA绑定实际输入，直接计算位运算和线性方程；不加载SDK模块、不执行目标代码、不连接设备。主agent独立复跑全部比较，并将同一变换用于boot/recovery取得以上结果。

接下来优先完整读取小型boot区并检查其布局/代码，再读取recovery正文验证存储checksum、入口及恢复实现。系统头的成功转换不证明ROM允许自写镜像、启动签名策略、物理写回方法或应用损坏后的独立恢复。
