# 同连接 NOR 读回与录音 DSP 头

2026-10-12，实机只读；没有执行擦除、写入、重启或 OTA。

## 512 B 双覆盖：245.492 s → 21.762 s

`uv run comi diag capture-nor-sector --nor-target boot --out artifacts/NEW`

一次 BLE 连接完成22次独立 `fread`，每次读取一个256 B日志窗口；11窗口一轮，共两轮。共享本次连接的代码守卫，各次重新读取28 B ring状态，检查 init/panic、缓冲区和边界。按实际收到的上下文行停止刷新；全部 ACK、STOP/F1 完成后才发布有效子记录。不是22次独立连接，也不是原子快照。

- 实测32/32行各两次一致，无冲突；输出512 B。
- SHA256 `72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec`，与此前22次冷连接独立取得的完整字节一致。
- 耗时取通知时间线末端，包含本次守卫与读回；约11.3倍提速。单个固定块测量，不能视为整片连续导出的速度保证。
- [22份窗口与报告](evidence/nor-warm-sector-2026-10-12/report.json)可离线重新合并。只有全行双覆盖才生成 `sector.bin`。

首次批量实验23.624 s，仅31/32行双覆盖，CLI拒绝输出。真实故障：ring跨尾拆成两段，第一段之后的 `help` 大量输出覆盖第二段，`0xd0`行末尾损坏。修复为先连续读取两段，再统一刷新。保留 `failed-window-06.json`、`failed-window-17.json` 和失败报告；解析器拒绝受损行，未把缺失当成功。

## aerecord.dsp 前64 B

[四次独立捕获与报告](evidence/record-dsp-prefix-2026-10-12/report.json)确认物理/API偏移 `0x24d400` 的前64 B。位置与110148 B文件长度来自[实际SDFS目录](nor-partition-prefixes.md)。

| 字段 | 实测值 |
|---|---|
| magic | `xhqy` |
| 工具版本word | `0x01030000` |
| file type / subtype | 0 / 0 |
| 算法版本word | `0x01000000` |
| entry point | `0x8e` |
| code section offset | `0x21c` |
| data section offset | `0x3ef0` |

字段位置来自[实际DSP加载器](dsp-file-loader.md)。它读取540 B头；当前仅取得64 B，不能验证完整bank表、sections或文件校验和。

下一步价值最高：在已知文件/分区范围内扩展可靠导出，取得完整录音DSP与boot/recovery内容；查清raw与映射表示转换，再验证独立恢复入口。当前CLI仍不支持整机备份或烧录；Android登录按用户选择暂缓。
