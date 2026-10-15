# CoMi Note 固件研究

目标：理解致远 CoMi Note（型号 `SY-N2A3F-5H2`）的 SoC、板级和固件，取得完整 NOR 备份和可靠恢复路径，然后在它上面跑自己写的最小固件。学习为主，顺带摆脱官方 App 绑定。

**状态（2026-10-15）**：设备平台已基本摸清，BLE CLI 可用；完整备份、恢复、自写固件三项都未完成。前期用 BLE 调试通道逐 512 B 导出 NOR 的路线已停止，原因见下。下一步是拆机用 SPI 编程器读片，见[路线图](docs/roadmap.md)。

## 设备一句话

炬芯 ATS3085L（Cortex-M4 r0p1，Zephyr 2.7），外置 4 MiB SPI NOR（Zbit ZB25VQ32，JEDEC `16405e`），录音存 64 GB SD（SD 协议），72×40 OLED（CH1115，I2C），BLE 5.3，400 mAh 电池，磁吸四触点充电口。固件板名 `ats3085l_dvb_watch_ext_nor_max`，版本 `1.04_2602030950`。详见[设备、固件与 SDK 总览](docs/device-platform-map.md)。

## NOR 分区与已有备份

18 项 ACPT 分区表连续覆盖 `0..0x400000`（[读回记录](docs/partition-readback.md)）。已通过固件自身 SPI API 取得并双读验证的原始字节：boot0、param0/1、boot1（全 FF）、recovery 全部 63 KiB、system 前 6 KiB、录音 DSP 110 KiB，合计约 47 KiB。另有完整的 system **映射**镜像（927 KiB，解码后）供离线分析，但它不是物理字节。这些切片是 M1 全片 dump 的校验 oracle：`tools/verify_full_dump.py`。

## 为什么停掉 BLE 逐页备份

路径是 BLE → 固件 shell → `fread` 512 B → 写 SD 临时文件 → 录音下载协议拉回，每页双读。三天得到 47 KiB，理想吞吐 81 小时 / 4 MiB，且每轮都有页失败。对一颗外置 SPI NOR 来说，拆机夹读是几分钟的事。相关代码在 `src/rcominote/experiments/`，报告在 `docs/archive/`，只作证据和溯源，不再推进。

## 从这里读

1. [路线图](docs/roadmap.md)：四个里程碑、拆机清单、flashrom/OpenOCD 命令稿。
2. [设备、固件与 SDK 总览](docs/device-platform-map.md)：平台知识地图。
3. [恢复/刷写入口分析](docs/recovery-transport.md)、[ROM ADFU 入口](docs/actual-rom-adfu-entry.md)、[实际启动流](docs/actual-boot-flow.md)。
4. [自建最小 M4 镜像](docs/minimal-firmware-image.md)、[LARK 寄存器恢复](docs/lark-register-recovery.md)、[公开 SDK 核查](docs/actions-sdk.md)。
5. [CLI 使用](docs/cli.md)、[能力边界](docs/cli-capabilities.md)、[证据索引](docs/evidence/README.md)。
6. [术语表](CONTEXT.md)、[agent 工作规则](AGENTS.md)、[交接](docs/handoff.md)。

## CLI

```sh
uv sync --all-extras
uv run comi scan
uv run comi info
uv run comi files
uv run comi download NAME --out artifacts/recordings
uv run comi settings show
uv run comi --help
```

包在 `src/rcominote/`。JSON 输出，错误非零退出，下载校验长度后原子保存。`maintenance` 子命令只提交请求、不验证效果；没有刷机或恢复命令。macOS 需蓝牙权限且先断开官方 App；Linux 需 BlueZ。

## 开发

```sh
just check            # ruff format/lint + 离线测试
just build-minimal    # 最小 M4 镜像（需 arm-none-eabi 工具链）
just check-image IMG  # 用本机 recovery 的真实 checker 离线校验镜像
```

`tools/` 为资料获取和离线分析脚本，`firmware/` 为最小镜像与参考寄存器定义，`docs/evidence/` 为可复验证据。私有录音、SDK 包、原始抓包在忽略的 `artifacts/`，不要批量删除。
