# CoMi Note 固件前期研究

目标：确认手上这台致远 CoMi Note 的芯片、板级资源、备份与恢复路径，随后尝试自写固件。当前有独立可用的 BLE 工具和研究资料，**尚无可刷写的 CoMi 固件或经验证的恢复方式**。

## 当前结论（2026-10-12）

| 问题 | 已知与边界 |
|---|---|
| 设备 | 自有 `C261CF0430`，广播 `CoMi Note 2F01`，固件 `1.0.4`；包装样本型号 `SY-N2A3F-5H2` 尚需和实机底标核对 |
| 平台 | GATT 与 Actions（炬芯）SDK 的日志服务逐字节匹配，平台来源有强证据；具体 SoC、板号仍未知 |
| 数据通路 | Boyi BLE 协议已验证，状态/列表/下载不需绑定；既往实测录音为 16 kHz 单声道、32 kbps MP3 |
| 新鲜实机证据 | 本轮重新枚举 GATT、读取状态；MTU 247，4 个服务，普通模式未见 Actions OTA UUID，`usb_mode=true` |
| USB | App 有 USB 模式控制；“先前仅观察到充电”不能推出无 USB 数据能力。线材、模式、板级走线仍待验证 |
| 日志/shell | SDK 有编译条件控制的 shell 路径；仅凭 UUID 不能证明 CoMi 可执行命令，本轮未向日志服务写入 |
| 自定义固件 | Actions 有构建、OTA、ADFU 等参考代码，也有签名/安全启动配置；CoMi 是否接受自签/未签名镜像尚未知 |

## 阅读顺序

1. [固件研究路线与待解问题](docs/firmware-roadmap.md)：哪些证据决定下一步。
2. [Actions SDK 核查](docs/actions-sdk.md)：平台、构建、分区、升级、恢复及源码定位。
3. [App 升级与 USB 线索](docs/app-upgrade.md)：Boyi/Mova 区分、APK 固定样本与可复核提取。
4. [BLE 协议与工具](docs/protocol.md)：帧格式、命令、已有实机验证边界。
5. [证据来源与本轮验证](docs/evidence/README.md)：历史资料与新采集分开记录。

## 可直接运行

需要 `uv`、Python ≥3.13（由 uv 解析脚本依赖）；`just`、`ruff` 用于开发检查。macOS 的启动终端/宿主进程需有蓝牙权限，官方 App 先断开连接。

```sh
just check                            # 格式、lint、7 个已有捕获帧测试；不连接设备
just scan                             # 只扫描广播
just gatt --out artifacts/gatt.json    # 连接并枚举；不读写应用特征，不订阅通知
just comi info                        # 通过 Boyi 查询序列号、绑定和状态
just comi files
just comi download NAME_FROM_FILES
just comi sync
just comi record start                # 明确改变设备录音状态；stop/pause/resume 同理
just comi set-time                    # 明确写入主机本地时间
```

连接操作默认只选广播序列号 `C261CF0430`；其他自有设备用 `--serial SERIAL`，如 `just comi info --serial SERIAL`。录音默认输出到 `~/.local/share/comi-research`；临时样本、APK、SDK、原始采集放进 git 忽略的 `artifacts/`。工具没有删除、格式化、刷写或任意 shell 命令入口。

工具及捕获帧测试从 rlcdv 迁入，运行不再依赖该项目、Obsidian 或交接临时文件。外部 SDK/APK 按研究文档中的固定版本单独获取；未将整个 SDK 或 APK 提交到仓库。
