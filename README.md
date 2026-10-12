# CoMi Note 固件前期研究

目标：确认手上这台致远 CoMi Note 的芯片、板级资源、备份与恢复路径，随后尝试自写固件。当前有独立可用的 BLE 工具和研究资料，**尚无可刷写的 CoMi 固件或经验证的恢复方式**。

## 当前结论（2026-10-12）

| 问题 | 已知与边界 |
|---|---|
| 设备 | 自有 `C261CF0430`，广播 `CoMi Note 2F01`，固件 `1.0.4`；包装样本型号 `SY-N2A3F-5H2` 尚需和实机底标核对 |
| 平台 | GATT 与 Actions（炬芯）SDK 的日志服务匹配，固定 PREPARE/ACK 也已实测相容；具体 SoC、板号仍未知 |
| 数据通路 | Boyi BLE 协议已验证，状态/列表/下载不需绑定；既往实测录音为 16 kHz 单声道、32 kbps MP3 |
| 新鲜实机证据 | 本轮重新枚举 GATT、读取状态；MTU 247，4 个服务，普通模式未见 Actions OTA UUID，`usb_mode=true` |
| USB | 用户确认数据线后做拔插对照，仍未见明确 CoMi 枚举；`usb_mode=true` 不等于主机数据接口已启用，板级走线/其他模式待查 |
| 日志/shell | 实机执行 `kernel version` 返回 Zephyr 2.7.0；`help`/`dbg` 列出存储读取与 ADFU 重启命令，后者未执行 |
| 配置读回 | `dbg nvram BT_LE_NAME` 已返回14字节实机内容；原始 flash 正文仍未通过 BLE 取得 |
| 程序字节读回 | 已独立核对五处共69字节映射代码/常量/函数名；尚无完整固件/物理分区备份 |
| 自定义固件 | Actions 有构建、OTA、ADFU 等参考代码，也有签名/安全启动配置；CoMi 是否接受自签/未签名镜像尚未知 |
| Linux 构建 | Ubuntu 上参考板 hello_world 已生成 ELF/BIN/HEX；SDK 无源码补丁，构建后 tracked 文件干净；尚不是 CoMi 固件 |

## 阅读顺序

1. [固件研究路线与待解问题](docs/firmware-roadmap.md)：哪些证据决定下一步。
2. [Actions SDK 核查](docs/actions-sdk.md)：平台、构建、分区、升级、恢复及源码定位。
3. [App 升级与 USB 线索](docs/app-upgrade.md)：Boyi/Mova 区分、APK 固定样本与可复核提取。
4. [BLE 协议与工具](docs/protocol.md)：帧格式、命令、已有实机验证边界。
5. [证据来源与本轮验证](docs/evidence/README.md)：历史资料与新采集分开记录。
6. [USB 对照与日志握手](docs/usb-log-probe.md)：第二轮实机结果、复现工具。
7. [USB/ADFU 恢复传输](docs/recovery-transport.md)：RAM helper、ROM/DFU 区别、旧 host 兼容边界。
8. [固定 SDK 构建可行性](docs/build-feasibility.md)：Linux 编译候选配方、Python 2/x86 打包依赖与缺失物。
9. [Ubuntu 实测构建](docs/ubuntu-build.md)：已跑通的一键准备/编译、产物与已知限制。
10. [不拆机诊断](docs/noninvasive-diagnostics.md)：默认日志和只读 shell 候选，包含 ACK/短缓冲陷阱。

11. [烧录、失败恢复与提取评估](docs/flash-recovery-assessment.md)：四个问题、恢复占位代码与完整备份条件。
12. [实机诊断](docs/device-diagnostics.md)：已执行 shell、命令清单及有限读取结果。

13. [读回通路与下一阶段](docs/next-investigation.md)：当前能推进什么、每一步需要什么新证据。

14. [实机代码读回](docs/mapped-code-readback.md)：16字节独立重读一致、Thumb解码、实时入口检查和长输出丢失。
15. [原厂helper静态分析](docs/helper-static-followup.md)：rm/rs处理器、存储初始化边界；[Ubuntu反编译工具](docs/offline-helper-analysis.md)。
15. [官方产物继续核查](docs/official-acquisition-followup.md)：远程页面配置、发布包与加固壳边界。

## 统一 uv CLI

```sh
uv sync --all-extras
uv run comi --help
uv run comi scan
uv run comi info
uv run comi files
uv run comi record start              # 明确开始录音；stop/pause/resume 同理
uv run comi download NAME --out artifacts/recordings
uv run comi settings show
uv run comi diag capture platform --out artifacts/platform.json
uv run comi verify --code --out artifacts/verification-NEW
```

[完整使用说明](docs/cli.md) · [命令协议与支持边界](docs/cli-capabilities.md)。支持 `uv tool install .` 后直接运行 `comi`。

包代码在 `src/rcominote/`；采集工具已统一迁入，不再维护独立 `tools/comi.py` 等副本。JSON输出，错误非零退出；按序列号选设备。下载校验完整长度后原子保存，拒绝覆盖。诊断只开放固定profile，代码读取限定经当前入口/指令/常量核对的固定位置；[69字节引用分析](docs/code-reference-followup.md)。没有刷机、任意shell、完整固件备份或恢复命令。

实机已验证录音start/pause/resume/stop、完整导出/sync、noise设置读回与恢复，以及一键只读诊断。其他setter源于固定App源码、按设备读回决定成功；时钟设置无已知getter，不能宣称回读验证。

macOS宿主需有蓝牙权限，官方App先断开；Linux需要本机BlueZ/适配器。APK/SDK/原始录音/完整日志放忽略的`artifacts/`；不依赖rlcdv、Obsidian或临时交接文件。

开发：`just check`，打包：`just build`。参考板Linux构建仍为`just sdk-setup`、`just sdk-build`，不打包或刷写CoMi。旧研究记录中的脚本命令对应其历史提交，当前命令以[CLI说明](docs/cli.md)为准。
