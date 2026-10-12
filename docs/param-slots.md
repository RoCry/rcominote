# 启动参数双槽：原始备份与回退条件

2026-10-13，C261CF0430 / FW010004。问题：boot所依赖的持久ACPT/FVER
是否已备份，备用参数槽是否有效？[实际boot](actual-boot-flow.md)尝试物理
偏移1000/3000；[分区表](partition-readback.md)各配置4KiB。
两个槽名不能证明有两份有效内容。

**已取得两个完整4KiB原始槽，全部16个512B块各独立双读一致。
主槽有效；备用槽完整4KiB全FF，不满足已分析的boot参数校验。**
[原始槽、配对记录及验收摘要](evidence/param-slots-2026-10-13/report.json)。

| 槽 | 物理范围 | SHA-256 | 结果 |
|---|---|---|---|
| [param0](evidence/param-slots-2026-10-13/param0-raw.bin) | `1000..2000` | `4a374a53ace6a201a23f43ff2a8ac137ec6379a2ad2c842a8b045694142875a1` | 前1KiB含有效元数据；后3KiB原始字节全FF |
| [param1](evidence/param-slots-2026-10-13/param1-raw.bin) | `3000..4000` | `f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6` | 全FF；没有有效参数副本 |

采集UTC23:22:47–23:33:15（本地10月13日），32次扇区读取的实验耗时合计
557.27s；首尾跨度约628s，包含阶段复验。64个不同SD测试路径共写256KiB
及文件系统元数据，未删除；7个正常录音列表不变，结束idle/unbound。
这是关键启动产物的有界补齐，吞吐仍不适合整片NOR备份。

## 为什么取得这份产物

先前只有SRAM缓存的744B ACPT及128B FVER，没有任何完整物理param槽。
[参考量产脚本](production-package-contract.md)对boot的16KiB擦除若照搬至
本机，会同时覆盖两个boot和两个param。先保存并验收这些小型启动依赖，
直接缩小恢复材料缺口；不重新启动整片NOR慢速导出。

本次固定范围：`1000..2000`、`3000..4000`，末端不含，总8KiB。
每槽前1KiB先独立双读；格式解释及CRC通过后才补余下3KiB。
任何guard、完整行、配对或非空白格式失败即停，不自动重试。

## 格式与校验边界

实际boot的`010106a8..010106ec`检查：

| 内容 | 相对槽起点 | 解码元数据中的存储CRC |
|---|---|---|
| ACPT | `0..2e8`；前740B CRC32，末4B存储值 | `703f5674` |
| FVER | `2e8..368`；前124B CRC32，末4B存储值 | `c06bda1e` |

主槽元数据唯一通过的已知转换为**每32B重置**，不是boot的每512B重置。
转换状态`0a15a191`是已观察到的有效状态，不是恢复出的efuse密钥。
32B候选依据本次第一扇区与旧独立SRAM ACPT前512B逐字相同，再由完整
ACPT/FVER两项CRC及旧缓存哈希交叉验收；不是只看magic或名称猜格式。

完整元数据与旧缓存一致：board=`ats3085l_dvb_watch_ext_nor_max`，
version=`1.04_2602030950`。明文offset`3fc`观察到`part`；它由SDK打包脚本
写入，但上述boot校验没有检查它，因此不把它当额外启动要求。
主槽明文`368..3fc`为148B零填充。仅转换前1KiB，不把原始FF尾部转换后的
垃圾发布为“完整明文参数”。备用槽无有效参数不等于本轮观察到启动失败，
也不证明boot1状态或任何自动回滚路径；没有执行失败切换实验。

**CRC只覆盖前872B及其存储校验字。** 槽的完整性由全部原始字节独立双读
相等证明，不把CRC扩大至未覆盖的3224B，也不把CRC当签名或可启动证明。

## 采集与离线复验

正常态固定`fread→printk ring→SD→Boyi`，沿用[已验通道](sd-file-bridge.md)。
每次读取核对真实系统代码guard、鲜活无旧NOR行的baseline、唯一producer
与文件名、物理连续32行、完整日志帧/ACK/STOP。跨块文件名也拒绝重复。
模块不开放任意地址，只允许实际两个4KiB槽各0..7块。

```sh
# 前1KiB门槛；写SD临时文件，不写NOR
uv run -m rcominote.experiments.param_slots \
  artifacts/mapped-system/mapped-system.bin artifacts/param-NEW --create-sd-files

# 复验前缀，通过后补齐；失败目录保留，不自动重试
uv run -m rcominote.experiments.param_slots \
  artifacts/mapped-system/mapped-system.bin artifacts/param-NEW --create-sd-files --complete

# 已保留全部capture时，仅离线重验；缺文件立即失败，禁止设备I/O
uv run -m rcominote.experiments.param_slots \
  artifacts/mapped-system/mapped-system.bin artifacts/param-NEW --cached-only --complete
```

`param_image.inspect_slots`只解释输入字节；独立配对由采集器及原始capture
复验完成。解析器允许已知plain/32B/512B候选，但要求唯一候选双CRC通过；
有效旧版本单独报告与当前缓存的差异，不能因版本不同就当坏槽。
空白前缀只说明已读前缀；任何非空白、无法解释的槽均使阶段门槛失败。

仓库中的[采集归档](evidence/param-slots-2026-10-13/captures.tar.gz)保留32次
完整原始frames、ring和sector及各自baseline；仅移除正常录音列表字段。
解压到新目录，搭配仓库原始系统镜像即可重放全部guard和配对检查：

```sh
mkdir artifacts/param-cache-NEW
tar -xzf docs/evidence/param-slots-2026-10-13/captures.tar.gz -C artifacts/param-cache-NEW
gzip -dc docs/evidence/minimal-image-2026-10-13/original-system.bin.gz > artifacts/param-system.bin
uv run -m rcominote.experiments.param_slots \
  artifacts/param-system.bin artifacts/param-cache-NEW --cached-only --complete
```

## 尚未证明

两槽原始内容不等于完整NOR备份；[factory-RW已另存8KiB私有备份](factory-rw-backup.md)，
boot1、factory-RO、user NVRAM、完整资源等
仍有缺口。没有尝试复位、ROM进入、运行上传代码、NOR写入或恢复。
即使参数检查通过，也还缺匹配的完整包/工具、早期启动约束与独立退出路径。
