# 完整boot读回：512 B分块转换与双checksum通过

2026-10-12。已取得ACPT `fw0_boot`完整4 KiB原始API字节，每512 B块的32行均独立双覆盖、无冲突。block0复用此前已验收扇区；block1..7从保留窗口重新解析，与拼接结果逐字节核对。

## 结果

- [原始4096 B](evidence/boot-complete-2026-10-12/raw.bin)：SHA256 `782c26c3ba9bee07a8b0b464898fb963a76eb35a2916586b854f8f45993f4166`。
- [解码镜像3672 B](evidence/boot-complete-2026-10-12/decoded.bin)：SHA256 `73a199d17490d5ae9e35e466b4ad8fafaa0757fb4a1ae7e79b5c90f90e4cb054`。
- ACTH头56 B、正文3616 B（`0xe20`），name=`mbrec`，load=`01010000`，entry=`01010039`（Thumb，正文起点+1）。头内14个LE u32之和=`ffffffff`；正文904个LE u32之和加存储checksum `1264aa7d`=`ffffffff`。
- [完整报告与新块哈希](evidence/boot-complete-2026-10-12/report.json)、[block1..7原始窗口归档](evidence/boot-complete-2026-10-12/windows.tar.gz)。block0来源：[独立双读](nor-sector-zero.md)。尾部424 B属于原始分区剩余范围，不算入声明镜像；不将其解码垃圾解释成代码。

**关键修正：boot每512 B重置转换状态，system头则每32 B。** 使用同一有效状态`0x0a15a191`。候选32、64、128、256、512、1024、2048、4096 B边界中，只有512 B通过完整正文checksum；[全部候选结果](evidence/boot-complete-2026-10-12/verification.json)。先前32 B模式得到的boot magic/name仅首块正确，后续不可信；此前 `raw-codec-2026-10-12/boot-decoded-header.bin`保留为失败模式历史证据，不能用于反汇编。

## 复现

```sh
uv run tools/verify_boot_image.py docs/evidence/boot-complete-2026-10-12/raw.bin
uv run comi diag capture-nor-sector --nor-target boot --block 7 --out artifacts/boot-last-NEW
```

boot新增块索引仅0..7，依据已校验ACPT的4096 B范围；索引8或更大立即拒绝，其他target仍只有原先允许范围。验证脚本SHA绑定原始数据，不连接设备、不执行或写入固件。格式校验独立于可启动性；下一步以这份真实boot的入口和调用链分析镜像选择、校验、失败转移与ROM接口。仍无独立恢复实测或可推荐试刷步骤。
