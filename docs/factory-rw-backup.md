# Factory-RW：本机配置的私有备份

2026-10-13。实际ACPT ID7固定物理范围`1ec000..1ee000`，8KiB；相邻
factory-RO和user NVRAM不在本次范围。目标：保留可能无法从通用固件包恢复
的本机配置，非整片NOR导出、刷写或恢复验收。

参考SDK明确把factory-RW用于机器专属配置，如SN/MAC：
[固定nvram_config.c](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/nvram/nvram_config.c)。
这解释备份价值，不证明本机每个身份或校准值都存放于此。

## 已验证头部与采集范围

两个4KiB区段各先读取512B，每块独立双读一致；第一段为CRC有效的
NVSR头，第二段前512B为FF。空白前缀不能证明完整区段空白。
完整区域结果见下方验收记录；头部CRC不覆盖整个区域。

沿用已验证的`fread→printk ring→SD→Boyi`通道，正常态采集；每次独立
连接核对设备身份/idle、原厂系统guard、鲜活baseline、唯一producer、
完整连续32行、日志帧/ACK/STOP及下载字节。每块两份独立capture必须相等，
跨块SD文件名不能重复。只开放0..15块，16会越入user NVRAM而被拒绝。
逐块双读不等于冻结运行中配置的原子快照；完整格式检查也不证明期间无更新。
流程留SD临时文件，未执行NOR写入、复位、ROM进入或上传代码。

## 格式依据与严格度

独立oracle为未修改的
[原厂build_nvram_bin.py](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_nvram_bin.py)
生成的合成配置，包括跨512B边界的601B值。测试不使用本解析器生成期望值。
源码注释称NVRS，实际little-endian magic`0x5253564e`生成字节**NVSR**；
以原厂packer输出为准，不按注释猜magic。

| 层 | 检查与边界 |
|---|---|
| 区段 | 16B头、version1、4096B区段；CRC-8/MAXIM仅覆盖头部`6..16`，不含magic/state |
| 条目 | 8B头、名称hash、名称终止/长度、数据跨度、16B对齐；CRC覆盖条目`3..end`，不含magic/state |
| 状态 | FF/5A分别报告valid/obsolete标记；不据此选择运行时active/latest段 |
| 未覆盖字节 | padding/尾部要求FF；完整原始一致性由独立双读证明，不扩张CRC覆盖 |

严格解析器检查obsolete记录的CRC；SDK恢复策略可能把损坏项标obsolete后
继续使用其他记录。因此**先保存完整raw，再解析**；解析拒绝仍保留raw，
不自动重采，不把语义拒绝当传输失败或不能启动的证明。

## 私有产物与复验

原始配置、ring、frames、键名、逐值hash和完整报告只留忽略的`artifacts/`；
不进Git/GitHub。hash不能匿名化短SN/MAC。仓库只保存工具、合成oracle和
删去配置内容的验收事实。外层实验及底层sd_bridge的factory-RW入口均限制
输出至本仓库`artifacts/`，默认stdout只打印进度。
设备SD上保留的测试文件也可能含配置转存；本轮不删除，不能把它们当普通音频。

```sh
# 两个512B头部关卡；SD临时写入，不写NOR
uv run -m rcominote.experiments.factory_rw \
  artifacts/factory-rw-system.bin artifacts/factory-rw-NEW --create-sd-files

# 重放已保留头部，通过后补齐8KiB
uv run -m rcominote.experiments.factory_rw \
  artifacts/factory-rw-system.bin artifacts/factory-rw-NEW --create-sd-files --complete

# 仅离线；缺capture即失败，禁止设备I/O
uv run -m rcominote.experiments.factory_rw \
  artifacts/factory-rw-system.bin artifacts/factory-rw-NEW --cached-only --complete
```

系统oracle来自仓库`docs/evidence/minimal-image-2026-10-13/original-system.bin.gz`，
解压后SHA必须等于`ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`。
失败capture目录不自动重试；复验会重查原始帧、guard和配对，不只信report成功标记。

## 完整区域验收

完整8192B已保存，16块各独立双读一致；所有头部/条目严格检查通过。
[脱敏验收摘要](evidence/factory-rw-2026-10-13-summary.json)：

| 区段 | 实测 |
|---|---|
| `1ec000..1ed000` | NVSR/version1、valid标记；12条记录，全部条目CRC通过；余3680B全FF |
| `1ed000..1ee000` | 完整4096B全FF，不仅头部前缀 |

32次源读取，实验耗时合计600.15s，首尾跨度611.41s；UTC10月12日
23:45:38–23:55:50（本地10月13日）。64个不同SD测试路径共写256KiB文件
内容及文件系统元数据，未删除。每次正常录音列表均保持7项，结束idle。
全部保留capture再次离线重放通过，新增设备读取0次。

原始区、完整capture/live报告和私有压缩归档留于`artifacts/`；不发布其hash。
本机布局与原厂packer格式兼容，支持复用这部分格式知识；不证明使用相同
SDK版本、全部代码仅有小改，或12条记录都是唯一/当前生效的身份与校准数据。

即使此8KiB完整保存，factory-RO、user NVRAM、boot1及其余资源仍有缺口；
没有完整物理NOR镜像、可写回备份或恢复证明。按钮退出边界见
[ROM退出条件](actual-rom-exit-condition.md#parked-independent-reset-lead)。
