# 录音 DSP 完整读回与断点导出

**完整DSP数据仍有效；批量获取路线已退役，见[路线决策](research-routes.md)。**

2026-10-12。已从本机 NOR `0x24d400` 完整取得 `aerecord.dsp`，110148 B。216个512 B块的每行均有独立producer双覆盖、无冲突；最终文件与此前独立取得的SDFS目录checksum一致。**这是单个原厂资源文件，不是整机备份，也未验证加载执行或恢复。**

## 完成证据

- [原始DSP文件](evidence/record-dsp-complete-2026-10-12/aerecord.dsp)：SHA256 `7ed5482ca4d37c39f6b70e72fc29c129f135bc77eed5d3c0889bfc8bc5fd436e`。
- [完整验收报告](evidence/record-dsp-complete-2026-10-12/report.json)：长度、540 B头、所有非零section链及各段哈希；SDFS checksum `0x96d685bb`，匹配此前捕获目录，而非由此次文件生成的预期值。
- [逐块清单](evidence/record-dsp-complete-2026-10-12/blocks.json)：216块哈希、NOR位置、尝试数及窗口数。290次尝试，64块需要重试；保留5808份有效窗口。无效采集没有贡献有效字节。
- 导出进程正常退出后，另运行当前版本的 `inspect-dsp-image`；随后再次运行导出命令，从全部保留窗口重新验收216块，验证缓存字节、段结构和checksum，无新增设备读取，正常退出。
- 约1.6 GB原始会话/窗口日志留在本地 `artifacts/record-dsp-export/`。仓库中的文件与报告可独立做结构/校验复核；逐块哈希不能替代未随仓库发布的原始采集记录。

## 实际段布局

| 表 | 非空段数 | 正文总字节 | 表起点 | 四字节终止项 |
|---|---:|---:|---:|---:|
| main code | 3 | 15544 | 540 | 16108 |
| main data | 3 | 36672 | 16112 | 52808 |
| bank18 code | 1 | 144 | 52812 | 52964 |
| bank19 code | 1 | 27656 | 52968 | 80632 |
| bank34 code | 1 | 24872 | 80636 | 105516 |
| bank34 data | 1 | 4616 | 105520 | 110144 |

六张表连续；最后四字节终止项恰好结束于110148 B，无尾部剩余。540 B头 + 109504 B正文 + 10×8 B段头 + 6×4 B终止项 = 110148 B。bank34代码/数据声明地址分别为 `0x20c86d00`、`0x20c89dcc`；它们是DSP编码地址，不是可直接读写的MCU/NOR地址。实际[地址转换与参考SDK不同](dsp-address-map.md)，bank切换和运行时序仍待验证。

## 复现

```sh
# 仓库内离线结构复核，无设备连接。
uv run comi diag inspect-dsp-image docs/evidence/record-dsp-complete-2026-10-12/aerecord.dsp
# 单块调研：record-dsp允许block0..215；boot允许0..7。
uv run comi diag capture-nor-sector --nor-target record-dsp --block 2 --out artifacts/NEW
```

续读拒绝错target/offset、冲突、与证据不同的缓存；不信任report的complete标志。失败非零退出、保留证据，后续尝试使用新目录。全部块通过后，检查完整头/段链与目录checksum，再原子发布文件；已有不同文件拒绝覆盖。SDFS累加和不是密码学签名。

固件 `fread` 固定读取512 B；最后块起点 `0x268200`，文件有效字节只有68 B。多读444 B属于同一已知SDFS分区的间隙和下一个文件，最终裁掉。读取块边界不等于文件边界。

每次采集保留代码守卫、命令/status归属、ACK与STOP/F1检查。没有擦除、写flash、ADFU、OTA订阅或DSP执行。

## 格式与阶段证据

`inspect-dsp-image`遍历主code/data及非零bank指针：非空段必须有完整8 B头及size字节正文；零size终止，只需4 B，与[实际加载器](dsp-file-loader.md)一致。输出文件偏移、声明地址、长度和SHA256，不验证DSP目标地址或硬件运行。

此前已扫描固定SDK的5个不同DSP二进制，分别61、61、37、20、79段；[SDK报告](evidence/sdk-dsp-sections-2026-10-12.json)。此次CoMi文件提供了独立的实际格式样本，尤其证实EOF四字节终止项。

保留早期阶段记录：[首次与续读](evidence/record-dsp-export-2026-10-12/resume-report.json)、[首段](evidence/record-dsp-first-section-2026-10-12.json)、[主code](evidence/record-dsp-main-code-2026-10-12.json)、[主data/bank18](evidence/record-dsp-main-data-2026-10-12.json)、[bank19](evidence/record-dsp-bank19-2026-10-12.json)。其中“不完整”描述是当时状态；当前完整结果以上述完成报告为准。
