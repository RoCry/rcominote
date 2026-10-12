# 录音 DSP 有界断点导出

2026-10-12。CLI限实际目录中的 `aerecord.dsp`：起点 `0x24d400`、长度110148 B、216个512 B读取块。每个块仍要求每行至少两次独立producer输出、无冲突；保留代码守卫、命令/status归属、ACK与STOP/F1检查。

```sh
# 限新增块数进行实机验证；已有块从原始窗口重新验收，不重复读取。
uv run comi diag export-record-dsp --out artifacts/record-dsp-export --max-new-blocks 3
# 同一目录续读完整文件；默认每块至多尝试3次，失败保留证据并非零退出。
uv run comi diag export-record-dsp --out artifacts/record-dsp-export
# 单块调研；仅record-dsp允许0..215，其余固定target只能block0。
uv run comi diag capture-nor-sector --nor-target record-dsp --block 2 --out artifacts/NEW
```

## 实机与验收边界

- 首次试跑已完成block0..2，共1536 B；前两块与此前独立读取完全一致。[第三块22份窗口及报告](evidence/record-dsp-export-2026-10-12/block-002-report.json)验证了新增非零block寻址和归属。
- 续读实测跳过这3块并取得block3，累计4/216；[续读报告](evidence/record-dsp-export-2026-10-12/resume-report.json)。后续完整任务已启动，本文不预报其结果。
- [进度记录](evidence/record-dsp-export-2026-10-12/progress.json)仅表示阶段结果，**不是完整文件导出成功**。
- 续读重新解析所有成功窗口，拒绝错target/offset、冲突和与证据不同的缓存sector。不信任report的complete标志。每次尝试写新目录，不覆盖旧失败。
- 单块512 B是固件固定读取长度。最后块起点 `0x268200`，有效文件剩68 B；其余444 B落在同一已知SDFS分区的间隙/后续文件内，只读后丢弃，最终文件严格110148 B。没有把读取块边界当成文件边界。
- 收齐216块后验证540 B头部、段指针边界，以及[原目录文件checksum](sdfs-checksum.md) `0x96d685bb`。全部通过才原子发布 `aerecord.dsp` 和SHA256。SDFS累加和不等于密码学签名。
- 没有擦除、写flash、ADFU、OTA或DSP运行。此命令只覆盖一个资源文件，不构成整机备份/恢复。

完整文件取得后仍须解析section链、检查长度和目标地址；不能用头部和校验和代替自写固件的硬件运行或恢复验收。

## Section验收工具

`uv run comi diag inspect-dsp-image PATH`逐一遍历主code/data及非零bank指针：非空段必须完整包含8 B头和size字节数据，之后继续读下一段；零size终止。四字节零size位于EOF可接受，与[已核对的实际加载器](dsp-file-loader.md)一致；非空短头严格拒绝，不照搬固件的宽松条件。输出每段文件偏移、声明DSP地址、长度和SHA256；不把DSP地址映射或运行成功当作已验证。

已对固定SDK中的5个不同哈希二进制DSP文件完成结构扫描，分别遍历61、61、37、20、79段；[样本哈希、路径与结果](evidence/sdk-dsp-sections-2026-10-12.json)。同后缀的两个非xhqy文件被拒绝。这是格式解析实测，样本不是CoMi录音DSP，不能替代正在导出的文件验收。

当前完整导出进程启动于分段检查功能加入之前，运行中代码不会自动更新；完成后须对实际输出单独运行上述命令，再记录验收结果。后续新启动的导出命令已把分段检查纳入发布前检查。
