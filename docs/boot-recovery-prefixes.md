# Backup boot与recovery的实际前512 B

2026-10-12。延续已验证的固定NOR读取；新增 `recovery` target，仅允许ACPT中的 `0x4000` 起点、512 B，不开放任意地址或额外块。未复位、切换模式、擦写或订阅OTA。

## 实测结果

| 目标 | NOR位置 | 独立producer窗口 | 确认行 | SHA256 |
|---|---|---:|---:|---|
| backup-boot | `0x2000` | 22 | 32/32 | `9f56cda75fefeab90f6fa5d5ddc9601544b121732c5ecccab32e631060453a5d` |
| recovery | `0x4000` | 44 | 32/32 | `9a79e301960bcb9cefeae206a64e9375ecc86d0a1616dd2010c3746f26c96449` |

每行至少两次独立输出，无冲突。recovery首轮仅28行双覆盖，工具非零退出且不发布二进制；第二轮32行通过，合并两轮再次通过。两轮有效数据没有冲突。

**backup-boot前512 B全部为FF。** 这是NOR API读回值；只覆盖4 KiB配置区域的前八分之一，不能断言整个分区擦空。ACPT中的mirror1条目不证明存在有效备用启动镜像，更不能证明自动回滚。

三处原始头部对照：

```text
boot     0x00000: dbd5f9a38960bfdc 5895bcea6ff3e341
recovery 0x04000: dbd5f9a38960bfdc 8db6bf7deb8376a9
system   0x24000: dbd5f9a38960bfdc 414dbffb62161a36
mapped system  : 4143544848544341 19d8021062000000
```

原始boot/recovery/system共享8 B前缀；system映射视图前8 B是 `ACTHHTCA`。共同前缀支持共同存储转换的假设，但未证明recovery解码后魔数、算法/密钥、签名策略或当前选择的启动镜像。不能把这些原始字节作为ARM指令直接解释，也不能把相同前缀当作完整性校验。

## 可复核证据

[backup字节](evidence/boot-recovery-prefixes-2026-10-12/backup-boot.bin)、[报告](evidence/boot-recovery-prefixes-2026-10-12/backup-boot-report.json)；[recovery字节](evidence/boot-recovery-prefixes-2026-10-12/recovery.bin)、[报告](evidence/boot-recovery-prefixes-2026-10-12/recovery-report.json)。[窗口归档](evidence/boot-recovery-prefixes-2026-10-12/windows.tar.gz)保留66份原始窗口，解压后可从帧/守卫/归属重新验收，无需原项目或本地artifacts。boot和system对照来源：[boot双读](nor-sector-zero.md)、[system前缀](nor-partition-prefixes.md)。

```sh
uv run comi diag capture-nor-sector --nor-target recovery --out artifacts/recovery-NEW
mkdir -p artifacts/boot-recovery-recheck
tar -xzf docs/evidence/boot-recovery-prefixes-2026-10-12/windows.tar.gz -C artifacts/boot-recovery-recheck
uv run comi diag assemble-nor-sector artifacts/boot-recovery-recheck/recovery/attempt-*/window-*.json --out artifacts/recovery-reassembled.bin
```

下一步须解决存储转换/启动映射，或取得完整原始boot/recovery后与匹配工具关联。当前证据仍不证明独立恢复入口、退出和官方镜像恢复成功。
