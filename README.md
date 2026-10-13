# CoMi Note 固件研究

目标：理解致远 CoMi Note 的 SoC、板级资源、固件与 SDK，取得完整备份和可恢复的运行路径，随后开发自写固件。已有独立 BLE CLI；**尚不支持完整固件备份、刷写或原厂恢复**。

## 从这里读

1. [设备、固件与 SDK 总览](docs/device-platform-map.md)：已知平台、固件组成、可复用材料、关键缺口及暂存问题。
2. [当前研究路线与淘汰记录](docs/research-routes.md)：唯一执行优先级；历史报告的“下一步”不作为计划。
3. [平台资料获取核查](docs/platform-source-followup.md)、[新增 GitHub SDK](docs/github-sdk-followup-2026-10-13.md)、[Gitee 录音卡源码对照](docs/domestic-sdk-followup-2026-10-13.md)：固定源码、平台分类和可复用的录音流程。
4. [CLI 能力边界](docs/cli-capabilities.md)与[使用说明](docs/cli.md)：区分源码线索、实测能力与未验证行为。
5. [证据索引](docs/evidence/README.md)：采集、样本、来源及历史研究记录。

[随机说明书核对](docs/manual-2026-10-13.md)：模拟硅麦+骨传导麦、NOTE/CALL、
电源按键与录音滑键、磁吸充电口；照片与校验值已归档。尚不能确定精确麦克风颗数或独立复位方法。

## 当前认识（2026-10-13）

| 主题 | 结论与边界 |
|---|---|
| 平台 | [实机CPUID](docs/cpu-identity.md)为Cortex-M4 r0p1；[固件板名](docs/firmware-board-identity.md)为 `ats3085l_dvb_watch_ext_nor_max`；实体SoC丝印仍未知 |
| SDK | 公开SDK的M33参考板已在Ubuntu构建；不能作为CoMi固件。[LARK材料](docs/lark-helper-candidate.md)更接近M4，但缺完整BSP |
| 存储 | [18项ACPT配置覆盖4 MiB NOR](docs/partition-readback.md)；[录音SD路径](docs/card-state-readback.md)独立，容量约64 GB |
| 已取得固件 | 完整[927632 B系统映射镜像](docs/offline-system-analysis.md)、[boot0](docs/boot-complete.md)、[110148 B录音DSP](docs/record-dsp-export.md)、分区表；[recovery完整63,288 B](docs/recovery-complete.md)校验通过；[param双槽原始各4KiB](docs/param-slots.md)，主槽有效、备用槽全FF；[factory-RW原始8KiB私有备份](docs/factory-rw-backup.md)，12条记录CRC通过。不是整片原始备份 |
| 恢复/刷写 | 已分析[实际boot](docs/actual-boot-flow.md)、[ROM下载入口](docs/actual-rom-adfu-entry.md)、[OTA容器](docs/ota-container-contract.md)；无匹配官方恢复包、实测ROM传输或恢复证明 |
| 自写镜像 | [最小M4 ELF与948 B ACTH镜像](docs/minimal-firmware-image.md)可重复构建，通过本机recovery真实checker离线仿真；未在硬件运行 |
| USB | 已知数据线拔插对照未发现CoMi枚举；ROM模式未试，不能断言接口只充电 |
| 客户端 | 固定官方App的[23个请求opcode均有主机路径](docs/remaining-client-contracts.md)，不等于全部实机验收。BLE状态、录音控制、文件下载、部分配置已实测；[短窗口实时流与离线MP3逐字节相同](docs/realtime-live.md)，不保证长时无丢失 |

优先获取匹配BSP/芯片资料、量产下载链、官方固件；细节疑点先记录，待其影响路线选择时再追。低效NOR日志批量导出已归档，不再作为默认备份方案。

## 使用 CLI

```sh
uv sync --all-extras
uv run comi --help
uv run comi scan
uv run comi info
uv run comi files
uv run comi record start
uv run comi record stop
uv run comi download NAME --out artifacts/recordings
uv run comi settings show
uv run comi watch --duration 5
uv run comi diag capture platform --out artifacts/platform-NEW.json
```

包在 `src/rcominote/`。JSON输出，错误非零退出，按序列号选设备；下载校验完整长度后原子保存，拒绝覆盖。下载／同步中Ctrl-C保留标注不完整的文件和元数据，断开连接、退出130。诊断只开放固定profile，没有任意shell、刷机或恢复命令。

[实际CLI取消验证](docs/download-cancel-contract.md#actual-cli-sigint-validation-2026-10-13)：真机上一次SIGINT保存4,416 B正确前缀、退出130；新连接完整下载与指定偏移下载均逐字节符合旧完整基线，设备状态及7项录音列表不变。不是自动续传或设备线程退出证明。

macOS需蓝牙权限，官方App先断开；Linux需本机BlueZ/适配器。APK、SDK、原始录音、完整日志在忽略的 `artifacts/`；仓库不依赖rlcdv、Obsidian或临时交接文件。

显式单文件删除见[CLI说明](docs/cli.md)：必填serial和文件名确认，只以完整列表中目标消失为验收；尚未实机执行。`maintenance`提供绑定／解绑／格式化／恢复出厂／手机类型的显式请求；退出3表示提交但效果未验证，没有实机执行这些管理操作。

## 开发与参考构建

```sh
just                 # 仅列出 recipes
just check           # 格式、lint、shell语法、离线测试
uv build
```

Linux x86_64参考板构建，不打包或刷写CoMi：

```sh
bash tools/setup_sdk.sh
uv run --locked tools/build_sdk.py \
  --sdk "$HOME/w/_tmp/lv_port_actions_technology" \
  --toolchain "$HOME/.cache/rcominote/gcc-arm-none-eabi-10.3-2021.10" \
  --out artifacts/sdk-build --jobs 4
```

[SDK源码定位](docs/actions-sdk.md) · [参考构建实测](docs/ubuntu-build.md) · [烧录/恢复评估](docs/flash-recovery-assessment.md) · [BLE协议](docs/protocol.md) · [官方后台参考](docs/seeyon-backend-reference.md)。旧脚本命令对应历史提交，现用命令以CLI文档为准。
