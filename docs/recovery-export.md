# Recovery有界断点导出

2026-10-13后续：[完整本机recovery与应用交接](recovery-complete.md)已取得并通过头/正文校验，补齐此前缺失尾部。下文保留阶段证据；缺字节/未绑定实际交接的限制以新报告为准，运行与整机恢复仍未验证。

**已退役为默认路线，见[路线决策](archive/research-routes.md)与[效率审计](archive/nor-efficiency.md)。** 以下为历史实验记录。

2026-10-12。原批量导出实验：实际已校验头声明512 B头+`0xf538`正文，共63288 B，固定NOR起点`0x4000`、124个512 B读取块。仅在已知recovery分区内读取，不开放任意地址。

批量命令已从默认CLI移除；实现保留在 `src/rcominote/archive/`，用于离线复核，不作为继续导出的建议。

首次有界验收复用之前两轮第0块原始窗口，离线复验后跳过设备读取，新增第1块并正常结束：2/124块。[报告](evidence/recovery-export-start-2026-10-12/report.json)、[第1块完整双覆盖](evidence/recovery-export-start-2026-10-12/block-001-report.json)、[来源窗口](evidence/recovery-export-start-2026-10-12/block-001-windows.tar.gz)。完整任务随后启动，本文不预报结果。

## 发布门槛

- 与录音DSP共用 `nor_export.collect`：已有块重新解析原始窗口，核对target/offset、双覆盖、无冲突及缓存一致性；报告complete标志不是依据。
- 每块默认至多3次尝试，失败保留新目录并非零退出；完整文件不能用缺失块填零。恢复头单独输入、或头后补零，离线验证均拒绝。
- 最后一块123起点`0x13600`，镜像只需312 B；其余200 B仍在已知分区内，最终裁掉，不算入镜像。
- 收齐后按已验证system/recovery头的32 B重置模式解码，核对独立已读512 B头SHA、头checksum、正文长度及存储正文checksum；正文模式尚待完整文件证实，失败即停止，不自动尝试其他算法后宣告成功。
- 只有所有验证通过，才分别原子发布 `recovery-raw.bin`、`recovery-decoded.bin`；已有不同输出拒绝覆盖。两文件不是事务性共同发布，若本地发布中断可重新复验续跑。
- 进度JSON逐块输出；`report.json`在本次调用结束时写入，因此长任务期间可能仍显示上次阶段值。

CLI不是刷机命令；无写Flash、模式切换、复位或目标代码执行。[实际boot流程](actual-boot-flow.md)已证明该区域是早期加载目标，但完整镜像与恢复协议仍待调查。

## 校验依据与测试

新增核心 `nor_codec.decode`用实读raw system与独立mapped头做字节oracle；boot512 B模式以存储正文checksum为oracle。SDK静态算法推导脚本保留为独立离线实现，来源见[转换分析](raw-storage-codec.md)。

共享收集器新增实际窗口的部分采集→重试→无设备续读测试，所有参数边界在创建输出目录或设备访问前失败。DSP完整216块另从原始窗口离线重验，确认重构后与已发布文件一致。
