# System原始头部的32 B重复块

后续：[静态重建转换已匹配完整system头并通过recovery头校验](raw-storage-codec.md)。本文保留找到算法前的观察与候选筛选过程。

2026-10-12。固定 `system` target读取NOR `0x24000` 前512 B；44份有效窗口合并，32行各独立双覆盖、无冲突。第一次29行确认；第二次RAM日志行截断导致整轮拒绝；第三次32行确认。失败轮不贡献字节。

- 原始512 B SHA256：`28b2e50ba95630f6485bd5e3ccfbd8ebe5f1406ffa36d6c0c4e35c4c71af0678`。
- 已校验mapped-system头512 B SHA256：`911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5`。
- [原始/映射字节、报告和采集窗口归档](evidence/system-raw-header-2026-10-12)。这些输入足以离线重现比较，无需设备或rlcdv项目。

## 观察

1. mapped头的offset64..511全零；对应相对位置的14个原始32 B块完全相同。
2. 相同mapped 8 B零块对应7种原始8 B值；16 B零块对应3种原始16 B值；32 B零块只对应1种原始32 B值。分组覆盖范围分别从40、48、64开始，不能混淆起点。
3. 逐字节 `raw XOR mapped` 在完整512 B中不符合周期1、2、4、8、16、32、64、128或256的重复掩码。只排除这些按相同偏移对齐的简单XOR候选，没有穷举所有变换。
4. 与[boot/recovery对照](boot-recovery-prefixes.md)一致，头部前8 B为 `dbd5f9a38960bfdc`，不是直接可见的ACTH magic。

32 B重复边界与固定SDK打包器的32 B无CRC加密块配置相容；这是候选关联，不证明本机使用该实现。相同偏移比较仍不能排除其他映射/分组转换。当前没有解密结果、密钥证据或可写回镜像。

SDK出处：固定提交 `26f51e584940d5b141cd1d09d2629d69b595f579` 的 `action_technology_sdk/bootloader/tools/build_firmware.py`，322–323行设置32/34 B，495–515行调用 `MakeEncryptBin`，526–547行选择CRC与非CRC块大小。调用链及flag边界另见[安全启动审计](boot-security-source-audit.md)。

## 重现

```sh
uv run tools/compare_raw_header.py docs/evidence/system-raw-header-2026-10-12/raw.bin docs/evidence/system-raw-header-2026-10-12/mapped.bin
```

脚本SHA绑定两份实际512 B输入；结果已与[保存报告](evidence/system-raw-header-2026-10-12/comparison.json)逐字节一致。归档 `windows.tar.gz` 解压后可用 `comi diag assemble-nor-sector`重新组装原始字节。无设备写入、重启、映射寄存器修改或工具二进制执行。
