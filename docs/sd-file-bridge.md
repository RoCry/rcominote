# RAM / boot0 → SD → Boyi：有界实测

2026-10-13，C261CF0430 / FW010004。**RAM→SD→蓝牙下载已验证；固定 NOR boot0 经 printk ring 导出已验证一次。** 尚不是完整备份、可靠批量导出、烧录或恢复能力。实测后停止，未扩大 offset。

后续：[完整recovery取得](recovery-complete.md)；[已知ROM336 B两次独立导出](rom-sd-bridge.md)。本报告保留首次实验范围。

## 为什么改变路线

旧 `fread→printk ring→mdb` 每512 B约232条命令；[效率审计](nor-efficiency.md)已淘汰默认批量路线。
之前因 `dumpbuf` 写文件而排除，范围过严：写SD临时文件与写启动NOR的后果不同。
现用固件已有命令，把固定RAM区写到独有测试路径，再复用已验证Boyi下载器。
这项工作直接影响固件提取路径；不延伸成通用内存/文件管理CLI。

## 实际固件合同

独立系统镜像SHA-256：`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。
实际 `dumpbuf` handler：`10024a28..10024aaa`，literal pool `10024aac..10024abc`。

- `dbg dumpbuf <address> <length> <path>`；数值base0解析，直接 `fs_write(file,address,length)`，无临时复制/范围保护。
- `fs_open` flags `0x12`；创建或打开现有文件，无EXCL/TRUNC。随机40-bit名称和可见文件列表碰撞检查不能保证不存在隐藏文件/竞态。
- 只传播open失败；write/close返回值被忽略。因此ACK和“done”不是写入成功证据，必须下载对比。
- 当前Boyi下载路径使用 `Call-<name>.mp3`；不解析音频，实测可直接下载未列入正常录音列表的测试名称。
- 原厂console读取最多64 B，NUL覆盖index63。首试68 B命令截断文件名，外层剩余长度错误导致ACK/STOP超时；之后的字节可能才触发截断命令。实验新增发送前长度拒绝，后续固定命令含newline63 B。

## 结果

所有下载均4096 B；RAM和ring的内容成功依据为独立字节oracle，不是文件长度。

| 源 / 目的 | 结果 | 时间与结论 |
|---|---|---|
| `10000000` 映射Flash → SD | 全零，与系统镜像不符 | 下载0.364 s；会话正常结束。直接XIP源失败；DMA访问限制仅假设，未继续追驱动细节 |
| `18000000` 固定RAM代码 → SD | 与镜像offset `dd500` 起4096 B完全相同 | 下载0.304 s；完整实验11.988 s。该区来自实际启动 `memcpy(18000000,100dd500,12c8)` |
| `1803ee09` printk ring基线 → SD | 本次独有dump命令标记存在；没有任何可接受NOR行 | 在任何本次fread之前下载、检查；排除旧行拼接及全零“基线” |
| 单次 `dbg fread spi_flash 0` → ring → SD | 唯一、物理循环顺序连续的32行，与独立boot原始前512 B相同 | producer到下载结束2.697 s；其中下载0.331 s；含两阶段基线/guards的完整实验25.137 s |

RAM SHA-256：`35437a73c3a6087f13ad981be8c5719a93db5ca38ef892bcb87fdc984d207d7b`。
boot0 SHA-256：`72952b98341a3089765c6cc8dd35ddc93ae699698d1455ce74dea1071cc277ec`。

ring解析要求起点在第一物理圈、offset按0..1f0顺序、相邻行字节连续、含前置CRLF总跨度≤4096、仅一个完整候选。禁止按地址收集散行拼接。
前后context是辅助证据，非原子且不计数回绕。下载与STOP结束、前后身份/idle检查通过。
未对齐ring地址本次可用，不能据此推广全部RAM/Flash地址。

2.697 s是本次局部阶段，25.137 s是完整实验；旧路线约22 s的统计口径不同。
**已绕过数百次mdb读取，但未建立批量吞吐、稳定性或重复一致性结论。**

## 保留产物与副作用

[实验模块](../src/rcominote/experiments/sd_bridge.py)固定镜像SHA、地址、长度、版本/idle、handler/ring/fread代码guards；无任意offset、重启、ROM进入或NOR写入接口。需显式 `--create-sd-file`：

```sh
uv run -m rcominote.experiments.sd_bridge artifacts/mapped-system/mapped-system.bin artifacts/NEW --create-sd-file --source nor-ring
```

当前CLI用 `nor-ring` 替代初轮 `boot-ring` 名称；默认仍固定boot0，另外只允许recovery块93..123。每次读取创建两份文件。初轮实验留下以下非音频测试文件，未删除；当前没有审计过的安全删除命令：

- `/SD:/RECORDER/Call-rcd66e84e42a.mp3`：全零映射源失败文件。
- `/SD:/RECORDER/Call-rc8d6174d379.mp3`：有效RAM测试文件。
- `/SD:/RECORDER/Call-rca8036fb3fd.mp3`：ring基线。
- `/SD:/RECORDER/Call-rcb61b078de5.mp3`：ring后像。
- 首次超长命令**可能**留下 `/SD:/RECORDER/Call-rcf24b45143596`，没有扩展名；正常录音列表未显示它，不能证明不存在。

命令会写SD文件内容及文件系统元数据；未发固件NOR写、删除、录音或重启命令。两个失败尝试后设备仍可查询，未观察到设备无法启动。

[保留证据](evidence/sd-bridge-2026-10-13/)含失败/成功报告、代码guard/log frames、下载原始字节和boot0结果；略去个人录音列表。
boot oracle来自[先前独立备份](evidence/boot-complete-2026-10-12/raw.bin)，不是从本次ring生成的期望值。

## 停止点

新通道保留为后续补齐recovery/个体配置的候选，不恢复旧长任务。
仅当补齐关键固件区域成为下一项明确交付时，才做少量不同扇区的重复读/失败行为验证，再决定批量工具。
当前主线仍是匹配ATS3085L BSP、原厂完整包与独立恢复入口；直接XIP→SD失败原因、通用文件管理和吞吐调优暂存。

## 后续：关键固件产物已交付

[完整recovery](recovery-complete.md)通过同一桥接路线补齐30个缺失扇区，各双读一致，并通过完整头/正文校验。当前命令、基线绑定及缓存复验见该报告；本篇首次单块结果保留为历史。未改进为整片NOR批量备份，也未继续追直接XIP失败。
